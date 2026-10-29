"""Time Series callbacks.

- update_timeseries: full rebuild when season / pollutant / counties change (payload is small).
- highlight_day: Patch only the highlight shape, so playback never rebuilds the figure.
- reset_counties: each season opens on counties that were hit hard that season.
Clicking the chart selects a day via callbacks/day.py:set_day (single writer).
"""

from dash import Input, Output, Patch, State, callback

from components.timeseries_tab import smoke_summary, ts_subtitle
from config import DEFAULT_TS_COUNTIES_BY_SEASON, MAX_TS_COUNTIES
from utils.timeseries_figure import build_timeseries_figure, highlight_shape


@callback(
    output=dict(
        figure=Output("ts-graph", "figure"),
        subtitle=Output("ts-subtitle", "children"),
        summary=Output("ts-smoke-summary", "children"),
    ),
    inputs=dict(
        season=Input("season", "value"),
        pollutant=Input("pollutant", "value"),
        counties=Input("ts-counties", "value"),
        threshold=Input("smoke-threshold", "value"),
        selection=State("selection", "data"),
    ),
    prevent_initial_call=True,  # timeseries_view() seeds the same figure
)
def update_timeseries(season: str, pollutant: str, counties: list[str], threshold: str, selection: dict) -> dict:
    """County-mean lines + statewide mean over AQI bands, with the HMS smoke strip below."""
    counties = (counties or [])[:MAX_TS_COUNTIES]
    day = selection["day"] if selection["season"] == season else None
    return {
        "figure": build_timeseries_figure(season, pollutant, counties, day),
        "subtitle": ts_subtitle(season, pollutant),
        "summary": smoke_summary(season, counties, int(threshold)),
    }


@callback(
    Output("ts-counties", "value"),
    Input("season", "value"),
    prevent_initial_call=True,
)
def reset_counties(season: str) -> list[str]:
    return DEFAULT_TS_COUNTIES_BY_SEASON[season]


@callback(
    Output("ts-graph", "figure", allow_duplicate=True),
    Input("selection", "data"),
    prevent_initial_call=True,
)
def highlight_day(selection: dict):
    """Keep the highlight band on the selected day (map navigation, playback, clicks)."""
    shape = highlight_shape(selection["day"])
    patch = Patch()
    for key in ("x0", "x1", "visible"):
        patch["layout"]["shapes"][0][key] = shape[key]
    return patch
