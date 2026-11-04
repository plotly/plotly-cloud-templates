"""
Synthetic hit-to-lead data for a made-up kinase target, TKX1.

The compounds, their measured values and their structure drawings are built
ahead of time by scripts/build_data.py (which uses RDKit) and saved to
data/compounds.json and data/structures.json. This module only loads them, so
the deployed app does not need RDKit or the system graphics libraries it links
to. The drawings travel inline as data URIs, so there are no image files to
upload or serve.
"""

import base64
import json
from dataclasses import dataclass
from pathlib import Path

TARGET = "TKX1"

# Criteria a compound must meet to count as working. Direction: ">=" or "<=".
# Each options list runs from lenient to strict, with the project default in the middle.
GATES = {
    "potency": {"label": "Biochemical potency", "short": "Potency", "unit": "pIC50",
                "options": [6.5, 7.0, 7.5, 8.0, 8.5], "dir": ">="},
    "cell": {"label": "Cell potency", "short": "Cell", "unit": "pEC50",
             "options": [5.5, 6.0, 6.5, 7.0, 7.5], "dir": ">="},
    "selectivity": {"label": "Kinome selectivity", "short": "Selectivity", "unit": "fold",
                    "options": [3, 10, 30, 100, 300], "dir": ">="},
    "solubility": {"label": "Kinetic solubility", "short": "Solubility", "unit": "µM",
                   "options": [5, 10, 20, 50, 100], "dir": ">="},
    "clint": {"label": "Microsomal clearance", "short": "Clearance", "unit": "µL/min/mg",
              "options": [100, 50, 30, 20, 10], "dir": "<="},
    "papp": {"label": "Caco-2 permeability", "short": "Permeability", "unit": "10⁻⁶ cm/s",
             "options": [1, 2, 5, 10, 20], "dir": ">="},
    "herg": {"label": "hERG safety margin", "short": "hERG", "unit": "µM",
             "options": [3, 5, 10, 30, 50], "dir": ">="},
}


@dataclass
class Compound:
    id: str
    series: str
    smiles: str
    clogp: float
    values: dict  # gate key -> measured value, or None if not tested
    structure: str  # 2D structure drawing as an SVG data URI, ready for an <img> src


def _load():
    data = Path(__file__).parent / "data"
    rows = json.loads((data / "compounds.json").read_text())
    drawings = json.loads((data / "structures.json").read_text())
    return [
        Compound(id=r["id"], series=r["series"], smiles=r["smiles"], clogp=r["clogp"], values=r["values"],
                 structure="data:image/svg+xml;base64," + base64.b64encode(drawings[r["id"]].encode()).decode())
        for r in rows
    ]


COMPOUNDS = _load()
BY_ID = {c.id: c for c in COMPOUNDS}


def passes(c, key, threshold):
    v = c.values[key]
    if v is None:
        return None
    return v >= threshold if GATES[key]["dir"] == ">=" else v <= threshold


def evaluate(c, criteria):
    """Per gate: True (pass), False (fail) or None (not tested)."""
    return {k: passes(c, k, criteria[k]) for k in GATES}
