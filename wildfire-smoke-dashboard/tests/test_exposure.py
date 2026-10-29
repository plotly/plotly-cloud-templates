"""Vulnerable & exposed ranking + smoke-day counting."""

import pandas as pd
import pytest

from config import AQI_CATEGORIES, SEASONS
from utils.data import COUNTY_FIPS, SEASON_DAYS, smoke_days_to_date, smoke_matrix
from utils.exposure import category_days, vulnerability_score, vulnerability_table


def test_score_scales_top_county_to_100():
    asthma = pd.Series([50.0, 25.0, None, 10.0])
    days = pd.Series([10, 40, 30, 0])
    score = vulnerability_score(asthma, days)
    assert score.tolist()[:2] == [50.0, 100.0]
    assert pd.isna(score[2])
    assert score[3] == 0


def test_score_without_any_smoke_is_zero():
    assert vulnerability_score(pd.Series([10.0, 20.0]), pd.Series([0, 0])).tolist() == [0, 0]


@pytest.mark.parametrize("season", list(SEASONS))
def test_table_has_every_county_ranked(season):
    t = vulnerability_table(season, "pm25", 2, "all")
    assert sorted(t["fips"]) == COUNTY_FIPS
    scored = t["score"].dropna()
    assert scored.tolist() == sorted(scored, reverse=True)
    assert t["score"].isna().sum() == t.loc[t["score"].isna(), "asthma_rate"].isna().sum()
    assert (t["smoke_days"] <= len(SEASON_DAYS[season])).all()


def test_stricter_threshold_never_adds_smoke_days():
    any_ = vulnerability_table("2020", "pm25", 1, "all").set_index("fips")["smoke_days"]
    heavy = vulnerability_table("2020", "pm25", 3, "all").set_index("fips")["smoke_days"]
    assert (heavy.reindex(any_.index) <= any_).all()
    assert any_.max() > 0


def test_smoke_days_to_date_reaches_season_total():
    last = SEASON_DAYS["2021"][-1]
    total = (smoke_matrix("2021") >= 2).sum()
    assert smoke_days_to_date("2021", last, 2).equals(total.astype(int))


def test_category_days_never_exceed_monitored_days():
    days = category_days("2020", "pm25")
    assert list(days.columns) == [c["key"] for c in AQI_CATEGORIES]
    t = vulnerability_table("2020", "pm25", 2, "all").set_index("fips")
    assert (days.sum(axis=1) == t.loc[days.index, "monitored_days"]).all()
