"""Domain stats over the real snapshot — invariants rather than hard-coded figures,
plus a few well-documented events the data must reflect (Sep 2020 smoke crisis)."""

import pandas as pd
import pytest

from config import SEASONS, UNHEALTHY_AQI
from utils.data import COUNTY_FIPS, SEASON_DAYS, county_means, peak_day, site_values
from utils.stats import Change, air_stats, exposure_stats, population_weighted, previous_day

ALL_DAYS = [(s, d) for s in SEASONS for d in SEASON_DAYS[s]]


def test_season_windows_cover_every_calendar_day():
    for season, meta in SEASONS.items():
        days = SEASON_DAYS[season]
        assert days[0] == meta["start"] and days[-1] == meta["end"]
        assert len(days) == len(set(days)) == (pd.Timestamp(meta["end"]) - pd.Timestamp(meta["start"])).days + 1


def test_2020_peak_day_is_in_the_september_smoke_crisis():
    # Statewide PM2.5 peaked in the second week of September 2020 (Creek / North Complex / August Complex).
    assert "2020-09-07" <= peak_day("2020") <= "2020-09-20"
    s = air_stats("2020", peak_day("2020"), "pm25")
    assert s.unhealthy_plus > 10
    assert s.peak > 150


@pytest.mark.parametrize(("season", "day"), ALL_DAYS[::9])
def test_level_counts_cover_every_reporting_monitor(season, day):
    for pollutant in ("pm25", "ozone"):
        s = air_stats(season, day, pollutant)
        assert sum(s.level_counts) == s.reporting
        assert s.unhealthy_plus == sum(s.level_counts[3:])
        if s.has_data:
            assert s.peak >= s.mean
            assert s.peak_site


def test_unhealthy_days_are_cumulative():
    days = SEASON_DAYS["2020"]
    counts = [exposure_stats("2020", d, "pm25").days_unhealthy for d in days]
    assert counts == sorted(counts)
    assert counts[-1] <= len(days)
    # Every counted day must really have a monitor above AQI 150.
    over = [d for d in days if (site_values("2020", d, "pm25")["aqi"] > UNHEALTHY_AQI).any()]
    assert counts[-1] == len(over)


def test_population_weighted_mean():
    means = pd.Series([10.0, 30.0, None], index=["a", "b", "c"])
    pop = pd.Series([100, 300, 1_000_000], index=["a", "b", "c"])
    assert population_weighted(means, pop) == pytest.approx(25.0)
    assert population_weighted(pd.Series([None], index=["a"], dtype=float), pd.Series([1], index=["a"])) is None


def test_exposure_population_is_bounded_by_monitored_counties():
    day = peak_day("2020")
    e = exposure_stats("2020", day, "pm25")
    assert 0 < e.pop_usg_plus <= e.pop_covered
    assert e.pop_weighted_aqi is not None and e.pop_weighted_aqi > 100
    assert sum(e.smoke_counties) <= len(COUNTY_FIPS)


def test_county_means_align_to_all_counties():
    means = county_means("2021", "2021-08-25", "pm25")
    assert means.index.tolist() == COUNTY_FIPS
    assert means.notna().sum() > 20


def test_previous_day():
    assert previous_day("2020", "2020-08-01") is None
    assert previous_day("2020", "2020-09-01") == "2020-08-31"


def test_results_are_memoised_and_immutable():
    a = air_stats("2020", "2020-09-10", "pm25")
    assert air_stats("2020", "2020-09-10", "pm25") is a
    with pytest.raises(AttributeError):
        a.mean = 0  # frozen dataclass


@pytest.mark.parametrize(
    ("current", "previous", "direction", "pct"),
    [(10, 5, "up", 100.0), (5, 10, "down", -50.0), (3, 3, "flat", 0.0), (4, 0, "up", None), (None, 2, "na", None)],
)
def test_change(current, previous, direction, pct):
    ch = Change(current, previous)
    assert ch.direction == direction
    assert ch.pct == (pytest.approx(pct) if pct is not None else None)
