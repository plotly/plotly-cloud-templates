"""Daily series for the Time Series tab — pure, no Dash imports.

All series share one index per season, SEASON_DAYS[season]: every calendar day of
the window. Days without a reporting monitor stay NaN so the chart shows a gap
instead of a misleading zero.
"""

from functools import lru_cache

import pandas as pd

from utils.data import SEASON_DAYS, county_mean_matrix, population, smoke_matrix
from utils.stats import population_weighted


@lru_cache(maxsize=16)
def _statewide_series(season: str, pollutant: str) -> pd.Series:
    means = county_mean_matrix(season, pollutant)
    pop = population(season)
    return pd.Series([population_weighted(means.loc[d], pop) for d in SEASON_DAYS[season]], index=SEASON_DAYS[season], dtype=float)


def statewide_series(season: str, pollutant: str) -> pd.Series:
    """Population-weighted mean of county means per day (counties with a monitor only)."""
    return _statewide_series(season, pollutant).copy()


def county_series(season: str, pollutant: str, counties: list[str]) -> pd.DataFrame:
    """Days × selected counties of county-mean concentration."""
    return county_mean_matrix(season, pollutant)[counties]


def smoke_strip(season: str, counties: list[str]) -> pd.DataFrame:
    """Days × selected counties of HMS smoke level (0–3, NaN = no HMS file that day)."""
    return smoke_matrix(season)[counties]


def padded_max(values: pd.DataFrame | pd.Series, frac: float = 0.12, floor: float = 1.0) -> float:
    """Upper y-limit with headroom; `floor` keeps empty selections drawable."""
    top = pd.DataFrame(values).max().max()
    return max(float(top) * (1 + frac), floor) if pd.notna(top) else floor
