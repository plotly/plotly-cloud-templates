import pandas as pd
import pytest

from utils import chart_utils, data_utils


def test_get_supply_data():
    df = data_utils.get_supply_data("forecast_version_1")
    assert type(df) == pd.DataFrame
