"""
Explorer page — port of the "Drill-Hole Cross-Section Explorer" CodePen.

Dash owns the page shell only. The chart (4-hole subplots, multi-axis spanning
geological bands) and all hover/click interactivity are built in
assets/explorer.js using Plotly.js 3.x's hoveranywhere/clickanywhere flags.
The sidebar exposes id-tagged spans the JS writes into directly.
"""

from dash import html, dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify


def _things_to_try():
    return dmc.Paper([
        dmc.Group(gap="xs", mb="sm", children=[
            DashIconify(icon="tabler:bulb", width=16, color="#e8a020"),
            dmc.Text("Things to Try", fw=600, size="sm", c="orange"),
        ]),
        dmc.Stack(gap="sm", children=[
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:crosshair", width=14),
                    size="sm", variant="light", color="grape", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Hover anywhere to track depth", fw=600, size="xs"),
                    dmc.Text(
                        "A horizontal crosshair plus depth pill follows the cursor across all four "
                        "hole panels — including the empty space between them. Powered by Plotly 3.x's "
                        "hoveranywhere flag.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:layers-intersect", width=14),
                    size="sm", variant="light", color="orange", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Multi-axis spanning bands", fw=600, size="xs"),
                    dmc.Text(
                        "Geological units are quadrilateral paths anchored to consecutive y-axes "
                        '(yref=["y","y2","y2","y"]) — they connect adjacent subplots automatically '
                        "even when each hole has its own axis pair.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:vector-triangle", width=14),
                    size="sm", variant="light", color="red", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Click two points to measure", fw=600, size="xs"),
                    dmc.Text(
                        "Click two depths inside the same hole panel to drop markers and read out the "
                        "depth interval. A third click resets. Cross-hole clicks are ignored.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:zoom", width=14),
                    size="sm", variant="light", color="teal", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Each hole is independent", fw=600, size="xs"),
                    dmc.Text(
                        "Every hole has its own x/y axis pair. Pan or zoom one panel without disturbing "
                        "the others — the spanning geological bands stretch correctly.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
        ]),
    ], p="md", radius="md", withBorder=True, className="tip-paper")


def _sidebar():
    cursor_panel = dmc.Paper([
        dmc.Text("Cursor Position", className="explorer-panel-title"),
        html.Div(className="explorer-info-row", children=[
            html.Span("Depth", className="explorer-info-label"),
            html.Span("--", id="cursor-depth", className="explorer-info-value"),
        ]),
        html.Div(className="explorer-info-row", children=[
            html.Span("Hole", className="explorer-info-label"),
            html.Span("--", id="cursor-hole", className="explorer-info-value"),
        ]),
        html.Div(className="explorer-info-row", children=[
            html.Span("Value", className="explorer-info-label"),
            html.Span("--", id="cursor-value", className="explorer-info-value"),
        ]),
    ], p="md", radius="md", withBorder=True, className="chart-paper explorer-info-panel")

    measure_panel = dmc.Paper([
        dmc.Text("Click-to-Measure", className="explorer-panel-title"),
        dmc.Text(
            "Click two points in the same subplot to measure the depth interval. "
            "Click again to reset.",
            size="xs", c="dimmed", mb=6,
        ),
        html.Div(id="distance-result", className="explorer-distance-result"),
    ], p="md", radius="md", withBorder=True, className="chart-paper explorer-info-panel")

    return dmc.Stack([cursor_panel, measure_panel], gap="md")


def _chart_paper():
    return dmc.Paper([
        html.P("Drill-Hole Cross-Section Explorer", className="section-title"),
        html.P(
            "Four drill holes side by side. Geological units span between panels via multi-axis "
            "shapes. Hover anywhere for the depth crosshair; click two points within one hole to "
            "measure interval thickness.",
            className="section-description",
        ),
        html.Div(
            id="explorer-chart",
            style={"height": "640px", "width": "100%"},
        ),
    ], p="md", radius="md", withBorder=True, className="chart-paper")


def layout():
    return [
        # Hidden dcc.Graph forces Dash 4 to lazy-load Plotly.js on this page.
        # The visible chart is rendered by assets/explorer.js into #explorer-chart.
        dcc.Graph(id="_explorer-plotly-loader", figure={}, style={"display": "none"}),
        dmc.Stack([
            _things_to_try(),
            dmc.Grid(gutter="md", children=[
                dmc.GridCol(_sidebar(), span={"base": 12, "md": 3}),
                dmc.GridCol(_chart_paper(), span={"base": 12, "md": 9}),
            ]),
        ], gap="md"),
    ]
