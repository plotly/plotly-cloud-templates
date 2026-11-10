"""
Synthetic high-throughput screening campaign and the plate QC metrics computed from it.

A primary screen of 23,040 compounds against a made-up kinase, ZK7, in a TR-FRET
assay on 384-well plates. Each plate has neutral controls (DMSO, full signal) in
columns 1–2, a reference inhibitor (no signal) in columns 23–24, and 320 compounds
in columns 3–22. Six runs of 12 plates were read over three weeks.

The generator plants the faults a screening lab actually sees, so the QC has
something to find:

- Evaporation at the edges of the last plates in a stack (run 2, run 6)
- A clogged reagent dispenser nozzle that under-fills row K (run 3, Multidrop-2)
- A new detection reagent lot with a smaller signal window (runs 4–6)
- A reference inhibitor that wasn't dispensed into half of column 24 (one plate)
- Signal decay through a long run as plates wait at room temperature (run 5)

None of the QC below knows about these: every flag is computed from the well
values the way it would be for real data.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

SEED = 7
N_ROWS, N_COLS = 16, 24
ROWS = list("ABCDEFGHIJKLMNOP")
HIGH_COLS = [0, 1]  # neutral control, DMSO
LOW_COLS = [22, 23]  # reference inhibitor, 1 µM staurosporine
CMPD_COLS = list(range(2, 22))
PLATES_PER_RUN = 12
N_RUNS = 6

ASSAY = "ZK7 kinase TR-FRET"
CAMPAIGN = "ZK7 primary screen"
COMPOUND_CONC = "10 µM"

# QC rules, the same ones written in the screening SOP
Z_FAIL = 0.4  # below this the plate can't separate actives from noise
Z_REVIEW = 0.5
CV_REVIEW = 0.10  # neutral control CV
EDGE_REVIEW = 0.06  # outer ring of compound wells off the interior median by more than this
LINE_REVIEW = 20  # a row or column whose median % inhibition is this far from 0
HIT_RATE_REVIEW = 0.02
HIT_THRESHOLD = 50  # % inhibition
CTRL_OUTLIER_Z = 4  # robust z of a control well against its own group

LOTS = {"24-118": (9400, 1350), "24-131": (8100, 1550)}  # high and low control means


@dataclass
class Plate:
    plate_id: str
    run: int
    seq: int  # position in run order
    order_in_run: int
    read_at: datetime
    reader: str
    dispenser: str
    lot: str
    raw: np.ndarray  # 16 × 24 TR-FRET ratio × 10,000
    compounds: np.ndarray  # 16 × 24 compound IDs, "" for control wells
    pct: np.ndarray = None  # % inhibition
    bscore: np.ndarray = None
    stats: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)  # (severity, short label, detail)
    status: str = "Pass"
    hits: list = field(default_factory=list)
    activity: np.ndarray = None  # true fraction of signal each compound removes, kept so a re-read repeats it
    rerun: bool = False


def well_name(r, c):
    return f"{ROWS[r]}{c + 1:02d}"


def _ring(n_rows=N_ROWS, n_cols=N_COLS):
    """Distance of each well from the nearest plate edge, 0 for the outer ring."""
    r = np.arange(n_rows)[:, None]
    c = np.arange(n_cols)[None, :]
    return np.minimum(np.minimum(r, n_rows - 1 - r), np.minimum(c, n_cols - 1 - c))


RING = _ring()
CMPD_MASK = np.zeros((N_ROWS, N_COLS), bool)
CMPD_MASK[:, CMPD_COLS] = True
# Compound wells on the outer ring of the compound area (rows A and P, columns 3 and 22)
EDGE_MASK = CMPD_MASK & (_ring() == 0) | CMPD_MASK & np.isin(np.arange(N_COLS), [2, 21])[None, :]
INNER_MASK = CMPD_MASK & ~EDGE_MASK


def _robust_sd(x):
    return 1.4826 * np.median(np.abs(x - np.median(x)))


def _median_polish(m, iters=10):
    """Tukey median polish, returns the residual matrix."""
    res = m.copy()
    for _ in range(iters):
        res -= np.median(res, axis=1, keepdims=True)
        res -= np.median(res, axis=0, keepdims=True)
    return res


def build_campaign():
    rng = np.random.default_rng(SEED)
    start = datetime(2026, 10, 12, 8, 30)
    run_days = [0, 2, 5, 8, 12, 16]
    plates = []
    cmpd_counter = 400_000
    for run in range(1, N_RUNS + 1):
        lot = "24-118" if run <= 3 else "24-131"
        hi_mu, lo_mu = LOTS[lot]
        reader = "EnVision-1" if run % 2 else "EnVision-2"
        for k in range(PLATES_PER_RUN):
            seq = (run - 1) * PLATES_PER_RUN + k
            dispenser = "Multidrop-2" if (run == 3 and k % 2 == 1) else "Multidrop-1"
            read_at = start + timedelta(days=run_days[run - 1], minutes=14 * k + int(rng.integers(0, 5)))

            hi, lo = hi_mu * rng.normal(1, 0.015), lo_mu * rng.normal(1, 0.02)
            hi_cv, lo_cv = 0.04, 0.07
            if run == 5:  # signal decays as later plates sit waiting for the reader
                hi *= 1 - 0.038 * k
                hi_cv += 0.0075 * k
            if run in (2, 5):
                hi_cv += 0.005

            # Inactive compounds scatter around the neutral control; a few are real inhibitors
            base = rng.normal(hi, hi * hi_cv, (N_ROWS, N_COLS))
            frac = np.zeros((N_ROWS, N_COLS))  # fraction of signal removed
            active = rng.random((N_ROWS, N_COLS)) < 0.006
            frac[active] = rng.beta(2.2, 1.4, active.sum())
            weak = rng.random((N_ROWS, N_COLS)) < 0.02
            frac[weak & ~active] = rng.uniform(0.15, 0.4, (weak & ~active).sum())
            quench = rng.random((N_ROWS, N_COLS)) < 0.002  # fluorescent compounds read high
            frac[quench] = -rng.uniform(0.3, 0.6, quench.sum())
            frac[~CMPD_MASK] = 0
            raw = base - frac * (hi - lo)
            raw[:, LOW_COLS] = rng.normal(lo, lo * lo_cv, (N_ROWS, len(LOW_COLS)))

            # Faults
            if (run == 2 and k >= 9) or (run == 6 and k == 11):
                bump = {0: 1.13 + 0.02 * (k - 9 if run == 2 else 1), 1: 1.04}
                for ring, f in bump.items():
                    raw[RING == ring] *= f
            if dispenser == "Multidrop-2" and k in (3, 5, 7, 9):
                raw[10, :] *= 0.5 + 0.03 * k / 3
            if run == 4 and k == 6:
                raw[8:, 23] = rng.normal(hi, hi * hi_cv, 8)

            raw = np.clip(raw, 200, None)
            compounds = np.full((N_ROWS, N_COLS), "", dtype=object)
            for c in CMPD_COLS:
                for r in range(N_ROWS):
                    cmpd_counter += int(rng.integers(1, 9))
                    compounds[r, c] = f"HB-{cmpd_counter}"
            plates.append(Plate(
                plate_id=f"ZK7-{run}{k + 1:02d}", run=run, seq=seq, order_in_run=k + 1, read_at=read_at,
                reader=reader, dispenser=dispenser, lot=lot, raw=raw, compounds=compounds, activity=frac,
            ))
    for p in plates:
        qc(p)
    return plates


def qc(p):
    hi_w = p.raw[:, HIGH_COLS].ravel()
    lo_w = p.raw[:, LOW_COLS].ravel()
    mh, ml = hi_w.mean(), lo_w.mean()
    sh, sl = hi_w.std(ddof=1), lo_w.std(ddof=1)
    z = 1 - 3 * (sh + sl) / abs(mh - ml)
    rz = 1 - 3 * (_robust_sd(hi_w) + _robust_sd(lo_w)) / abs(np.median(hi_w) - np.median(lo_w))

    # Normalise to the controls on this plate, using medians so one bad control well can't move every value
    p.pct = 100 * (np.median(hi_w) - p.raw) / (np.median(hi_w) - np.median(lo_w))
    cm = p.pct[:, CMPD_COLS]
    resid = _median_polish(cm)
    b = np.full((N_ROWS, N_COLS), np.nan)
    b[:, CMPD_COLS] = resid / _robust_sd(resid)
    p.bscore = b

    # Control wells far from their own group, e.g. inhibitor not dispensed
    hi_out = np.abs(hi_w - np.median(hi_w)) / _robust_sd(hi_w) > CTRL_OUTLIER_Z
    lo_out = np.abs(lo_w - np.median(lo_w)) / _robust_sd(lo_w) > CTRL_OUTLIER_Z

    edge = np.median(p.raw[EDGE_MASK]) / np.median(p.raw[INNER_MASK]) - 1
    row_med = np.median(cm, axis=1)
    col_med = np.median(cm, axis=0)
    worst_row = int(np.argmax(np.abs(row_med)))
    worst_col = int(np.argmax(np.abs(col_med)))

    hit_mask = CMPD_MASK & (p.pct >= HIT_THRESHOLD)
    n_hits = int(hit_mask.sum())
    hit_rate = n_hits / CMPD_MASK.sum()

    p.stats = {
        "z": z, "robust_z": rz, "sb": mh / ml, "hi_mean": mh, "lo_mean": ml, "hi_sd": sh, "lo_sd": sl,
        "hi_cv": sh / mh, "lo_cv": sl / ml, "edge": edge, "row_med": row_med, "col_med": col_med,
        "worst_row": worst_row, "worst_col": CMPD_COLS[worst_col], "n_hits": n_hits, "hit_rate": hit_rate,
        "ctrl_outliers": int(hi_out.sum() + lo_out.sum()),
    }

    flags = []
    if z < Z_FAIL:
        flags.append(("fail", f"Z′ {z:.2f}", f"Z′ {z:.2f} is below the {Z_FAIL} limit for this assay."))
    elif z < Z_REVIEW:
        flags.append(("review", f"Z′ {z:.2f}", f"Z′ {z:.2f} is in the review band ({Z_FAIL}–{Z_REVIEW})."))
    if lo_out.sum() + hi_out.sum() >= 2:
        parts = []
        if lo_out.sum():
            parts.append(f"{int(lo_out.sum())} reference-inhibitor wells read like neutral controls")
        if hi_out.sum():
            parts.append(f"{int(hi_out.sum())} neutral control wells sit far from the rest")
        flags.append(("review", "Control outliers",
                      "; ".join(parts).capitalize() + f". Robust Z′, which shrugs them off, is {rz:.2f}."))
    if p.stats["hi_cv"] > CV_REVIEW:
        flags.append(("review", f"CV {p.stats['hi_cv']:.0%}",
                      f"Neutral control CV is {p.stats['hi_cv']:.1%}, above {CV_REVIEW:.0%}."))
    if abs(edge) > EDGE_REVIEW:
        flags.append(("review", "Edge effect",
                      f"Outer compound wells read {edge:+.0%} against the interior. Typical of evaporation in "
                      "plates that sat longest in the stacker."))
    if abs(row_med[worst_row]) > LINE_REVIEW:
        in_row = int(hit_mask[worst_row].sum())
        flags.append(("review", f"Row {ROWS[worst_row]} stripe",
                      f"Row {ROWS[worst_row]} has a median of {row_med[worst_row]:+.0f}% inhibition and holds "
                      f"{in_row} of {n_hits} hits. Points to a dispenser nozzle, not chemistry."))
    if abs(col_med[worst_col]) > LINE_REVIEW:
        flags.append(("review", f"Column {CMPD_COLS[worst_col] + 1} stripe",
                      f"Column {CMPD_COLS[worst_col] + 1} median is {col_med[worst_col]:+.0f}% inhibition."))
    if hit_rate > HIT_RATE_REVIEW:
        flags.append(("review", f"Hit rate {hit_rate:.1%}",
                      f"{n_hits} hits ({hit_rate:.1%}) against an expected rate under {HIT_RATE_REVIEW:.0%}."))
    p.flags = flags
    p.status = "Fail" if any(s == "fail" for s, *_ in flags) else "Review" if flags else "Pass"

    suspect_row = worst_row if abs(row_med[worst_row]) > LINE_REVIEW else None
    hits = []
    for r, c in zip(*np.nonzero(hit_mask)):
        note = ""
        if r == suspect_row:
            note = f"In row {ROWS[r]} stripe"
        elif EDGE_MASK[r, c] and abs(edge) > EDGE_REVIEW:
            note = "Edge well"
        hits.append({"well": well_name(r, c), "compound": p.compounds[r, c], "pct": float(p.pct[r, c]),
                     "bscore": float(p.bscore[r, c]), "note": note})
    p.hits = sorted(hits, key=lambda h: -h["pct"])


def reread(p):
    """The same compounds dispensed and read again with the fault fixed: the chemistry repeats, the noise doesn't."""
    rng = np.random.default_rng(SEED * 1000 + p.seq)
    hi_mu, lo_mu = LOTS[p.lot]
    hi, lo = hi_mu * rng.normal(1, 0.015), lo_mu * rng.normal(1, 0.02)
    raw = rng.normal(hi, hi * 0.04, (N_ROWS, N_COLS)) - p.activity * (hi - lo)
    raw[:, LOW_COLS] = rng.normal(lo, lo * 0.07, (N_ROWS, len(LOW_COLS)))
    q = Plate(
        plate_id=p.plate_id, run=p.run, seq=p.seq, order_in_run=p.order_in_run, read_at=p.read_at,
        reader=p.reader, dispenser="Multidrop-1", lot=p.lot, raw=np.clip(raw, 200, None), compounds=p.compounds,
        activity=p.activity, rerun=True,
    )
    qc(q)
    return q


PLATES = build_campaign()
BY_ID = {p.plate_id: p for p in PLATES}
# What each flagged plate looks like when the lab re-runs it, built up front so the server holds no state
REREADS = {p.plate_id: reread(p) for p in PLATES if p.status != "Pass"}
RUN_DATES = {r: min(p.read_at for p in PLATES if p.run == r).date() for r in range(1, N_RUNS + 1)}
LOT_CHANGE_SEQ = next(p.seq for p in PLATES if p.lot != PLATES[0].lot)
AS_OF = max(p.read_at for p in PLATES)

# Earlier runs were already reviewed by the screening lead, with these decisions
REVIEWER = "M. Okafor"
INITIAL_DECISIONS = {}
for p in PLATES:
    if p.status == "Pass":
        INITIAL_DECISIONS[p.plate_id] = {"decision": "Accepted", "by": "Auto QC", "note": "All QC rules passed"}
    elif p.run <= 2:
        INITIAL_DECISIONS[p.plate_id] = {
            "decision": "Accepted" if p.status == "Review" else "Re-run",
            "by": REVIEWER,
            "note": "Edge wells masked from hit calling" if any(f[1] == "Edge effect" for f in p.flags) else "",
        }
