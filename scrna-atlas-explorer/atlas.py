"""
Synthetic single-cell RNA-seq atlas of melanoma tumor biopsies.

Eight made-up patients on anti-PD-1 therapy, four responders and four
non-responders, each biopsied before treatment and three weeks in: 16 samples,
about 14,000 cells and 160 genes. Everything is generated at import from a fixed
seed, so every gunicorn worker builds the same atlas.

What the generator puts in, so the app has something to find:

- Responders start with more TCF7+ memory CD8 T cells, and on treatment gain
  effector and proliferating T cells, cDC1s and an interferon response
  (CXCL9, CXCL10, STAT1) in macrophages and tumor cells, while tumor shrinks
- Non-responders accumulate exhausted CD8 T cells, Tregs, SPP1+ macrophages and
  an AXL-high, MHC-low tumor state
- CD8 T cells sit on one continuous path from memory to exhausted, with
  pseudotime known for every cell
- About 5% of cells are low quality (few genes, high mitochondrial reads), and
  one sample, P06 on treatment, is much worse than the rest

Expression is drawn from a Poisson-gamma model per cell and log-normalized the
usual way: log1p(counts / library size * 10,000).
"""

import math
from dataclasses import dataclass

import numpy as np

SEED = 20261104
rng = np.random.default_rng(SEED)

PATIENTS = [f"P{i:02d}" for i in range(1, 9)]
RESPONSE = {p: ("Responder" if i < 4 else "Non-responder") for i, p in enumerate(PATIENTS)}
TIMEPOINTS = ["Pre", "On"]
RESPONSES = ["Responder", "Non-responder"]
SAMPLES = [f"{p}-{t}" for p in PATIENTS for t in TIMEPOINTS]

# ---------------------------------------------------------------- genes

GENE_SETS = {
    "T cell": ["CD3D", "CD3E", "CD2", "TRAC"],
    "CD4": ["CD4", "IL7R", "CCR7", "SELL", "LEF1"],
    "Treg": ["FOXP3", "IL2RA", "CTLA4", "TNFRSF4", "IKZF2"],
    "CD8": ["CD8A", "CD8B", "TCF7", "GZMK", "GZMA", "GZMB", "PRF1", "NKG7", "GNLY", "IFNG", "CCL5", "CX3CR1"],
    "Exhaustion": ["PDCD1", "HAVCR2", "LAG3", "TIGIT", "TOX", "CXCL13", "ENTPD1", "LAYN"],
    "Cycling": ["MKI67", "TOP2A", "STMN1", "TUBB", "CENPF"],
    "NK": ["KLRD1", "KLRF1", "NCAM1", "FCGR3A", "TYROBP"],
    "B cell": ["MS4A1", "CD79A", "CD79B", "CD19", "BANK1", "IGHM"],
    "Plasma": ["JCHAIN", "MZB1", "IGHG1", "XBP1", "SDC1"],
    "Monocyte": ["CD14", "LYZ", "S100A8", "S100A9", "VCAN", "FCN1"],
    "Macrophage": ["C1QA", "C1QB", "C1QC", "APOE", "CD68", "CD163", "MRC1"],
    "SPP1 TAM": ["SPP1", "TREM2", "GPNMB", "APOC1", "FN1"],
    "cDC1": ["CLEC9A", "XCR1", "BATF3", "IDO1"],
    "pDC": ["LILRA4", "IL3RA", "CLEC4C", "IRF7"],
    "Fibroblast": ["COL1A1", "COL1A2", "DCN", "LUM", "PDGFRB", "ACTA2", "FAP"],
    "Endothelial": ["PECAM1", "VWF", "CDH5", "PLVAP", "KDR"],
    "Melanoma": ["PMEL", "MLANA", "TYR", "MITF", "DCT", "SOX10", "S100B"],
    "Resistance": ["AXL", "NGFR", "WNT5A", "TGFBI"],
    "Interferon": ["ISG15", "IFI6", "MX1", "STAT1", "CXCL9", "CXCL10", "GBP1"],
    "Antigen presentation": ["HLA-DRA", "HLA-DRB1", "CD74", "HLA-A", "HLA-B", "B2M"],
    "Housekeeping": ["ACTB", "GAPDH", "MALAT1", "TMSB4X", "EEF1A1", "FTL", "RPL13", "RPS27", "RPLP0"],
    "Stress": ["HSPA1A", "FOS", "JUN", "DUSP1"],
    "Mitochondrial": ["MT-CO1", "MT-ND1", "MT-CYB", "MT-ATP6", "MT-CO3"],
}
GENES = [g for genes in GENE_SETS.values() for g in genes]
GENE_INDEX = {g: i for i, g in enumerate(GENES)}
GENE_SET_OF = {g: s for s, genes in GENE_SETS.items() for g in genes}
MITO = np.array([g.startswith("MT-") for g in GENES])

# ---------------------------------------------------------------- cell types


@dataclass(frozen=True)
class CellType:
    name: str
    compartment: str
    share: float  # baseline share of cells in a pre-treatment biopsy
    center: tuple  # UMAP location
    spread: tuple  # UMAP x/y standard deviation
    markers: dict  # gene -> expected UMIs per 10k
    log_lib: float  # mean log library size


def _m(**kw):
    return {k.replace("_", "-"): v for k, v in kw.items()}


T_BASE = _m(CD3D=60, CD3E=40, CD2=30, TRAC=35, CCL5=6, B2M=220, HLA_A=40, HLA_B=50)
MYELOID_BASE = _m(TYROBP=60, LYZ=40, CD74=120, HLA_DRA=90, HLA_DRB1=50, FTL=150, B2M=180, HLA_A=40, HLA_B=50)

CELL_TYPES = [
    CellType("CD4 naive/memory", "CD4 T", 0.09, (1.0, 8.5), (1.3, 1.0),
             T_BASE | _m(CD4=18, IL7R=40, CCR7=20, SELL=18, LEF1=15, TCF7=14), 8.0),
    CellType("Treg", "CD4 T", 0.05, (4.2, 7.2), (0.9, 0.9),
             T_BASE | _m(CD4=15, FOXP3=20, IL2RA=22, CTLA4=30, TNFRSF4=20, IKZF2=10, TIGIT=14), 8.1),
    CellType("CD8 TCF7+ memory", "CD8 T", 0.06, (-1.5, 5.0), (0.8, 0.8), T_BASE, 8.0),
    CellType("CD8 effector", "CD8 T", 0.08, (-5.0, 3.0), (0.8, 0.8), T_BASE, 8.2),
    CellType("CD8 exhausted", "CD8 T", 0.08, (-8.0, -1.5), (0.8, 0.8), T_BASE, 8.3),
    CellType("Proliferating T", "CD8 T", 0.02, (-10.5, -5.0), (0.9, 0.9),
             T_BASE | _m(CD8A=20, CD8B=12, MKI67=25, TOP2A=30, STMN1=40, TUBB=40, CENPF=15, GZMB=10, PDCD1=6), 8.6),
    CellType("NK", "NK", 0.04, (-6.0, 7.5), (1.0, 0.9),
             _m(KLRD1=40, KLRF1=25, NCAM1=10, FCGR3A=30, TYROBP=60, NKG7=80, GNLY=120, GZMB=40, PRF1=30,
                GZMA=25, CCL5=40, CX3CR1=10, B2M=200, HLA_A=40, HLA_B=50), 8.0),
    CellType("B cells", "B lineage", 0.05, (7.5, 12.0), (1.0, 0.9),
             _m(MS4A1=40, CD79A=50, CD79B=30, CD19=12, BANK1=15, IGHM=60, CD74=180, HLA_DRA=100,
                HLA_DRB1=60, B2M=200, HLA_A=40, HLA_B=50), 8.1),
    CellType("Plasma cells", "B lineage", 0.02, (10.8, 14.0), (0.7, 0.6),
             _m(JCHAIN=120, MZB1=80, IGHG1=400, XBP1=40, SDC1=10, CD79A=15, B2M=150, HLA_A=40, HLA_B=50), 8.9),
    CellType("Classical monocytes", "Myeloid", 0.04, (6.0, 1.0), (1.0, 0.9),
             MYELOID_BASE | _m(CD14=40, LYZ=200, S100A8=150, S100A9=200, VCAN=30, FCN1=40, CD68=15), 8.5),
    CellType("TAM C1QC+", "Myeloid", 0.07, (9.0, -2.5), (1.1, 1.0),
             MYELOID_BASE | _m(C1QA=120, C1QB=120, C1QC=90, APOE=150, CD68=40, CD163=30, MRC1=25,
                               APOC1=40), 8.8),
    CellType("TAM SPP1+", "Myeloid", 0.04, (12.0, -0.5), (0.9, 0.9),
             MYELOID_BASE | _m(SPP1=180, TREM2=40, GPNMB=60, APOC1=80, FN1=40, CD68=45, APOE=60, C1QA=20), 8.9),
    CellType("cDC1", "Myeloid", 0.01, (5.0, -4.5), (0.6, 0.6),
             MYELOID_BASE | _m(CLEC9A=25, XCR1=15, BATF3=10, IDO1=30, CD74=200, HLA_DRA=150), 8.4),
    CellType("pDC", "Myeloid", 0.01, (12.8, 5.0), (0.6, 0.6),
             _m(LILRA4=30, IL3RA=20, CLEC4C=15, IRF7=25, CD74=140, HLA_DRA=60, JCHAIN=20, B2M=150), 8.2),
    CellType("CAFs", "Stromal", 0.05, (-1.0, -10.0), (1.2, 0.9),
             _m(COL1A1=250, COL1A2=200, DCN=120, LUM=100, PDGFRB=20, ACTA2=40, FAP=15, TGFBI=20, FN1=50,
                B2M=80, HLA_A=20, HLA_B=25), 9.0),
    CellType("Endothelial", "Stromal", 0.03, (3.0, -11.5), (0.9, 0.7),
             _m(PECAM1=40, VWF=80, CDH5=20, PLVAP=60, KDR=15, B2M=90, HLA_A=20, HLA_B=30, HLA_DRA=20), 8.8),
    CellType("Melanoma MITF-high", "Tumor", 0.20, (12.0, -9.0), (1.5, 1.2),
             _m(PMEL=150, MLANA=120, TYR=40, MITF=20, DCT=30, SOX10=25, S100B=50, B2M=100, HLA_A=40,
                HLA_B=40), 9.2),
    CellType("Melanoma AXL-high", "Tumor", 0.04, (15.0, -12.5), (1.0, 1.0),
             _m(AXL=30, NGFR=15, WNT5A=12, TGFBI=40, SOX10=10, S100B=30, PMEL=15, MLANA=10, FN1=30,
                B2M=25, HLA_A=8, HLA_B=10), 9.3),
]
LOW_QUALITY = "Low quality"
CELL_TYPE_NAMES = [c.name for c in CELL_TYPES] + [LOW_QUALITY]
COMPARTMENTS = ["CD4 T", "CD8 T", "NK", "B lineage", "Myeloid", "Stromal", "Tumor", LOW_QUALITY]
CD8_LINEAGE = ["CD8 TCF7+ memory", "CD8 effector", "CD8 exhausted"]
CD8_PT_RANGE = {"CD8 TCF7+ memory": (0.0, 0.3), "CD8 effector": (0.3, 0.62), "CD8 exhausted": (0.62, 1.0)}

# Fold change in cell-type share by response and timepoint, before patient noise
ABUNDANCE_SHIFT = {
    ("Responder", "Pre"): {"CD8 TCF7+ memory": 1.7, "cDC1": 1.4, "CD8 exhausted": 0.8},
    ("Responder", "On"): {"CD8 TCF7+ memory": 1.5, "CD8 effector": 2.2, "Proliferating T": 3.0,
                          "CD8 exhausted": 1.1, "cDC1": 2.0, "NK": 1.4, "Melanoma MITF-high": 0.35,
                          "Melanoma AXL-high": 0.5, "TAM SPP1+": 0.7, "B cells": 1.6},
    ("Non-responder", "Pre"): {"CD8 TCF7+ memory": 0.6, "Treg": 1.2, "TAM SPP1+": 1.3},
    ("Non-responder", "On"): {"CD8 TCF7+ memory": 0.5, "CD8 exhausted": 1.8, "Treg": 1.6, "TAM SPP1+": 2.0,
                              "Melanoma AXL-high": 2.4, "cDC1": 0.6},
}


def _trajectory_point(t):
    """UMAP position along the CD8 memory -> effector -> exhausted curve, t in [0, 1]."""
    pts = np.array([(-1.5, 5.0), (-5.0, 3.0), (-8.0, -1.5)])
    a = (1 - t) ** 2
    b = 2 * (1 - t) * t
    c = t ** 2
    ctrl = pts[1] + np.array([-1.2, 1.4])  # bow the curve outward
    return a[:, None] * pts[0] + b[:, None] * ctrl + c[:, None] * pts[2]


def _cd8_profile(t):
    """Expected UMIs per 10k for CD8 genes as smooth functions of pseudotime."""
    sig = lambda x, mid, k: 1 / (1 + np.exp(-(x - mid) * k))  # noqa: E731
    bump = lambda x, mid, w: np.exp(-((x - mid) / w) ** 2)  # noqa: E731
    early = 1 - sig(t, 0.35, 12)
    late = sig(t, 0.6, 14)
    return {
        "CD8A": 30 + 0 * t, "CD8B": 18 + 0 * t,
        "TCF7": 2 + 30 * early, "IL7R": 3 + 35 * early, "SELL": 1 + 14 * early, "CCR7": 1 + 10 * early,
        "LEF1": 1 + 10 * early,
        "GZMK": 4 + 45 * bump(t, 0.42, 0.18), "GZMA": 5 + 30 * sig(t, 0.3, 10), "CCL5": 10 + 60 * sig(t, 0.3, 10),
        "CX3CR1": 1 + 12 * bump(t, 0.45, 0.12), "NKG7": 6 + 60 * sig(t, 0.35, 10),
        "GZMB": 1 + 40 * sig(t, 0.5, 10), "PRF1": 1 + 25 * sig(t, 0.5, 10), "IFNG": 1 + 12 * bump(t, 0.55, 0.15),
        "PDCD1": 1 + 25 * late, "HAVCR2": 0.5 + 30 * late, "LAG3": 0.5 + 25 * late, "TIGIT": 1 + 25 * late,
        "TOX": 1 + 18 * late, "CXCL13": 0.3 + 30 * sig(t, 0.75, 14), "ENTPD1": 0.3 + 14 * late,
        "LAYN": 0.2 + 10 * sig(t, 0.8, 16), "CTLA4": 0.5 + 8 * late,
    }


def _blob(n, center, spread):
    """An organic-looking cluster: three overlapping rotated Gaussians."""
    k = rng.integers(0, 3, n)
    offsets = rng.normal(0, 0.45, (3, 2)) * np.array(spread)
    angles = rng.uniform(0, np.pi, 3)
    out = np.empty((n, 2))
    for j in range(3):
        idx = k == j
        z = rng.normal(0, 1, (idx.sum(), 2)) * np.array(spread) * rng.uniform(0.6, 1.0, 2)
        c, s = math.cos(angles[j]), math.sin(angles[j])
        out[idx] = z @ np.array([[c, -s], [s, c]]) + np.array(center) + offsets[j]
    return out


def _build():
    rows = []  # (sample index, cell type name)
    patient_noise = {p: rng.lognormal(0, 0.3, len(CELL_TYPES)) for p in PATIENTS}
    for si, sample in enumerate(SAMPLES):
        patient, tp = sample.split("-")
        shift = ABUNDANCE_SHIFT[RESPONSE[patient], tp]
        w = np.array([c.share * shift.get(c.name, 1.0) for c in CELL_TYPES]) * patient_noise[patient]
        w *= rng.lognormal(0, 0.12, len(w))
        w /= w.sum()
        n = int(rng.integers(650, 1100))
        lq_frac = 0.16 if sample == "P06-On" else rng.uniform(0.02, 0.06)
        n_lq = int(n * lq_frac)
        counts = rng.multinomial(n - n_lq, w)
        for c, k in zip(CELL_TYPES, counts):
            rows += [(si, c.name)] * int(k)
        rows += [(si, LOW_QUALITY)] * n_lq

    n = len(rows)
    sample_idx = np.array([r[0] for r in rows])
    cell_type = np.array([r[1] for r in rows], dtype=object)
    by_name = {c.name: c for c in CELL_TYPES}

    umap = np.zeros((n, 2))
    pseudotime = np.full(n, np.nan)
    mu = np.full((n, len(GENES)), 0.0)
    log_lib = np.zeros(n)

    background = np.clip(rng.lognormal(math.log(0.08), 0.7, len(GENES)), 0.01, 0.5)
    housekeeping = _m(ACTB=300, GAPDH=80, MALAT1=600, TMSB4X=400, EEF1A1=350, FTL=60, RPL13=250, RPS27=220,
                      RPLP0=150, HSPA1A=4, FOS=10, JUN=10, DUSP1=12)
    base = background.copy()
    for g, v in housekeeping.items():
        base[GENE_INDEX[g]] = v

    def apply(rowsel, markers):
        for g, v in markers.items():
            mu[rowsel, GENE_INDEX[g]] = np.broadcast_to(v, mu[rowsel, GENE_INDEX[g]].shape)

    response = np.array([RESPONSE[SAMPLES[s].split("-")[0]] for s in sample_idx], dtype=object)
    timepoint = np.array([SAMPLES[s].split("-")[1] for s in sample_idx], dtype=object)

    for c in CELL_TYPES:
        sel = np.where(cell_type == c.name)[0]
        mu[sel] = base
        apply(sel, c.markers)
        log_lib[sel] = rng.normal(c.log_lib, 0.35, len(sel))
        if c.name in CD8_LINEAGE:
            lo, hi = CD8_PT_RANGE[c.name]
            t = rng.uniform(lo, hi, len(sel))
            pseudotime[sel] = t
            umap[sel] = _trajectory_point(t) + rng.normal(0, 0.55, (len(sel), 2))
            for g, v in _cd8_profile(t).items():
                mu[sel, GENE_INDEX[g]] = v
        else:
            umap[sel] = _blob(len(sel), c.center, c.spread)

    # Interferon response on treatment, strong in responders
    ifn_genes = {"ISG15": 25, "IFI6": 20, "MX1": 12, "STAT1": 15, "GBP1": 12}
    ifn_strength = np.where(timepoint == "On", np.where(response == "Responder", 1.0, 0.25), 0.05)
    ifn_strength = ifn_strength * rng.lognormal(0, 0.3, n)
    for g, v in ifn_genes.items():
        mu[:, GENE_INDEX[g]] += v * ifn_strength
    macro = np.isin(cell_type, ["TAM C1QC+", "Classical monocytes", "cDC1"])
    mu[macro, GENE_INDEX["CXCL9"]] += 60 * ifn_strength[macro]
    mu[macro, GENE_INDEX["CXCL10"]] += 45 * ifn_strength[macro]
    tumor = np.isin(cell_type, ["Melanoma MITF-high", "Melanoma AXL-high"])
    for g in ["HLA-A", "HLA-B", "B2M", "CD74", "HLA-DRA"]:
        mu[tumor, GENE_INDEX[g]] *= 1 + 1.5 * ifn_strength[tumor]
    # Non-responder tumors lose MHC class I on treatment
    nr_on_tumor = tumor & (response == "Non-responder") & (timepoint == "On")
    for g in ["HLA-A", "HLA-B", "B2M"]:
        mu[nr_on_tumor, GENE_INDEX[g]] *= 0.45
    # Effector cells in responders make more IFNG and GZMB on treatment
    r_on_cd8 = np.isin(cell_type, CD8_LINEAGE) & (response == "Responder") & (timepoint == "On")
    for g, f in [("IFNG", 2.2), ("GZMB", 1.6)]:
        mu[r_on_cd8, GENE_INDEX[g]] *= f
    mu[r_on_cd8, GENE_INDEX["MKI67"]] += 3

    # Biological and technical variation between patients and between biopsies, per gene
    patient_of = np.array([PATIENTS.index(SAMPLES[si].split("-")[0]) for si in range(len(SAMPLES))])
    patient_fx = rng.lognormal(0, 0.22, (len(PATIENTS), len(GENES)))
    sample_fx = rng.lognormal(0, 0.12, (len(SAMPLES), len(GENES)))
    mu *= patient_fx[patient_of[sample_idx]] * sample_fx[sample_idx]

    # Mitochondrial fraction: healthy cells 2-8%, low-quality cells 20-60%
    pct_mito = rng.beta(3, 60, n) * 100 + 1
    lq = np.where(cell_type == LOW_QUALITY)[0]
    if len(lq):
        parents = rng.choice(len(CELL_TYPES), len(lq))
        for i, p in zip(lq, parents):
            c = CELL_TYPES[p]
            mu[i] = base
            for g, v in c.markers.items():
                mu[i, GENE_INDEX[g]] = v * 0.35
        umap[lq] = _blob(len(lq), (2.5, 0.5), (1.6, 1.4))
        log_lib[lq] = rng.normal(6.6, 0.45, len(lq))
        pct_mito[lq] = rng.uniform(18, 60, len(lq))
        for g in ["MALAT1", "FOS", "JUN", "HSPA1A"]:
            mu[lq, GENE_INDEX[g]] *= 2.5
    p06 = (np.array(SAMPLES)[sample_idx] == "P06-On") & (cell_type != LOW_QUALITY)
    pct_mito[p06] += rng.uniform(2, 12, p06.sum())

    # Scale mitochondrial genes so they make up pct_mito of the cell's reads
    mito_share = rng.dirichlet(np.ones(MITO.sum()) * 5, n)
    non_mito = mu[:, ~MITO].sum(1)
    mito_total = non_mito * pct_mito / (100 - pct_mito)
    mu[:, MITO] = mito_share * mito_total[:, None]

    # Draw counts: Poisson-gamma, library size scaled to the 160 genes we keep
    lib = np.exp(log_lib)
    rate = mu / mu.sum(1, keepdims=True) * lib[:, None] * 0.55
    counts = rng.poisson(rate * rng.gamma(2.0, 0.5, rate.shape)).astype(np.float32)
    n_counts = np.round(lib).astype(int)
    # Detected genes genome-wide grows sublinearly with library size
    n_genes = np.round(np.exp(0.8 * log_lib + 0.55 + rng.normal(0, 0.14, n))).astype(int)
    total = counts.sum(1, keepdims=True)
    total[total == 0] = 1
    expr = np.log1p(counts / total * 1e4).astype(np.float32)

    # Shuffle so no sample or type is drawn on top of the others in scatter plots
    order = rng.permutation(n)
    compartment = np.array([by_name[t].compartment if t in by_name else LOW_QUALITY for t in cell_type], dtype=object)
    return {
        "umap": umap[order].astype(np.float32),
        "expr": expr[order],
        "cell_type": cell_type[order],
        "compartment": compartment[order],
        "sample": np.array(SAMPLES, dtype=object)[sample_idx[order]],
        "patient": np.array([s.split("-")[0] for s in np.array(SAMPLES)[sample_idx[order]]], dtype=object),
        "response": response[order],
        "timepoint": timepoint[order],
        "pseudotime": pseudotime[order],
        "n_counts": n_counts[order],
        "n_genes": n_genes[order],
        "pct_mito": pct_mito[order],
    }


CELLS = _build()
N_CELLS = len(CELLS["cell_type"])
EXPR = CELLS["expr"]


def gene(g):
    return EXPR[:, GENE_INDEX[g]]


# ---------------------------------------------------------------- statistics


def _betacf(a, b, x, iters=200, eps=3e-14):
    """Continued fraction for the regularized incomplete beta (Numerical Recipes)."""
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, iters + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1) < eps:
            break
    return h


def t_pvalue(t, df):
    """Two-sided p-value for Student's t."""
    if not np.isfinite(t):
        return 0.0 if np.isinf(t) else 1.0
    x = df / (df + t * t)
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    a, b = df / 2, 0.5
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log1p(-x) * b - lbeta)
    if x < (a + 1) / (a + b + 2):
        return min(1.0, front * _betacf(a, b, x) / a)
    return min(1.0, 1 - front * _betacf(b, a, 1 - x) / b)


def bh_adjust(p):
    """Benjamini-Hochberg adjusted p-values."""
    p = np.asarray(p, float)
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.minimum(q, 1)
    return out


def cells_vs_rest(in_mask, out_mask):
    """Cell-level test of one group against another: Welch t on log-normalized expression.

    With hundreds of cells per group nearly everything is significant, so the
    app ranks by fold change and filters on detection, the way marker tables
    are usually read.
    """
    a, b = EXPR[in_mask], EXPR[out_mask]
    ma, mb = a.mean(0), b.mean(0)
    va, vb = a.var(0, ddof=1), b.var(0, ddof=1)
    se = np.sqrt(va / len(a) + vb / len(b)) + 1e-12
    t = (ma - mb) / se
    p = np.array([math.erfc(abs(x) / math.sqrt(2)) for x in t])
    lfc = np.log2((np.expm1(a).mean(0) + 0.1) / (np.expm1(b).mean(0) + 0.1))
    return {
        "gene": GENES, "log2fc": lfc, "p": np.maximum(p, 1e-300), "q": np.maximum(bh_adjust(p), 1e-300),
        "pct_in": (a > 0).mean(0), "pct_out": (b > 0).mean(0), "mean_in": ma, "mean_out": mb,
        "n_in": int(len(a)), "n_out": int(len(b)), "unit": "cells",
    }


def pseudobulk(mask, min_cells=10):
    """Per-sample mean expression (log2 of mean normalized counts + 1) for the masked cells."""
    out = {}
    samples = CELLS["sample"]
    for s in SAMPLES:
        sel = mask & (samples == s)
        if sel.sum() >= min_cells:
            out[s] = np.log2(np.expm1(EXPR[sel]).mean(0) + 1)
    return out


def samples_test(mask, group_a, group_b, paired):
    """Pseudobulk test between two sets of samples.

    Each sample contributes one value per gene, so the test has as many
    observations as there are samples, which is the honest unit for a
    comparison between patients or timepoints.
    """
    pb = pseudobulk(mask)
    if paired:
        pairs = [(a, b) for a, b in zip(group_a, group_b) if a in pb and b in pb]
        if len(pairs) < 3:
            return None
        d = np.array([pb[a] - pb[b] for a, b in pairs])
        mean, sd = d.mean(0), d.std(0, ddof=1) + 1e-9
        t = mean / (sd / math.sqrt(len(d)))
        df = np.full(len(GENES), len(d) - 1.0)
        lfc, na, nb = mean, len(pairs), len(pairs)
        xa = np.array([pb[a] for a, _ in pairs])
        xb = np.array([pb[b] for _, b in pairs])
    else:
        xa = np.array([pb[s] for s in group_a if s in pb])
        xb = np.array([pb[s] for s in group_b if s in pb])
        if len(xa) < 2 or len(xb) < 2:
            return None
        va, vb = xa.var(0, ddof=1) / len(xa), xb.var(0, ddof=1) / len(xb)
        t = (xa.mean(0) - xb.mean(0)) / (np.sqrt(va + vb) + 1e-9)
        df = (va + vb) ** 2 / (va ** 2 / (len(xa) - 1) + vb ** 2 / (len(xb) - 1) + 1e-18)
        lfc, na, nb = xa.mean(0) - xb.mean(0), len(xa), len(xb)
    p = np.array([t_pvalue(float(ti), float(di)) for ti, di in zip(t, df)])
    sel_cells = EXPR[mask]
    in_a = mask & np.isin(CELLS["sample"], list(group_a))
    in_b = mask & np.isin(CELLS["sample"], list(group_b))
    return {
        "gene": GENES, "log2fc": lfc, "p": np.maximum(p, 1e-300), "q": np.maximum(bh_adjust(p), 1e-300),
        "pct_in": (EXPR[in_a] > 0).mean(0) if in_a.any() else np.zeros(len(GENES)),
        "pct_out": (EXPR[in_b] > 0).mean(0) if in_b.any() else np.zeros(len(GENES)),
        "mean_in": xa.mean(0), "mean_out": xb.mean(0), "n_in": na, "n_out": nb, "unit": "samples",
        "n_cells": int(len(sel_cells)),
    }


# Marker statistics per cell type against all other healthy cells, computed once
_healthy = CELLS["cell_type"] != LOW_QUALITY
MARKERS = {}
for _c in CELL_TYPES:
    _in = CELLS["cell_type"] == _c.name
    MARKERS[_c.name] = cells_vs_rest(_in, _healthy & ~_in)


def top_markers(cell_type, k=3, min_pct=0.4):
    m = MARKERS[cell_type]
    ok = (m["pct_in"] >= min_pct) & ~MITO & np.array([GENE_SET_OF[g] not in ("Housekeeping",) for g in GENES])
    score = np.where(ok, m["log2fc"], -np.inf)
    return [GENES[i] for i in np.argsort(-score)[:k] if np.isfinite(score[i])]


CURATED_MARKERS = [
    "CD3D", "CD4", "IL7R", "FOXP3", "CTLA4", "CD8A", "TCF7", "GZMK", "GZMB", "HAVCR2", "CXCL13", "MKI67",
    "GNLY", "KLRF1", "MS4A1", "CD79A", "JCHAIN", "CD14", "S100A8", "C1QC", "APOE", "SPP1", "TREM2",
    "CLEC9A", "LILRA4", "COL1A1", "DCN", "VWF", "PLVAP", "PMEL", "MLANA", "AXL", "NGFR",
]
