"""
Synthetic portfolio, factor history and risk engine for the stress-test app.

Everything here is made up. The book is a $1.6B multi-asset fund whose 20
positions are mapped onto 10 market risk factors. Each position's P&L for a
factor move `s` is

    pnl = exposure · s  +  ½ · gamma · s_eq²

where `exposure` is $M per unit factor move (per 1.00 return, or per 1bp for
rates and spreads, or per vol point) and `gamma` is non-zero only for the
equity put overlay, which makes Monte Carlo and historical VaR differ from the
delta-normal number.

Factor history: 1,300 business days of daily moves drawn from a Student-t
copula with GARCH-style volatility clustering, one stressed regime (a
made-up liquidity shock in spring 2025) where volatility triples and
correlations jump towards a crisis matrix, and a shorter summer 2026 wobble
that lands inside the VaR backtest window.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from math import comb, erfc, sqrt
from statistics import NormalDist

import numpy as np

AS_OF = date(2026, 10, 30)

# key, label, unit of one move, daily vol (in that unit), shock unit shown in the UI
FACTORS = [
    ("US_EQ", "US equities", "return", 0.011),
    ("DM_EQ", "Developed ex-US equities", "return", 0.012),
    ("EM_EQ", "Emerging equities", "return", 0.014),
    ("UST10", "US 10y yield", "bp", 6.0),
    ("IG", "IG credit spread", "bp", 2.2),
    ("HY", "HY credit spread", "bp", 12.0),
    ("OIL", "Crude oil", "return", 0.023),
    ("GOLD", "Gold", "return", 0.009),
    ("USD", "US dollar index", "return", 0.0045),
    ("VIX", "Equity volatility (VIX)", "pts", 1.4),
]
FKEYS = [f[0] for f in FACTORS]
FLABEL = {f[0]: f[1] for f in FACTORS}
FUNIT = {f[0]: f[2] for f in FACTORS}
FVOL = np.array([f[3] for f in FACTORS])
NF = len(FACTORS)
IDX = {k: i for i, k in enumerate(FKEYS)}

# Calm-regime correlation (upper triangle, order = FKEYS)
_CALM = {
    ("US_EQ", "DM_EQ"): 0.78, ("US_EQ", "EM_EQ"): 0.65, ("DM_EQ", "EM_EQ"): 0.72,
    ("US_EQ", "UST10"): 0.20, ("DM_EQ", "UST10"): 0.15, ("EM_EQ", "UST10"): 0.05,
    ("US_EQ", "IG"): -0.45, ("DM_EQ", "IG"): -0.40, ("EM_EQ", "IG"): -0.40,
    ("US_EQ", "HY"): -0.65, ("DM_EQ", "HY"): -0.58, ("EM_EQ", "HY"): -0.55,
    ("IG", "HY"): 0.70, ("UST10", "IG"): -0.25, ("UST10", "HY"): -0.20,
    ("US_EQ", "OIL"): 0.30, ("DM_EQ", "OIL"): 0.30, ("EM_EQ", "OIL"): 0.38,
    ("OIL", "HY"): -0.30, ("OIL", "UST10"): 0.25,
    ("GOLD", "UST10"): -0.35, ("GOLD", "USD"): -0.40, ("GOLD", "US_EQ"): 0.05,
    ("USD", "EM_EQ"): -0.45, ("USD", "DM_EQ"): -0.30, ("USD", "US_EQ"): -0.10, ("USD", "OIL"): -0.25,
    ("VIX", "US_EQ"): -0.78, ("VIX", "DM_EQ"): -0.62, ("VIX", "EM_EQ"): -0.55,
    ("VIX", "HY"): 0.60, ("VIX", "IG"): 0.45, ("VIX", "UST10"): -0.20,
}
# Crisis regime: equities, credit and vol move together, bonds rally, dollar bid
_STRESS = {
    ("US_EQ", "DM_EQ"): 0.92, ("US_EQ", "EM_EQ"): 0.88, ("DM_EQ", "EM_EQ"): 0.90,
    ("US_EQ", "UST10"): 0.45, ("DM_EQ", "UST10"): 0.40, ("EM_EQ", "UST10"): 0.35,
    ("US_EQ", "IG"): -0.80, ("DM_EQ", "IG"): -0.78, ("EM_EQ", "IG"): -0.75,
    ("US_EQ", "HY"): -0.88, ("DM_EQ", "HY"): -0.85, ("EM_EQ", "HY"): -0.84,
    ("IG", "HY"): 0.90, ("UST10", "IG"): -0.45, ("UST10", "HY"): -0.45,
    ("US_EQ", "OIL"): 0.60, ("DM_EQ", "OIL"): 0.60, ("EM_EQ", "OIL"): 0.65,
    ("OIL", "HY"): -0.60, ("OIL", "UST10"): 0.40,
    ("GOLD", "UST10"): -0.30, ("GOLD", "USD"): -0.20, ("GOLD", "US_EQ"): -0.10,
    ("USD", "EM_EQ"): -0.70, ("USD", "DM_EQ"): -0.60, ("USD", "US_EQ"): -0.50, ("USD", "OIL"): -0.45,
    ("VIX", "US_EQ"): -0.90, ("VIX", "DM_EQ"): -0.85, ("VIX", "EM_EQ"): -0.82,
    ("VIX", "HY"): 0.85, ("VIX", "IG"): 0.78, ("VIX", "UST10"): -0.45,
}


def _matrix(pairs):
    m = np.eye(NF)
    for (a, b), v in pairs.items():
        m[IDX[a], IDX[b]] = m[IDX[b], IDX[a]] = v
    return nearest_corr(m)


def nearest_corr(m):
    """Clip negative eigenvalues and rescale to a unit diagonal."""
    w, v = np.linalg.eigh((m + m.T) / 2)
    m = (v * np.clip(w, 1e-4, None)) @ v.T
    d = np.sqrt(np.diag(m))
    return m / np.outer(d, d)


CORR_CALM = _matrix(_CALM)
CORR_STRESS = _matrix(_STRESS)


# ---------------------------------------------------------------- positions

ASSET_CLASSES = ["US Equity", "Intl Equity", "Fixed Income", "Real Assets", "Alts & Overlays"]


@dataclass
class Position:
    name: str
    asset_class: str
    mv: float  # market value, $M (unfunded derivatives carry 0)
    exposure: dict  # factor -> $M per unit move
    gamma: float = 0.0  # $M per (US equity return)²
    note: str = ""
    vec: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        self.vec = np.array([self.exposure.get(k, 0.0) for k in FKEYS])


def _beta(mv, **betas):
    """Exposures from betas: return factors take beta, rate/spread factors take -duration/1e4."""
    return {k: mv * b for k, b in betas.items()}


POSITIONS = [
    Position("US Large Cap Core", "US Equity", 220, _beta(220, US_EQ=1.0)),
    Position("US Technology Growth", "US Equity", 120, _beta(120, US_EQ=1.28, VIX=-0.002)),
    Position("US Small Cap Value", "US Equity", 60, _beta(60, US_EQ=1.15, HY=-0.0001)),
    Position("US Energy Sector", "US Equity", 45, _beta(45, US_EQ=0.75, OIL=0.45)),
    Position("Europe Equity (unhedged)", "Intl Equity", 110, _beta(110, DM_EQ=1.0, USD=-0.9)),
    Position("Japan Equity (USD-hedged)", "Intl Equity", 60, _beta(60, DM_EQ=0.8, US_EQ=0.15)),
    Position("Emerging Markets Equity", "Intl Equity", 80, _beta(80, EM_EQ=1.0, USD=-0.55)),
    Position("US Treasury 7–10y", "Fixed Income", 200, _beta(200, UST10=-8.1e-4), note="Duration 8.1"),
    Position("US TIPS", "Fixed Income", 60, _beta(60, UST10=-5.2e-4, OIL=0.03), note="Real duration 5.2"),
    Position("IG Corporate Bonds", "Fixed Income", 150, _beta(150, UST10=-7.0e-4, IG=-7.0e-4), note="Duration 7.0"),
    Position("High Yield Bonds", "Fixed Income", 90, _beta(90, UST10=-2.0e-4, HY=-3.8e-4, US_EQ=0.12), note="Spread duration 3.8"),
    Position("EM Hard-Currency Debt", "Fixed Income", 50, _beta(50, UST10=-6.5e-4, HY=-2.5e-4, EM_EQ=0.12)),
    Position("Physical Gold", "Real Assets", 70, _beta(70, GOLD=1.0)),
    Position("Broad Commodities", "Real Assets", 50, _beta(50, OIL=0.55, GOLD=0.15, USD=-0.3)),
    Position("Global REITs", "Real Assets", 45, _beta(45, US_EQ=0.85, UST10=-4.0e-4)),
    Position("Equity Long/Short Fund", "Alts & Overlays", 80, _beta(80, US_EQ=0.35, DM_EQ=0.05)),
    Position("Managed Futures (CTA)", "Alts & Overlays", 60, _beta(60, US_EQ=-0.08, UST10=1.5e-4, VIX=0.0025)),
    Position("S&P 500 Put Spread Overlay", "Alts & Overlays", 8,
             {"US_EQ": -95.0, "VIX": 0.45}, gamma=600.0, note="$300M notional 95/80 put spread: pays at most $45M, can lose its $8M premium"),
    Position("CDX HY Protection", "Alts & Overlays", 0, {"HY": 60 * 3.8e-4},
             note="Bought $60M protection, unfunded"),
    Position("EUR/USD Hedge (short EUR)", "Alts & Overlays", 0, {"USD": 75 * 0.9},
             note="$75M forward, unfunded"),
    Position("Cash & T-Bills", "Alts & Overlays", 75, {}),
]
NAMES = [p.name for p in POSITIONS]
EXPOSURE = np.array([p.vec for p in POSITIONS])  # (positions, factors)
GAMMA = np.array([p.gamma for p in POSITIONS])
MV = np.array([p.mv for p in POSITIONS])
NAV = float(MV.sum())
OVERLAY = NAMES.index("S&P 500 Put Spread Overlay")
OVERLAY_PREMIUM, OVERLAY_MAX_PAYOFF = 8.0, 300 * 0.15
CLASS_OF = np.array([ASSET_CLASSES.index(p.asset_class) for p in POSITIONS])

VAR_LIMIT_PCT = 2.0  # 1-day 99% VaR limit, % of NAV
STRESS_LIMIT_PCT = 16.0  # worst stress loss limit, % of NAV


def position_pnl(shocks):
    """P&L per position, $M. shocks: (n, factors) -> (n, positions)."""
    shocks = np.atleast_2d(shocks)
    eq = shocks[:, IDX["US_EQ"]]
    pnl = shocks @ EXPOSURE.T + 0.5 * np.outer(eq**2, GAMMA)
    # The put spread can lose no more than its premium and pay no more than its width
    pnl[:, OVERLAY] = np.clip(pnl[:, OVERLAY], -OVERLAY_PREMIUM, OVERLAY_MAX_PAYOFF - OVERLAY_PREMIUM)
    return pnl


def portfolio_pnl(shocks):
    return position_pnl(shocks).sum(axis=1)


# ---------------------------------------------------------------- history

def business_days(end, n):
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days[::-1]


N_DAYS = 1300
DAYS = business_days(AS_OF, N_DAYS)
STRESS_START, STRESS_END = date(2025, 3, 10), date(2025, 5, 16)
WOBBLE_START, WOBBLE_END = date(2026, 8, 3), date(2026, 8, 21)


def _history(seed=4):
    rng = np.random.default_rng(seed)
    nu = 5
    in_stress = np.array([STRESS_START <= d <= STRESS_END for d in DAYS])
    in_wobble = np.array([WOBBLE_START <= d <= WOBBLE_END for d in DAYS])
    l_calm, l_stress = np.linalg.cholesky(CORR_CALM), np.linalg.cholesky(CORR_STRESS)
    # GARCH(1,1) on a common volatility multiplier
    omega, alpha, beta = 0.04, 0.09, 0.87
    h, out = 1.0, np.empty((N_DAYS, NF))
    prev = 0.0
    for t in range(N_DAYS):
        h = omega + alpha * prev**2 + beta * h
        regime = 3.0 if in_stress[t] else 2.3 if in_wobble[t] else 1.0
        z = rng.standard_normal(NF)
        w = np.sqrt(rng.chisquare(nu) / (nu - 2))  # shared mixing -> t-copula, fat joint tails
        x = (l_stress if in_stress[t] or in_wobble[t] else l_calm) @ z / w
        vol = sqrt(h) * regime
        out[t] = x * vol * FVOL
        prev = sqrt(h) * x[0]
    # Opening leg of the stress regime: a few gap days down in risk assets
    first = int(np.argmax(in_stress))
    gap = np.array([-0.034, -0.031, -0.04, -14, 9, 55, -0.06, 0.012, 0.009, 9.5])
    out[first:first + 3] += gap * np.array([[1.0], [0.7], [0.5]])
    first = int(np.argmax(in_wobble))
    out[first:first + 4] += gap * np.array([[0.75], [0.0], [0.6], [0.45]])
    return out


HISTORY = _history()  # (days, factors)
HIST_PNL = portfolio_pnl(HISTORY)  # hypothetical P&L of today's book on each historical day


# ---------------------------------------------------------------- VaR engine

def z_score(conf):
    return NormalDist().inv_cdf(conf)


def blend_corr(corr, stress):
    """Move each correlation `stress` of the way to its crisis value."""
    return nearest_corr((1 - stress) * corr + stress * CORR_STRESS)


def window_cov(lookback):
    return np.cov(HISTORY[-lookback:], rowvar=False)


def stressed_cov(lookback, vol_mult, corr_stress):
    cov = window_cov(lookback)
    sd = np.sqrt(np.diag(cov))
    corr = cov / np.outer(sd, sd)
    if corr_stress > 0:
        corr = blend_corr(corr, corr_stress)
    sd = sd * vol_mult
    return corr * np.outer(sd, sd)


def overlapping(x, h):
    """Overlapping h-day sums of daily moves."""
    if h == 1:
        return x
    c = np.cumsum(np.vstack([np.zeros((1, x.shape[1])), x]), axis=0)
    return c[h:] - c[:-h]


@dataclass
class RiskResult:
    var: float  # $M, positive = loss
    es: float
    pnl: np.ndarray  # simulated/historical portfolio P&L sample (None for parametric)
    contrib: np.ndarray  # per-position contribution to ES, $M, sums to es
    standalone: np.ndarray  # per-position standalone VaR, $M
    sigma: float  # portfolio P&L stdev, $M
    n: int


def _tail_contrib(pos_pnl, port, var):
    tail = port <= -var
    return -pos_pnl[tail].mean(axis=0)


def _sample_var(x, conf):
    v = -np.quantile(x, 1 - conf)
    return v, -x[x <= -v].mean()


def compute(method, conf, horizon, lookback, vol_mult=1.0, corr_stress=0.0, n_sims=20000, seed=11):
    if method == "historical":
        moves = overlapping(HISTORY[-lookback:], horizon) * vol_mult
        pos = position_pnl(moves)
        port = pos.sum(axis=1)
        var, es = _sample_var(port, conf)
        standalone = np.array([max(_sample_var(pos[:, i], conf)[0], 0) for i in range(len(POSITIONS))])
        return RiskResult(var, es, port, _tail_contrib(pos, port, var), standalone, port.std(), len(port))

    cov = stressed_cov(lookback, vol_mult, corr_stress) * horizon
    if method == "parametric":
        z = z_score(conf)
        e = EXPOSURE.sum(axis=0)
        sigma = sqrt(e @ cov @ e)
        es_mult = NormalDist().pdf(z) / (1 - conf)
        comp = (EXPOSURE @ cov @ e) / sigma  # Euler contributions to sigma
        standalone = z * np.sqrt(np.einsum("ij,jk,ik->i", EXPOSURE, cov, EXPOSURE))
        return RiskResult(z * sigma, es_mult * sigma, None, comp * es_mult, standalone, sigma, 0)

    # Monte Carlo: multivariate Student-t (5 dof) scaled to the covariance, full revaluation
    rng = np.random.default_rng(seed)
    nu = 5
    z = rng.standard_normal((n_sims, NF)) @ np.linalg.cholesky(cov).T
    w = np.sqrt(rng.chisquare(nu, n_sims) / (nu - 2))[:, None]
    moves = z / w
    pos = position_pnl(moves)
    port = pos.sum(axis=1)
    var, es = _sample_var(port, conf)
    standalone = np.array([max(_sample_var(pos[:, i], conf)[0], 0) for i in range(len(POSITIONS))])
    return RiskResult(var, es, port, _tail_contrib(pos, port, var), standalone, port.std(), n_sims)


# ---------------------------------------------------------------- backtest

BACKTEST_DAYS = 250


def backtest(method, conf, lookback):
    """Rolling 1-day VaR over the last 250 days vs the book's hypothetical P&L.

    Monte Carlo is approximated by a Student-t quantile on the rolling P&L
    volatility (a full simulation per day would be slow for a live demo).
    """
    end = N_DAYS
    start = end - BACKTEST_DAYS
    pnl = HIST_PNL
    var = np.empty(BACKTEST_DAYS)
    if method == "historical":
        for j, t in enumerate(range(start, end)):
            var[j] = -np.quantile(pnl[t - lookback:t], 1 - conf)
    else:
        if method == "parametric":
            q = z_score(conf)
        else:
            rng = np.random.default_rng(3)
            sample = rng.standard_t(5, 400000) * sqrt(3 / 5)
            q = -np.quantile(sample, 1 - conf)
        for j, t in enumerate(range(start, end)):
            var[j] = q * pnl[t - lookback:t].std()
    realized = pnl[start:end]
    breaches = realized < -var
    return DAYS[start:end], realized, var, breaches


def kupiec(n, x, conf):
    """Kupiec proportion-of-failures test p-value."""
    p = 1 - conf
    if x == 0:
        lr = -2 * n * np.log(1 - p)
    elif x == n:
        lr = -2 * n * np.log(p)
    else:
        phat = x / n
        lr = -2 * ((n - x) * np.log(1 - p) + x * np.log(p) - (n - x) * np.log(1 - phat) - x * np.log(phat))
    return erfc(sqrt(max(lr, 0) / 2))


def traffic_light(n, x, conf):
    """Basel zones: green while P(X <= x) < 95%, yellow below 99.99%, else red."""
    p = 1 - conf
    cdf = sum(comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(x + 1))
    return "green" if cdf < 0.95 else "yellow" if cdf < 0.9999 else "red"


# ---------------------------------------------------------------- scenarios

def _shock(**kw):
    """Scenario in UI units: % for return factors, bp, VIX points."""
    return {k: kw.get(k, 0.0) for k in FKEYS}


SCENARIOS = {
    "Global financial crisis": dict(kind="Historical", period="Sep–Nov 2008", shock=_shock(
        US_EQ=-30, DM_EQ=-36, EM_EQ=-42, UST10=-120, IG=260, HY=950, OIL=-55, GOLD=4, USD=12, VIX=48)),
    "Covid crash": dict(kind="Historical", period="Feb–Mar 2020", shock=_shock(
        US_EQ=-34, DM_EQ=-33, EM_EQ=-31, UST10=-105, IG=210, HY=560, OIL=-62, GOLD=-3, USD=7, VIX=66)),
    "Inflation & rate shock": dict(kind="Historical", period="Jan–Oct 2022", shock=_shock(
        US_EQ=-24, DM_EQ=-21, EM_EQ=-27, UST10=240, IG=75, HY=270, OIL=38, GOLD=-6, USD=16, VIX=15)),
    "Bond market rout": dict(kind="Historical", period="Feb–Nov 1994", shock=_shock(
        US_EQ=-8, DM_EQ=-11, EM_EQ=-16, UST10=245, IG=22, HY=85, OIL=6, GOLD=-2, USD=-5, VIX=7)),
    "Taper tantrum": dict(kind="Historical", period="May–Jun 2013", shock=_shock(
        US_EQ=-5, DM_EQ=-8, EM_EQ=-16, UST10=105, IG=28, HY=110, OIL=-3, GOLD=-16, USD=4, VIX=9)),
    "Stagflation": dict(kind="Hypothetical", period="12-month view", shock=_shock(
        US_EQ=-17, DM_EQ=-20, EM_EQ=-22, UST10=160, IG=120, HY=420, OIL=65, GOLD=22, USD=-4, VIX=20)),
    "AI capex bust": dict(kind="Hypothetical", period="6-month view", shock=_shock(
        US_EQ=-27, DM_EQ=-13, EM_EQ=-16, UST10=-70, IG=65, HY=260, OIL=-18, GOLD=9, USD=-3, VIX=26)),
    "Dollar confidence crisis": dict(kind="Hypothetical", period="3-month view", shock=_shock(
        US_EQ=-12, DM_EQ=4, EM_EQ=6, UST10=95, IG=45, HY=150, OIL=12, GOLD=28, USD=-16, VIX=14)),
}


def to_model_units(shock):
    """UI shock dict -> factor vector (returns as decimals, bp and pts as is)."""
    return np.array([shock[k] / 100 if FUNIT[k] == "return" else shock[k] for k in FKEYS])


def _worst_window(h=10):
    """The book's worst h-day stretch in the factor history, replayed as a scenario."""
    sums = overlapping(HIST_PNL[:, None], h)[:, 0]
    i = int(np.argmin(sums))
    v = HISTORY[i:i + h].sum(axis=0)
    shock = {k: float(round(v[j] * 100, 1)) if FUNIT[k] == "return" else float(round(v[j])) for j, k in enumerate(FKEYS)}
    return shock, f"{DAYS[i]:%-d %b} – {DAYS[i + h - 1]:%-d %b %Y}"


_shock_w, _period_w = _worst_window()
SCENARIOS["Worst 10 days in the data"] = dict(kind="In-sample", period=_period_w, shock=_shock_w)


def scenario_pnl(shock):
    """Per-position P&L, $M, for a UI-unit shock dict."""
    return position_pnl(to_model_units(shock))[0]


def factor_attribution(shock):
    """Linear P&L by factor, $M, plus the put overlay's convexity and payoff cap as one residual."""
    s = to_model_units(shock)
    lin = EXPOSURE.sum(axis=0) * s
    return lin, float(portfolio_pnl(s)[0] - lin.sum())


def reverse_stress(shock, loss_pct):
    """Smallest multiple of the scenario that loses `loss_pct` of NAV (None if never within 3x)."""
    target = -loss_pct / 100 * NAV
    s = to_model_units(shock)
    grid = np.linspace(0, 3, 601)
    pnl = portfolio_pnl(np.outer(grid, s))
    hit = np.nonzero(pnl <= target)[0]
    return float(grid[hit[0]]) if len(hit) else None
