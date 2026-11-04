"""
Synthetic hit-to-lead data for a made-up kinase target, TKX1.

Every compound is a real, valid structure: four scaffolds are decorated with
R-groups and RDKit computes their physicochemical properties. The assay results
are invented with an additive model (scaffold + R1 + R2 contributions, plus
property-driven effects and noise) so the data has believable structure-activity
patterns: lipophilic compounds are more potent but less soluble, less stable and
more likely to block hERG; basic amines raise hERG risk; polar compounds lose
permeability and therefore cell potency.

Compounds go through a testing cascade, as they would in a real project:
everything gets the biochemical assay, only actives go on to the cell assay,
and only cell-active compounds are profiled for ADME and safety.
"""

import base64
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import QED, Crippen, Descriptors, Lipinski, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

RDLogger.DisableLog("rdApp.*")

TARGET = "TKX1"
AS_OF = date(2026, 10, 30)
START = date(2025, 8, 4)

# Scaffold template, base pIC50, base log selectivity, series name
SERIES = {
    "Aminopyrimidine": ("{R1}Nc1nccc(-c2ccc({R2})cc2)n1", 6.45, 1.25),
    "Pyrazolopyridine": ("{R1}n1ncc2cc(-c3ccc({R2})cc3)cnc21", 6.85, 1.6),
    "Quinazoline": ("{R1}Nc1ncnc2cc({R2})ccc12", 6.1, 0.8),
    "Indazole amide": ("O=C(N{R1})c1ccc2[nH]nc({R2})c2c1", 5.85, 1.95),
}
SERIES_NAMES = list(SERIES)
SERIES_CODE = dict(zip(SERIES_NAMES, ["AP", "PP", "QZ", "IA"]))
# The month each series was started; later series build on what was learned
SERIES_START = dict(zip(SERIES_NAMES, [0, 3, 1, 6]))

# R1 sits on the hinge-binding nitrogen; the fragment's last atom bonds to it
R1 = {
    "C": 0.0, "CC": 0.15, "CC(C)": 0.25, "C%10CC%10": 0.45, "C%10CCOCC%10": 0.35, "OCC": 0.05,
    "FC(F)C": 0.2, "c%10ccccc%10": 0.55, "c%10ccc(F)cc%10": 0.7, "C%10CCN(C)CC%10": 0.4,
    "CN(C)CC": -0.1, "C%10CCC%10": 0.3,
}
# R2 points to solvent; the fragment's first atom bonds to the ring
R2 = {
    "F": 0.0, "Cl": 0.25, "OC": 0.1, "C(F)(F)F": 0.35, "C#N": 0.2, "N%11CCOCC%11": 0.45,
    "N%11CCN(C)CC%11": 0.6, "S(C)(=O)=O": 0.15, "C(=O)N": 0.3, "OCC%11CC%11": 0.4,
    "C(=O)N%11CCOCC%11": 0.5, "c%11cn(C)nc%11": 0.65,
}

# Criteria a compound must meet to count as working. Direction: ">=" or "<="
GATES = {
    "potency": {"label": "Biochemical potency", "short": "Potency", "unit": "pIC50", "default": 7.5,
                "options": [6.5, 7.0, 7.5, 8.0, 8.5], "dir": ">=", "stage": "Biochemical"},
    "cell": {"label": "Cell potency", "short": "Cell", "unit": "pEC50", "default": 6.5,
             "options": [5.5, 6.0, 6.5, 7.0, 7.5], "dir": ">=", "stage": "Cell"},
    "selectivity": {"label": "Kinome selectivity", "short": "Selectivity", "unit": "fold", "default": 30,
                    "options": [3, 10, 30, 100, 300], "dir": ">=", "stage": "Cell", "log": True},
    "solubility": {"label": "Kinetic solubility", "short": "Solubility", "unit": "µM", "default": 20,
                   "options": [5, 10, 20, 50, 100], "dir": ">=", "stage": "ADME", "log": True},
    "clint": {"label": "Microsomal clearance", "short": "Clearance", "unit": "µL/min/mg", "default": 30,
              "options": [100, 50, 30, 20, 10], "dir": "<=", "stage": "ADME", "log": True},
    "papp": {"label": "Caco-2 permeability", "short": "Permeability", "unit": "10⁻⁶ cm/s", "default": 5,
             "options": [1, 2, 5, 10, 20], "dir": ">=", "stage": "ADME", "log": True},
    "herg": {"label": "hERG safety margin", "short": "hERG", "unit": "µM", "default": 10,
             "options": [3, 5, 10, 30, 50], "dir": ">=", "stage": "Safety", "log": True},
}
STAGES = ["Biochemical", "Cell", "ADME", "Safety"]
# Which compounds were sent to each stage (fixed by the project's historic triage rules)
STAGE_RULE = {"Biochemical": None, "Cell": ("potency", 6.0), "ADME": ("cell", 5.8), "Safety": ("cell", 5.8)}


@dataclass
class Compound:
    id: str
    series: str
    smiles: str
    r1: str
    r2: str
    made: date
    mw: float
    clogp: float
    tpsa: float
    hbd: int
    hba: int
    rotb: int
    qed: float
    basic: bool
    values: dict = field(default_factory=dict)  # gate key -> measured value, or None if not tested
    curve: dict = field(default_factory=dict)  # biochemical dose-response replicates

    @property
    def lle(self):
        return self.values["potency"] - self.clogp

    @property
    def lipinski_violations(self):
        return sum([self.mw > 500, self.clogp > 5, self.hbd > 5, self.hba > 10])


def _is_basic(mol):
    """Aliphatic amine that is not an amide, sulfonamide, aniline or ring-fused aromatic N."""
    patt = Chem.MolFromSmarts("[NX3;H0,H1,H2;!$(N-C=O);!$(N-S(=O)=O);!$(N-a);!$(N-[#7,#8])]([C;!$(C=*)])")
    return mol.HasSubstructMatch(patt)


def _generate(seed=7):
    rng = np.random.default_rng(seed)
    out = []
    months = (AS_OF.year - START.year) * 12 + AS_OF.month - START.month
    for s, (tmpl, base, sel_base) in SERIES.items():
        combos = [(a, b) for a in R1 for b in R2]
        rng.shuffle(combos)
        n = {"Aminopyrimidine": 96, "Pyrazolopyridine": 84, "Quinazoline": 70, "Indazole amide": 52}[s]
        start = SERIES_START[s]
        for i, (a, b) in enumerate(combos[:n]):
            mol = Chem.MolFromSmiles(tmpl.format(R1=a, R2=b))
            if mol is None:
                continue
            frac = i / n
            made = START + timedelta(days=int(30.4 * (start + frac * (months - start - 0.3)))
                                     + int(rng.integers(0, 12)))
            out.append((s, a, b, mol, min(made, AS_OF)))
    return out, rng


def _build():
    raw, rng = _generate()
    by_series = {}
    for item in raw:
        by_series.setdefault(item[0], []).append(item)
    compounds = []
    for s, items in by_series.items():
        # Sort the R-group pairs by their true effect plus noise, then hand out the dates in order,
        # so the series improves over time the way a real program would
        dates = sorted(it[4] for it in items)
        items.sort(key=lambda it: R1[it[1]] + R2[it[2]] + rng.normal(0, 0.35))
        tmpl, base, sel_base = SERIES[s]
        for k, ((_, a, b, mol, _), made) in enumerate(zip(items, dates)):
            clogp = Crippen.MolLogP(mol)
            mw = Descriptors.MolWt(mol)
            tpsa = rdMolDescriptors.CalcTPSA(mol)
            hbd = Lipinski.NumHDonors(mol)
            basic = _is_basic(mol)
            c = Compound(
                id=f"TKX-{SERIES_CODE[s]}-{k + 1:03d}", series=s, smiles=Chem.MolToSmiles(mol), r1=a, r2=b,
                made=made, mw=mw, clogp=clogp, tpsa=tpsa, hbd=hbd, hba=Lipinski.NumHAcceptors(mol),
                rotb=rdMolDescriptors.CalcNumRotatableBonds(mol), qed=QED.qed(mol), basic=basic,
            )
            # Biochemical potency: scaffold + R-groups + a lipophilicity bonus
            pic50 = base + R1[a] + R2[b] + 0.22 * (clogp - 3) + rng.normal(0, 0.32)
            pic50 = float(np.clip(pic50, 4.6, 9.6))
            v = {"potency": round(pic50, 2)}
            # Cell potency: drops further for poorly permeable compounds
            log_papp = 0.95 - 0.0085 * (tpsa - 60) - 0.12 * max(hbd - 1, 0) + 0.06 * clogp + rng.normal(0, 0.18)
            papp = float(np.clip(10 ** log_papp, 0.3, 45))
            if pic50 >= STAGE_RULE["Cell"][1]:
                shift = 0.55 + 0.9 * max(0, 0.7 - np.log10(papp)) + rng.normal(0, 0.25)
                v["cell"] = round(float(pic50 - max(shift, 0.1)), 2)
                # Selectivity mostly a scaffold property, aryl R1 helps
                log_sel = sel_base + (0.35 if a.startswith("c") else 0) + 0.15 * R2[b] + rng.normal(0, 0.35)
                v["selectivity"] = round(float(np.clip(10 ** log_sel, 1, 1000)), 1)
            else:
                v["cell"] = v["selectivity"] = None
            if v["cell"] is not None and v["cell"] >= STAGE_RULE["ADME"][1]:
                arom = rdMolDescriptors.CalcNumAromaticRings(mol)
                log_sol = 2.75 - 0.42 * clogp - 0.15 * (arom - 2) + (0.35 if basic else 0) + rng.normal(0, 0.28)
                v["solubility"] = round(float(np.clip(10 ** log_sol, 0.5, 250)), 1)
                log_cl = 0.62 + 0.27 * clogp + (0.15 if "OC" == b else 0) + rng.normal(0, 0.2)
                v["clint"] = round(float(np.clip(10 ** log_cl, 3, 400)), 1)
                v["papp"] = round(papp, 1)
                p_herg = 3.75 + 0.32 * clogp + (0.75 if basic else 0) + rng.normal(0, 0.25)
                v["herg"] = round(float(np.clip(10 ** (6 - p_herg), 0.3, 100)), 1)
            else:
                v.update(solubility=None, clint=None, papp=None, herg=None)
            c.values = v
            c.curve = _dose_response(pic50, rng)
            compounds.append(c)
    compounds.sort(key=lambda c: c.made)
    return compounds


def hill(conc_nm, ic50_nm, slope=1.0, top=100.0, bottom=0.0):
    return bottom + (top - bottom) / (1 + (conc_nm / ic50_nm) ** slope)


def _dose_response(pic50, rng):
    """Ten-point, three-fold dilution from 10 µM, run in triplicate; % activity remaining."""
    conc = 10_000 / 3 ** np.arange(10)  # nM
    ic50 = 10 ** (9 - pic50)
    slope = float(np.clip(rng.normal(1.0, 0.15), 0.6, 1.5))
    reps = [np.clip(hill(conc, ic50, slope) + rng.normal(0, 4.5, conc.size), -5, 110) for _ in range(3)]
    return {"conc": conc, "reps": np.array(reps), "slope": slope}


COMPOUNDS = _build()
BY_ID = {c.id: c for c in COMPOUNDS}


def passes(c, key, threshold):
    v = c.values[key]
    if v is None:
        return None
    return v >= threshold if GATES[key]["dir"] == ">=" else v <= threshold


def evaluate(c, criteria):
    """Per gate: True (pass), False (fail) or None (not tested)."""
    return {k: passes(c, k, criteria[k]) for k in GATES}


def margin(c, key, threshold):
    """How far past the bar, in log10 units (positive = passes). pIC50/pEC50 are already logs."""
    v = c.values[key]
    if v is None:
        return None
    if GATES[key].get("log"):
        d = np.log10(max(v, 1e-3)) - np.log10(threshold)
    else:
        d = v - threshold
    return float(d if GATES[key]["dir"] == ">=" else -d)


@lru_cache(maxsize=512)
def structure_svg(smiles, width=260, height=190, dark=False):
    mol = Chem.MolFromSmiles(smiles)
    d = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = d.drawOptions()
    opts.clearBackground = False
    opts.bondLineWidth = 1.6
    opts.padding = 0.06
    opts.additionalAtomLabelPadding = 0.08
    opts.minFontSize = 11
    d.DrawMolecule(mol)
    d.FinishDrawing()
    return "data:image/svg+xml;base64," + base64.b64encode(d.GetDrawingText().encode()).decode()
