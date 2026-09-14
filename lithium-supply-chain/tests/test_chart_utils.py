import pytest

from utils import chart_utils
from .mock_data import spod_df, supply_df, test_links


@pytest.fixture
def get_supply_df():
    return supply_df


@pytest.fixture
def get_spod_df():
    return spod_df


@pytest.fixture
def get_links():
    return test_links


def test_generate_sankey_data(get_supply_df, get_spod_df, get_links):
    columns = ["Resource 1", "Product"]
    year = "2023"
    view_top = "view_all"
    (
        labels,
        sources,
        targets,
        values,
        link_colors,
        node_colors,
    ) = chart_utils.generate_sankey_data(
        columns, get_supply_df, year, get_spod_df, view_top
    )
    fn_links = [(a, b) for a, b in zip(sources, targets)]
    test_links = [link[0] for link in get_links]
    nb_test_links = len(test_links)
    assert len(labels) == len(node_colors)
    assert len(sources) == nb_test_links
    assert len(targets) == nb_test_links
    assert len(values) == nb_test_links
    assert sorted(sources) == sorted([val[0][0] for val in get_links])
    assert fn_links.sort() == test_links.sort()
    assert sum(values) == sum([val[1] for val in get_links])
    assert len(link_colors) == nb_test_links
