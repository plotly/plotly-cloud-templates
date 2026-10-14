"""
App callbacks
"""
import datashader as ds
import pandas as pd
from dash import Input, Output, State, callback, ctx, no_update
from dash.exceptions import PreventUpdate

from dash_opencellid import data
from dash_opencellid.data import get_dataset
from dash_opencellid.figures import (
    MAX_POINTS,
    build_created_histogram,
    build_map,
    build_radio_histogram,
    build_range_histogram,
)
from dash_opencellid.theme import RADIO_CATEGORIES
from dash_opencellid.utils import epsg_4326_to_3857

# Size of the Datashader image rendered for the map
MAP_IMAGE_SIZE = (900, 450)


@callback(
    Output("data-status", "children"),
    Output("data-status-card", "style"),
    Output("data-loader", "style"),
    Output("data-ready", "data"),
    Output("data-poll", "disabled"),
    Input("data-poll", "n_intervals"),
)
def poll_data_status(_):
    """Show the dataset loading progress until it is ready"""
    if data.is_ready():
        return no_update, {"display": "none"}, no_update, True, True
    if data.error is not None:
        # Stop polling, but keep the error on screen
        return data.status, None, {"display": "none"}, False, True
    return data.status, None, None, False, False


@callback(
    Output("map-graph", "relayoutData"),
    Output("radio-histogram", "selectedData"),
    Output("range-histogram", "selectedData"),
    Output("created-histogram", "selectedData"),
    Input("reset-map", "n_clicks"),
    Input("clear-radio", "n_clicks"),
    Input("clear-range", "n_clicks"),
    Input("clear-created", "n_clicks"),
    Input("clear-all", "n_clicks"),
    prevent_initial_call=True,
)
def clear_selections(*_):
    """Clear the selection of the panel whose button was clicked, or all of them"""
    targets = ["reset-map", "clear-radio", "clear-range", "clear-created"]
    if ctx.triggered_id == "clear-all":
        return [None] * len(targets)
    return [None if target == ctx.triggered_id else no_update for target in targets]


def _map_view(relayout_data):
    """
    Return the map's visible area as [[lon0, lat0], [lon1, lat1]] (clipped to the
    data), and the center/zoom to display, or None for the default world view
    """
    coordinates = (relayout_data or {}).get("map._derived", {}).get("coordinates")
    if not coordinates:
        return None, None
    data_4326 = get_dataset("data_4326")
    lons, lats = zip(*coordinates)
    bounds = [
        [max(min(lons), data_4326[0][0]), max(min(lats), data_4326[0][1])],
        [min(max(lons), data_4326[1][0]), min(max(lats), data_4326[1][1])],
    ]
    view = {
        "zoom": relayout_data.get("map.zoom"),
        "center": relayout_data.get("map.center"),
    }
    return bounds, view


def _histogram_selection(selected_data):
    """Return the (start, end) of a histogram's box selection, or None"""
    if not selected_data or "range" not in selected_data:
        return None
    start, end = selected_data["range"]["x"]
    return (start, end) if start <= end else (end, start)


@callback(
    Output("selected-count", "children"),
    Output("selected-share", "children"),
    Output("selected-progress", "value"),
    Output("selected-count-skeleton", "visible"),
    Output("map-graph", "figure"),
    Output("radio-histogram", "figure"),
    Output("range-histogram", "figure"),
    Output("created-histogram", "figure"),
    Input("map-graph", "relayoutData"),
    Input("radio-histogram", "selectedData"),
    Input("range-histogram", "selectedData"),
    Input("created-histogram", "selectedData"),
    Input("data-ready", "data"),
    State("reset-map", "n_clicks"),
    State("clear-all", "n_clicks"),
)
def update_plots(
    relayout_data,
    selected_radio,
    selected_range,
    selected_created,
    data_ready,
    reset_map_clicks,
    clear_all_clicks,
):
    if not data_ready or not data.wait_until_ready(timeout=20):
        raise PreventUpdate

    bounds_4326, view = _map_view(relayout_data)
    if (
        set(ctx.triggered_prop_ids) == {"map-graph.relayoutData"}
        and relayout_data is not None
        and bounds_4326 is None
    ):
        # A map event that doesn't move the view (e.g. a resize). Only skip it when it
        # is the sole trigger: on page load it can arrive together with data-ready, and
        # skipping then would leave the charts empty.
        raise PreventUpdate

    df = get_dataset("cell_towers_df")
    if bounds_4326 is None:
        bounds_4326 = get_dataset("data_4326")
        bounds_3857 = get_dataset("data_3857")
        center = get_dataset("data_center_4326")[0]
        view = {
            "zoom": 0.6,
            "pitch": 0,
            "bearing": 0,
            "center": {"lon": center[0], "lat": center[1]},
        }
    else:
        bounds_3857 = epsg_4326_to_3857(bounds_4326)
    (x0, y0), (x1, y1) = bounds_3857

    # Rows matching the signal range and year added selections
    mask = None
    range_slice = created_slice = slice(None, None)
    log10_range = _histogram_selection(selected_range)
    if log10_range:
        range_slice = slice(*log10_range)
        mask = df["log10_range"].between(*log10_range)
    created = _histogram_selection(selected_created)
    if created:
        created = pd.to_datetime(list(created)).as_unit("ns")
        created_slice = slice(*created)
        created_mask = df["created"].between(*created.asi8)
        mask = created_mask if mask is None else mask & created_mask

    # Selected radio technologies, out of those in the dataset
    available = get_dataset("total_radio_counts").index
    if selected_radio and selected_radio.get("points"):
        selected = {point["customdata"] for point in selected_radio["points"]}
    else:
        selected = set(RADIO_CATEGORIES)
    radios = [radio for radio in available if radio in selected]

    # Count the towers in view of each radio technology
    map_columns = ["x_3857", "y_3857", "radio"]
    towers = df[map_columns] if mask is None else df.loc[mask, map_columns]
    canvas = ds.Canvas(
        plot_width=MAP_IMAGE_SIZE[0],
        plot_height=MAP_IMAGE_SIZE[1],
        x_range=(x0, x1),
        y_range=(y0, y1),
    )
    agg = canvas.points(towers, x="x_3857", y="y_3857", agg=ds.count_cat("radio"))
    agg = agg.sel(radio=radios)
    n_selected = int(agg.sum())

    # Few enough towers in view to draw each one with a tooltip
    points = None
    if 0 < n_selected <= MAX_POINTS:
        in_view = (
            df["x_3857"].between(x0, x1)
            & df["y_3857"].between(y0, y1)
            & df["radio"].isin(radios)
        )
        points = df[in_view if mask is None else in_view & mask]

    # Clicking a reset button changes uirevision, which recenters the map
    uirevision = (reset_map_clicks or 0) + (clear_all_clicks or 0)
    map_figure = build_map(
        view, bounds_4326, agg if n_selected else None, points, uirevision
    )

    # Histograms of the selection, from the pre-computed range/created/radio counts
    counts = get_dataset("range_created_radio_agg")
    radio_histogram = build_radio_histogram(
        get_dataset("total_radio_counts"),
        counts.sel(log10_range=range_slice, created=created_slice)
        .sum(["log10_range", "created"])
        .to_series(),
        selected_radio,
    )
    range_histogram = build_range_histogram(
        get_dataset("total_range_counts"),
        counts.sel(radio=radios, created=created_slice)
        .sum(["radio", "created"])
        .to_series(),
        selected_range,
    )
    created_histogram = build_created_histogram(
        get_dataset("total_created_counts"),
        counts.sel(radio=radios, log10_range=range_slice)
        .sum(["radio", "log10_range"])
        .to_series(),
        selected_created,
    )

    total = len(df)
    share = n_selected / total * 100 if total else 0
    share_text = "<0.1%" if 0 < share < 0.1 else f"{share:.1f}%"
    return (
        f"{n_selected:,}",
        f"{share_text} of {total:,} towers",
        share,
        False,
        map_figure,
        radio_histogram,
        range_histogram,
        created_histogram,
    )
