"""Map + legend callbacks. The map is only ever Patched, so the county GeoJSON is sent once."""

from dash import Input, Output, Patch, State, callback

from components.map_panel import aqi_legend, choro_legend, map_context_text
from config import SEASONS
from utils.map_figure import CHORO, apply_map_state, choropleth_values, map_state


@callback(
    Output("map", "figure"),
    Input("selection", "data"),
    Input("pollutant", "value"),
    Input("choro-metric", "value"),
    Input("show-smoke", "checked"),
    Input("show-fires", "checked"),
    Input("smoke-threshold", "value"),
    Input("asthma-age", "value"),
    State("choro-opacity", "value"),
    prevent_initial_call=True,  # initial figure is built with the same defaults
)
def update_map(selection, pollutant, choro, show_smoke, show_fires, threshold, age, opacity):
    patch = Patch()
    apply_map_state(
        patch,
        map_state(selection["season"], selection["day"], pollutant, choro, show_smoke, show_fires, int(threshold), age, opacity),
    )
    return patch


@callback(
    Output("map", "figure", allow_duplicate=True),
    Output("choro-opacity-label", "children"),
    Input("choro-opacity", "value"),
    prevent_initial_call=True,
)
def update_opacity(opacity):
    patch = Patch()
    patch["data"][CHORO]["marker"]["opacity"] = opacity
    return patch, f"{opacity:.0%}"


@callback(
    Output("legend-choro", "children"),
    Output("legend-aqi", "children"),
    Output("map-context", "children"),
    Output("season-badge", "children"),
    Input("selection", "data"),
    Input("pollutant", "value"),
    Input("choro-metric", "value"),
    Input("smoke-threshold", "value"),
    Input("asthma-age", "value"),
    prevent_initial_call=True,
)
def update_legend(selection, pollutant, choro, threshold, age):
    season, day = selection["season"], selection["day"]
    z = choropleth_values(choro, season, day, pollutant, int(threshold), age)
    z_max = float(z.max()) if z.notna().any() else None
    return (
        choro_legend(choro, season, z_max, age),
        aqi_legend(pollutant),
        map_context_text(season, day, pollutant),
        SEASONS[season]["label"],
    )
