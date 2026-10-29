"""EPA AQI — breakpoint edges from the 2024 Technical Assistance Document."""

import pandas as pd
import pytest

from utils.aqi import aqi, aqi_series, category, category_key


@pytest.mark.parametrize(
    ("conc", "expected"),
    [
        (0.0, 0),
        (9.0, 50),
        (9.1, 51),
        (12.0, 56),  # (100−51)/(35.4−9.1)·(12.0−9.1)+51 = 56.4
        (35.4, 100),
        (35.5, 101),
        (55.4, 150),
        (55.5, 151),
        (125.4, 200),
        (125.5, 201),
        (225.4, 300),
        (225.5, 301),
        (325.4, 500),
        (600.0, 500),  # capped above the last breakpoint
        (35.49, 100),  # truncated to 35.4 before lookup
        (-2.0, 0),  # small negative FEM readings clamp to 0
    ],
)
def test_pm25_breakpoints(conc, expected):
    assert aqi(conc, "pm25") == expected


@pytest.mark.parametrize(
    ("ppb", "expected"),
    [(0, 0), (54, 50), (55, 51), (70, 100), (71, 101), (85, 150), (86, 151), (105, 200), (106, 201), (200, 300), (260, 300)],
)
def test_ozone_breakpoints(ppb, expected):
    assert aqi(ppb, "ozone") == expected


def test_missing_values_stay_missing():
    assert aqi(None, "pm25") is None
    assert aqi(float("nan"), "pm25") is None
    assert category(None) is None
    out = aqi_series(pd.Series([1.0, None, 40.0]), "pm25")
    assert out.isna().tolist() == [False, True, False]


@pytest.mark.parametrize("pollutant", ["pm25", "ozone"])
def test_vectorised_matches_scalar(pollutant):
    grid = pd.Series([x / 10 for x in range(0, 4000, 7)])
    expected = [aqi(v, pollutant) for v in grid]
    assert aqi_series(grid, pollutant).tolist() == expected


@pytest.mark.parametrize(
    ("index", "key"),
    [(0, "good"), (50, "good"), (51, "moderate"), (100, "moderate"), (101, "usg"), (151, "unhealthy"), (201, "very"), (301, "hazardous"), (500, "hazardous")],
)
def test_category_edges(index, key):
    assert category_key(index) == key
