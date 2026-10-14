"""
Generate synthetic Western Australia mineral exploration drillhole data.
Modeled on the Kaggle "mineral-exploration-drillholes-western-australia" structure.
Au-Cu porphyry prospect, ~50 holes in a 7x7 grid pattern.
Run once: python data_generator.py
"""

import numpy as np
import pandas as pd
import pathlib

DATA_PATH = pathlib.Path(__file__).parent / "data"
DATA_PATH.mkdir(exist_ok=True)

rng = np.random.default_rng(42)

EAST_ORIGIN = 350000.0
NORTH_ORIGIN = 7200000.0
SPACING = 100.0
N_HOLES = 50

# --- COLLAR ---

hole_ids = [f"DH{i:03d}" for i in range(1, N_HOLES + 1)]

cols = 7
east_base = [EAST_ORIGIN + (i % cols) * SPACING for i in range(N_HOLES)]
north_base = [NORTH_ORIGIN + (i // cols) * SPACING for i in range(N_HOLES)]

collar = pd.DataFrame({
    "HOLEID":   hole_ids,
    "EAST":     np.round(np.array(east_base) + rng.uniform(-15, 15, N_HOLES), 1),
    "NORTH":    np.round(np.array(north_base) + rng.uniform(-15, 15, N_HOLES), 1),
    "ELEV":     np.round(400 + rng.uniform(-10, 10, N_HOLES), 1),
    "TOTDEPTH": np.round(rng.uniform(150, 450, N_HOLES), 0),
    "AZ":       np.round(rng.uniform(0, 360, N_HOLES), 1),
    "DIP":      np.round(rng.uniform(-90, -60, N_HOLES), 1),
})

collar.to_csv(DATA_PATH / "collar.csv", index=False)
print(f"collar.csv: {len(collar)} holes")

# --- SURVEY ---

survey_rows = []
for _, hole in collar.iterrows():
    depths = np.arange(0, hole["TOTDEPTH"] + 30, 30)
    for d in depths:
        d = min(d, hole["TOTDEPTH"])
        survey_rows.append({
            "HOLEID": hole["HOLEID"],
            "DEPTH":  round(float(d), 1),
            "AZ":     round(float(hole["AZ"]) + float(rng.uniform(-5, 5)), 1),
            "DIP":    round(float(hole["DIP"]) + float(rng.uniform(-3, 3)), 1),
        })

survey = pd.DataFrame(survey_rows).drop_duplicates(["HOLEID", "DEPTH"])
survey.to_csv(DATA_PATH / "survey.csv", index=False)
print(f"survey.csv: {len(survey)} stations")

# --- LITHOLOGY ---

LITH_SEQUENCE = [
    ("Alluvium",             0,    20),
    ("Weathered Granite",   20,    60),
    ("Granite",             60,   120),
    ("Quartz Diorite",     120,   180),
    ("Mineralized Porphyry",180,  280),
    ("Fresh Granite",      280,  9999),
]

lith_rows = []
for _, hole in collar.iterrows():
    depth = 0.0
    for lith, base_from, base_to in LITH_SEQUENCE:
        jitter = float(rng.uniform(-15, 15))
        actual_from = round(depth, 1)
        actual_to = round(min(float(hole["TOTDEPTH"]), base_to + jitter), 1)
        if actual_from >= float(hole["TOTDEPTH"]):
            break
        actual_to = max(actual_to, actual_from + 2.0)
        actual_to = min(actual_to, float(hole["TOTDEPTH"]))
        lith_rows.append({
            "HOLEID":    hole["HOLEID"],
            "FROM":      actual_from,
            "TO":        actual_to,
            "LITHOLOGY": lith,
        })
        depth = actual_to
        if depth >= float(hole["TOTDEPTH"]):
            break

lith = pd.DataFrame(lith_rows)
lith.to_csv(DATA_PATH / "lith.csv", index=False)
print(f"lith.csv: {len(lith)} intervals")

# --- ASSAY (2m composites) ---

assay_rows = []
for _, hole in collar.iterrows():
    depth = 0.0
    tot = float(hole["TOTDEPTH"])
    while depth < tot:
        to = min(depth + 2.0, tot)
        mid = (depth + to) / 2.0
        in_zone = 80 <= mid <= 250

        if in_zone:
            au = float(max(0, rng.lognormal(mean=0.8, sigma=1.2)))
            cu = float(max(0, rng.lognormal(mean=-1.5, sigma=0.8)))
            ag = au * float(rng.uniform(1.5, 3.0))
        else:
            au = float(max(0, rng.lognormal(mean=-2.5, sigma=0.6)))
            cu = float(max(0, rng.lognormal(mean=-4.0, sigma=0.5)))
            ag = au * float(rng.uniform(0.5, 1.5))

        assay_rows.append({
            "HOLEID": hole["HOLEID"],
            "FROM":   round(depth, 1),
            "TO":     round(to, 1),
            "Au_ppm": round(au, 3),
            "Cu_pct": round(cu, 4),
            "Ag_ppm": round(ag, 3),
        })
        depth = to

assay = pd.DataFrame(assay_rows)
assay.to_csv(DATA_PATH / "assay.csv", index=False)
print(f"assay.csv: {len(assay)} intervals")
print("Done — all CSVs written to data/")
