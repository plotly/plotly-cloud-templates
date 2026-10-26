"""Time Series figure — county-mean concentration lines over AQI bands, with a smoke strip.

Row 1: one line per selected county + the population-weighted statewide mean,
       drawn over faint horizontal bands at the AQI category breakpoints.
Row 2: a heatmap strip (county × day) of the NOAA HMS smoke level, so smoke days
       line up with the concentration spikes above them.

Layout contract (Patched by callbacks/timeseries.py):
    layout.shapes[0] = selected-day highlight band
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import AQI_CATEGORIES, POLLUTANTS, SMOKE_LEVELS, STATE_LINE_COLOR, TS_COLORS
from theme import SLATE
from utils.chart_theme import CHART_TEMPLATE
from utils.data import COUNTY_NAMES, SEASON_DAYS
from utils.timeseries import county_series, padded_max, smoke_strip, statewide_series

TS_GRAPH_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d"],
    "toImageButtonOptions": {"filename": "wildfire-smoke-time-series", "scale": 2},
}

HALF_DAY = pd.Timedelta(hours=12)
HIGHLIGHT_FILL = "rgba(41, 76, 96, 0.10)"  # charcoal-blue
BAND_OPACITY = 0.10
SMOKE_SCALE = [
    [0.0, "#ffffff"], [0.125, "#ffffff"],
    [0.125, SMOKE_LEVELS[1]["color"]], [0.5, SMOKE_LEVELS[1]["color"]],
    [0.5, SMOKE_LEVELS[2]["color"]], [0.75, SMOKE_LEVELS[2]["color"]],
    [0.75, SMOKE_LEVELS[3]["color"]], [1.0, SMOKE_LEVELS[3]["color"]],
]  # fmt: skip
SMOKE_NAMES = {0: "None", 1: "Light", 2: "Medium", 3: "Heavy"}


def day_window(day: str) -> list[str]:
    """[start, end] of the 24-h slot centred on a day's marker."""
    d = pd.Timestamp(day)
    return [(d - HALF_DAY).isoformat(), (d + HALF_DAY).isoformat()]


def highlight_shape(day: str | None) -> dict:
    x0, x1 = day_window(day) if day else ("2000-01-01", "2000-01-01")
    return {
        "type": "rect",
        "xref": "x",
        "yref": "paper",
        "x0": x0,
        "x1": x1,
        "y0": 0,
        "y1": 1,
        "fillcolor": HIGHLIGHT_FILL,
        "line": {"width": 0},
        "layer": "below",
        "visible": bool(day),
    }


def aqi_bands(pollutant: str, y_top: float) -> list[dict]:
    """One faint band per AQI category, in concentration units, clipped to the y-range."""
    shapes = []
    for (c_lo, c_hi, _i_lo, _i_hi), cat in zip(POLLUTANTS[pollutant]["breakpoints"], AQI_CATEGORIES):
        if c_lo >= y_top:
            break
        shapes.append(
            {
                "type": "rect",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": c_lo,
                "y1": min(c_hi, y_top),
                "fillcolor": cat["color"],
                "opacity": BAND_OPACITY,
                "line": {"width": 0},
                "layer": "below",
            }
        )
    return shapes


def build_timeseries_figure(season: str, pollutant: str, counties: list[str], selected_day: str | None) -> go.Figure:
    meta = POLLUTANTS[pollutant]
    unit, dec = meta["unit"], meta["decimals"]
    days = SEASON_DAYS[season]
    counties = counties or []

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)

    state = statewide_series(season, pollutant)
    fig.add_trace(
        go.Scatter(
            x=days,
            y=state.round(dec + 1).tolist(),
            name="California (pop-weighted)",
            mode="lines",
            line={"color": STATE_LINE_COLOR, "width": 2, "dash": "dot"},
            hovertemplate=f"California  %{{y:.{dec}f}} {unit}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    lines = county_series(season, pollutant, counties)
    for i, fips in enumerate(counties):
        color = TS_COLORS[i % len(TS_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=days,
                y=lines[fips].round(dec + 1).tolist(),
                name=COUNTY_NAMES[fips],
                mode="lines",
                line={"color": color, "width": 2.2},
                connectgaps=False,
                hovertemplate=f"{COUNTY_NAMES[fips]}  %{{y:.{dec}f}} {unit}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    if counties:
        strip = smoke_strip(season, counties)
        names = [COUNTY_NAMES[f] for f in counties]
        fig.add_trace(
            go.Heatmap(
                x=days,
                y=names,
                z=strip.T.values.tolist(),
                zmin=0,
                zmax=3,
                colorscale=SMOKE_SCALE,
                showscale=False,
                xgap=1,
                ygap=2,
                customdata=strip.T.map(lambda v: "no HMS data" if pd.isna(v) else SMOKE_NAMES[int(v)]).values.tolist(),
                hovertemplate="%{y} smoke  %{customdata}<extra></extra>",
                name="Smoke",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    y_top = padded_max(pd.concat([lines, state.rename("state")], axis=1), floor=meta["breakpoints"][1][1])
    annotations = []
    if lines.isna().all().all() and counties:
        annotations.append(
            {
                "text": "No monitor data for the selected counties",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.6,
                "showarrow": False,
                "font": {"size": 13, "color": SLATE[6]},
            }
        )

    fig.update_layout(
        template=CHART_TEMPLATE,
        autosize=True,
        hovermode="x unified",
        hoverlabel={"font": {"size": 12}},
        margin={"l": 64, "r": 16, "t": 16, "b": 36},
        legend={"orientation": "h", "yanchor": "top", "y": -0.08, "x": 0, "font": {"size": 11}},
        shapes=[highlight_shape(selected_day), *aqi_bands(pollutant, y_top)],
        annotations=annotations,
        uirevision=f"ts-{season}",
        yaxis={"title": {"text": f"{meta['long']} ({unit})"}, "range": [0, y_top], "zeroline": False},
        yaxis2={"showgrid": False, "fixedrange": True, "autorange": "reversed", "tickfont": {"size": 10}},
        xaxis2={"type": "date", "tickformat": "%b %-d", "hoverformat": "%a %b %-d, %Y", "showgrid": False},
        xaxis={"type": "date", "showgrid": False, "hoverformat": "%a %b %-d, %Y"},
    )
    return fig
