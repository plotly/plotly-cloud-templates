"""Callback glue — called directly with a faked callback context (Dash testing pattern)."""

from contextvars import copy_context

import dash_mantine_components as dmc
from dash import Patch, no_update
from dash._callback_context import context_value
from dash._utils import AttributeDict

dmc.add_figure_templates()  # figure builders use the "mantine_light" template

from callbacks.day import day_from_click, set_day  # noqa: E402
from callbacks.map_view import update_legend, update_map  # noqa: E402
from callbacks.stat_cards import to_outputs  # noqa: E402
from components.stat_cards import air_view, exposure_view, stats_column  # noqa: E402
from config import AQI_CATEGORIES, SEASONS  # noqa: E402
from utils.data import SEASON_DAYS, peak_day  # noqa: E402
from utils.map_figure import BUBBLE_TRACES, CHORO, build_base_map, map_state  # noqa: E402
from utils.stats import air_stats, exposure_stats  # noqa: E402
from utils.timeseries_figure import build_timeseries_figure  # noqa: E402


def _run(func, trigger: str, *args):
    def inner():
        context_value.set(AttributeDict(triggered_inputs=[{"prop_id": trigger, "value": 1}]))
        return func(*args)

    return copy_context().run(inner)


def _slot(type_, key, prop="children"):
    return {"id": {"type": type_, "key": key}, "property": prop}


def test_to_outputs_orders_pattern_outputs_by_key():
    view = {"kpis": {"mean": "12.0", "peak": "200.1", "reporting": "140"}, "subtitle": "x"}
    grouping = {
        "kpis": [_slot("aq-kpi", "peak"), _slot("aq-kpi", "reporting"), _slot("aq-kpi", "mean")],
        "subtitle": {"id": "aq-subtitle", "property": "children"},
    }
    assert to_outputs(view, grouping) == {"kpis": ["200.1", "140", "12.0"], "subtitle": "x"}


def test_views_have_a_value_for_every_slot():
    air = air_view(air_stats("2020", "2020-09-12", "pm25"))
    assert set(air["kpis"]) == {"reporting", "unhealthy", "mean", "peak"}
    assert set(air["levels"]) == {c["key"] for c in AQI_CATEGORIES}
    ex = exposure_view(exposure_stats("2020", "2020-09-12", "pm25"))
    assert set(ex["kpis"]) == {"popmean", "popusg", "days", "popsmoke"}
    assert set(ex["smoke_levels"]) == {"1", "2", "3"}


def test_layout_is_seeded_with_real_values():
    day = peak_day("2020")
    layout = str(stats_column("2020", day).to_plotly_json())
    assert air_view(air_stats("2020", day, "pm25"))["kpis"]["mean"] in layout


def test_set_day_next_and_season_switch():
    current = {"season": "2020", "day": "2020-09-12"}
    out = _run(set_day, "day-next.n_clicks", "2020", None, 0, 1, 0, 0, 0, None, 0, current)
    assert out[0] == {"season": "2020", "day": "2020-09-13"}
    assert out[1] == SEASON_DAYS["2020"].index("2020-09-13")

    out = _run(set_day, "season.value", "2025", None, 0, 0, 0, 0, 0, None, 0, current)
    assert out[0] == {"season": "2025", "day": peak_day("2025")}
    assert out[2] == len(SEASON_DAYS["2025"]) - 1  # slider max follows the season


def test_set_day_tick_stops_at_end():
    last = SEASON_DAYS["2021"][-1]
    out = _run(set_day, "playback-interval.n_intervals", "2021", None, 0, 0, 0, 0, 0, None, 5, {"season": "2021", "day": last})
    assert out[0] is no_update
    assert out[-2] is True  # interval disabled


def test_day_from_click_clamps_into_season():
    assert day_from_click("2025", {"points": [{"x": "2025-01-09 06:00"}]}) == "2025-01-09"
    assert day_from_click("2025", {"points": [{"x": "2026-01-01"}]}) == SEASON_DAYS["2025"][-1]
    assert day_from_click("2025", None) is None


def test_update_map_returns_patch_and_state_is_consistent():
    sel = {"season": "2020", "day": "2020-09-10"}
    assert isinstance(update_map(sel, "pm25", "aq_mean", True, True, "2", "all", 0.6), Patch)
    state = map_state("2020", "2020-09-10", "pm25", "smoke_days")
    n_sites = len(state[2]["lat"])  # halo has one point per monitor
    assert n_sites == sum(len(state[i]["lat"]) for i in BUBBLE_TRACES)
    assert len(state[CHORO]["z"]) == 58
    assert any(layer["type"] == "fill" for layer in state["layers"])  # smoke and/or fire layers


def test_base_map_and_figures_build_for_every_season():
    for season in SEASONS:
        day = peak_day(season)
        assert len(build_base_map(season, day).data) == 3 + len(AQI_CATEGORIES)
        fig = build_timeseries_figure(season, "ozone", ["06037", "06019"], day)
        assert fig.layout.shapes[0].visible
        legend = update_legend({"season": season, "day": day}, "pm25", "asthma", "2", "all")
        assert legend[3] == SEASONS[season]["label"]
