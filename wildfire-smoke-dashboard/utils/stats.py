"""Stat-card domain logic — pure functions over the read-only frames in utils.data.

No Dash imports: everything here is unit-testable and memoised. Results are
frozen dataclasses so cached objects can be shared safely between callbacks.

Day-over-day compares against the previous calendar day of the same season.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import pandas as pd

from config import AQI_CATEGORIES, SMOKE_LEVELS, UNHEALTHY_AQI, USG_AQI
from utils.aqi import aqi, category_key
from utils.data import SEASON_DAYS, county_aqi_matrix, county_means, county_smoke, population, site_values

Direction = Literal["up", "down", "flat", "na"]
_EPS = 1e-9


@dataclass(frozen=True)
class Change:
    """A value today vs the previous day."""

    current: float | None
    previous: float | None

    @property
    def delta(self) -> float | None:
        if self.current is None or self.previous is None:
            return None
        return self.current - self.previous

    @property
    def pct(self) -> float | None:
        delta = self.delta
        if delta is None or abs(self.previous) < _EPS:
            return None
        return 100 * delta / abs(self.previous)

    @property
    def direction(self) -> Direction:
        delta = self.delta
        if delta is None:
            return "na"
        if abs(delta) < _EPS:
            return "flat"
        return "up" if delta > 0 else "down"


@dataclass(frozen=True)
class AirStats:
    """Monitor summary for one day and pollutant (concentrations in display units)."""

    season: str
    day: str
    pollutant: str
    prev_day: str | None
    reporting: int
    mean: float | None
    peak: float | None
    peak_aqi: int | None
    peak_site: str | None
    unhealthy_plus: int  # monitors with AQI > 150
    level_counts: tuple[int, ...]  # aligned with AQI_CATEGORIES
    mean_change: Change
    peak_change: Change

    @property
    def has_data(self) -> bool:
        return self.reporting > 0


@dataclass(frozen=True)
class ExposureStats:
    """Population exposure and smoke coverage for one day (season-to-date where noted)."""

    season: str
    day: str
    pollutant: str
    pop_weighted: float | None  # county means weighted by county population
    pop_weighted_aqi: int | None
    pop_covered: int  # residents of counties with ≥1 reporting monitor
    pop_usg_plus: int  # residents of counties whose mean AQI > 100
    days_unhealthy: int  # season to date: days with any monitor AQI > 150
    days_elapsed: int
    smoke_counties: tuple[int, ...]  # counties under Light / Medium / Heavy (highest level only)
    pop_smoke: int  # residents of counties under Medium+ smoke
    smoke_available: bool


def previous_day(season: str, day: str) -> str | None:
    days = SEASON_DAYS[season]
    idx = days.index(day)
    return days[idx - 1] if idx > 0 else None


def _mean_peak(season: str, day: str | None, pollutant: str) -> tuple[float | None, float | None]:
    if day is None:
        return None, None
    sites = site_values(season, day, pollutant)
    if sites.empty:
        return None, None
    return float(sites["value"].mean()), float(sites["value"].max())


@lru_cache(maxsize=1024)
def air_stats(season: str, day: str, pollutant: str) -> AirStats:
    sites = site_values(season, day, pollutant)
    reporting = len(sites)
    keys = sites["aqi"].map(category_key).tolist() if reporting else []
    prev = previous_day(season, day)
    mean, peak = _mean_peak(season, day, pollutant)
    p_mean, p_peak = _mean_peak(season, prev, pollutant)
    if reporting:
        top = sites["value"].idxmax()
        peak_aqi, peak_site = int(sites.loc[top, "aqi"]), str(sites.loc[top, "name"])
    else:
        peak_aqi = peak_site = None
    return AirStats(
        season=season,
        day=day,
        pollutant=pollutant,
        prev_day=prev,
        reporting=reporting,
        mean=mean,
        peak=peak,
        peak_aqi=peak_aqi,
        peak_site=peak_site,
        unhealthy_plus=int((sites["aqi"] > UNHEALTHY_AQI).sum()) if reporting else 0,
        level_counts=tuple(keys.count(c["key"]) for c in AQI_CATEGORIES),
        mean_change=Change(mean, p_mean),
        peak_change=Change(peak, p_peak),
    )


@lru_cache(maxsize=16)
def _daily_max_aqi(season: str, pollutant: str) -> pd.Series:
    """Highest monitor AQI per day of the season (NaN where nothing reported)."""
    days = SEASON_DAYS[season]
    return pd.Series([site_values(season, d, pollutant)["aqi"].max() for d in days], index=days, dtype=float)


def population_weighted(means: pd.Series, pop: pd.Series) -> float | None:
    """Σ(mean · pop) / Σ(pop) over counties with a value; None if no county reported."""
    ok = means.notna() & pop.notna()
    if not ok.any():
        return None
    return float((means[ok] * pop[ok]).sum() / pop[ok].sum())


@lru_cache(maxsize=1024)
def exposure_stats(season: str, day: str, pollutant: str) -> ExposureStats:
    means = county_means(season, day, pollutant)
    pop = population(season)
    weighted = population_weighted(means, pop)
    county_aqi = county_aqi_matrix(season, pollutant).loc[day]

    daily_max = _daily_max_aqi(season, pollutant).loc[:day]
    smoke = county_smoke(season, day)
    available = smoke.notna().any()
    return ExposureStats(
        season=season,
        day=day,
        pollutant=pollutant,
        pop_weighted=weighted,
        pop_weighted_aqi=aqi(weighted, pollutant),
        pop_covered=int(pop[means.notna()].sum()),
        pop_usg_plus=int(pop[(county_aqi > USG_AQI).fillna(False).astype(bool)].sum()),
        days_unhealthy=int((daily_max > UNHEALTHY_AQI).sum()),
        days_elapsed=len(daily_max),
        smoke_counties=tuple(int((smoke == lvl).sum()) for lvl in SMOKE_LEVELS),
        pop_smoke=int(pop[(smoke >= 2).fillna(False).astype(bool)].sum()),
        smoke_available=bool(available),
    )
