"""
Synthetic probe-test data for Northbridge Fab 2, a made-up 300 mm wafer fab, and
the analysis behind the Yield Loss Finder.

Every wafer gets a route (which litho, etch, deposition, CMP and implant tool it ran
on, plus slurry lot, probe card and shift) and a count of failing die per fail bin.
Four problems are planted in the last 60 days:

- ETC-03 chamber B starts leaving residue at the wafer edge (Edge leakage) on Oct 22.
- One slurry drum on CMP-02 scratches wafers (Metal short) for about a week in early October.
- DEP-04 film drifts thick in the center (Via open), getting slowly worse from Oct 19.
- After maintenance on Oct 27, IMP-02 shifts threshold voltage on PM-12 only (Vt shift).

Everything else is random loss. The app does not know about these problems: it
finds them with a commonality analysis (which route step the losing wafers share).
"""

import datetime as dt
from functools import lru_cache

import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

END = dt.date(2026, 11, 3)
DAYS = 60
DATES = pd.to_datetime([END - dt.timedelta(days=DAYS - 1 - i) for i in range(DAYS)])
LOTS_PER_DAY = 12
WAFERS_PER_LOT = 25
TARGET_YIELD = 0.93

PRODUCTS = {  # name: (share of starts, value per good die in $)
    "NX-7": (0.5, 14.0),
    "PM-12": (0.3, 7.5),
    "RF-3": (0.2, 22.0),
}
PRODUCT_NOTE = {"NX-7": "MCU", "PM-12": "Power management", "RF-3": "RF front end"}

# Fail bins in test order, with their typical (healthy) loss rate
BINS = ["Random defects", "Edge leakage", "Metal short", "Via open", "Vt shift", "Other"]
BASE_RATE = np.array([0.026, 0.007, 0.005, 0.009, 0.008, 0.006])
BIN_NOTE = {
    "Random defects": "Particles, killer defects anywhere on the die",
    "Edge leakage": "Gate leakage above limit",
    "Metal short": "Shorts between metal lines",
    "Via open": "Open via chains, high resistance",
    "Vt shift": "Threshold voltage out of spec",
    "Other": "Continuity, functional and other bins",
}

FACTORS = {  # column: label shown in the app
    "product": "Product",
    "litho": "Litho",
    "etch": "Etch tool",
    "chamber": "Etch chamber",
    "dep": "Deposition",
    "cmp": "CMP tool",
    "slurry": "CMP slurry lot",
    "imp": "Implanter",
    "probe": "Probe card",
    "shift": "Lot start shift",
}


# ---------- wafer map geometry ----------

GRID = 24
_c = (np.arange(GRID) + 0.5 - GRID / 2) / (GRID / 2)
MX, MY = np.meshgrid(_c, _c)
MR = np.hypot(MX, MY)
VALID = MR <= 0.96
GROSS_DIE = int(VALID.sum())


def _norm(p):
    p = np.where(VALID, p, np.nan)
    return p / np.nanmean(p)


_arc = np.abs(np.hypot(MX + 0.95, MY + 1.25) - 1.45)
SIGNATURES = {
    "Edge ring": _norm(np.exp((MR - 1) / 0.09)),
    "Arc scratch": _norm(np.exp(-(_arc / 0.06) ** 2) + 0.02),
    "Center cluster": _norm(np.exp(-(MR / 0.32) ** 2)),
    "Mid-radius ring": _norm(np.exp(-((MR - 0.6) / 0.12) ** 2)),
    "Outer zone": _norm(0.3 + MR ** 3),
}
UNIFORM = _norm(np.ones_like(MR))
BIN_PATTERN = [UNIFORM, SIGNATURES["Edge ring"], SIGNATURES["Arc scratch"], SIGNATURES["Center cluster"],
               SIGNATURES["Mid-radius ring"], SIGNATURES["Outer zone"]]
# Healthy loss is mostly uniform with a hint of each bin's usual spot
BASE_PATTERN = [_norm(0.75 * UNIFORM + 0.25 * p) for p in BIN_PATTERN]


# ---------- build the wafers ----------

def _slurry_lots():
    """Each CMP tool runs one slurry drum for 4 to 7 days at a time."""
    lots, n = {}, 2270
    for tool in ["CMP-01", "CMP-02", "CMP-03"]:
        day, seq = 0, []
        while day < DAYS:
            length = int(rng.integers(4, 8))
            seq += [f"SL-{n}"] * length
            n += 1
            day += length
        lots[tool] = seq[:DAYS]
    return lots


def _build():
    slurry = _slurry_lots()
    bad_slurry = slurry["CMP-02"][31]
    prod_names = list(PRODUCTS)
    prod_p = [PRODUCTS[p][0] for p in prod_names]

    rows = []
    lot_no = 41000
    for d in range(DAYS):
        for _ in range(LOTS_PER_DAY):
            lot_no += 1
            etch = f"ETC-0{rng.integers(1, 5)}"
            litho = "LTH-02" if etch == "ETC-03" and rng.random() < 0.55 else f"LTH-0{rng.integers(1, 5)}"
            cmp_tool = f"CMP-0{rng.integers(1, 4)}"
            rows.append(dict(
                lot=f"N{lot_no}", day=d, product=rng.choice(prod_names, p=prod_p), litho=litho, etch=etch,
                dep=f"DEP-0{rng.integers(1, 5)}", cmp=cmp_tool, slurry=slurry[cmp_tool][d],
                imp=f"IMP-0{rng.integers(1, 3)}", probe=f"PC-{rng.integers(11, 17)}",
                shift="Day" if rng.random() < 0.5 else "Night",
                lot_noise=rng.lognormal(0, 0.25, len(BINS)),
            ))
    lots = pd.DataFrame(rows)

    w = lots.loc[lots.index.repeat(WAFERS_PER_LOT)].reset_index(drop=True)
    n = len(w)
    w["slot"] = np.tile(np.arange(1, WAFERS_PER_LOT + 1), len(lots))
    w["chamber"] = w["etch"] + " · " + np.where(w["slot"] % 2, "A", "B")

    base = BASE_RATE * np.stack(w.pop("lot_noise").to_numpy()) * rng.lognormal(0, 0.15, (n, len(BINS)))
    exc = np.zeros((n, len(BINS)))
    noise = rng.lognormal(0, 0.3, n)
    day = w["day"].to_numpy()

    exc[:, 1] = np.where((w["chamber"] == "ETC-03 · B") & (day >= 47), 0.062, 0) * noise
    exc[:, 2] = np.where(w["slurry"] == bad_slurry, 0.048, 0) * noise
    exc[:, 3] = np.where(w["dep"] == "DEP-04", np.clip((day - 44) / 15, 0, 1) * 0.032, 0) * noise
    exc[:, 4] = np.where((w["imp"] == "IMP-02") & (w["product"] == "PM-12") & (day >= 53), 0.055, 0) * noise

    rate = np.clip(base + exc, 0, 0.9)
    fails = rng.binomial(GROSS_DIE, rate)
    w["date"] = DATES[day]
    for c in FACTORS:
        w[c] = w[c].astype("category")
    return w, fails, base, exc


WAFERS, FAILS, BASE, EXC = _build()
N_WAFERS = len(WAFERS)
N_LOTS = WAFERS["lot"].nunique()
DIE_VALUE = WAFERS["product"].map({p: v for p, (_, v) in PRODUCTS.items()}).astype(float).to_numpy()
CODES = {c: WAFERS[c].cat.codes.to_numpy() for c in FACTORS}
LEVELS = {c: list(WAFERS[c].cat.categories) for c in FACTORS}


# ---------- analysis ----------

def window_mask(product, days):
    m = WAFERS["day"].to_numpy() >= DAYS - int(days)
    if product != "All":
        m &= (WAFERS["product"] == product).to_numpy()
    return m


def typical_rate(product):
    """A bin's healthy loss rate: the 20th percentile of its daily loss over the full 60 days."""
    m = window_mask(product, DAYS)
    day = WAFERS["day"].to_numpy()[m]
    tot = np.stack([np.bincount(day, FAILS[m, b], DAYS) for b in range(len(BINS))], 1)
    cnt = np.bincount(day, minlength=DAYS)[:, None] * GROSS_DIE
    with np.errstate(invalid="ignore"):
        return np.nanpercentile(tot / cnt, 20, axis=0)


@lru_cache(maxsize=32)
def summary(product, days):
    m = window_mask(product, days)
    die = m.sum() * GROSS_DIE
    lost = FAILS[m].sum(0)
    typ = typical_rate(product)
    loss = lost / die
    value = (FAILS[m] * DIE_VALUE[m, None]).sum(0)
    excess = np.clip(loss - typ, 0, None)
    excess_value = value * np.divide(excess, loss, out=np.zeros_like(loss), where=loss > 0)
    return dict(
        wafers=int(m.sum()), lots=int(WAFERS.loc[m, "lot"].nunique()), yield_=1 - loss.sum(), loss=loss, typ=typ,
        excess=excess, excess_value=excess_value, value=value,
    )


def parse_suspect(sid):
    """'etch=ETC-03&chamber=ETC-03 · B' -> [('etch', 'ETC-03'), ('chamber', 'ETC-03 · B')]"""
    return [tuple(p.split("=", 1)) for p in sid.split("&")] if sid else []


def suspect_mask(sid):
    m = np.ones(N_WAFERS, bool)
    for col, lvl in parse_suspect(sid):
        m &= CODES[col] == LEVELS[col].index(lvl)
    return m


def suspect_label(sid):
    return " + ".join(lvl for _, lvl in parse_suspect(sid))


def suspect_steps(sid):
    return " + ".join(FACTORS[col] for col, _ in parse_suspect(sid))


LOT_IDX = WAFERS["lot"].astype("category").cat.codes.to_numpy()
LOT_DAY = WAFERS.groupby(LOT_IDX)["day"].first().to_numpy()


def _stats(f, lot, mask_in, n_die_excess):
    """Compare loss on wafers through a step with wafers from other lots, or the other chamber, on the
    same days. Matching by day keeps anything that merely changed at the same time (a new slurry drum,
    a new probe card) from taking the blame. Wafers in one lot move together, so each lot's wafers on
    either side count as one sample."""
    n_in = int(mask_in.sum())
    if n_in < 25 or n_in > len(mask_in) - 25:
        return None
    unit = lot * 2 + mask_in
    k = np.bincount(unit, minlength=2 * N_LOTS)
    rate = np.bincount(unit, f, 2 * N_LOTS) / np.maximum(k, 1) / GROSS_DIE
    sides = []
    for side in (1, 0):
        has = k[side::2] > 0
        r, d = rate[side::2][has], LOT_DAY[has]
        n = np.bincount(d, minlength=DAYS)
        mean = np.bincount(d, r, DAYS) / np.maximum(n, 1)
        sides.append((r, d, n, mean))
    (ri, di, ni, mi), (ro, do, no, mo) = sides
    both = (ni > 0) & (no > 0)
    if both.sum() == 0 or ni[both].sum() < 3:
        return None
    w = np.where(both, ni * no / np.maximum(ni + no, 1), 0)
    est = (w * (mi - mo)).sum() / w.sum()
    res = np.concatenate([(ri - mi[di])[both[di]], (ro - mo[do])[both[do]]])
    dof = max(len(res) - 2 * both.sum(), 1)
    z = est / np.sqrt((res ** 2).sum() / dof / w.sum() + 1e-12)

    rate_in, rate_out = f[mask_in].sum() / (n_in * GROSS_DIE), f[~mask_in].sum() / ((~mask_in).sum() * GROSS_DIE)
    share = float(min(max(rate_in - rate_out, 0) * n_in * GROSS_DIE / n_die_excess, 1))
    return dict(n=n_in, lots=int(len(ri)), rate_in=rate_in, rate_out=rate_out, z=float(z), share=share,
                score=float(max(z, 0) * np.sqrt(share)))


@lru_cache(maxsize=64)
def commonality(product, days, b):
    """Rank route steps by how strongly the wafers that ran through them lose more of bin b."""
    m = window_mask(product, days)
    f, lot = FAILS[m, b].astype(float), LOT_IDX[m]
    typ = summary(product, days)["typ"][b]
    n_die_excess = max(f.sum() - typ * m.sum() * GROSS_DIE, 1)
    out = []
    for col in FACTORS:
        if product != "All" and col == "product":
            continue
        codes = CODES[col][m]
        for i, lvl in enumerate(LEVELS[col]):
            s = _stats(f, lot, codes == i, n_die_excess)
            if s:
                out.append(dict(id=f"{col}={lvl}", **s))
    out.sort(key=lambda s: -s["score"])

    # Some problems need two things at once (a tool and a product): test pairs of the leaders. A pair
    # only counts if it is sharper than either part and still explains most of what they explain.
    lead = [s for s in out[:5] if s["z"] > 2]
    for i, s1 in enumerate(lead):
        for s2 in lead[i + 1:]:
            c1, c2 = s1["id"].split("=")[0], s2["id"].split("=")[0]
            if c1 == c2 or {c1, c2} == {"etch", "chamber"}:
                continue
            sid = f"{s1['id']}&{s2['id']}"
            s = _stats(f, lot, suspect_mask(sid)[m], n_die_excess)
            if (s and s["z"] > 1.2 * max(s1["z"], s2["z"]) and s["share"] >= 0.5
                    and s["share"] >= 0.85 * max(s1["share"], s2["share"])):
                out.append(dict(id=sid, **s))
    out.sort(key=lambda s: -s["score"])

    # A chamber inside its tool says the same thing twice. Keep the chamber when the loss is
    # concentrated there, the whole tool otherwise.
    drop = set()
    for s in out:
        if s["id"].startswith("chamber="):
            tool = next((t for t in out if t["id"] == "etch=" + s["id"].split("=")[1].split(" ")[0]), None)
            if tool:
                drop.add(tool["id"] if s["rate_in"] - tool["rate_out"] > 1.5 * (tool["rate_in"] - tool["rate_out"])
                         else s["id"])
    return [s for s in out if s["id"] not in drop][:6]


def confidence(z):
    if z >= 8:
        return "Strong", "critical"
    if z >= 5:
        return "Likely", "serious"
    if z >= 3:
        return "Possible", "warning"
    return "Weak", "neutral"


def daily(product, days, b, sid):
    """Daily loss rate of bin b for wafers through the suspect and everything else."""
    m = window_mask(product, days)
    s = suspect_mask(sid) if sid else np.zeros(N_WAFERS, bool)
    day = WAFERS["day"].to_numpy()
    res = {}
    for name, mm in [("in", m & s), ("out", m & ~s)]:
        f = np.bincount(day[mm], FAILS[mm, b], DAYS)
        n = np.bincount(day[mm], minlength=DAYS)
        res[name] = np.where(n > 0, f / np.maximum(n, 1) / GROSS_DIE, np.nan)
        res[f"n_{name}"] = n
    first = DAYS - int(days)
    return {k: v[first:] for k, v in res.items()} | {"dates": DATES[first:]}


def onset(series, typ):
    """First day the loss jumps above typical and mostly stays there."""
    s = pd.Series(series).rolling(3, min_periods=1).mean().to_numpy()
    peak = np.nanmax(s) if np.isfinite(s).any() else 0
    if peak < 2 * typ + 0.005:
        return None
    hi = s > typ + 0.5 * (peak - typ)
    for i in range(len(hi)):
        if hi[i] and hi[i:i + 5].mean() >= 0.6:
            return i
    return None


def composite(mask, b, seed):
    """Fail rate at each die position across the masked wafers."""
    n = int(mask.sum())
    if n == 0:
        return np.where(VALID, np.nan, np.nan)
    p = (BASE[mask, b].mean() * BASE_PATTERN[b] + EXC[mask, b].mean() * BIN_PATTERN[b])
    p = np.clip(np.nan_to_num(p), 0, 1)
    g = np.random.default_rng(seed)
    hits = g.binomial(n, p)
    return np.where(VALID, hits / n, np.nan)


def signature(diff_map):
    """Name the spatial pattern that best matches the extra loss on suspect wafers."""
    v = diff_map[VALID]
    if np.nanstd(v) < 1e-4:
        return None, 0
    best, score = None, 0
    for name, tpl in SIGNATURES.items():
        c = np.corrcoef(v, tpl[VALID])[0, 1]
        if c > score:
            best, score = name, c
    return (best, score) if score > 0.45 else (None, score)


def top_lots(product, days, b, sid, n=8):
    m = window_mask(product, days) & (suspect_mask(sid) if sid else True)
    df = WAFERS.loc[m, ["lot", "date", "product"] + [c for c, _ in parse_suspect(sid) if c != "product"]].copy()
    df["bin_fails"] = FAILS[m, b]
    df["all_fails"] = FAILS[m].sum(1)
    g = df.groupby("lot", observed=True).agg(
        date=("date", "first"), product=("product", "first"), wafers=("bin_fails", "size"),
        bin_fails=("bin_fails", "sum"), all_fails=("all_fails", "sum"))
    g["bin_rate"] = g["bin_fails"] / (g["wafers"] * GROSS_DIE)
    g["lot_yield"] = 1 - g["all_fails"] / (g["wafers"] * GROSS_DIE)
    return g.sort_values("bin_rate", ascending=False).head(n).reset_index()


# ---------- views for the demo panels ----------

PATH = ["litho", "chamber", "dep", "cmp", "imp"]  # route order shown in the line-flow chart


@lru_cache(maxsize=64)
def flow(product, days, b):
    """Wafer counts and bin-b loss between consecutive route steps, for a Sankey of the line."""
    m = window_mask(product, days)
    f = FAILS[m, b].astype(float)
    nodes, offset = [], {}
    for col in PATH:
        offset[col] = len(nodes)
        nodes += [(col, lvl) for lvl in LEVELS[col]]
    node_n = np.zeros(len(nodes))
    node_f = np.zeros(len(nodes))
    for col in PATH:
        k = len(LEVELS[col])
        codes = CODES[col][m]
        node_n[offset[col]:offset[col] + k] = np.bincount(codes, minlength=k)
        node_f[offset[col]:offset[col] + k] = np.bincount(codes, f, k)
    links = []
    for c1, c2 in zip(PATH, PATH[1:]):
        k1, k2 = len(LEVELS[c1]), len(LEVELS[c2])
        pair = CODES[c1][m] * k2 + CODES[c2][m]
        n = np.bincount(pair, minlength=k1 * k2)
        fl = np.bincount(pair, f, k1 * k2)
        for p in np.flatnonzero(n):
            links.append((offset[c1] + p // k2, offset[c2] + p % k2, int(n[p]), fl[p] / (n[p] * GROSS_DIE)))
    node_rate = node_f / np.maximum(node_n, 1) / GROSS_DIE
    return nodes, node_rate, links


def lot_wafers(lot):
    return np.flatnonzero((WAFERS["lot"] == lot).to_numpy())


def die_map(i):
    """One wafer's probe map: -1 off the wafer, 0 a good die, b + 1 a die failing bin b.
    The wafer's fail counts are real; where they land follows its bins' spatial patterns."""
    g = np.random.default_rng(int(i))
    cells = np.flatnonzero(VALID.ravel())
    out = np.full(GRID * GRID, -1)
    out[cells] = 0
    free = np.ones(len(cells), bool)
    for b in np.argsort(-EXC[i]):  # place the excursion first so it keeps its shape
        k = int(min(FAILS[i, b], free.sum()))
        if k == 0:
            continue
        p = np.nan_to_num(BASE[i, b] * BASE_PATTERN[b] + EXC[i, b] * BIN_PATTERN[b]).ravel()[cells] * free
        pick = g.choice(len(cells), k, replace=False, p=p / p.sum())
        out[cells[pick]] = b + 1
        free[pick] = False
    return out.reshape(GRID, GRID)
