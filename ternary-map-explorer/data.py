"""Load and tidy the well and production data once at startup."""

from pathlib import Path

import pandas as pd

from theme import FORMATION_COLORS, OTHER_FORMATIONS

DATA_DIR = Path(__file__).parent / "data"

FORMATION_NAMES = {
    "Ohio Sh": "Ohio Shale",
    "Clinton Sh": "Clinton Shale",
    "Clinton Sd": "Clinton Sandstone",
    "Big Six Sd": "Big Six Sandstone",
    "Salt Sd": "Salt Sandstone",
    "Maxon Sd": "Maxon Sandstone",
    "Lockport Dol": "Lockport Dolomite",
    "Olentangy Mbr, Ohio Sh": "Olentangy Member",
}


def _load_wells():
    wells = (
        pd.read_csv(DATA_DIR / "test_composition.csv")
        .drop_duplicates("RecordNumber")
        .rename(
            columns={
                "RecordNumber": "well_id",
                "nlat83": "lat",
                "wlon83": "lon",
                "op": "operator",
                "fm_name": "formation",
            }
        )
    )
    wells["formation"] = wells["formation"].replace(FORMATION_NAMES)
    wells["group"] = wells["formation"].where(
        wells["formation"].isin(FORMATION_COLORS), OTHER_FORMATIONS
    )
    wells["operator"] = wells["operator"].str.title().str.replace(", Inc", " Inc")

    # Two-digit years: every well in this dataset was completed before 2000
    completed = pd.to_datetime(wells["cmpl"], format="%d-%b-%y", errors="coerce")
    wells["completed"] = completed.where(
        completed.dt.year < 2000, completed - pd.DateOffset(years=100)
    ).dt.year.astype("Int64")

    return wells[
        [
            "well_id",
            "lat",
            "lon",
            "operator",
            "formation",
            "group",
            "completed",
            "Quartz",
            "Carbonate",
            "Clay",
        ]
    ].reset_index(drop=True)


def _load_production():
    prod = pd.read_csv(DATA_DIR / "YearlyProduction_table_1.csv")
    prod = prod.rename(columns={"RecordNumber": "well_id", "VolumeMCF": "mcf"})
    return prod[["well_id", "Year", "mcf"]]


wells = _load_wells()
production = _load_production()

cumulative_mmcf = production.groupby("well_id")["mcf"].sum() / 1_000
wells["cum_mmcf"] = wells["well_id"].map(cumulative_mmcf).round(1)

OPERATORS = wells["operator"].value_counts().index.tolist()
