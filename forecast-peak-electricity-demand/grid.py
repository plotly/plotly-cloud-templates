"""
Synthetic data and forecast model for Lakeshore Power Pool, a made-up summer-
peaking grid operator serving about 5 million people.

History: 120 days of hourly actual load and temperature up to AS_OF.
Forecast: a 14-day hourly weather ensemble (ENSEMBLE members) whose spread grows
with lead time. Each member's temperature path goes through the load model, so
the forecast load is a distribution, not a single line.

Load model, per hour:
    base(hour, weekday) + cooling(T_eff) + heating(T_eff)
where T_eff blends the temperature two hours earlier with a slow exponential
average of the last day and a half, so a run of hot days keeps pushing load up
(buildings soak up heat).

Supply, per hour: online units, thermal capacity derated in extreme heat, solar
following the sun, low wind in heat waves, firm imports and 4-hour batteries
that discharge into the evening ramp.

Operating reserve: the largest online unit (the single worst contingency) plus
3% of load. When load would eat into that reserve the pool issues alerts.
"""

import datetime as dt
from dataclasses import dataclass

import numpy as np

AS_OF = dt.datetime(2026, 7, 13, 23)  # last hour of actuals
HIST_DAYS = 120
FC_DAYS = 14
ENSEMBLE = 120
SEASON_RECORD = 18_640  # MW, all-time peak, set Aug 2023
RECORD_DATE = "Aug 17, 2023"

HIST_START = AS_OF.replace(hour=0) - dt.timedelta(days=HIST_DAYS - 1)
FC_START = AS_OF.replace(hour=0) + dt.timedelta(days=1)
HIST_HOURS = np.array([HIST_START + dt.timedelta(hours=h) for h in range(HIST_DAYS * 24)])
FC_HOURS = np.array([FC_START + dt.timedelta(hours=h) for h in range(FC_DAYS * 24)])
HIST_DATES = [(HIST_START + dt.timedelta(days=d)).date() for d in range(HIST_DAYS)]
FC_DATES = [(FC_START + dt.timedelta(days=d)).date() for d in range(FC_DAYS)]

HOUR = np.arange(24)


# ---------- supply ----------

@dataclass(frozen=True)
class Unit:
    id: str
    name: str
    kind: str  # nuclear | thermal | hydro
    mw: float


UNITS = [
    Unit("ridgeback1", "Ridgeback Nuclear 1", "nuclear", 1150),
    Unit("ridgeback2", "Ridgeback Nuclear 2", "nuclear", 1150),
    Unit("harbor", "Harbor Point CC", "thermal", 820),
    Unit("millbrook", "Millbrook CC", "thermal", 760),
    Unit("granite", "Granite Falls CC", "thermal", 680),
    Unit("westfield", "Westfield CC", "thermal", 640),
    Unit("coldspring1", "Cold Spring Coal 1", "thermal", 650),
    Unit("coldspring2", "Cold Spring Coal 2", "thermal", 650),
    Unit("cascade", "Cascade Hydro", "hydro", 1400),
]
UNIT_BY_ID = {u.id: u for u in UNITS}
OUTAGEABLE = [u.id for u in UNITS]
DEFAULT_OUTAGES = ["millbrook"]  # forced outage since Jul 11

STEAM_FLEET_MW = 6900  # older gas steam units, never individually outaged here
PEAKER_FLEET_MW = 3600  # combustion turbines
IMPORTS_MW = 2200
WIND_MW = 3000
SOLAR_MW = 4500
STORAGE_MW = 1200
STORAGE_HOURS = (17, 18, 19, 20)
DR_HOURS = np.arange(15, 22)  # demand response window, 3 pm to 10 pm

RESOURCES = ["Nuclear", "Gas & coal", "Hydro & imports", "Wind", "Solar", "Storage"]

# clear-sky solar shape, fraction of nameplate (DST, sun peaks ~13:30)
_SOLAR = np.clip(np.sin((HOUR + 0.5 - 6.2) / 14.6 * np.pi), 0, None) ** 1.35 * 0.78


def supply(outages, temp_max, wind_cf, cloud):
    """Available MW by resource for each hour of one day. temp_max derates thermal units."""
    out = set(outages)
    nuclear = sum(u.mw for u in UNITS if u.kind == "nuclear" and u.id not in out)
    thermal = sum(u.mw for u in UNITS if u.kind == "thermal" and u.id not in out) + STEAM_FLEET_MW + PEAKER_FLEET_MW
    hydro = sum(u.mw for u in UNITS if u.kind == "hydro" and u.id not in out)
    derate = 1 - 0.0045 * max(0.0, temp_max - 90)  # hot cooling water and thin air
    wind_shape = 0.8 + 0.35 * np.cos((HOUR - 3) / 24 * 2 * np.pi)  # stronger overnight
    stack = {
        "Nuclear": np.full(24, nuclear * 0.985),
        "Gas & coal": np.full(24, thermal * derate * 0.95),
        "Hydro & imports": np.full(24, hydro * 0.9 + IMPORTS_MW),
        "Wind": WIND_MW * wind_cf * wind_shape,
        "Solar": SOLAR_MW * _SOLAR * (1 - cloud),
        "Storage": np.where(np.isin(HOUR, STORAGE_HOURS), STORAGE_MW, 0.0),
    }
    largest = max([u.mw for u in UNITS if u.id not in out], default=0)
    return stack, largest


# ---------- load model ----------

_WEEKDAY_SHAPE = np.array([0.66, 0.63, 0.61, 0.60, 0.61, 0.65, 0.73, 0.82, 0.88, 0.91, 0.93, 0.94,
                           0.95, 0.95, 0.95, 0.96, 0.97, 0.98, 0.98, 0.96, 0.93, 0.87, 0.79, 0.71])
_WEEKEND_SHAPE = np.array([0.68, 0.64, 0.62, 0.60, 0.60, 0.61, 0.64, 0.69, 0.75, 0.81, 0.85, 0.88,
                           0.89, 0.89, 0.89, 0.90, 0.91, 0.92, 0.92, 0.91, 0.89, 0.84, 0.78, 0.72])
BASE_MW = 10_300


def base_load(hours):
    wk = np.array([h.weekday() >= 5 for h in hours])
    hr = np.array([h.hour for h in hours])
    return BASE_MW * np.where(wk, _WEEKEND_SHAPE[hr] * 0.93, _WEEKDAY_SHAPE[hr])


def effective_temp(temp, seed_avg=None):
    """temp: (..., hours). Blend of temp 2 h ago and a slow ~36 h exponential average."""
    lag = np.concatenate([temp[..., :1], temp[..., :1], temp[..., :-2]], axis=-1)
    slow = np.empty_like(temp)
    acc = temp[..., 0] if seed_avg is None else seed_avg
    a = 1 / 36
    for h in range(temp.shape[-1]):
        acc = acc + a * (temp[..., h] - acc)
        slow[..., h] = acc
    return 0.55 * lag + 0.45 * slow, acc


def weather_load(t_eff):
    hot = np.clip(t_eff - 64, 0, None)
    cold = np.clip(50 - t_eff, 0, None)
    return 200 * hot + 1.5 * hot ** 2 + 120 * cold


def diurnal_temp(tmax, tmin):
    """Hourly temperature from daily max/min (max at 16:00, min at 05:00)."""
    tmax, tmin = np.asarray(tmax, float), np.asarray(tmin, float)
    shape = 0.5 - 0.5 * np.cos((HOUR - 5) / 11 * np.pi)
    shape = np.where(HOUR > 16, 0.5 + 0.5 * np.cos((HOUR - 16) / 13 * np.pi), shape)
    shape = np.where(HOUR < 5, 0.5 + 0.5 * np.cos((HOUR + 8) / 13 * np.pi), shape)
    return tmin[..., None] + (tmax - tmin)[..., None] * shape


# ---------- history ----------

def _history():
    rng = np.random.default_rng(7)
    d = np.arange(HIST_DAYS)
    season = 60 + 27 * np.sin((d - 30) / 150 * np.pi)  # mid March ~60F -> July ~87F
    fronts = np.zeros(HIST_DAYS)
    for i in range(1, HIST_DAYS):
        fronts[i] = 0.72 * fronts[i - 1] + rng.normal(0, 3.6)
    tmax = season + fronts
    tmax[-4:] = [86, 89, 88, 90]  # warm-up before the forecast window
    tmin = tmax - rng.uniform(15, 22, HIST_DAYS)
    temp = diurnal_temp(tmax, tmin).ravel() + rng.normal(0, 0.8, HIST_DAYS * 24)
    t_eff, avg_end = effective_temp(temp)
    load = base_load(HIST_HOURS) + weather_load(t_eff)
    load *= 1 + np.repeat(rng.normal(0, 0.018, HIST_DAYS), 24) + rng.normal(0, 0.006, HIST_DAYS * 24)
    return temp, load, tmax, avg_end, temp[-2:]


HIST_TEMP, HIST_LOAD, HIST_TMAX, _AVG_END, _TAIL = _history()
HIST_DAILY_PEAK = HIST_LOAD.reshape(HIST_DAYS, 24).max(axis=1)
HIST_PEAK_HOUR = HIST_LOAD.reshape(HIST_DAYS, 24).argmax(axis=1)


# ---------- forecast ----------

# Central forecast: a heat wave builds through the weekend, peaks Jul 21-22, breaks Jul 24
FC_TMAX = np.array([90, 92, 91, 89, 93, 96, 99, 101, 102, 98, 93, 89, 88, 90], float)
FC_TMIN = FC_TMAX - np.array([18, 17, 17, 18, 16, 15, 14, 13, 13, 15, 18, 19, 19, 18])
FC_CLOUD = np.array([0.15, 0.10, 0.25, 0.35, 0.10, 0.05, 0.05, 0.05, 0.10, 0.30, 0.40, 0.20, 0.15, 0.10])
FC_WIND = np.array([0.22, 0.18, 0.25, 0.30, 0.17, 0.12, 0.10, 0.09, 0.11, 0.24, 0.32, 0.27, 0.22, 0.19])


def _ensemble_noise():
    rng = np.random.default_rng(42)
    sd = 1.1 + 0.42 * np.arange(FC_DAYS)  # degF, grows with lead time
    z = np.zeros((ENSEMBLE, FC_DAYS))
    z[:, 0] = rng.normal(0, 1, ENSEMBLE)
    for d in range(1, FC_DAYS):
        z[:, d] = 0.75 * z[:, d - 1] + np.sqrt(1 - 0.75 ** 2) * rng.normal(0, 1, ENSEMBLE)
    temp_dev = z * sd
    hourly = rng.normal(0, 0.7, (ENSEMBLE, FC_DAYS * 24))
    load_err = np.repeat(rng.normal(0, 0.014, (ENSEMBLE, FC_DAYS)), 24, axis=1)
    return temp_dev, hourly, load_err


_TEMP_DEV, _HOURLY_NOISE, _LOAD_ERR = _ensemble_noise()
_FC_BASE = base_load(FC_HOURS)


def forecast(temp_shift=0.0, outages=DEFAULT_OUTAGES, dr_mw=0.0):
    """Run the ensemble. Returns a dict of arrays; load arrays are (members, days, 24)."""
    tmax = FC_TMAX + temp_shift + _TEMP_DEV  # (members, days)
    tmin = FC_TMIN + temp_shift + 0.7 * _TEMP_DEV
    temp = diurnal_temp(tmax, tmin).reshape(ENSEMBLE, -1) + _HOURLY_NOISE
    seeded = np.concatenate([np.broadcast_to(_TAIL, (ENSEMBLE, 2)), temp], axis=1)
    t_eff, _ = effective_temp(seeded, seed_avg=np.full(ENSEMBLE, _AVG_END))
    load = (_FC_BASE + weather_load(t_eff[:, 2:])) * (1 + _LOAD_ERR)
    load = load.reshape(ENSEMBLE, FC_DAYS, 24)

    stacks, avail, reserve = [], np.zeros((FC_DAYS, 24)), np.zeros((FC_DAYS, 24))
    p50_load = np.median(load, axis=0)
    for d in range(FC_DAYS):
        stack, largest = supply(outages, FC_TMAX[d] + temp_shift, FC_WIND[d], FC_CLOUD[d])
        stacks.append(stack)
        avail[d] = sum(stack.values())
        reserve[d] = largest + 0.03 * p50_load[d]
    limit = avail - reserve  # load above this eats into operating reserve

    def risk_of(ld):
        short = (ld > limit).any(axis=2)  # member hits the limit at any hour that day
        return short.mean(axis=0)

    risk_before = risk_of(load)
    dr_days = np.zeros(FC_DAYS, bool)
    load_before = load
    if dr_mw > 0:
        dr_days = risk_before >= 0.05  # DR is called on Watch days and above
        shave = np.zeros((FC_DAYS, 24))
        shave[np.ix_(dr_days, DR_HOURS)] = dr_mw
        load = load - shave
    risk = risk_of(load)

    peaks = load.max(axis=2)  # (members, days)
    q = np.percentile(load, [10, 50, 90], axis=0)  # (3, days, 24)
    peak_q = np.percentile(peaks, [10, 50, 90], axis=0)
    peak_hour = q[1].argmax(axis=1)
    tight_hour = (limit - q[1]).argmin(axis=1)
    margin = (limit - q[1]).min(axis=1)  # MW of headroom at the tightest hour, P50 load
    new_record = (peaks.max(axis=1) > SEASON_RECORD).mean()
    tmax_q = np.percentile(tmax, [10, 50, 90], axis=0)
    return {
        "load": load, "load_before": load_before, "q": q, "peaks": peaks, "peak_q": peak_q,
        "peak_hour": peak_hour, "tight_hour": tight_hour, "margin": margin,
        "avail": avail, "reserve": reserve, "limit": limit, "stacks": stacks,
        "risk": risk, "risk_before": risk_before, "dr_days": dr_days,
        "new_record": new_record, "tmax_q": tmax_q,
    }


LEVELS = [  # (name, min risk, status color key, icon)
    ("Emergency", 0.50, "critical", "tabler:alert-octagon"),
    ("Warning", 0.20, "serious", "tabler:alert-triangle"),
    ("Watch", 0.05, "warning", "tabler:eye"),
    ("Normal", 0.0, "good", "tabler:circle-check"),
]


def level(risk):
    for name, lo, color, icon in LEVELS:
        if risk >= lo:
            return name, color, icon
    return LEVELS[-1][0], LEVELS[-1][2], LEVELS[-1][3]
