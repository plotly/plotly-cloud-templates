"""EPA AQI — pure functions, no data imports (unit-tested in tests/test_aqi.py).

AQI = (I_hi − I_lo) / (C_hi − C_lo) · (C − C_lo) + I_lo, with the concentration
truncated first (PM2.5 to 0.1 µg/m³, ozone to 1 ppb) and the index rounded to
the nearest integer. Values above the last breakpoint are capped at its I_hi.
"""

import math

import numpy as np
import pandas as pd

from config import AQI_CATEGORIES, POLLUTANTS


def _truncate(value: float, decimals: int) -> float:
    factor = 10**decimals
    # The small epsilon keeps 35.4 (stored as 35.39999…) from truncating to 35.3.
    return math.floor(value * factor + 1e-9) / factor


def aqi(value: float | None, pollutant: str) -> int | None:
    """AQI for one concentration in the pollutant's display unit; None for missing/negative."""
    if value is None or pd.isna(value):
        return None
    meta = POLLUTANTS[pollutant]
    c = max(_truncate(float(value), meta["decimals"]), 0.0)
    for c_lo, c_hi, i_lo, i_hi in meta["breakpoints"]:
        if c <= c_hi:
            # Values that fall in a truncation gap (e.g. 9.05 → 9.0) land in the lower bin.
            c = max(c, c_lo)
            return int(math.floor((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo) + i_lo + 0.5))
    return meta["breakpoints"][-1][3]


def aqi_series(values: pd.Series, pollutant: str) -> pd.Series:
    """Vectorised `aqi` (nullable Int64 so missing stays missing)."""
    meta = POLLUTANTS[pollutant]
    factor = 10 ** meta["decimals"]
    c = np.floor(values.astype(float) * factor + 1e-9) / factor
    c = c.clip(lower=0)
    out = pd.Series(np.nan, index=values.index)
    lower = -np.inf
    for c_lo, c_hi, i_lo, i_hi in meta["breakpoints"]:
        mask = (c > lower) & (c <= c_hi)
        cc = c[mask].clip(lower=c_lo)
        out[mask] = np.floor((i_hi - i_lo) / (c_hi - c_lo) * (cc - c_lo) + i_lo + 0.5)
        lower = c_hi
    out[c > lower] = meta["breakpoints"][-1][3]
    out[values.isna()] = np.nan
    return out.astype("Int64")


def category(index: float | None) -> dict | None:
    """AQI category dict (label, colour, …) for an AQI value; None when missing."""
    if index is None or pd.isna(index):
        return None
    return next((c for c in AQI_CATEGORIES if index <= c["max"]), AQI_CATEGORIES[-1])


def category_key(index: float | None) -> str | None:
    cat = category(index)
    return cat["key"] if cat else None
