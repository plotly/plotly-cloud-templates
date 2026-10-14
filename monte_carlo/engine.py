"""Monte Carlo pricing engine: path simulation, estimators, benchmarks, Greeks.

Pure numpy/scipy with no Dash imports, so it can be tested and profiled on its
own.
"""

import math
import time
from dataclasses import asdict, dataclass, replace

import numpy as np
from scipy.special import ndtr  # standard normal CDF

PRODUCTS = {
    "euro_call": "European call",
    "euro_put": "European put",
    "asian_call": "Asian call (arithmetic)",
    "uo_call": "Up-and-out barrier call",
}
MODELS = {"gbm": "GBM", "merton": "Merton jump-diffusion"}
ESTIMATORS = {
    "plain": "Plain",
    "anti": "Antithetic",
    "cv": "Control variate",
    "anti_cv": "Antithetic + CV",
}

CHUNK_PATHS = 25_000  # simulate in chunks so memory stays bounded
GREEK_PATHS = 20_000  # bump-and-revalue sample size (common random numbers)
DISPLAY_PATHS = 2_000  # paths behind the fan chart percentiles
SAMPLE_PATHS = 25  # individual paths drawn on the fan chart
BGK_BETA = 0.5826  # Broadie-Glasserman-Kou discrete-monitoring constant


@dataclass(frozen=True)
class Params:
    product: str
    model: str
    s0: float
    k: float
    t: float
    r: float
    q: float
    sigma: float
    barrier: float
    jump_lambda: float
    jump_mean: float
    jump_vol: float
    n_paths: int
    n_steps: int
    seed: int

    @property
    def path_dependent(self) -> bool:
        return self.product in ("asian_call", "uo_call")

    @property
    def steps(self) -> int:
        # European payoffs depend only on S_T, which both models sample
        # exactly in one step.
        return self.n_steps if self.path_dependent else 1

    @property
    def jump_kappa(self) -> float:
        """Mean relative jump size E[e^J] - 1 (the compensator)."""
        return math.exp(self.jump_mean + 0.5 * self.jump_vol**2) - 1


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def log_increments(p: Params, z: np.ndarray, rng: np.random.Generator):
    """Risk-neutral log-price increments for standard normal draws z.

    z has shape (paths, steps); the time step is T / steps.

    GBM:    dlnS = (r - q - sigma^2/2) dt + sigma sqrt(dt) Z
    Merton: adds compound-Poisson jumps J ~ N(mu_J, sigma_J^2) and the
            compensator -lambda*kappa dt that keeps e^{-(r-q)t} S_t a martingale.
    """
    dt = p.t / z.shape[1]
    drift = (p.r - p.q - 0.5 * p.sigma**2) * dt
    increments = drift + p.sigma * math.sqrt(dt) * z
    if p.model == "merton" and p.jump_lambda > 0:
        n_jumps = rng.poisson(p.jump_lambda * dt, size=z.shape)
        jump_sizes = n_jumps * p.jump_mean + np.sqrt(n_jumps) * p.jump_vol * (
            rng.standard_normal(z.shape)
        )
        increments += jump_sizes - p.jump_lambda * p.jump_kappa * dt
    return increments


def price_paths(p: Params, increments: np.ndarray) -> np.ndarray:
    """Prices at each monitoring date (excluding S0), shape (paths, steps)."""
    return p.s0 * np.exp(np.cumsum(increments, axis=1))


def payoff(p: Params, prices: np.ndarray) -> np.ndarray:
    s_t = prices[:, -1]
    if p.product == "euro_call":
        return np.maximum(s_t - p.k, 0.0)
    if p.product == "euro_put":
        return np.maximum(p.k - s_t, 0.0)
    if p.product == "asian_call":
        return np.maximum(prices.mean(axis=1) - p.k, 0.0)
    if p.product == "uo_call":
        alive = prices.max(axis=1) < p.barrier  # discretely monitored
        return np.where(alive, np.maximum(s_t - p.k, 0.0), 0.0)
    raise ValueError(f"Unknown product {p.product}")


def simulate(p: Params, antithetic: bool, rng: np.random.Generator):
    """Discounted payoffs X and control Y = e^{-rT} S_T for p.n_paths paths.

    With antithetic=True, draws come in (Z, -Z) pairs and the results are the
    pair averages, so there are n_paths / 2 observations.
    """
    discount = math.exp(-p.r * p.t)
    xs, ys = [], []
    remaining = p.n_paths // 2 if antithetic else p.n_paths
    while remaining > 0:
        n = min(CHUNK_PATHS, remaining)
        z = rng.standard_normal((n, p.steps))
        draws = (z, -z) if antithetic else (z,)
        x = np.zeros(n)
        y = np.zeros(n)
        for zz in draws:
            prices = price_paths(p, log_increments(p, zz, rng))
            x += discount * payoff(p, prices)
            y += discount * prices[:, -1]
        xs.append(x / len(draws))
        ys.append(y / len(draws))
        remaining -= n
    return np.concatenate(xs), np.concatenate(ys)


# ---------------------------------------------------------------------------
# Estimators
# ---------------------------------------------------------------------------


def control_variate(p: Params, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Adjust X by the control Y, whose mean E[e^{-rT} S_T] = S0 e^{-qT} is known.

    b* = Cov(X, Y) / Var(Y) minimises the variance of X - b (Y - E[Y]).
    """
    b = np.cov(x, y)[0, 1] / np.var(y, ddof=1)
    return x - b * (y - p.s0 * math.exp(-p.q * p.t))


def summarize(samples: np.ndarray) -> dict:
    mean = float(samples.mean())
    se = float(samples.std(ddof=1) / math.sqrt(len(samples)))
    return {
        "price": mean,
        "se": se,
        "ci_low": mean - 1.96 * se,
        "ci_high": mean + 1.96 * se,
    }


def estimator_samples(p: Params, seed: int) -> dict[str, np.ndarray]:
    """Per-observation samples for every estimator, all at the same path count."""
    rng = np.random.default_rng(seed)
    x_plain, y_plain = simulate(p, antithetic=False, rng=rng)
    x_anti, y_anti = simulate(p, antithetic=True, rng=rng)
    return {
        "plain": x_plain,
        "anti": x_anti,
        "cv": control_variate(p, x_plain, y_plain),
        "anti_cv": control_variate(p, x_anti, y_anti),
    }


def running_estimate(
    samples: np.ndarray, paths_per_sample: int = 1, points: int = 160
) -> dict:
    """Running mean and 95% band at log-spaced path counts (for charting)."""
    n = np.arange(1, len(samples) + 1)
    mean = np.cumsum(samples) / n
    var = (np.cumsum(samples**2) - n * mean**2) / np.maximum(n - 1, 1)
    se = np.sqrt(np.maximum(var, 0) / n)
    idx = np.unique(np.geomspace(20, len(samples), points).astype(int)) - 1
    return {
        "paths": ((idx + 1) * paths_per_sample).tolist(),
        "mean": mean[idx].tolist(),
        "low": (mean[idx] - 1.96 * se[idx]).tolist(),
        "high": (mean[idx] + 1.96 * se[idx]).tolist(),
    }


# ---------------------------------------------------------------------------
# Closed-form benchmarks
# ---------------------------------------------------------------------------


def black_scholes(s, k, t, r, q, sigma, call=True) -> float:
    vol = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma**2) * t) / vol
    d2 = d1 - vol
    if call:
        return s * math.exp(-q * t) * ndtr(d1) - k * math.exp(-r * t) * ndtr(d2)
    return k * math.exp(-r * t) * ndtr(-d2) - s * math.exp(-q * t) * ndtr(-d1)


def merton_price(p: Params, call=True, terms: int = 60) -> float:
    """Merton (1976) series: Poisson-weighted Black-Scholes prices."""
    lam_prime = p.jump_lambda * (1 + p.jump_kappa)
    total, weight = 0.0, math.exp(-lam_prime * p.t)
    for n in range(terms):
        if n:
            weight *= lam_prime * p.t / n
        sigma_n = math.sqrt(p.sigma**2 + n * p.jump_vol**2 / p.t)
        r_n = p.r - p.jump_lambda * p.jump_kappa + n * math.log(1 + p.jump_kappa) / p.t
        total += weight * black_scholes(p.s0, p.k, p.t, r_n, p.q, sigma_n, call)
    return total


def up_and_out_call(s, k, h, t, r, q, sigma) -> float:
    """Continuously monitored up-and-out call, zero rebate (Reiner-Rubinstein)."""
    if s >= h or k >= h:
        return 0.0
    vol = sigma * math.sqrt(t)
    mu = (r - q - 0.5 * sigma**2) / sigma**2
    x1 = math.log(s / k) / vol + (1 + mu) * vol
    x2 = math.log(s / h) / vol + (1 + mu) * vol
    y1 = math.log(h**2 / (s * k)) / vol + (1 + mu) * vol
    y2 = math.log(h / s) / vol + (1 + mu) * vol
    fs, fk = s * math.exp(-q * t), k * math.exp(-r * t)
    ratio = h / s

    def leg(a, b, power_s=0.0, power_k=0.0):
        return fs * ratio**power_s * ndtr(a) - fk * ratio**power_k * ndtr(b)

    a = leg(x1, x1 - vol)
    b = leg(x2, x2 - vol)
    c = leg(-y1, -y1 + vol, 2 * (mu + 1), 2 * mu)
    d = leg(-y2, -y2 + vol, 2 * (mu + 1), 2 * mu)
    return a - b + c - d


def benchmark(p: Params) -> tuple[float | None, str]:
    """Closed-form reference price and a short description of it."""
    call = p.product != "euro_put"
    if p.product in ("euro_call", "euro_put"):
        if p.model == "merton":
            return merton_price(p, call), "Merton series"
        return black_scholes(p.s0, p.k, p.t, p.r, p.q, p.sigma, call), "Black-Scholes"
    if p.product == "uo_call" and p.model == "gbm":
        # Discrete monitoring knocks out less often than continuous, which
        # BGK (1997) approximates by shifting an up barrier away from spot.
        dt = p.t / p.n_steps
        h_adj = p.barrier * math.exp(BGK_BETA * p.sigma * math.sqrt(dt))
        price = up_and_out_call(p.s0, p.k, h_adj, p.t, p.r, p.q, p.sigma)
        return price, "Closed form + BGK correction"
    if p.product == "asian_call":
        return None, "No closed form for arithmetic Asians"
    return None, "No closed form under jumps"


def analytic_greeks(p: Params) -> dict | None:
    """Black-Scholes Greeks, when the European GBM benchmark applies."""
    if p.model != "gbm" or p.product not in ("euro_call", "euro_put"):
        return None
    call = p.product == "euro_call"
    vol = p.sigma * math.sqrt(p.t)
    d1 = (math.log(p.s0 / p.k) + (p.r - p.q + 0.5 * p.sigma**2) * p.t) / vol
    d2 = d1 - vol
    pdf = math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi)
    disc_q, disc_r = math.exp(-p.q * p.t), math.exp(-p.r * p.t)
    delta = disc_q * (ndtr(d1) if call else ndtr(d1) - 1)
    rho = p.k * p.t * disc_r * (ndtr(d2) if call else -ndtr(-d2))
    return {
        "Delta": delta,
        "Gamma": disc_q * pdf / (p.s0 * vol),
        "Vega": p.s0 * disc_q * pdf * math.sqrt(p.t) / 100,  # per vol point
        "Rho": rho / 100,  # per 1% rate move
    }


# ---------------------------------------------------------------------------
# Greeks by bump-and-revalue with common random numbers
# ---------------------------------------------------------------------------


def mc_price(p: Params, estimator: str, seed: int) -> float:
    rng = np.random.default_rng(seed)
    antithetic = estimator in ("anti", "anti_cv")
    x, y = simulate(p, antithetic, rng)
    if estimator in ("cv", "anti_cv"):
        x = control_variate(p, x, y)
    return float(x.mean())


def mc_greeks(p: Params, estimator: str) -> dict:
    """Central differences, reusing one seed so bumps share random numbers."""
    g = replace(p, n_paths=min(p.n_paths, GREEK_PATHS))
    seed = p.seed + 1
    h = 0.01 * p.s0

    def price(**changes):
        return mc_price(replace(g, **changes), estimator, seed)

    base, up, down = price(), price(s0=g.s0 + h), price(s0=g.s0 - h)
    return {
        "Delta": (up - down) / (2 * h),
        "Gamma": (up - 2 * base + down) / h**2,
        "Vega": (price(sigma=g.sigma + 0.01) - price(sigma=g.sigma - 0.01)) / 2,
        "Rho": (price(r=g.r + 0.01) - price(r=g.r - 0.01)) / 2,
    }


# ---------------------------------------------------------------------------
# Chart data
# ---------------------------------------------------------------------------


def display_paths(p: Params) -> dict:
    """Percentile bands and a few sample paths for the fan chart."""
    steps = p.n_steps  # full paths, even for Europeans priced in one step
    rng = np.random.default_rng(p.seed + 2)
    z = rng.standard_normal((DISPLAY_PATHS, steps))
    prices = price_paths(p, log_increments(p, z, rng))
    prices = np.hstack([np.full((DISPLAY_PATHS, 1), p.s0), prices])
    times = np.linspace(0, p.t, steps + 1)
    pct = np.percentile(prices, [5, 25, 50, 75, 95], axis=0)
    return {
        "t": times.tolist(),
        "p05": pct[0].tolist(),
        "p25": pct[1].tolist(),
        "p50": pct[2].tolist(),
        "p75": pct[3].tolist(),
        "p95": pct[4].tolist(),
        "samples": prices[:SAMPLE_PATHS].tolist(),
    }


def terminal_distribution(p: Params, bins: int = 60) -> dict:
    """Histogram of S_T split by outcome: pays off, worthless, knocked out."""
    rng = np.random.default_rng(p.seed + 3)
    n = min(p.n_paths, 100_000)
    z = rng.standard_normal((n, p.steps))
    prices = price_paths(p, log_increments(p, z, rng))
    s_t = prices[:, -1]
    pays = payoff(p, prices) > 0
    knocked = (
        prices.max(axis=1) >= p.barrier
        if p.product == "uo_call"
        else np.zeros(n, dtype=bool)
    )
    lo, hi = np.percentile(s_t, [0.5, 99.5])
    edges = np.linspace(lo, hi, bins + 1)

    def counts(mask):
        return np.histogram(s_t[mask], bins=edges)[0].tolist()

    return {
        "centers": ((edges[:-1] + edges[1:]) / 2).tolist(),
        "width": float(edges[1] - edges[0]),
        "pays": counts(pays),
        "worthless": counts(~pays & ~knocked),
        "knocked": counts(knocked),
        "share_pays": float(pays.mean()),
        "share_knocked": float(knocked.mean()),
    }


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------


def run(p: Params, estimator: str) -> dict:
    """Everything the dashboard shows, as JSON-serialisable data."""
    started = time.perf_counter()
    samples = estimator_samples(p, p.seed)
    elapsed = time.perf_counter() - started

    stats = {name: summarize(s) for name, s in samples.items()}
    plain_var = stats["plain"]["se"] ** 2
    comparison = [
        {
            "estimator": name,
            "Estimator": ESTIMATORS[name],
            "Price": stats[name]["price"],
            "Std error": stats[name]["se"],
            # Variance ratio at equal path count: how many times more plain
            # paths you'd need for the same precision.
            "Efficiency": (
                plain_var / stats[name]["se"] ** 2 if stats[name]["se"] else None
            ),
        }
        for name in ESTIMATORS
    ]

    bench, bench_label = benchmark(p)
    head = stats[estimator]
    return {
        "params": asdict(p),
        "product": p.product,
        "model": p.model,
        "estimator": estimator,
        "strike": p.k,
        "barrier": p.barrier if p.product == "uo_call" else None,
        "n_paths": p.n_paths,
        "steps": p.steps,
        "runtime_s": elapsed,
        # All four estimators run: n_paths plain + n_paths antithetic paths.
        "path_steps_per_s": 2 * p.n_paths * p.steps / elapsed if elapsed else None,
        "headline": head,
        "benchmark": bench,
        "benchmark_label": bench_label,
        "z_score": (
            (head["price"] - bench) / head["se"] if bench and head["se"] else None
        ),
        "comparison": comparison,
        "convergence": {
            "selected": running_estimate(
                samples[estimator], 2 if estimator in ("anti", "anti_cv") else 1
            ),
            "plain": running_estimate(samples["plain"]),
        },
        "greeks": mc_greeks(p, estimator),
        "analytic_greeks": analytic_greeks(p),
        "fan": display_paths(p),
        "distribution": terminal_distribution(p),
    }
