"""
Synthetic sales history and the forecasting model behind the app.

Cascade Market is a made-up grocery chain with 18 stores across the Pacific
Northwest. Daily unit sales for six departments are simulated from a known
recipe: store size and growth, yearly seasonality, day-of-week shape (which
depends on the store format), holidays, chain-wide weekly circular promotions,
local temperature, a few store events, and autocorrelated noise. Stores close
on Thanksgiving and Christmas Day.

Each store x department series gets its own forecasting model: a regression on
log units with a trend, Fourier terms for the year, day-of-week, holiday,
promotion, temperature anomaly and store event terms, plus AR(1) errors. The
forecast is simulated (sample paths) so that intervals hold when daily
forecasts are summed into weeks, stores or departments. The model only sees the
same inputs a real planner would have: past sales, the promo calendar, store
events and weather normals, not the future weather.
"""

import datetime as dt
from dataclasses import dataclass

import numpy as np

START = dt.date(2024, 9, 30)  # first day of history, a Monday
AS_OF = dt.date(2026, 10, 11)  # last day with actuals, a Sunday
HORIZON = 84  # days, 12 weeks
WEEKS = HORIZON // 7
DRAWS = 400
N_HIST = (AS_OF - START).days + 1
DATES = [START + dt.timedelta(days=i) for i in range(N_HIST + HORIZON)]
FORECAST_DATES = DATES[N_HIST:]
WEEK_STARTS = FORECAST_DATES[::7]

DEPARTMENTS = ["Produce", "Bakery", "Dairy", "Frozen", "Beverages", "Deli"]
HOLIDAYS = ["pre_thanksgiving", "christmas_runup", "nye", "summer_weekend", "post_holiday"]

# Temperature anomalies follow an AR(1) with a 3 C standard deviation
TEMP_PHI = 0.85
TEMP_SD = 3.0

# Truth recipe per department. peak is the day of year of the seasonal high,
# temp is the log-lift per degree C above normal, hol is the log-lift per holiday.
DEPT = {
    "Produce": dict(base=2300, peak=195, amp=0.08, temp=0.004, promo=0.14,
                    hol=[0.55, 0.30, 0.08, 0.20, -0.25]),
    "Bakery": dict(base=850, peak=350, amp=0.05, temp=-0.003, promo=0.20,
                   hol=[0.70, 0.60, 0.15, 0.15, -0.30]),
    "Dairy": dict(base=1700, peak=15, amp=0.04, temp=0.0, promo=0.12,
                  hol=[0.50, 0.35, 0.10, 0.05, -0.20]),
    "Frozen": dict(base=1050, peak=200, amp=0.07, temp=0.012, promo=0.25,
                   hol=[0.25, 0.20, 0.12, 0.30, -0.20]),
    "Beverages": dict(base=1500, peak=205, amp=0.06, temp=0.020, promo=0.30,
                      hol=[0.30, 0.35, 0.60, 0.45, -0.25]),
    "Deli": dict(base=650, peak=100, amp=0.02, temp=0.003, promo=0.18,
                 hol=[0.35, 0.40, 0.50, 0.25, -0.25]),
}

# Store formats: day-of-week log-lifts (Mon..Sun), noise level and department mix
FORMATS = {
    "Superstore": dict(dow=[-0.12, -0.15, -0.10, -0.05, 0.08, 0.22, 0.12], noise=0.05,
                       mix=[1.0, 1.0, 1.05, 1.15, 1.1, 0.9]),
    "Neighborhood": dict(dow=[-0.06, -0.08, -0.05, 0.0, 0.08, 0.12, 0.0], noise=0.065,
                         mix=[1.05, 1.1, 1.0, 0.9, 0.95, 1.0]),
    "Express": dict(dow=[0.05, 0.04, 0.06, 0.07, 0.06, -0.12, -0.16], noise=0.09,
                    mix=[0.75, 0.9, 0.85, 0.7, 1.25, 1.5]),
}


@dataclass
class Store:
    id: str
    name: str
    region: str
    lat: float
    lon: float
    format: str
    size: float  # volume multiplier
    growth: float  # true yearly growth in log units
    climate: tuple  # (annual mean C, seasonal amplitude C)


STORES = [
    Store("S01", "Ballard", "Puget Sound", 47.6687, -122.3847, "Neighborhood", 1.10, 0.035, (11.5, 7.0)),
    Store("S02", "Capitol Hill", "Puget Sound", 47.6235, -122.3200, "Express", 0.55, 0.050, (11.5, 7.0)),
    Store("S03", "Bellevue Crossroads", "Puget Sound", 47.6177, -122.1300, "Superstore", 2.10, 0.020, (11.0, 7.5)),
    Store("S04", "Tacoma Proctor", "Puget Sound", 47.2620, -122.4900, "Neighborhood", 0.95, 0.010, (11.0, 7.0)),
    Store("S05", "Everett Mall", "Puget Sound", 47.9100, -122.2150, "Superstore", 1.75, -0.015, (10.5, 7.0)),
    Store("S06", "Olympia Westside", "Puget Sound", 47.0440, -122.9300, "Neighborhood", 0.85, 0.025, (10.5, 7.5)),
    Store("S07", "Bellingham Fairhaven", "Puget Sound", 48.7200, -122.5040, "Neighborhood", 0.80, 0.030, (10.0, 6.5)),
    Store("S08", "Spokane South Hill", "Inland Northwest", 47.6310, -117.4040, "Superstore", 1.60, 0.015, (9.0, 11.5)),
    Store("S09", "Yakima", "Inland Northwest", 46.6000, -120.5300, "Neighborhood", 0.75, -0.030, (11.0, 12.5)),
    Store("S10", "Kennewick", "Inland Northwest", 46.2100, -119.1600, "Superstore", 1.45, 0.045, (12.5, 13.0)),
    Store("S11", "Vancouver Uptown", "Portland Metro", 45.6380, -122.6700, "Neighborhood", 1.00, 0.020, (12.0, 8.0)),
    Store("S12", "Portland Pearl", "Portland Metro", 45.5290, -122.6830, "Express", 0.60, 0.060, (12.5, 8.0)),
    Store("S13", "Portland Sellwood", "Portland Metro", 45.4660, -122.6530, "Neighborhood", 0.90, 0.000, (12.5, 8.0)),
    Store("S14", "Beaverton", "Portland Metro", 45.4870, -122.8030, "Superstore", 1.90, 0.025, (12.0, 8.0)),
    Store("S15", "Salem Lancaster", "Willamette & Central OR", 44.9400, -122.9800, "Superstore", 1.55, 0.010, (12.0, 8.0)),
    Store("S16", "Eugene Whiteaker", "Willamette & Central OR", 44.0560, -123.1060, "Neighborhood", 0.85, 0.015, (11.5, 7.5)),
    Store("S17", "Bend Old Mill", "Willamette & Central OR", 44.0480, -121.3150, "Neighborhood", 0.90, 0.070, (8.0, 9.5)),
    Store("S18", "Boise Downtown", "Idaho", 43.6150, -116.2020, "Express", 0.65, 0.055, (12.0, 12.0)),
]
STORE = {s.id: s for s in STORES}
REGIONS = list(dict.fromkeys(s.region for s in STORES))


@dataclass
class Event:
    store: str
    label: str
    start: dt.date
    end: dt.date | None  # None for a permanent step change
    effect: float  # true log-lift


EVENTS = [
    Event("S04", "Remodel", dt.date(2025, 2, 3), dt.date(2025, 3, 2), -0.35),
    Event("S17", "Store expansion", dt.date(2025, 9, 15), None, 0.12),
    Event("S15", "Competitor opened nearby", dt.date(2026, 5, 11), None, -0.10),
]


def _thanksgiving(y):
    nov1 = dt.date(y, 11, 1)
    return nov1 + dt.timedelta(days=(3 - nov1.weekday()) % 7 + 21)


def _memorial_day(y):
    may31 = dt.date(y, 5, 31)
    return may31 - dt.timedelta(days=may31.weekday())


def _labor_day(y):
    sep1 = dt.date(y, 9, 1)
    return sep1 + dt.timedelta(days=(7 - sep1.weekday()) % 7)


def _calendar(dates):
    """Holiday indicators (n, len(HOLIDAYS)) and an open-day mask."""
    days = {k: set() for k in HOLIDAYS}
    closed = set()
    for y in sorted({d.year for d in dates}):
        tg = _thanksgiving(y)
        closed.update([tg, dt.date(y, 12, 25)])
        days["pre_thanksgiving"].update(tg - dt.timedelta(days=i) for i in (1, 2, 3))
        days["christmas_runup"].update(dt.date(y, 12, d) for d in range(20, 25))
        days["nye"].add(dt.date(y, 12, 31))
        days["post_holiday"].update([dt.date(y, 12, 26), dt.date(y, 1, 1)])
        for monday in (_memorial_day(y), _labor_day(y)):
            days["summer_weekend"].update(monday - dt.timedelta(days=i) for i in (0, 1, 2))
        days["summer_weekend"].update([dt.date(y, 7, 3), dt.date(y, 7, 4)])
    hol = np.array([[d in days[k] for k in HOLIDAYS] for d in dates], float)
    is_open = np.array([d not in closed for d in dates])
    return hol, is_open


HOL, OPEN = _calendar(DATES)
T = np.arange(len(DATES)) / 365.25
DOY = np.array([d.timetuple().tm_yday for d in DATES])
DOW = np.array([d.weekday() for d in DATES])
WEEK = np.arange(len(DATES)) // 7
CLOSED_DATES = [d for d, o in zip(FORECAST_DATES, OPEN[N_HIST:]) if not o]


def _ar1(rng, shape, phi, sd):
    """AR(1) paths along the last axis with marginal standard deviation sd."""
    innov = rng.standard_normal(shape) * sd * np.sqrt(1 - phi**2)
    out = np.empty(shape)
    out[..., 0] = innov[..., 0] / np.sqrt(1 - phi**2)
    for i in range(1, shape[-1]):
        out[..., i] = phi * out[..., i - 1] + innov[..., i]
    return out


def _simulate_history():
    rng = np.random.default_rng(42)
    n = N_HIST
    # Chain-wide circular: each department is on promotion in about one week in six.
    # The calendar runs through the forecast horizon, since future promos are planned.
    n_weeks = WEEK[-1] + 1
    promo = {}
    for d in DEPARTMENTS:
        on = rng.random(n_weeks) < 0.17
        on[1:] &= ~on[:-1]  # never two weeks in a row
        promo[d] = on
    # Temperature: seasonal normal plus a regional and a local anomaly
    regional = _ar1(rng, (n,), TEMP_PHI, TEMP_SD * 0.75)
    normal, anomaly = {}, {}
    for s in STORES:
        mean, amp = s.climate
        normal[s.id] = mean + amp * np.cos(2 * np.pi * (DOY - 205) / 365.25)
        anomaly[s.id] = regional + _ar1(rng, (n,), TEMP_PHI, TEMP_SD * 0.66)
    chain_shock = rng.standard_normal(n) * 0.02
    units = {}
    for s in STORES:
        fmt = FORMATS[s.format]
        event = np.zeros(n)
        for e in EVENTS:
            if e.store == s.id:
                end = e.end or DATES[-1]
                event += e.effect * np.array([e.start <= d <= end for d in DATES[:n]])
        for j, d in enumerate(DEPARTMENTS):
            p = DEPT[d]
            log_u = (
                np.log(p["base"] * s.size * fmt["mix"][j])
                + s.growth * T[:n]
                + p["amp"] * np.cos(2 * np.pi * (DOY[:n] - p["peak"]) / 365.25)
                + np.array(fmt["dow"])[DOW[:n]]
                + HOL[:n] @ np.array(p["hol"])
                + p["promo"] * promo[d][WEEK[:n]]
                + p["temp"] * anomaly[s.id]
                + event
                + _ar1(rng, (n,), 0.35, fmt["noise"])
                + chain_shock
            )
            units[(s.id, d)] = np.where(OPEN[:n], np.round(np.exp(log_u)), 0.0)
    return units, promo, anomaly


UNITS, PROMO, ANOMALY = _simulate_history()
KEYS = list(UNITS)


def _design(store_id):
    """Columns shared by every department of a store, and the group each column belongs to."""
    angle = 2 * np.pi * DOY / 365.25
    cols = [np.ones(len(DATES)), T]
    groups = ["base", "trend"]
    for k in (1, 2, 3):
        cols += [np.sin(k * angle), np.cos(k * angle)]
        groups += ["base", "base"]
    for dow in range(1, 7):
        cols.append((DOW == dow).astype(float))
        groups.append("base")
    cols += list(HOL.T)
    groups += ["holiday"] * len(HOLIDAYS)
    for e in EVENTS:
        if e.store == store_id:
            end = e.end or DATES[-1]
            cols.append(np.array([e.start <= d <= end for d in DATES], float))
            groups.append("event")
    return np.column_stack(cols), groups


DESIGN = {s.id: _design(s.id) for s in STORES}


@dataclass
class Model:
    key: tuple
    end: int  # index of the first forecast day
    beta: np.ndarray
    groups: list
    phi: float
    sigma: float  # AR innovation standard deviation
    last_resid: float
    last_anomaly: float
    resid: np.ndarray  # in-sample residuals, 0 on closed days

    @property
    def beta_temp(self):
        return self.beta[-1]


def _features(key, promo_on):
    """Full design matrix for a series, with promo and temperature columns last."""
    base, groups = DESIGN[key[0]]
    anomaly = np.concatenate([ANOMALY[key[0]], np.zeros(HORIZON)])
    return np.column_stack([base, promo_on, anomaly]), groups + ["promo", "weather"]


def fit(key, end=N_HIST):
    """Fit the regression and AR(1) error on history up to (not including) day `end`."""
    X, groups = _features(key, PROMO[key[1]][WEEK].astype(float))
    y = UNITS[key]
    rows = OPEN[:end]
    beta, *_ = np.linalg.lstsq(X[:end][rows], np.log(y[:end][rows]), rcond=None)
    resid = np.where(rows, np.log(np.maximum(y[:end], 1)) - X[:end] @ beta, 0.0)
    r = resid[rows]
    phi = float(np.clip(np.corrcoef(r[1:], r[:-1])[0, 1], 0, 0.95))
    sigma = float(np.std(r[1:] - phi * r[:-1]))
    return Model(key, end, beta, groups, phi, sigma, resid[end - 1], ANOMALY[key[0]][end - 1], resid)


MODELS = {k: fit(k) for k in KEYS}
BACKTEST = {k: fit(k, N_HIST - HORIZON) for k in KEYS}

# Average correlation between the residuals of different series, used to
# correlate the simulated errors (a chain-wide shock moves every store at once)
_R = np.array([m.resid[OPEN[:N_HIST]] for m in MODELS.values()])
_C = np.corrcoef(_R)
RHO = float(np.clip((_C.sum() - len(_C)) / (len(_C) ** 2 - len(_C)), 0, 0.9))

_H = np.arange(1, HORIZON + 1)


def _promo_path(m, promo_weeks):
    """Promotion flags over the horizon: the planned calendar, or promo_weeks (week offsets) if given."""
    if promo_weeks is None:
        return PROMO[m.key[1]][WEEK[m.end:m.end + HORIZON]].astype(float)
    return np.isin((_H - 1) // 7, list(promo_weeks)).astype(float)


def components(m, promo_weeks=None, temp_shift=0.0):
    """Log-scale forecast components over the horizon, grouped as in the design matrix."""
    X, groups = _features(m.key, PROMO[m.key[1]][WEEK].astype(float))
    X = X[m.end:m.end + HORIZON].copy()
    X[:, -2] = _promo_path(m, promo_weeks)
    # The weather we expect: today's anomaly fades into the chosen outlook
    X[:, -1] = temp_shift + (m.last_anomaly - temp_shift) * TEMP_PHI**_H
    out = {g: np.zeros(HORIZON) for g in ["base", "trend", "holiday", "event", "promo", "weather"]}
    for j, g in enumerate(groups):
        out[g] += X[:, j] * m.beta[j]
    return out


def variance(m):
    """Variance of the log forecast at each horizon: AR errors plus unknown weather."""
    ar = m.sigma**2 * (1 - m.phi ** (2 * _H)) / (1 - m.phi**2)
    weather = (m.beta_temp * TEMP_SD) ** 2 * (1 - TEMP_PHI ** (2 * _H))
    return ar + weather


def expected(m, promo_weeks=None, temp_shift=0.0):
    """Mean daily units over the horizon."""
    mu = sum(components(m, promo_weeks, temp_shift).values()) + m.last_resid * m.phi**_H
    return np.exp(mu + variance(m) / 2) * OPEN[m.end:m.end + HORIZON]


def _ar_matrix(phi):
    i = np.arange(HORIZON)
    lag = i[:, None] - i[None, :]
    return np.where(lag >= 0, phi ** np.maximum(lag, 0), 0.0)


def simulate(models, promo_weeks=None, temp_shift=0.0, seed=0):
    """Sample paths of total daily units, shape (DRAWS, HORIZON), summed over the models.

    promo_weeks maps a department to the week offsets it is on promotion; departments
    not in it keep the planned calendar.
    """
    rng = np.random.default_rng(seed)
    promo_weeks = promo_weeks or {}
    common = rng.standard_normal((DRAWS, HORIZON))
    weather = {}
    total = np.zeros((DRAWS, HORIZON))
    for m in models:
        store = m.key[0]
        if store not in weather:
            # Weather surprise around the expected path, shared by a store's departments
            innov = rng.standard_normal((DRAWS, HORIZON)) * TEMP_SD * np.sqrt(1 - TEMP_PHI**2)
            weather[store] = innov @ _ar_matrix(TEMP_PHI).T
        mu = sum(components(m, promo_weeks.get(m.key[1]), temp_shift).values())
        z = np.sqrt(RHO) * common + np.sqrt(1 - RHO) * rng.standard_normal((DRAWS, HORIZON))
        err = (z * m.sigma) @ _ar_matrix(m.phi).T + m.last_resid * m.phi**_H
        total += np.exp(mu + err + m.beta_temp * weather[store]) * OPEN[m.end:m.end + HORIZON]
    return total


def actuals(keys, start=0, stop=N_HIST):
    return sum(UNITS[k][start:stop] for k in keys)


def last_year(m):
    """Components, residuals and open mask for the same 84 days one year (52 weeks) earlier."""
    lo = m.end - 364
    X, groups = _features(m.key, PROMO[m.key[1]][WEEK].astype(float))
    X = X[lo:lo + HORIZON]
    out = {g: np.zeros(HORIZON) for g in ["base", "trend", "holiday", "event", "promo", "weather"]}
    for j, g in enumerate(groups):
        out[g] += X[:, j] * m.beta[j]
    return out, m.resid[lo:lo + HORIZON], OPEN[lo:lo + HORIZON]


BRIDGE = [
    ("resid", "Last year's one-offs"),
    ("trend", "Underlying growth"),
    ("event", "Store events"),
    ("promo", "Promotions"),
    ("holiday", "Holidays & calendar"),
    ("weather", "Weather"),
]


def bridge(models, promo_weeks=None, temp_shift=0.0):
    """Walk from last year's actual units to this forecast, one driver at a time.

    Returns last year's total, a list of (label, change) and the forecast total
    (expected units). Each step swaps one driver from its last-year value to its
    forecast value, so the steps add up exactly.
    """
    promo_weeks = promo_weeks or {}
    parts = []
    for m in models:
        f = components(m, promo_weeks.get(m.key[1]), temp_shift)
        f["resid"] = m.last_resid * m.phi**_H + variance(m) / 2
        ly, ly_resid, ly_open = last_year(m)
        ly["resid"] = ly_resid
        parts.append((ly, f, ly_open, OPEN[m.end:m.end + HORIZON]))

    def total(switched):
        out = 0.0
        for ly, f, ly_open, f_open in parts:
            # Seasonality and day-of-week ride along with the holiday calendar
            log_u = sum((f if ("holiday" if g == "base" else g) in switched else ly)[g] for g in ly)
            out += np.sum(np.exp(log_u) * (f_open if "holiday" in switched else ly_open))
        return out

    switched = set()
    start = prev = total(switched)
    steps = []
    for g, label in BRIDGE:
        switched.add(g)
        now = total(switched)
        steps.append((label, now - prev))
        prev = now
    return start, steps, prev
