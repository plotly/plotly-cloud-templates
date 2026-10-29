"""California Wildfire Smoke & Respiratory Health Dashboard — Dash + Dash Mantine Components.

Run:  .venv/bin/python app.py   →  http://127.0.0.1:8050
Data: the local snapshot in data/ (rebuild with `.venv/bin/python -I scripts/fetch_data.py`).
"""

import os

import dash_mantine_components as dmc
from dash import Dash, dcc, html

dmc.add_figure_templates()  # registers "mantine_light" before any figure is built

import callbacks  # noqa: E402,F401  (registers @callback functions)
from components.about_tab import about_page  # noqa: E402
from components.header import header  # noqa: E402
from components.map_panel import map_view  # noqa: E402
from components.sidebar import sidebar  # noqa: E402
from components.timeseries_tab import timeseries_view  # noqa: E402
from config import APP_TITLE, DEFAULT_SEASON, DEFAULT_SPEED, DEFAULT_TS_COUNTIES_BY_SEASON, HEADER_HEIGHT, SIDEBAR_WIDTH  # noqa: E402
from theme import THEME  # noqa: E402
from utils.data import peak_day  # noqa: E402

app = Dash(
    __name__,
    title=APP_TITLE,
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700"
        "&family=IBM+Plex+Serif:ital,wght@0,400;0,500;0,600;1,400&display=swap"
    ],
)
server = app.server


def serve_layout() -> dmc.MantineProvider:
    season = DEFAULT_SEASON
    day = peak_day(season)  # open on the season's worst statewide PM2.5 day
    return dmc.MantineProvider(
        [
            dcc.Location(id="url", refresh="callback-nav"),
            dcc.Store(id="page-title"),
            dcc.Store(id="selection", data={"season": season, "day": day}),
            dcc.Interval(id="playback-interval", interval=int(DEFAULT_SPEED), disabled=True),
            dmc.AppShell(
                [
                    header(),
                    sidebar(season, day),
                    dmc.AppShellMain(
                        [
                            html.Div(map_view(season, day), id="panel-map"),
                            html.Div(
                                timeseries_view(season, day, DEFAULT_TS_COUNTIES_BY_SEASON[season]),
                                id="panel-timeseries",
                                style={"display": "none"},
                            ),
                            html.Div(
                                html.Div(about_page(None), id="about-content"),
                                id="panel-about",
                                style={"display": "none"},
                            ),
                        ],
                        bg="papaya.1",
                    ),
                ],
                id="appshell",
                header={"height": HEADER_HEIGHT},
                navbar={"width": SIDEBAR_WIDTH, "breakpoint": "sm", "collapsed": {"mobile": True, "desktop": False}},
                padding=0,
            ),
        ],
        theme=THEME,
        forceColorScheme="light",
    )


app.layout = serve_layout()

if __name__ == "__main__":
    app.run(debug=True, port=8054)
