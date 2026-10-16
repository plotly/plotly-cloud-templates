from datetime import date, timedelta
from pathlib import Path

import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback, ctx, dcc, html, no_update
from dash_iconify import DashIconify

app = Dash(
    __name__,
    title="NYC Uber Rides",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
)
server = app.server

FONT = "Inter, sans-serif"
FIRST_DAY = date(2014, 4, 1)
LAST_DAY = date(2014, 9, 30)
NYC_CENTER = {"lat": 40.7272, "lon": -73.991251}

# Notable locations to center the map on
LOCATIONS = {
    "Madison Square Garden": {"lat": 40.7505, "lon": -73.9934},
    "Yankee Stadium": {"lat": 40.8296, "lon": -73.9262},
    "Empire State Building": {"lat": 40.7484, "lon": -73.9857},
    "New York Stock Exchange": {"lat": 40.7069, "lon": -74.0113},
    "JFK Airport": {"lat": 40.644987, "lon": -73.785607},
    "Grand Central Station": {"lat": 40.7527, "lon": -73.9772},
    "Times Square": {"lat": 40.7589, "lon": -73.9851},
    "Columbia University": {"lat": 40.8075, "lon": -73.9626},
    "United Nations HQ": {"lat": 40.7489, "lon": -73.9680},
}

# One color per hour of the day, from early morning (yellow) to late night (purple)
HOUR_COLORS = [
    "#F4EC15", "#DAF017", "#BBEC19", "#9DE81B", "#80E41D", "#66E01F",
    "#4CDC20", "#34D822", "#24D249", "#25D042", "#26CC58", "#28C86D",
    "#29C481", "#2AC093", "#2BBCA4", "#2BB5B8", "#2C99B4", "#2D7EB0",
    "#2D65AC", "#2E4EA4", "#2E38A4", "#3B2FA0", "#4E2F9C", "#603099",
]  # fmt: skip
HOUR_COLORSCALE = [[h / 23, c] for h, c in enumerate(HOUR_COLORS)]


def hour_label(h):
    h %= 24
    return f"{(h - 1) % 12 + 1} {'AM' if h < 12 else 'PM'}"


# Uber pickups in New York City, April-September 2014, sorted by time
# Source: https://github.com/fivethirtyeight/uber-tlc-foil-response
rides = pd.read_parquet(Path(__file__).parent / "data" / "uber_rides.parquet")
DAY = (rides["time"] - pd.Timestamp(FIRST_DAY)).dt.days.to_numpy()
HOUR = rides["time"].dt.hour.to_numpy()
LAT = rides["lat"].to_numpy()
LON = rides["lon"].to_numpy()
N_DAYS = (LAST_DAY - FIRST_DAY).days + 1
# Rows of day d are DAY_START[d]:DAY_START[d + 1]
DAY_START = np.searchsorted(DAY, np.arange(N_DAYS + 1))
# HOURLY[d, h] = number of rides on day d during hour h
HOURLY = np.zeros((N_DAYS, 24), dtype=int)
np.add.at(HOURLY, (DAY, HOUR), 1)
del rides


def icon(name, size=16):
    return DashIconify(icon=f"tabler:{name}", width=size)


def stat_card(label, value_id):
    return dmc.Paper(
        [
            dmc.Text(label, size="xs", c="dimmed", fw=500),
            dmc.Text(id=value_id, className="hero-number"),
        ],
        className="stat-card",
        withBorder=True,
    )


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Title("New York City Uber Rides", order=4),
                    dmc.Text(
                        "4.5 million pickups, April to September 2014",
                        size="xs",
                        c="dimmed",
                        visibleFrom="sm",
                    ),
                ],
                gap=0,
            ),
            html.A(
                html.Img(src=app.get_asset_url("dash-logo-dark.png"), height=32, alt="Plotly"),
                href="https://dash.plotly.com/",
                className="dash-logo",
            ),
        ],
        justify="space-between",
        h="100%",
        px="lg",
        wrap="nowrap",
    )
)

controls = dmc.Paper(
    dmc.Stack(
        [
            dmc.Text(
                "Pick a day to map its pickups, then click or drag across the "
                "hourly chart to focus on certain hours.",
                size="sm",
                c="dimmed",
            ),
            dmc.DatePickerInput(
                id="date",
                label="Day",
                value=FIRST_DAY,
                minDate=FIRST_DAY,
                maxDate=LAST_DAY,
                valueFormat="ddd, MMM D, YYYY",
                leftSection=icon("calendar"),
            ),
            dmc.Select(
                id="location",
                label="Center map on",
                placeholder="All of New York City",
                data=list(LOCATIONS),
                clearable=True,
                searchable=True,
                leftSection=icon("map-pin"),
            ),
            dmc.MultiSelect(
                id="hours",
                label="Hours",
                placeholder="All hours",
                data=[{"value": str(h), "label": hour_label(h)} for h in range(24)],
                value=[],
                clearable=True,
                leftSection=icon("clock"),
                className="hours-select",
            ),
            dmc.Button(
                "Reset all filters",
                id="reset-all",
                variant="default",
                leftSection=icon("restore"),
                fullWidth=True,
                n_clicks=0,
            ),
            html.Div(
                [
                    stat_card("Rides that day", "total-rides"),
                    stat_card("In selected hours", "selected-rides"),
                    stat_card("Busiest hour", "busiest-hour"),
                ],
                className="stat-grid",
            ),
            dcc.Markdown(
                "Data: [FiveThirtyEight](https://github.com/fivethirtyeight/uber-tlc-foil-response)"
                " via the NYC Taxi & Limousine Commission",
                className="source",
                link_target="_blank",
            ),
        ],
        gap="sm",
    ),
    className="card controls",
    withBorder=True,
)

map_card = dmc.Paper(
    [
        html.Div(
            [
                dmc.Text(id="map-title", fw=600, size="sm"),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        icon("focus-centered"),
                        id="reset-view",
                        variant="subtle",
                        color="gray",
                        n_clicks=0,
                    ),
                    label="Reset map view",
                ),
            ],
            className="card-head",
        ),
        dcc.Graph(
            id="map",
            className="map-graph",
            config={"displaylogo": False, "scrollZoom": True, "responsive": True},
        ),
    ],
    className="card map-card",
    withBorder=True,
)

hist_card = dmc.Paper(
    [
        html.Div(
            [
                dmc.Text("Rides by hour", fw=600, size="sm"),
                dmc.Text(
                    "Click a bar to toggle it, drag to select a range, double-click to clear",
                    size="xs",
                    c="dimmed",
                    visibleFrom="sm",
                ),
            ],
            className="card-head",
        ),
        dcc.Graph(
            id="histogram",
            className="histogram-graph",
            config={"displayModeBar": False, "responsive": True},
        ),
    ],
    className="card hist-card",
    withBorder=True,
)

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [
            header,
            dmc.AppShellMain(
                html.Div(
                    [controls, html.Div([map_card, hist_card], className="charts")],
                    className="page",
                )
            ),
        ],
        header={"height": 60},
    ),
    theme={
        "fontFamily": FONT,
        "headings": {"fontFamily": FONT},
        "primaryColor": "indigo",
        "defaultRadius": "md",
    },
    forceColorScheme="dark",
)


def selected_hours(hours):
    """Hours to show, as a sorted list of ints; no selection means all hours."""
    return sorted(int(h) for h in hours) if hours else list(range(24))


def describe_hours(hours):
    if len(hours) == 24:
        return "all hours"
    if hours == list(range(hours[0], hours[-1] + 1)) and len(hours) > 2:
        return f"{hour_label(hours[0])} to {hour_label(hours[-1] + 1)}"
    return ", ".join(hour_label(h) for h in hours)


@callback(
    Output("hours", "value"),
    Input("histogram", "clickData"),
    Input("histogram", "selectedData"),
    State("hours", "value"),
    prevent_initial_call=True,
)
def select_hours_from_histogram(click, selection, hours):
    if "histogram.clickData" in ctx.triggered_prop_ids:
        if not click:
            return no_update
        hour = str(int(click["points"][0]["x"]))
        return sorted(set(hours or []) ^ {hour}, key=int)
    # Double-clicking the chart clears the selection
    if not selection or not selection.get("points"):
        return []
    return sorted({str(int(p["x"])) for p in selection["points"]}, key=int)


@callback(
    Output("date", "value"),
    Output("location", "value"),
    Output("hours", "value", allow_duplicate=True),
    Output("histogram", "selectedData"),
    Input("reset-all", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    return FIRST_DAY, None, [], None


@callback(
    Output("total-rides", "children"),
    Output("selected-rides", "children"),
    Output("busiest-hour", "children"),
    Output("histogram", "figure"),
    Input("date", "value"),
    Input("hours", "value"),
)
def update_histogram(day, hours):
    counts = HOURLY[(date.fromisoformat(day) - FIRST_DAY).days]
    shown = selected_hours(hours)
    in_selection = np.isin(np.arange(24), shown)

    fig = go.Figure(
        go.Bar(
            x=list(range(24)),
            y=counts,
            marker={
                "color": HOUR_COLORS,
                "opacity": np.where(in_selection, 1, 0.35),
                "line": {"width": 0},
            },
            customdata=[hour_label(h) for h in range(24)],
            hovertemplate="%{customdata}: <b>%{y:,}</b> rides<extra></extra>",
        )
    )
    fig.update_layout(
        margin={"l": 44, "r": 8, "t": 4, "b": 24},
        bargap=0.12,
        barcornerradius=4,
        dragmode="select",
        selectdirection="h",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT, "size": 11, "color": "#a6a7ab"},
        hoverlabel={"font": {"family": FONT}},
        showlegend=False,
        xaxis={
            "range": [-0.5, 23.5],
            "tickvals": list(range(0, 24, 3)),
            "ticktext": [hour_label(h) for h in range(0, 24, 3)],
            "fixedrange": True,
            "showgrid": False,
        },
        yaxis={"fixedrange": True, "gridcolor": "#373a40", "zeroline": False},
    )

    busiest = int(counts.argmax())
    return (
        f"{counts.sum():,}",
        f"{counts[in_selection].sum():,}",
        f"{hour_label(busiest)} ({counts[busiest]:,})",
        fig,
    )


@callback(
    Output("map", "figure"),
    Output("map-title", "children"),
    Input("date", "value"),
    Input("hours", "value"),
    Input("location", "value"),
    Input("reset-view", "n_clicks"),
    Input("reset-all", "n_clicks"),
)
def update_map(day, hours, location, n_reset, n_reset_all):
    picked = date.fromisoformat(day)
    d = (picked - FIRST_DAY).days
    rows = slice(DAY_START[d], DAY_START[d + 1])
    shown = selected_hours(hours)
    mask = np.isin(HOUR[rows], shown)
    lat, lon, hour = LAT[rows][mask], LON[rows][mask], HOUR[rows][mask]

    fig = go.Figure(
        [
            go.Scattermap(
                lat=lat,
                lon=lon,
                mode="markers",
                marker={
                    "color": hour,
                    "colorscale": HOUR_COLORSCALE,
                    "cmin": 0,
                    "cmax": 23,
                    "size": 5,
                    "opacity": 0.6,
                },
                text=[hour_label(h) for h in hour],
                hovertemplate="Pickup at %{text}<extra></extra>",
            ),
            go.Scattermap(
                lat=[p["lat"] for p in LOCATIONS.values()],
                lon=[p["lon"] for p in LOCATIONS.values()],
                text=list(LOCATIONS),
                mode="markers",
                marker={"size": 11, "color": "#ff6b8b"},
                hovertemplate="<b>%{text}</b><extra></extra>",
            ),
        ]
    )
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        showlegend=False,
        font={"family": FONT},
        map={
            "style": "carto-darkmatter",
            "center": LOCATIONS[location] if location else NYC_CENTER,
            "zoom": 14 if location else 11.8,
        },
        # Keep the user's pan and zoom when the day or hours change
        uirevision=f"{location}-{n_reset}-{n_reset_all}",
    )

    title = f"{mask.sum():,} pickups on {picked:%A, %B} {picked.day}, {describe_hours(shown)}"
    return fig, title


if __name__ == "__main__":
    app.run(debug=True)
