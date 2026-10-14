"""
Build the Plotly figures displayed by the app
"""
import base64
import io

import datashader.transfer_functions as tf
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dash_opencellid.theme import (
    BAR_SELECTED,
    BAR_TOTAL,
    BAR_UNSELECTED,
    RADIO_CATEGORIES,
    RADIO_COLORS,
    RADIO_LABELS,
    TEMPLATE,
)

# When this many towers or fewer are in view, draw each one as a point with a tooltip
# instead of a Datashader image
MAX_POINTS = 5000

MAP_HEIGHT = 560
HISTOGRAM_HEIGHT = 260
RADIO_HEIGHT = 150


def blank_figure(height):
    """Empty placeholder figure shown until the dataset has loaded"""
    fig = go.Figure(layout={"template": TEMPLATE, "height": height})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _selection_props(selected_data):
    # selectedpoints=False clears the selection drawn on the chart; None keeps it
    return False if selected_data is None else None


def _selections(selected_data):
    """
    The user's box selection, to draw it again on the updated figure. Without it,
    Plotly removes the box when the figure changes and reports an empty selection.
    """
    box = (selected_data or {}).get("range")
    if not box:
        return []
    selection = {"type": "rect", "line": {"width": 1, "dash": "dot"}}
    for axis in ["x", "y"]:
        if axis in box:
            selection.update({f"{axis}ref": axis, f"{axis}0": box[axis][0], f"{axis}1": box[axis][1]})
        else:
            selection.update({f"{axis}ref": "paper", f"{axis}0": 0, f"{axis}1": 1})
    return [selection]


def build_radio_histogram(total_counts, selected_counts, selected_data):
    """Horizontal bar chart of the number of towers of each radio technology"""
    categories = [cat for cat in RADIO_CATEGORIES if cat in total_counts.index]
    labels = [RADIO_LABELS[cat] for cat in categories]
    selectedpoints = _selection_props(selected_data)
    hovertemplate = "%{y}: %{x:,} towers<extra></extra>"

    fig = go.Figure(
        [
            go.Bar(
                x=total_counts.loc[categories].values,
                y=labels,
                customdata=categories,
                orientation="h",
                marker={"color": BAR_TOTAL, "cornerradius": 4},
                selectedpoints=selectedpoints,
                selected={"marker": {"opacity": 1}},
                unselected={"marker": {"opacity": 1}},
                hovertemplate=hovertemplate,
            ),
            go.Bar(
                x=selected_counts.reindex(categories, fill_value=0).values,
                y=labels,
                customdata=categories,
                orientation="h",
                marker={
                    "color": [RADIO_COLORS[cat] for cat in categories],
                    "cornerradius": 4,
                },
                selectedpoints=selectedpoints,
                unselected={"marker": {"opacity": 0.2}},
                hovertemplate=hovertemplate,
            ),
        ]
    )
    fig.update_layout(
        template=TEMPLATE,
        height=RADIO_HEIGHT,
        margin={"l": 8, "r": 8, "t": 0, "b": 0},
        barmode="overlay",
        bargap=0.3,
        showlegend=False,
        dragmode="select",
        selectdirection="v",
        clickmode="event+select",
        selectionrevision=True,
        selections=_selections(selected_data),
    )
    fig.update_xaxes(
        type="log",
        dtick=1,
        range=[0, np.log10(max(total_counts.max(), 1) * 2)],
    )
    fig.update_yaxes(
        type="category",
        categoryorder="array",
        categoryarray=labels[::-1],
        showgrid=False,
        tickfont={"size": 12},
    )
    return fig


def _overlay_histogram(x, total, selected, selected_data, hovertemplate, customdata):
    """Histogram of all towers with the selected towers overlaid on top"""
    selectedpoints = _selection_props(selected_data)
    fig = go.Figure(
        [
            go.Bar(
                x=x,
                y=total,
                customdata=customdata,
                marker={"color": BAR_TOTAL, "cornerradius": 4},
                selectedpoints=selectedpoints,
                unselected={"marker": {"opacity": 1}},
                hovertemplate=hovertemplate,
            ),
            go.Bar(
                x=x,
                y=selected,
                customdata=customdata,
                marker={"color": BAR_SELECTED, "cornerradius": 4},
                selectedpoints=selectedpoints,
                selected={"marker": {"color": BAR_SELECTED, "opacity": 1}},
                unselected={"marker": {"color": BAR_UNSELECTED, "opacity": 0.8}},
                hovertemplate=hovertemplate,
            ),
        ]
    )
    fig.update_layout(
        template=TEMPLATE,
        height=HISTOGRAM_HEIGHT,
        barmode="overlay",
        bargap=0.15,
        showlegend=False,
        dragmode="select",
        selectdirection="h",
        hovermode="closest",
        selectionrevision=True,
        selections=_selections(selected_data),
    )
    fig.update_yaxes(type="log", dtick=1, title_text="Towers (log scale)")
    return fig


def build_range_histogram(total_counts, selected_counts, selected_data):
    """Histogram of the towers' signal range, binned by log10(range)"""
    fig = _overlay_histogram(
        total_counts.index,
        total_counts.values,
        selected_counts.values,
        selected_data,
        "Range ≈ %{customdata:,} m<br>%{y:,} towers<extra></extra>",
        (10 ** total_counts.index).astype("int64"),
    )
    tick_values = np.arange(np.ceil(total_counts.index.min()), total_counts.index.max() + 1)
    fig.update_xaxes(
        title_text="Signal range",
        tickvals=tick_values,
        ticktext=[_format_distance(10**v) for v in tick_values],
    )
    return fig


def _format_distance(meters):
    if meters >= 1000:
        return f"{meters / 1000:,.0f} km"
    return f"{meters:,.0f} m"


def build_created_histogram(total_counts, selected_counts, selected_data):
    """Histogram of the year each tower was added to the database"""
    fig = _overlay_histogram(
        total_counts.index,
        total_counts.values,
        selected_counts.values,
        selected_data,
        "%{x|%Y}<br>%{y:,} towers<extra></extra>",
        None,
    )
    fig.update_xaxes(title_text="Year added")
    return fig


def _shaded_image_uri(agg):
    """Shade a Datashader aggregation into a base64 encoded png"""
    img = tf.shade(agg, color_key=RADIO_COLORS, min_alpha=100).to_pil()
    # Upscale to reduce blurring when the map is zoomed before the next update
    img = img.resize((img.width * 2, img.height * 2))
    buffer = io.BytesIO()
    img.save(buffer, format="png")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _tower_points(towers):
    """Scattermap trace with one point and tooltip per tower"""
    description = towers["Description"].astype(object).fillna("Unknown operator")
    status = towers["Status"].astype(object).fillna("Unknown")
    radio = towers["radio"].astype(str)
    created = pd.to_datetime(towers["created"]).dt.strftime("%b %Y")
    customdata = np.column_stack(
        [
            description.str.slice(0, 30),
            radio.map(RADIO_LABELS).fillna(radio),
            (10 ** towers["log10_range"]).round().astype("int64"),
            towers["mcc"],
            towers["net"],
            created,
            status,
        ]
    )
    return go.Scattermap(
        lat=towers["lat"],
        lon=towers["lon"],
        mode="markers",
        marker={
            "color": radio.map(RADIO_COLORS).fillna(BAR_SELECTED),
            "size": 9,
            "opacity": 0.85,
        },
        customdata=customdata,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]} · %{customdata[6]}<br>"
            "Range: %{customdata[2]:,} m<br>"
            "MCC %{customdata[3]} · MNC %{customdata[4]}<br>"
            "Added %{customdata[5]}<br>"
            "%{lat:.4f}°, %{lon:.4f}°"
            "<extra></extra>"
        ),
    )


def build_map(view, coordinates_4326, agg, towers, uirevision):
    """
    Map of the selected towers: each tower as a point when few are in view (towers is
    not None), otherwise a Datashader image of agg covering coordinates_4326
    """
    layers = []
    if towers is not None:
        trace = _tower_points(towers)
    else:
        # The map needs a trace even when every tower is drawn as an image layer
        trace = go.Scattermap(lat=[], lon=[], hoverinfo="skip")
        if agg is not None:
            (lon0, lat0), (lon1, lat1) = coordinates_4326
            layers.append(
                {
                    "sourcetype": "image",
                    "source": _shaded_image_uri(agg),
                    "coordinates": [
                        [lon0, lat1],
                        [lon1, lat1],
                        [lon1, lat0],
                        [lon0, lat0],
                    ],
                }
            )

    fig = go.Figure(trace)
    fig.update_layout(
        template=TEMPLATE,
        height=MAP_HEIGHT,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        showlegend=False,
        # Keep the user's pan/zoom across updates; a new value resets the view
        uirevision=uirevision,
        map={"style": "carto-positron", "layers": layers, **view},
    )
    return fig
