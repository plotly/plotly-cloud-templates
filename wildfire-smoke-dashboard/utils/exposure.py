"""Vulnerable & exposed ranking — pure, no Dash imports.

For one season, each county gets:
    smoke_days   days with HMS smoke ≥ threshold over ≥25% of the county
    usg_days     days the county-mean AQI exceeded 100 (Unhealthy for Sensitive Groups+)
    asthma_rate  CDPH age-adjusted asthma ED visits per 10k (season year, or latest)
    score        asthma_rate × smoke_days, rescaled so the top county = 100

The score is a simple screening index (burden × exposure), not a risk estimate.
"""

from functools import lru_cache

import pandas as pd

from config import AQI_CATEGORIES, USG_AQI
from utils.aqi import category_key
from utils.data import COUNTY_FIPS, COUNTY_NAMES, asthma_rates, county_aqi_matrix, population, smoke_matrix


def vulnerability_score(asthma: pd.Series, smoke_days: pd.Series) -> pd.Series:
    """Burden × exposure on a 0–100 scale (NaN where the asthma rate is suppressed)."""
    raw = asthma * smoke_days
    top = raw.max()
    if pd.isna(top) or top <= 0:
        return raw * 0
    return (100 * raw / top).round(1)


@lru_cache(maxsize=64)
def _vulnerability_table(season: str, pollutant: str, threshold: int, age: str) -> pd.DataFrame:
    smoke = smoke_matrix(season)
    aqi = county_aqi_matrix(season, pollutant)
    asthma = asthma_rates(season, age)
    smoke_days = (smoke >= threshold).sum().astype(int)
    table = pd.DataFrame(
        {
            "fips": COUNTY_FIPS,
            "county": [COUNTY_NAMES[f] for f in COUNTY_FIPS],
            "smoke_days": smoke_days.values,
            "usg_days": (aqi > USG_AQI).fillna(False).astype(bool).sum().values,
            "monitored_days": aqi.notna().sum().values,
            "asthma_rate": asthma.values,
            "population": population(season).values,
        }
    )
    table["score"] = vulnerability_score(table["asthma_rate"], table["smoke_days"]).values
    return table.sort_values(["score", "smoke_days"], ascending=False, na_position="last").reset_index(drop=True)


def vulnerability_table(season: str, pollutant: str = "pm25", threshold: int = 2, age: str = "all") -> pd.DataFrame:
    """One row per county, ranked by score (suppressed asthma rates sort last)."""
    return _vulnerability_table(season, pollutant, threshold, age).copy()


@lru_cache(maxsize=16)
def _category_days(season: str, pollutant: str) -> pd.DataFrame:
    aqi = county_aqi_matrix(season, pollutant)
    keys = aqi.apply(lambda col: col.map(category_key))
    return pd.DataFrame({c["key"]: (keys == c["key"]).sum() for c in AQI_CATEGORIES}).reindex(COUNTY_FIPS)


def category_days(season: str, pollutant: str = "pm25") -> pd.DataFrame:
    """Counties × AQI categories: number of days the county mean fell in each category."""
    return _category_days(season, pollutant).copy()
