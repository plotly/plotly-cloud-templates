"""
Synthetic sensor history and failure model for the Calder Bay Nitrogen Works,
a made-up fertilizer plant with 36 pieces of rotating equipment.

Every asset streams four hourly sensors (vibration, bearing temperature, motor
current, outlet pressure) alongside plant load and ambient temperature. Failures
are simulated with a P-F interval: some days before a breakdown the asset starts
to degrade and each failure mode leaves its own signature on the sensors. Some
failures give almost no warning, and a few sensors drift without any failure,
so the model has real misses and false alarms to deal with.

The model is a regularized logistic regression, written in numpy, that predicts
the chance an asset fails within 7, 14 or 30 days from daily features: how far
each sensor sits from its own healthy, load-corrected baseline, how fast that is
moving, vibration spread and run time since the last repair. It trains on the
first eight months and is scored on the last four.
"""

import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

# Days an asset was down give empty slices; those come out as NaN on purpose
warnings.filterwarnings("ignore", "Mean of empty slice", RuntimeWarning)
warnings.filterwarnings("ignore", "Degrees of freedom", RuntimeWarning)
warnings.filterwarnings("ignore", "All-NaN slice", RuntimeWarning)

AS_OF = datetime(2026, 11, 4, 6, 0)
DAYS = 365
HOURS = DAYS * 24
FUTURE_DAYS = 45  # simulated past the as-of date so degradation in progress is real
START = AS_OF - timedelta(hours=HOURS)
DAY_DATES = [START + timedelta(days=d + 1) for d in range(DAYS)]  # end of each day
TRAIN_DAYS = 245
WARMUP = 14
HORIZONS = (7, 14, 30)

SENSORS = ("vib", "temp", "current", "pressure")
SENSOR_LABEL = {
    "vib": "Vibration",
    "temp": "Bearing temp",
    "current": "Motor current",
    "pressure": "Outlet pressure",
}
SENSOR_UNIT = {"vib": "mm/s", "temp": "°C", "current": "A", "pressure": "bar"}

AREAS = {
    # name: (x0, y0, x1, y1) on the floor plan
    "Utilities": (0, 34, 30, 60),
    "Cooling water": (0, 0, 30, 30),
    "Compression": (34, 34, 66, 60),
    "Synthesis": (34, 0, 66, 30),
    "Product handling": (70, 0, 100, 60),
}

# Healthy operating point per equipment type: vibration mm/s, bearing temp °C at
# zero load and 15 °C ambient, full-load current A, full-load outlet pressure bar
TYPES = {
    "Centrifugal pump": dict(vib=2.6, temp=46, current=110, pressure=18.0, mtbf=210,
                             modes=("Bearing wear", "Cavitation", "Misalignment")),
    "Compressor": dict(vib=3.8, temp=58, current=420, pressure=32.0, mtbf=240,
                       modes=("Bearing wear", "Lube oil breakdown", "Valve fouling")),
    "Cooling tower fan": dict(vib=4.5, temp=40, current=75, pressure=1.2, mtbf=200,
                              modes=("Bearing wear", "Imbalance")),
    "Blower": dict(vib=3.2, temp=50, current=160, pressure=1.8, mtbf=230,
                   modes=("Valve fouling", "Bearing wear", "Lube oil breakdown")),
    "Drive motor": dict(vib=1.9, temp=52, current=95, pressure=0.0, mtbf=260,
                        modes=("Winding insulation", "Bearing wear", "Misalignment")),
}

# Effect of each failure mode on (vib, temp, current, pressure) when it is about to
# fail, in units of sensor noise, plus how sharply it ramps up (power on severity)
MODES = {
    "Bearing wear": dict(sig=(8.0, 6.0, 1.5, 0.0), shape=2.0,
                         action="Schedule bearing replacement; take a vibration spectrum to confirm defect frequencies."),
    "Cavitation": dict(sig=(4.0, 1.0, -3.0, -7.0), shape=1.2,
                       action="Check suction strainer and NPSH margin; inspect impeller and mechanical seal."),
    "Misalignment": dict(sig=(9.0, 2.0, 1.0, 0.0), shape=1.0,
                         action="Laser-align the coupling and check for soft foot at the next opportunity."),
    "Imbalance": dict(sig=(9.0, 1.5, 1.5, -1.0), shape=1.3,
                      action="Inspect blades for build-up or damage; trim-balance the rotor."),
    "Lube oil breakdown": dict(sig=(3.0, 9.0, 1.0, 0.0), shape=1.5,
                               action="Pull an oil sample, change oil and filters, check cooler performance."),
    "Valve fouling": dict(sig=(1.0, 2.0, 5.0, -5.0), shape=1.0,
                          action="Plan valve or inlet cleaning; compare power draw against throughput."),
    "Winding insulation": dict(sig=(1.0, 5.0, 7.0, 0.0), shape=1.6,
                               action="Run insulation resistance and partial discharge tests; check cooling airflow."),
}

# One unit of degradation effect, per sensor, relative to the healthy operating point
UNIT = {"vib": 0.10, "temp": 1.4, "current": 0.018, "pressure": 0.012}

ASSET_LIST = [
    # tag, name, area, type
    ("P-101A", "Boiler feed water pump A", "Utilities", "Centrifugal pump"),
    ("P-101B", "Boiler feed water pump B", "Utilities", "Centrifugal pump"),
    ("P-102", "Condensate return pump", "Utilities", "Centrifugal pump"),
    ("P-103", "Fire water jockey pump", "Utilities", "Centrifugal pump"),
    ("K-101", "Instrument air compressor", "Utilities", "Compressor"),
    ("B-101", "Combustion air blower", "Utilities", "Blower"),
    ("P-201A", "Cooling water pump A", "Cooling water", "Centrifugal pump"),
    ("P-201B", "Cooling water pump B", "Cooling water", "Centrifugal pump"),
    ("P-201C", "Cooling water pump C", "Cooling water", "Centrifugal pump"),
    ("P-202", "Side-stream filter pump", "Cooling water", "Centrifugal pump"),
    ("F-201", "Cooling tower fan, cell 1", "Cooling water", "Cooling tower fan"),
    ("F-202", "Cooling tower fan, cell 2", "Cooling water", "Cooling tower fan"),
    ("F-203", "Cooling tower fan, cell 3", "Cooling water", "Cooling tower fan"),
    ("F-204", "Cooling tower fan, cell 4", "Cooling water", "Cooling tower fan"),
    ("K-301", "Syngas compressor", "Compression", "Compressor"),
    ("K-302", "Recycle compressor", "Compression", "Compressor"),
    ("K-303", "Refrigeration compressor", "Compression", "Compressor"),
    ("B-301", "Process air blower", "Compression", "Blower"),
    ("P-301", "Compressor lube oil pump", "Compression", "Centrifugal pump"),
    ("P-401", "Ammonia transfer pump", "Synthesis", "Centrifugal pump"),
    ("P-402A", "Semi-lean solvent pump A", "Synthesis", "Centrifugal pump"),
    ("P-402B", "Semi-lean solvent pump B", "Synthesis", "Centrifugal pump"),
    ("P-403", "Stripper reflux pump", "Synthesis", "Centrifugal pump"),
    ("B-401", "Reformer ID fan", "Synthesis", "Blower"),
    ("K-401", "Purge gas compressor", "Synthesis", "Compressor"),
    ("M-401", "Catalyst handling drive", "Synthesis", "Drive motor"),
    ("M-501", "Conveyor drive 1", "Product handling", "Drive motor"),
    ("M-502", "Conveyor drive 2", "Product handling", "Drive motor"),
    ("M-503", "Conveyor drive 3", "Product handling", "Drive motor"),
    ("M-504", "Bagging line drive", "Product handling", "Drive motor"),
    ("M-505", "Granulator drive", "Product handling", "Drive motor"),
    ("M-506", "Bucket elevator drive", "Product handling", "Drive motor"),
    ("B-501", "Dryer exhaust blower", "Product handling", "Blower"),
    ("F-501", "Prill tower fan", "Product handling", "Cooling tower fan"),
    ("P-501", "Urea melt pump", "Product handling", "Centrifugal pump"),
    ("P-502", "Scrubber recirculation pump", "Product handling", "Centrifugal pump"),
]


@dataclass
class Failure:
    hour: int  # hour index of the breakdown (can be past the as-of date)
    mode: str
    onset: int  # hour index degradation starts
    down_hours: int
    strength: float = 1.0  # sudden failures barely show on the sensors first


@dataclass
class Asset:
    i: int
    tag: str
    name: str
    area: str
    kind: str
    x: float
    y: float
    failures: list


rng = np.random.default_rng(42)
H_ALL = HOURS + FUTURE_DAYS * 24
t_h = np.arange(H_ALL)


def _layout_positions():
    pos = {}
    for area, (x0, y0, x1, y1) in AREAS.items():
        tags = [a[0] for a in ASSET_LIST if a[2] == area]
        cols = 2 if area == "Product handling" or len(tags) <= 6 else 3
        if area in ("Utilities", "Compression"):
            cols = 3
        if area in ("Cooling water", "Synthesis"):
            cols = 4
        rows = int(np.ceil(len(tags) / cols))
        for k, tag in enumerate(tags):
            r, c = divmod(k, cols)
            pos[tag] = (x0 + (x1 - x0) * (c + 0.5) / cols,
                        y1 - 7 - (y1 - y0 - 10) * (r + 0.5) / rows)
    return pos


def _ar1(n, phi, sd, size=None):
    """AR(1) noise with stationary standard deviation sd along the last axis."""
    shape = (n,) if size is None else (size, n)
    e = rng.normal(0, sd * np.sqrt(1 - phi**2), shape)
    out = np.empty(shape)
    out[..., 0] = rng.normal(0, sd, shape[:-1]) if size else rng.normal(0, sd)
    for k in range(1, n):
        out[..., k] = phi * out[..., k - 1] + e[..., k]
    return out


def _simulate_failures(kind, forced_future):
    mtbf_h = TYPES[kind]["mtbf"] * 24
    modes = TYPES[kind]["modes"]
    out, h = [], int(rng.uniform(0.1, 1.0) * mtbf_h)
    while h < H_ALL - 24:
        mode = modes[rng.choice(len(modes), p=np.r_[0.5, np.full(len(modes) - 1, 0.5 / (len(modes) - 1))])]
        sudden = rng.random() < 0.22
        pf_days = rng.uniform(1, 3) if sudden else rng.uniform(8, 30)
        onset = max(0, h - int(pf_days * 24))
        if out:
            onset = max(onset, out[-1].hour + out[-1].down_hours + 48)
        out.append(Failure(h, mode, onset, int(rng.uniform(20, 96)), 0.3 if sudden else 1.0))
        h += out[-1].down_hours + int(rng.exponential(mtbf_h))
    if forced_future:
        # Make sure this asset is degrading right now, failing a few days to weeks out
        out = [f for f in out if f.hour + f.down_hours < HOURS - 24 * 25]
        h = HOURS + int(rng.uniform(3, 32) * 24)
        mode = modes[rng.integers(len(modes))]
        pf = int(rng.uniform(18, 34) * 24)
        out.append(Failure(h, mode, h - pf, 48))
    return out


def _simulate():
    pos = _layout_positions()
    n = len(ASSET_LIST)
    forced = set(rng.choice(n, 7, replace=False).tolist())

    day_frac = (t_h % 24) / 24
    doy = ((START - datetime(START.year, 1, 1)).days + t_h / 24) % 365
    ambient = 9 + 11 * np.sin(2 * np.pi * (doy - 110) / 365) - 4 * np.cos(2 * np.pi * day_frac) + _ar1(H_ALL, 0.98, 2.0)

    # Plant load: daily swing, softer weekends, a few turndowns, shared by an area
    weekday = ((START.weekday() + t_h // 24) % 7)
    base_load = 0.86 + 0.06 * np.sin(2 * np.pi * (day_frac - 0.3)) - 0.05 * (weekday >= 5)
    for _ in range(6):
        s = int(rng.uniform(0, H_ALL - 200))
        base_load[s:s + int(rng.uniform(30, 120))] -= rng.uniform(0.2, 0.35)
    area_load = {a: np.clip(base_load + _ar1(H_ALL, 0.97, 0.03), 0.35, 1.05) for a in AREAS}

    assets, raw, load, running = [], {s: np.empty((n, H_ALL)) for s in SENSORS}, np.empty((n, H_ALL)), np.ones((n, H_ALL), bool)
    severity = np.zeros((n, H_ALL))
    effect = {s: np.zeros((n, H_ALL)) for s in SENSORS}
    for i, (tag, name, area, kind) in enumerate(ASSET_LIST):
        spec = TYPES[kind]
        fails = _simulate_failures(kind, i in forced)
        assets.append(Asset(i, tag, name, area, kind, *pos[tag], fails))
        L = np.clip(area_load[area] + rng.normal(0, 0.015, H_ALL), 0.3, 1.05)
        load[i] = L
        jitter = rng.uniform(0.85, 1.15)
        for f in fails:
            seg = slice(f.onset, f.hour)
            prog = (t_h[seg] - f.onset) / max(1, f.hour - f.onset)
            sev = prog ** MODES[f.mode]["shape"]
            severity[i, seg] = sev
            for k, s in enumerate(SENSORS):
                effect[s][i, seg] = MODES[f.mode]["sig"][k] * sev * f.strength * rng.uniform(0.7, 1.3)
            running[i, f.hour:f.hour + f.down_hours] = False

        v0, T0, c0, p0 = spec["vib"] * jitter, spec["temp"] + rng.uniform(-3, 3), spec["current"] * jitter, spec["pressure"]
        vib = v0 * (0.6 + 0.4 * L) * (1 + _ar1(H_ALL, 0.9, 0.05) + _ar1(H_ALL, 0.995, 0.03)) + effect["vib"][i] * UNIT["vib"] * v0
        vib *= 1 + (effect["vib"][i] > 2) * rng.normal(0, 0.06, H_ALL) * (kind == "Centrifugal pump")
        spikes = rng.random(H_ALL) < 0.002
        vib[spikes] *= rng.uniform(1.5, 2.5, spikes.sum())
        temp = T0 + 0.35 * (ambient - 15) + 18 * L + _ar1(H_ALL, 0.95, 0.7) + _ar1(H_ALL, 0.998, 0.6) + effect["temp"][i] * UNIT["temp"]
        cur = c0 * (0.3 + 0.7 * L) * (1 + _ar1(H_ALL, 0.9, 0.012) + _ar1(H_ALL, 0.998, 0.008) + effect["current"][i] * UNIT["current"])
        prs = p0 * (0.7 + 0.3 * L) * (1 + _ar1(H_ALL, 0.9, 0.008) + _ar1(H_ALL, 0.998, 0.006) + effect["pressure"][i] * UNIT["pressure"])

        # Nuisance: a temperature or vibration sensor that drifts and gets recalibrated
        if rng.random() < 0.3:
            s0 = int(rng.uniform(24 * 20, HOURS - 24 * 5))
            ln = int(rng.uniform(6, 16) * 24)
            ramp = np.clip((t_h - s0) / ln, 0, 1) * (t_h < s0 + ln + 24)
            if rng.random() < 0.5:
                temp += 7 * ramp
            else:
                vib *= 1 + 0.6 * ramp

        for s, arr in zip(SENSORS, (vib, temp, cur, prs)):
            arr = arr.copy()
            arr[~running[i]] = np.nan
            raw[s][i] = arr
        load[i][~running[i]] = 0.0
    return assets, raw, load, running, ambient, severity


ASSETS, _RAW, _LOAD, _RUNNING, _AMBIENT, _SEVERITY = _simulate()
BY_TAG = {a.tag: a for a in ASSETS}
N = len(ASSETS)

# Only what the plant historian would have seen up to the as-of time
RAW = {s: v[:, :HOURS] for s, v in _RAW.items()}
LOAD = _LOAD[:, :HOURS]
RUNNING = _RUNNING[:, :HOURS]
AMBIENT = _AMBIENT[:HOURS]
HOUR_TIMES = np.array([START + timedelta(hours=h + 1) for h in range(HOURS)])


def load_factor(s, L):
    """Expected multiplier of each sensor at load L, the physics the model corrects for."""
    return {"vib": 0.6 + 0.4 * L, "current": 0.3 + 0.7 * L, "pressure": 0.7 + 0.3 * L}[s]


def corrected(s, i=slice(None)):
    """Sensor with load (and ambient, for temperature) effects removed."""
    if s == "temp":
        return RAW[s][i] - 0.35 * (AMBIENT - 15) - 18 * LOAD[i]
    return RAW[s][i] / load_factor(s, LOAD[i])


def _daily(x):
    return x.reshape(x.shape[0], DAYS, 24)


with np.errstate(all="ignore"):
    _CORR = {s: corrected(s) for s in SENSORS}
    DAILY = {s: np.nanmean(_daily(_CORR[s]), axis=2) for s in SENSORS}
    UP = _daily(RUNNING).mean(axis=2) >= 0.6  # asset ran most of the day
    for s in SENSORS:
        DAILY[s][~UP] = np.nan
    VIB_SPREAD = np.nanstd(_daily(_CORR["vib"]), axis=2)
    VIB_SPREAD[~UP] = np.nan

    # Healthy baseline per asset from the training period: median and robust spread
    BASE, SCALE = {}, {}
    for s in SENSORS:
        tr = DAILY[s][:, :TRAIN_DAYS]
        BASE[s] = np.nanmedian(tr, axis=1)
        SCALE[s] = 1.4826 * np.nanmedian(np.abs(tr - BASE[s][:, None]), axis=1) + 1e-9
    SPREAD_BASE = np.nanmedian(VIB_SPREAD[:, :TRAIN_DAYS], axis=1)

# Breakdowns the historian has recorded (before the as-of time)
FAIL_RECORDS = [(a.i, f.hour, f.mode) for a in ASSETS for f in a.failures if f.hour < HOURS]


def _days_since_repair():
    out = np.zeros((N, DAYS))
    for a in ASSETS:
        last = -24 * rng.uniform(30, 300)  # time in service before the history starts
        ends = sorted(f.hour + f.down_hours for f in a.failures if f.hour < HOURS)
        for d in range(DAYS):
            h = (d + 1) * 24
            while ends and ends[0] <= h:
                last = ends.pop(0)
            out[a.i, d] = (h - last) / 24
    return out


FEATURES = [
    ("vib_z", "vib", "Vibration level"),
    ("temp_z", "temp", "Bearing temp level"),
    ("current_z", "current", "Motor current level"),
    ("pressure_z", "pressure", "Outlet pressure level"),
    ("vib_d", "vib", "Vibration 7-day rise"),
    ("temp_d", "temp", "Bearing temp 7-day rise"),
    ("current_d", "current", "Motor current 7-day rise"),
    ("pressure_d", "pressure", "Outlet pressure 7-day change"),
    ("vib_spread", "vib", "Vibration erraticness"),
    ("age", None, "Run time since repair"),
]


def _build_features():
    cols = []
    Z = {}
    for s in SENSORS:
        z = (DAILY[s] - BASE[s][:, None]) / SCALE[s][:, None]
        # Smooth over two days so a single noisy day does not dominate
        zp = np.concatenate([z[:, :1], z[:, :-1]], axis=1)
        Z[s] = np.where(np.isnan(zp), z, 0.6 * z + 0.4 * zp)
    for s in SENSORS:
        cols.append(Z[s] if s != "pressure" else -Z[s])
    for s in SENSORS:
        z = Z[s] if s != "pressure" else -Z[s]
        prev = np.full_like(z, np.nan)
        for d in range(7, DAYS):
            prev[:, d] = np.nanmean(z[:, d - 7:d - 3], axis=1)
        cols.append(z - prev)
    cols.append(np.log(VIB_SPREAD / SPREAD_BASE[:, None]))
    cols.append(np.log1p(_days_since_repair() / 30))
    X = np.stack(cols, axis=2)
    X = np.clip(np.nan_to_num(X, nan=0.0), -12, 12)
    return X, Z


with np.errstate(all="ignore"):
    X, ZSCORE = _build_features()


def _labels(h_days):
    """1 if the asset breaks down within h_days after the end of day d. NaN when the
    window runs past the as-of date and the outcome is not known yet."""
    y = np.zeros((N, DAYS))
    for i, hour, _ in FAIL_RECORDS:
        fd = hour / 24
        lo = max(0, int(np.ceil(fd - h_days - 1)))
        y[i, lo:int(np.ceil(fd - 1))] = 1
    known = (np.arange(DAYS) + 1 + h_days) <= DAYS
    y[:, ~known] = np.nan
    return y


def _fit_logistic(Xm, y, lam=2.0, iters=50):
    """L2-regularized logistic regression by Newton's method with backtracking."""
    Xb = np.c_[np.ones(len(Xm)), Xm]
    R = lam * np.eye(Xb.shape[1])
    R[0, 0] = 0

    def loss(w):
        z = Xb @ w
        return np.sum(np.logaddexp(0, z) - y * z) + 0.5 * w @ R @ w

    w = np.zeros(Xb.shape[1])
    w[0] = np.log(y.mean() / (1 - y.mean()))
    f = loss(w)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Xb @ w, -30, 30)))
        g = Xb.T @ (p - y) + R @ w
        Hm = (Xb * (p * (1 - p))[:, None]).T @ Xb + R
        step = np.linalg.solve(Hm + 1e-8 * np.eye(len(w)), g)
        t = 1.0
        while loss(w - t * step) > f and t > 1e-4:
            t /= 2
        w = w - t * step
        f_new = loss(w)
        if f - f_new < 1e-8:
            break
        f = f_new
    return w


def _auc(score, y):
    order = np.argsort(score)
    ranks = np.empty(len(score))
    ranks[order] = np.arange(1, len(score) + 1)
    pos = y == 1
    return (ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum())


@dataclass
class Model:
    horizon: int
    mean: np.ndarray
    std: np.ndarray
    w: np.ndarray
    prob: np.ndarray  # (N, DAYS) predicted chance of failure within the horizon
    test_auc: float
    n_train: int
    base_rate: float

    def contributions(self, i, d):
        """Push of each feature on the log-odds of failure for asset i on day d."""
        return self.w[1:] * (X[i, d] - self.mean) / self.std


def _train(h):
    y = _labels(h)
    day = np.broadcast_to(np.arange(DAYS), (N, DAYS))
    ok = UP & ~np.isnan(y)
    tr = ok & (day >= WARMUP) & (day < TRAIN_DAYS)
    te = ok & (day >= TRAIN_DAYS)
    Xtr = X[tr]
    mean, std = Xtr.mean(axis=0), Xtr.std(axis=0) + 1e-9
    w = _fit_logistic((Xtr - mean) / std, y[tr])
    Xs = (X - mean) / std
    prob = 1 / (1 + np.exp(-(w[0] + Xs @ w[1:])))
    prob[~UP] = np.nan
    return Model(h, mean, std, w, prob, _auc(prob[te], y[te]), int(tr.sum()), float(y[tr].mean()))


MODELS = {h: _train(h) for h in HORIZONS}

# A longer horizon can never be less likely than a shorter one
_last = None
for h in HORIZONS:
    if _last is not None:
        MODELS[h].prob = np.fmax(MODELS[h].prob, MODELS[_last].prob)
    _last = h


def current_risk(h):
    """Latest prediction per asset; assets down for repair keep their last reading."""
    p = MODELS[h].prob
    out = np.full(N, np.nan)
    last_day = np.full(N, -1)
    for i in range(N):
        idx = np.where(~np.isnan(p[i]))[0]
        if len(idx):
            out[i], last_day[i] = p[i, idx[-1]], idx[-1]
    return out, last_day


def likely_mode(i, d):
    """Failure mode whose sensor signature best matches where the asset sits today."""
    z = np.array([ZSCORE[s][i, d] for s in SENSORS])
    z = np.nan_to_num(z)
    best, best_sim = None, -1.0
    for m in TYPES[ASSETS[i].kind]["modes"]:
        sig = np.array(MODES[m]["sig"])
        sim = float(z @ sig / (np.linalg.norm(z) * np.linalg.norm(sig) + 1e-9))
        if sim > best_sim:
            best, best_sim = m, sim
    return best, max(best_sim, 0.0), float(np.linalg.norm(z))


def is_down(i):
    return not RUNNING[i, -1]


def evaluate(h, threshold):
    """Score the alert rule 'risk >= threshold' on the held-out months, by event:
    a failure counts as caught if an alert fired within the horizon before it, and
    an alert run with no failure within the horizon after it starts is a false alarm."""
    p = MODELS[h].prob
    test = np.arange(TRAIN_DAYS, DAYS)
    alert = (np.nan_to_num(p[:, TRAIN_DAYS:], nan=0) >= threshold)
    fails = [(i, hour / 24, mode) for i, hour, mode in FAIL_RECORDS if hour / 24 >= TRAIN_DAYS + 3]
    events = []
    for i, fd, mode in fails:
        win = (test >= fd - h - 1) & (test <= fd - 1)
        hits = test[win & alert[i]]
        lead = fd - (hits[0] + 1) if len(hits) else None
        events.append(dict(i=i, day=fd, mode=mode, lead=lead))
    false_alarms, alarms = 0, 0
    for i in range(N):
        a = alert[i]
        starts = np.where(a & ~np.r_[False, a[:-1]])[0]
        for s in starts:
            day = test[s] + 1
            alarms += 1
            if not any(fi == i and day - 1 <= hr / 24 <= day + h for fi, hr, _ in FAIL_RECORDS):
                false_alarms += 1
    return events, false_alarms, alarms


TEST_MONTHS = (DAYS - TRAIN_DAYS) / 30.4
