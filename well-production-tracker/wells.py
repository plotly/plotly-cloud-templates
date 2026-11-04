"""
Synthetic daily production for a made-up unconventional oil field, plus the
decline-curve analysis the app runs on it.

The Red Mesa Unit has 12 pads of 4 east-west horizontal wells, landed in three
formations. Each well follows a modified Arps hyperbolic decline with
formation-specific parameters, a choke-managed ramp-up, a rising gas-oil ratio
and water-oil ratio, random downtime, and frac hits when a nearby pad is
completed. A handful of wells have a problem in the last two months: a failed
pump, liquid loading or a water breakthrough.

Everything is generated once at import with a fixed seed, so every worker shows
the same numbers.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

AS_OF = date(2026, 10, 31)
START = date(2021, 1, 1)
N_DAYS = (AS_OF - START).days + 1
DAYS = np.array([START + timedelta(days=i) for i in range(N_DAYS)])

FIT_CUTOFF = 60  # fit on data older than this many days, then check the forecast against what came after
VARIANCE_WINDOW = 30
UNDER = -0.15  # below forecast by more than this counts as underperforming
ECON_LIMIT = 8.0  # bbl/d
D_MIN = 0.08  # terminal exponential decline, per year
FORECAST_YEARS = 30
BOE_PER_MCF = 1 / 6

ORIGIN = (31.86, -102.71)  # pad grid origin (lat, lon), fictional field
FT_PER_DEG_LAT = 364_000
FT_PER_DEG_LON = 364_000 * np.cos(np.radians(ORIGIN[0]))

# name: (oil IP per 1,000 ft lateral bbl/d, Di per year, b, initial GOR mcf/bbl, GOR growth per year,
#        initial water-oil ratio, WOR growth per year)
FORMATIONS = {
    "Kestrel Shale": (95, 1.55, 1.05, 1.4, 0.35, 1.2, 0.20),
    "Marlow Lime": (70, 1.10, 0.85, 0.9, 0.20, 2.4, 0.25),
    "Dunmore Sand": (115, 1.90, 1.25, 2.1, 0.45, 0.8, 0.15),
}
STREAMS = {"Oil": "bbl/d", "Gas": "mcf/d", "Water": "bbl/d", "BOE": "boe/d"}

PROBLEMS = {
    "pump": "Pump failure",
    "loading": "Liquid loading",
    "water": "Water breakthrough",
}


@dataclass
class Well:
    name: str
    api: str
    pad: str
    formation: str
    lateral_ft: int
    first_prod: date
    heel: tuple
    toe: tuple
    oil: np.ndarray  # daily rates over DAYS, NaN before first production
    gas: np.ndarray
    water: np.ndarray
    events: list = field(default_factory=list)  # (start_idx, end_idx, label)
    fit: dict = None
    stats: dict = None


def arps(t_days, qi, di_yr, b):
    """Modified Arps: hyperbolic until the decline rate falls to D_MIN, exponential after."""
    t = np.asarray(t_days, float) / 365.25
    di, dmin = di_yr, D_MIN
    t_switch = (di / dmin - 1) / (b * di) if b > 0 and di > dmin else 0.0
    hyp = qi / np.power(1 + b * di * t, 1 / b)
    q_switch = qi / (1 + b * di * t_switch) ** (1 / b)
    exp = q_switch * np.exp(-dmin * (t - t_switch))
    return np.where(t < t_switch, hyp, exp)


def fit_arps(t_days, q):
    """Grid search over b and Di with qi solved in log space. Returns qi, Di (per year), b and R²."""
    t = np.asarray(t_days, float)
    lq = np.log(q)
    bs = np.linspace(0.3, 1.6, 27)
    dis = np.geomspace(0.2, 6.0, 60)
    best = None
    for b in bs:
        # shape[d, n] = log of the normalized decline at each time
        shape = -np.log1p(b * dis[:, None] * t[None, :] / 365.25) / b
        lqi = (lq[None, :] - shape).mean(axis=1)
        sse = ((lq[None, :] - lqi[:, None] - shape) ** 2).sum(axis=1)
        k = int(np.argmin(sse))
        if best is None or sse[k] < best[0]:
            best = (sse[k], np.exp(lqi[k]), dis[k], b)
    sse, qi, di, b = best
    sst = ((lq - lq.mean()) ** 2).sum() or 1
    return {"qi": qi, "di": di, "b": b, "r2": 1 - sse / sst}


def _layout(rng):
    """Pads on a 3 x 4 grid, each with 4 laterals drilled east, 660 ft apart."""
    forms = list(FORMATIONS)
    pads = []
    for i in range(12):
        col, row = i % 3, i // 3
        pads.append({
            "name": f"RM-{i + 1:02d}",
            "x": col * 15_000 + rng.normal(0, 250),
            "y": row * 8000 + rng.normal(0, 250),
            "formation": forms[(col + row) % 3],
        })
    # A pad about every six months, shuffled so neighbouring pads aren't completed in sequence
    for k, p in zip(rng.permutation(12), pads):
        p["online"] = START + timedelta(days=int(k * 186 + rng.integers(0, 15)))
    return pads


def _to_latlon(x, y):
    return (ORIGIN[0] + y / FT_PER_DEG_LAT, ORIGIN[1] + x / FT_PER_DEG_LON)


def build_field(seed=7):
    rng = np.random.default_rng(seed)
    pads = _layout(rng)
    wells = []
    for p in pads:
        ip_k, di, b, gor0, gor_g, wor0, wor_g = FORMATIONS[p["formation"]]
        for j in range(4):
            lateral = int(rng.choice([7500, 10000, 10000, 12500]) + rng.integers(-300, 300))
            y = p["y"] + 990 - j * 660
            heel = _to_latlon(p["x"] + 500, y)
            toe = _to_latlon(p["x"] + 500 + lateral, y)
            first = p["online"] + timedelta(days=int(rng.integers(0, 6)))
            i0 = (first - START).days
            n = N_DAYS - i0
            t = np.arange(n, dtype=float)

            qi = ip_k * lateral / 1000 * rng.lognormal(0, 0.18)
            well_di = di * rng.lognormal(0, 0.12)
            well_b = float(np.clip(b + rng.normal(0, 0.1), 0.4, 1.5))
            oil = arps(t, qi, well_di, well_b)
            oil *= np.clip((t + 1) / 25, 0.35, 1)  # flowback, choke opened up over ~25 days
            oil *= rng.lognormal(0, 0.07, n)
            gor = gor0 * rng.lognormal(0, 0.1) * (1 + gor_g * t / 365.25)
            wor = wor0 * rng.lognormal(0, 0.15) * (1 + wor_g * t / 365.25)
            wor *= np.where(t < 30, 3.0 - 2.0 * t / 30, 1.0)  # frac fluid recovery
            wells.append(Well(
                name=f"{p['name']} {j + 1}H", api=f"42-317-{38000 + len(wells) * 7:05d}", pad=p["name"],
                formation=p["formation"], lateral_ft=lateral, first_prod=first, heel=heel, toe=toe,
                oil=np.concatenate([np.full(i0, np.nan), oil]),
                gas=np.concatenate([np.full(i0, np.nan), oil * gor * rng.lognormal(0, 0.05, n)]),
                water=np.concatenate([np.full(i0, np.nan), oil * wor * rng.lognormal(0, 0.08, n)]),
            ))
            wells[-1]._pad = p  # used by the frac-hit pass below

    _add_frac_hits(wells, rng)
    _add_downtime(wells, rng)
    _add_problems(wells, rng)
    for w in wells:
        del w._pad
        w.fit = _fit(w)
    _borrow_fits(wells)
    for w in wells:
        _analyse(w)
    return wells


def _add_frac_hits(wells, rng):
    """Offset wells on neighbouring pads shut in during a new pad's completion, then come back slightly lower."""
    pads = {w.pad: w._pad for w in wells}
    for p in pads.values():
        frac = (p["online"] - START).days - 21
        for w in wells:
            q = w._pad
            if q is p or q["online"] >= p["online"]:
                continue
            if np.hypot(q["x"] - p["x"], q["y"] - p["y"]) > 16_000:
                continue
            i, j = frac, frac + int(rng.integers(12, 22))
            hit = rng.uniform(0.82, 0.97)
            for s in (w.oil, w.gas, w.water):
                s[j:] *= hit if s is not w.water else 1 / hit
                s[i:j] = 0
            w.events.append((i, j, f"Offset frac ({p['name']})"))


def _add_downtime(wells, rng):
    for w in wells:
        i0 = (w.first_prod - START).days + 30
        i = i0 + int(rng.exponential(220))
        while i < N_DAYS - FIT_CUTOFF:
            d = int(rng.choice([1, 2, 3, 5, 9, 14]))
            label = "Workover" if d >= 9 else "Facility downtime"
            for s in (w.oil, w.gas, w.water):
                s[i:i + d] = 0
            w.events.append((i, min(i + d, N_DAYS), label))
            i += d + int(rng.exponential(220))


def _add_problems(wells, rng):
    """Give a few older wells a problem that shows up only in the last two months."""
    old = [w for w in wells if (AS_OF - w.first_prod).days > 400]
    picks = rng.choice(len(old), 7, replace=False)
    kinds = ["pump", "pump", "loading", "loading", "loading", "water", "water"]
    for k, kind in zip(picks, kinds):
        w = old[k]
        start = N_DAYS - int(rng.integers(20, 55))
        n = N_DAYS - start
        if kind == "pump":
            down = start + int(rng.integers(5, 15))
            ramp = np.linspace(1, 0.55, down - start)
            for s in (w.oil, w.gas, w.water):
                s[start:down] *= ramp
                s[down:] = 0
            w.events.append((down, N_DAYS, "Pump failure"))
        elif kind == "loading":
            fall = np.linspace(1, rng.uniform(0.45, 0.65), n)
            w.oil[start:] *= fall
            w.water[start:] *= fall * 0.7
            w.gas[start:] *= np.linspace(1, 0.8, n)
        else:
            w.oil[start:] *= np.linspace(1, 0.7, n)
            w.water[start:] *= np.linspace(1, 2.6, n)
    for w in rng.choice([w for w in wells if (AS_OF - w.first_prod).days > 200], 3, replace=False):
        w.oil[-30:] *= rng.uniform(1.18, 1.35)  # recent cleanout or choke opened: above forecast
        w.gas[-30:] *= 1.2


def monthly(series, idx_end=N_DAYS):
    """Calendar-month averages of a producing-day rate (zeros and NaN dropped) with months on production."""
    s = series[:idx_end]
    first = int(np.argmax(~np.isnan(s)))
    vals = s[first:]
    m = np.arange(len(vals)) // 30.4375
    rates, t = [], []
    for k in range(int(m.max()) + 1 if len(vals) else 0):
        chunk = vals[m == k]
        on = chunk[chunk > 0]
        if len(on) >= 10:
            rates.append(on.mean())
            t.append((k + 0.5) * 30.4375)
    return np.array(t), np.array(rates)


def _fit(w):
    t, q = monthly(w.oil, N_DAYS - FIT_CUTOFF)
    keep = t > 45  # skip the ramp-up
    return fit_arps(t[keep], q[keep]) if keep.sum() >= 4 else None


def _borrow_fits(wells):
    """Wells too new to fit get the median b and Di of their formation, scaled to their last 30 days."""
    for w in wells:
        if w.fit:
            continue
        peers = [p.fit for p in wells if p.fit and p.formation == w.formation]
        b = float(np.median([f["b"] for f in peers]))
        di = float(np.median([f["di"] for f in peers]))
        i0 = (w.first_prod - START).days
        recent = w.oil[N_DAYS - 30:]
        t_mid = N_DAYS - 15 - i0
        qi = np.nanmean(recent[recent > 0]) / arps([t_mid], 1.0, di, b)[0]
        w.fit = {"qi": qi, "di": di, "b": b, "r2": np.nan, "borrowed": True}


def _analyse(w):
    i0 = (w.first_prod - START).days
    days_on = N_DAYS - i0

    last = slice(N_DAYS - VARIANCE_WINDOW, N_DAYS)
    prior = slice(N_DAYS - 2 * VARIANCE_WINDOW, N_DAYS - VARIANCE_WINDOW)
    t_last = np.arange(N_DAYS - VARIANCE_WINDOW, N_DAYS) - i0
    actual = np.nanmean(w.oil[last])
    if w.fit.get("borrowed"):
        expected = variance = np.nan  # the borrowed fit is anchored on this window, so it can't judge it
    else:
        expected = arps(t_last, **_fit_args(w.fit)).mean()
        variance = actual / expected - 1

    shut_days = 0
    while shut_days < days_on and w.oil[N_DAYS - 1 - shut_days] == 0:
        shut_days += 1

    oil_l, wat_l, gas_l = (np.nanmean(s[last]) for s in (w.oil, w.water, w.gas))
    oil_p, wat_p, gas_p = (np.nanmean(s[prior]) for s in (w.oil, w.water, w.gas))
    wc = wat_l / (wat_l + oil_l) if oil_l + wat_l > 0 else np.nan
    wc_prior = wat_p / (wat_p + oil_p) if oil_p + wat_p > 0 else np.nan
    gor = gas_l / oil_l if oil_l > 0 else np.nan

    if shut_days >= 2:
        status, issue = "Shut in", f"No production for {shut_days} days"
    elif days_on < 90:
        status, issue = "Ramping up", f"Online {days_on} days"
    elif variance < UNDER:
        status = "Underperforming"
        if wc - wc_prior > 0.06:
            issue = f"Water cut up {100 * (wc - wc_prior):.0f} pts in 30 days"
        else:
            # oil falling faster than the decline over the last month
            drop = oil_l / oil_p - 1 if oil_p else 0
            issue = f"Oil {drop:+.0%} month on month, possible liquid loading" if drop < -0.12 \
                else "Below decline curve"
    else:
        status, issue = "Producing", ""

    cum = {k: np.nansum(getattr(w, k)) for k in ("oil", "gas", "water")}
    fc = forecast(w, FORECAST_YEARS * 365)
    remaining = fc[fc >= ECON_LIMIT].sum() if fc is not None else 0.0
    ip30 = np.nanmax(np.convolve(np.nan_to_num(w.oil[i0:i0 + 120]), np.ones(30) / 30, "valid")) \
        if days_on >= 30 else np.nan
    w.stats = {
        "days_on": days_on, "expected": expected, "status": status, "issue": issue, "variance": variance, "shut_days": shut_days,
        "oil": oil_l, "gas": gas_l, "water": wat_l, "boe": oil_l + gas_l * BOE_PER_MCF,
        "wc": wc, "gor": gor, "ip30": ip30, "cum_oil": cum["oil"], "cum_gas": cum["gas"],
        "cum_water": cum["water"], "eur": cum["oil"] + remaining,
        "eur_per_ft": (cum["oil"] + remaining) / w.lateral_ft,
    }


def _fit_args(fit):
    return {"qi": fit["qi"], "di_yr": fit["di"], "b": fit["b"]}


def forecast(w, n_days, from_idx=N_DAYS):
    """Daily oil forecast from the fit, starting the day after from_idx."""
    if not w.fit:
        return None
    i0 = (w.first_prod - START).days
    t = np.arange(from_idx, from_idx + n_days) - i0
    return arps(t, **_fit_args(w.fit))


def ratio_trend(w, stream, n_days):
    """Extend the gas-oil or water-oil ratio with a straight line fitted to the last year of producing days."""
    s, o = getattr(w, stream), w.oil
    idx = np.arange(max(0, N_DAYS - 365), N_DAYS)
    ok = (o[idx] > 0) & (s[idx] > 0) & ~np.isnan(o[idx])
    if ok.sum() < 20:
        r = np.nansum(s[-90:]) / max(np.nansum(o[-90:]), 1)
        return np.full(n_days, r)
    slope, icpt = np.polyfit(idx[ok], s[idx][ok] / o[idx][ok], 1)
    return np.maximum(icpt + slope * np.arange(N_DAYS, N_DAYS + n_days), 0)


def stream_forecast(w, stream, n_days):
    oil = forecast(w, n_days)
    if oil is None:
        return np.zeros(n_days)
    if w.stats["status"] == "Shut in":
        oil = oil * 0  # stays down until someone fixes it
    if stream == "Oil":
        return oil
    if stream == "BOE":
        return oil + oil * ratio_trend(w, "gas", n_days) * BOE_PER_MCF
    return oil * ratio_trend(w, stream.lower(), n_days)


def stream_series(w, stream):
    if stream == "BOE":
        return w.oil + w.gas * BOE_PER_MCF
    return getattr(w, stream.lower())


def type_curve(wells, months=36):
    """Oil rate per 1,000 ft of lateral by month on production: P10, P50 and P90 across the wells given."""
    grid = np.full((len(wells), months), np.nan)
    for k, w in enumerate(wells):
        t, q = monthly(w.oil)
        m = (t // 30.4375).astype(int)
        ok = m < months
        grid[k, m[ok]] = q[ok] / w.lateral_ft * 1000
    counts = (~np.isnan(grid)).sum(axis=0)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            p90, p50, p10 = np.nanpercentile(grid, [10, 50, 90], axis=0)
    usable = counts >= 3
    return np.arange(1, months + 1)[usable], p10[usable], p50[usable], p90[usable]


WELLS = build_field()
BY_NAME = {w.name: w for w in WELLS}
