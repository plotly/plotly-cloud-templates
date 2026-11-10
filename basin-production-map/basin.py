"""
Synthetic monthly production for the wells of a made-up oil and gas basin.

The Caprock Basin is an oval about 50 miles across. Horizontal wells are drilled
from multi-well pads into three stacked benches, with a scatter of old vertical
wells that were on production before the data starts. Rock quality varies across
the basin (a few sweet spots), and the oil gets gassier to the west where the
benches are deeper.

Each well follows an Arps hyperbolic decline from its initial rate, with a
choke-managed first two months, a rising gas-oil ratio and water-oil ratio,
random workovers, shut-ins while an offset pad within about a mile and a
half is fracked, and a
few wells that are shut in at the end of the record. Some old verticals are
plugged and abandoned along the way.

Everything here is invented: basin, operators, leases and wells.
"""

from dataclasses import dataclass, field
from datetime import date
from math import cos, radians

import numpy as np

BASIN = "Caprock Basin"
N_MONTHS = 94  # Jan 2019 to Oct 2026
MONTHS = [date(2019 + i // 12, i % 12 + 1, 1) for i in range(N_MONTHS)]
DAYS_IN = np.array([
    ((date(d.year + (d.month == 12), d.month % 12 + 1, 1)) - d).days for d in MONTHS
])
AS_OF = MONTHS[-1]

CENTER = (32.36, -103.42)
LAT_PER_MILE = 1 / 69.0
LON_PER_MILE = 1 / (69.17 * cos(radians(CENTER[0])))

OPERATORS = ["Mesa Ridge Energy", "Halberd Petroleum", "Coyote Draw Resources", "Other operators"]
FORMATIONS = ["Tascosa Shale", "Caprock Sand", "Lower Saltfork"]
# Oil rate at 10,000 ft of lateral in good rock (bbl/d), gas factor, water-oil ratio
FORMATION_PARAMS = {
    "Tascosa Shale": dict(qi=880, gas=0.8, wor=1.3, b=1.05, di=1.9),
    "Caprock Sand": dict(qi=640, gas=1.0, wor=2.6, b=0.95, di=1.5),
    "Lower Saltfork": dict(qi=520, gas=1.7, wor=1.6, b=1.15, di=2.2),
}
WELL_TYPES = ["Horizontal", "Vertical"]
STATUSES = ["Producing", "Shut in", "Plugged"]  # codes 1, 2, 3; 0 = not online yet

LEASES = [
    "Pronghorn", "Mesquite", "Yucca", "Sidewinder", "Roadrunner", "Jackrabbit", "Cholla",
    "Javelina", "Caliche", "Tumbleweed", "Bluestem", "Sotol", "Ocotillo", "Lechuguilla",
    "Agave", "Horned Toad", "Bobcat", "Kestrel", "Harrier", "Thrasher", "Quail", "Gila",
    "Saltcedar", "Shinnery", "Sandbur", "Bitterweed", "Badger", "Lobo", "Creosote",
    "Paloverde", "Coachwhip", "Scaled Quail", "Burrowing Owl", "Ringtail", "Pinon",
]

# Rock quality: a low background with a few sweet spots (lat, lon, strength, radius deg)
SWEET_SPOTS = [
    (32.48, -103.55, 0.85, 0.11),
    (32.25, -103.30, 0.75, 0.09),
    (32.40, -103.18, 0.55, 0.08),
    (32.18, -103.62, 0.45, 0.10),
]
# Operator acreage: a few blocks each; a point belongs to the nearest seed
OPERATOR_SEEDS = [
    (32.50, -103.60, 0), (32.30, -103.55, 0), (32.44, -103.80, 0),
    (32.26, -103.28, 1), (32.12, -103.42, 1),
    (32.45, -103.25, 2), (32.58, -103.40, 2), (32.38, -103.05, 2),
    (32.20, -103.72, 3), (32.36, -103.42, 3), (32.62, -103.66, 3),
]

# Midstream: a gas plant, an oil terminal and central tank batteries
FACILITIES = [
    dict(name="Caprock Gas Plant", kind="Gas plant", lat=32.31, lon=-103.47),
    dict(name="Saltfork Crude Terminal", kind="Oil terminal", lat=32.10, lon=-103.18),
    dict(name="North CTB", kind="Tank battery", lat=32.55, lon=-103.52),
    dict(name="West CTB", kind="Tank battery", lat=32.30, lon=-103.74),
    dict(name="East CTB", kind="Tank battery", lat=32.42, lon=-103.14),
    dict(name="South CTB", kind="Tank battery", lat=32.17, lon=-103.48),
]
PIPELINES = [
    ["North CTB", "Caprock Gas Plant"], ["West CTB", "Caprock Gas Plant"],
    ["East CTB", "Caprock Gas Plant"], ["South CTB", "Caprock Gas Plant"],
    ["Caprock Gas Plant", "Saltfork Crude Terminal"],
]


@dataclass
class Well:
    idx: int
    name: str
    api: str
    lease: str
    operator: str
    formation: str
    well_type: str
    lat: float  # marker location: lateral midpoint for horizontals, wellhead for verticals
    lon: float
    heel: tuple
    toe: tuple
    lateral_ft: int
    first_month: int  # index into MONTHS; negative for wells online before 2019
    pad: int
    events: list = field(default_factory=list)  # (month index, label)


def _quality(lat, lon):
    q = 0.32
    for slat, slon, s, r in SWEET_SPOTS:
        q += s * np.exp(-((lat - slat) ** 2 + ((lon - slon) * 0.85) ** 2) / (2 * r * r))
    return q


def _gassiness(lat, lon):
    """Gas-oil ratio at first production (scf/bbl) before the formation factor."""
    west = 1 / (1 + np.exp((lon - (-103.5)) / 0.09))
    return 1100 + 4200 * west + 600 * (lat - CENTER[0]) / 0.3


def _operator(lat, lon):
    d = [(lat - a) ** 2 + ((lon - b) * 0.85) ** 2 for a, b, _ in OPERATOR_SEEDS]
    return OPERATORS[OPERATOR_SEEDS[int(np.argmin(d))][2]]


def _in_basin(lat, lon):
    th = radians(25)
    x, y = (lon - CENTER[1]) * 0.85, lat - CENTER[0]
    u, v = x * cos(th) + y * np.sin(th), -x * np.sin(th) + y * cos(th)
    return (u / 0.40) ** 2 + (v / 0.27) ** 2 <= 1


def miles(lat1, lon1, lat2, lon2):
    return np.hypot((lat1 - lat2) / LAT_PER_MILE, (lon1 - lon2) / LON_PER_MILE)


def _build():
    rng = np.random.default_rng(11)
    wells, pads = [], []
    lease_pool = list(LEASES)
    rng.shuffle(lease_pool)

    # Pads, placed by rejection sampling inside the basin, at least 1.3 miles apart
    tries = 0
    while len(pads) < 74 and tries < 20000:
        tries += 1
        lat = CENTER[0] + rng.uniform(-0.32, 0.32)
        lon = CENTER[1] + rng.uniform(-0.48, 0.48)
        if not _in_basin(lat, lon):
            continue
        q = _quality(lat, lon)
        if rng.random() > 0.35 + 0.6 * min(q, 1):  # operators drill the good rock first
            continue
        if any(miles(lat, lon, p[0], p[1]) < 1.3 for p in pads):
            continue
        pads.append((lat, lon, q))

    # Better rock is developed earlier
    order = sorted(range(len(pads)), key=lambda i: -pads[i][2] + rng.normal(0, 0.18))
    pad_month = np.empty(len(pads), dtype=int)
    for rank, i in enumerate(order):
        pad_month[i] = int(np.clip(2 + rank * 1.18 + rng.normal(0, 3), 0, N_MONTHS - 2))

    lease_of_pad, used = {}, set()
    for p, (plat, plon, q) in enumerate(pads):
        lease = lease_pool[p % len(lease_pool)]
        section = int(rng.integers(1, 37))
        while (lease, section) in used:  # keep well names unique
            section = section % 36 + 1
        used.add((lease, section))
        lease_of_pad[p] = lease
        n = int(rng.choice([2, 3, 4, 4, 5, 6]))
        north_south = rng.random() < 0.78
        length_mi = float(rng.choice([1.0, 1.5, 2.0, 2.0, 2.5], p=[0.15, 0.2, 0.3, 0.2, 0.15]))
        west = 1 / (1 + np.exp((plon - (-103.5)) / 0.09))
        bench_w = np.array([0.45 - 0.2 * west, 0.35, 0.2 + 0.2 * west])
        for k in range(n):
            side = 1 if k % 2 == 0 else -1  # two-way pads: half the wells drill each way
            offset = (k // 2 - (n // 2 - 1) / 2) * 0.22
            if north_south:
                heel = (plat, plon + offset * LON_PER_MILE)
                toe = (plat + side * length_mi * LAT_PER_MILE, heel[1])
            else:
                heel = (plat + offset * LAT_PER_MILE, plon)
                toe = (heel[0], plon + side * length_mi * LON_PER_MILE)
            lat_ft = int(round(length_mi * 5280 * rng.uniform(0.94, 1.0), -1))
            formation = FORMATIONS[int(rng.choice(3, p=bench_w / bench_w.sum()))]
            wells.append(Well(
                idx=len(wells), name=f"{lease} {section}-{k + 1}{'H'}",
                api=f"30-0{rng.integers(15, 26)}-{rng.integers(40000, 49999)}",
                lease=lease, operator=_operator(plat, plon), formation=formation,
                well_type="Horizontal",
                lat=(heel[0] + toe[0]) / 2, lon=(heel[1] + toe[1]) / 2,
                heel=heel, toe=toe, lateral_ft=lat_ft,
                first_month=int(min(pad_month[p] + rng.integers(0, 2), N_MONTHS - 1)), pad=p,
            ))

    # Old vertical wells, on production before 2019
    n_vert = 0
    while n_vert < 34:
        lat = CENTER[0] + rng.uniform(-0.3, 0.3)
        lon = CENTER[1] + rng.uniform(-0.46, 0.46)
        if not _in_basin(lat, lon):
            continue
        n_vert += 1
        lease = lease_pool[int(rng.integers(len(lease_pool)))]
        wells.append(Well(
            idx=len(wells), name=f"{lease} State {int(rng.integers(1, 30))}",
            api=f"30-0{rng.integers(15, 26)}-{rng.integers(20000, 29999)}",
            lease=lease, operator=_operator(lat, lon),
            formation=str(rng.choice(["Caprock Sand", "Caprock Sand", "Tascosa Shale"])),
            well_type="Vertical", lat=lat, lon=lon, heel=(lat, lon), toe=(lat, lon),
            lateral_ft=0, first_month=-int(rng.integers(30, 180)), pad=-1,
        ))

    W = len(wells)
    oil = np.zeros((W, N_MONTHS))
    gas = np.zeros((W, N_MONTHS))
    water = np.zeros((W, N_MONTHS))
    status = np.zeros((W, N_MONTHS), dtype=np.int8)
    uptime = np.ones((W, N_MONTHS))
    m_idx = np.arange(N_MONTHS)

    # Offset frac shut-ins: when a pad comes online, producing wells within a mile shut in
    for p, (plat, plon, _) in enumerate(pads):
        m = pad_month[p]
        for w in wells:
            if w.pad != p and w.first_month < m - 1 and miles(w.lat, w.lon, plat, plon) < 1.4:
                uptime[w.idx, m] *= rng.uniform(0.15, 0.45)
                if m + 1 < N_MONTHS:
                    uptime[w.idx, m + 1] *= rng.uniform(0.7, 0.95)
                w.events.append((int(m), f"Shut in for offset frac ({lease_of_pad[p]} pad)"))

    for w in wells:
        i = w.idx
        fp = FORMATION_PARAMS[w.formation]
        q = _quality(w.lat, w.lon) * rng.lognormal(0, 0.22)
        t = (m_idx - w.first_month + 0.5) / 12  # years on production at mid-month
        on = m_idx >= w.first_month
        if w.well_type == "Horizontal":
            qi = fp["qi"] * (w.lateral_ft / 10000) * q
            b, di = fp["b"] * rng.uniform(0.9, 1.1), fp["di"] * rng.uniform(0.85, 1.15)
        else:
            qi = rng.uniform(60, 160) * q
            b, di = 0.6, 0.35
        tt = np.clip(t, 0, None)
        q_oil = qi / (1 + b * di * tt) ** (1 / b)
        ramp = np.ones(N_MONTHS)
        if w.first_month >= 0:
            ramp[w.first_month] = 0.55
            if w.first_month + 1 < N_MONTHS:
                ramp[w.first_month + 1] = 0.9
        gor0 = _gassiness(w.lat, w.lon) * fp["gas"] * rng.lognormal(0, 0.15)
        gor = gor0 * (1 + 0.3 * tt)
        wor = fp["wor"] * rng.lognormal(0, 0.25) * (1 + 0.22 * tt)

        up = uptime[i] * np.clip(rng.normal(0.965, 0.02, N_MONTHS), 0.85, 1)
        # Workovers: a rod part, ESP swap or paraffin job takes a well down for part of a month
        for m in np.flatnonzero((rng.random(N_MONTHS) < 0.012) & on):
            up[m] *= rng.uniform(0.25, 0.6)
            w.events.append((int(m), str(rng.choice(["Rod pump repair", "ESP replaced", "Paraffin cleanout", "Tubing leak repaired"]))))
        # Shut in for a few months mid-history (waiting on workover, low prices in 2020)
        if rng.random() < 0.07:
            s = int(rng.integers(max(w.first_month, 0) + 3, N_MONTHS - 6)) if max(w.first_month, 0) + 3 < N_MONTHS - 6 else None
            if s is not None:
                d = int(rng.integers(2, 5))
                up[s:s + d] = 0
                w.events.append((s, "Shut in, waiting on workover"))
        if w.well_type == "Vertical" and rng.random() < 0.08:
            up[16:19] = 0  # 2020 price curtailment on a few marginal wells
            w.events.append((16, "Curtailed, low oil price"))
        # Shut in at the end of the record
        if w.well_type == "Horizontal" and w.first_month < N_MONTHS - 14 and rng.random() < 0.06:
            s = N_MONTHS - int(rng.integers(1, 5))
            up[s:] = 0
            w.events.append((s, str(rng.choice(["Shut in, casing pressure issue", "Shut in, ESP failed", "Shut in, high water cut"]))))

        o = np.where(on, q_oil * ramp * up, 0)
        oil[i], gas[i], water[i] = o, o * gor / 1000, o * wor
        status[i] = np.where(on, np.where(up > 0, 1, 2), 0)

        # Old verticals: some are plugged and abandoned
        if w.well_type == "Vertical" and rng.random() < 0.3:
            pm = int(rng.integers(8, N_MONTHS - 3))
            oil[i, pm:], gas[i, pm:], water[i, pm:] = 0, 0, 0
            status[i, pm:] = 3
            w.events.append((pm, "Plugged and abandoned"))
        w.events.sort()

    return wells, oil, gas, water, status


WELLS, OIL, GAS, WATER, STATUS = _build()
N_WELLS = len(WELLS)
BOE = OIL + GAS / 6  # 6 Mcf of gas = 1 barrel of oil equivalent

# Static per-well attributes as arrays, for fast filtering
LAT = np.array([w.lat for w in WELLS])
LON = np.array([w.lon for w in WELLS])
OPERATOR = np.array([w.operator for w in WELLS])
FORMATION = np.array([w.formation for w in WELLS])
TYPE = np.array([w.well_type for w in WELLS])
FIRST_MONTH = np.array([w.first_month for w in WELLS])
FIRST_YEAR = np.array([MONTHS[m].year if m >= 0 else 2018 for m in FIRST_MONTH])
LATERAL_FT = np.array([w.lateral_ft for w in WELLS])

# Cumulative volumes to the end of each month: bbl, Mcf
CUM_OIL = np.cumsum(OIL * DAYS_IN, axis=1)
CUM_GAS = np.cumsum(GAS * DAYS_IN, axis=1)
CUM_WATER = np.cumsum(WATER * DAYS_IN, axis=1)

# First-year oil per 1,000 ft of lateral: how good the rock and completion are
Y1_OIL_PER_KFT = np.full(N_WELLS, np.nan)
for _w in WELLS:
    if _w.well_type == "Horizontal" and _w.first_month + 12 <= N_MONTHS:
        _s = slice(_w.first_month, _w.first_month + 12)
        Y1_OIL_PER_KFT[_w.idx] = (OIL[_w.idx, _s] * DAYS_IN[_s]).sum() / (_w.lateral_ft / 1000)


def offsets(i, n=5):
    """The n nearest horizontal wells to well i, with distance in miles."""
    d = miles(LAT[i], LON[i], LAT, LON)
    d[i] = np.inf
    d[TYPE != "Horizontal"] = np.inf
    near = np.argsort(d)[:n]
    return [(int(j), float(d[j])) for j in near]
