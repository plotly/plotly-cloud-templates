"""
Downhole Logs page — showcases Plotly.js plot-wide hover/click events.

Two new-feature demonstrations:
1. Depth cursor: a horizontal gold line that tracks the mouse across ALL
   four strip-log panels simultaneously, even over empty areas between
   data points (plot-wide hover events via transparent sentinel traces +
   clientside callback for zero-latency response).

2. Click-to-measure: clicking anywhere on the plot (plot-wide click events)
   records a start depth, then a second click computes the interval
   thickness and draws a shaded span across all panels.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import dash_tour_component as dtc
import numpy as np
import pandas as pd

from utils import load_data, CHART_LAYOUT, LITH_COLORS, LITH_ORDER

DL_TOUR_STEPS = [
    {
        "selector": "#strip-log-chart-paper",
        "content": "Welcome to Downhole Logs! Step through to discover all the interactive features on this page.",
        "position": "bottom",
    },
    {
        "selector": "#strip-log-chart",
        "content": "Hover anywhere on the chart — even over lithology blocks and empty areas — to see a gold dashed cursor track depth across all four panels simultaneously.",
        "position": "right",
    },
    {
        "selector": "#strip-log-chart",
        "content": "Click once anywhere to mark a start depth (a gold line snaps to that position). Then click a second time to measure the interval — a shaded span appears across all panels and the exact thickness is shown.",
        "position": "right",
    },
    {
        "selector": "#hole-selector",
        "content": "Use this dropdown to switch between drillholes. All four panels update together.",
        "position": "bottom",
    },
]


def _strip_log_figure(hole_id: str, collar, assay, lith, survey) -> go.Figure:
    hole_assay  = assay[assay["HOLEID"] == hole_id].sort_values("FROM")
    hole_lith   = lith[lith["HOLEID"]   == hole_id].sort_values("FROM")
    hole_survey = survey[survey["HOLEID"] == hole_id].sort_values("DEPTH")
    hole_collar = collar[collar["HOLEID"] == hole_id].iloc[0]

    max_depth = float(hole_collar["TOTDEPTH"])
    depth_range = list(np.arange(0, max_depth + 5, 5))

    fig = make_subplots(
        rows=1, cols=4,
        shared_yaxes=True,
        column_widths=[0.14, 0.30, 0.30, 0.26],
        subplot_titles=["Lithology", "Au Grade (g/t)", "Cu Grade (%)", "Hole Deviation (°)"],
        horizontal_spacing=0.03,
    )

    for ann in fig.layout.annotations:
        ann.font = dict(size=11, color="#495057")

    # ── Col 1: Lithology rectangles ─────────────────────────────────────────
    for _, row in hole_lith.iterrows():
        color = LITH_COLORS.get(row["LITHOLOGY"], "#aaa")
        fig.add_shape(
            type="rect",
            x0=0, x1=1,
            y0=row["FROM"], y1=row["TO"],
            xref="x", yref="y",
            fillcolor=color,
            line_width=0,
            layer="below",
        )
        mid = (row["FROM"] + row["TO"]) / 2
        if row["TO"] - row["FROM"] >= 8:
            fig.add_annotation(
                x=0.5, y=mid,
                text=row["LITHOLOGY"],
                xref="x", yref="y",
                showarrow=False,
                font=dict(size=8, color="#212529"),
                bgcolor="rgba(255,255,255,0.75)",
                borderpad=2,
            )

    # Invisible trace on col1 so axis is registered
    fig.add_trace(go.Scatter(
        x=[0.5] * len(depth_range),
        y=depth_range,
        mode="markers",
        marker=dict(opacity=0, size=1),
        hoverinfo="skip",
        showlegend=False,
    ), row=1, col=1)

    fig.update_xaxes(
        showticklabels=False, showgrid=False, zeroline=False,
        range=[0, 1], row=1, col=1,
    )

    # ── Col 2: Au grade bars ─────────────────────────────────────────────────
    mid_depths = (hole_assay["FROM"] + hole_assay["TO"]) / 2
    widths      = hole_assay["TO"] - hole_assay["FROM"]

    fig.add_trace(go.Bar(
        x=hole_assay["Au_ppm"],
        y=mid_depths,
        orientation="h",
        width=widths,
        marker=dict(
            color=hole_assay["Au_ppm"],
            colorscale=[[0, "#f8f9fa"], [0.3, "#e8a020"], [1, "#ff6b35"]],
            cmin=0, cmax=float(hole_assay["Au_ppm"].quantile(0.99)),
            showscale=False,
            line_width=0,
        ),
        hovertemplate="Depth: %{y:.1f} m<br>Au: %{x:.3f} g/t<extra></extra>",
        name="Au (g/t)",
        showlegend=False,
    ), row=1, col=2)

    # Sentinel trace for hover coverage on col2
    fig.add_trace(go.Scatter(
        x=[0] * len(depth_range), y=depth_range,
        mode="markers", marker=dict(opacity=0, size=3),
        hoverinfo="skip", showlegend=False,
    ), row=1, col=2)

    # ── Col 3: Cu grade bars ─────────────────────────────────────────────────
    fig.add_trace(go.Bar(
        x=hole_assay["Cu_pct"],
        y=mid_depths,
        orientation="h",
        width=widths,
        marker=dict(
            color=hole_assay["Cu_pct"],
            colorscale=[[0, "#f8f9fa"], [0.3, "#FF8C00"], [1, "#ff4444"]],
            cmin=0, cmax=float(hole_assay["Cu_pct"].quantile(0.99)),
            showscale=False,
            line_width=0,
        ),
        hovertemplate="Depth: %{y:.1f} m<br>Cu: %{x:.4f} %<extra></extra>",
        name="Cu (%)",
        showlegend=False,
    ), row=1, col=3)

    fig.add_trace(go.Scatter(
        x=[0] * len(depth_range), y=depth_range,
        mode="markers", marker=dict(opacity=0, size=3),
        hoverinfo="skip", showlegend=False,
    ), row=1, col=3)

    # ── Col 4: Survey dip line ────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=hole_survey["DIP"],
        y=hole_survey["DEPTH"],
        mode="lines+markers",
        line=dict(color="#1971c2", width=2),
        marker=dict(size=4, color="#1971c2"),
        hovertemplate="Depth: %{y:.1f} m<br>Dip: %{x:.1f}° from vertical<extra></extra>",
        name="Dip (°)",
        showlegend=False,
    ), row=1, col=4)

    fig.add_trace(go.Scatter(
        x=[hole_survey["DIP"].mean()] * len(depth_range), y=depth_range,
        mode="markers", marker=dict(opacity=0, size=3),
        hoverinfo="skip", showlegend=False,
    ), row=1, col=4)

    # ── Depth cursor shape ──────────────────────────────────────────────────
    # xref="paper" spans the full plot width across all 4 panels.
    # Updated by a clientside callback on hoverData (plot-wide hover feature).
    fig.add_shape(
        type="line",
        x0=0, x1=1,
        y0=-10, y1=-10,
        xref="paper", yref="y",
        line=dict(color="#e8a020", width=1.5, dash="dash"),
        name="depth-cursor",
        visible=False,
    )

    # ── Measurement span shape (hidden initially) ────────────────────────────
    fig.add_shape(
        type="rect",
        x0=0, x1=1,
        y0=0, y1=0,
        xref="paper", yref="y",
        fillcolor="rgba(232,160,32,0.12)",
        line=dict(color="#e8a020", width=1),
        name="measure-span",
        visible=False,
    )

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_yaxes(
        autorange="reversed",
        title_text="Depth (m ↓ downhole)",
        showgrid=True, gridcolor="#e9ecef",
        tickfont=dict(color="#6c757d"),
        title_font=dict(color="#495057"),
        range=[max_depth + 5, -5],
        row=1, col=1,
    )
    for col_idx in range(2, 5):
        fig.update_xaxes(
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d"),
            zeroline=True, zerolinecolor="#ced4da",
            row=1, col=col_idx,
        )
    fig.update_xaxes(
        title_text="Au (g/t) — gold grade", title_font=dict(color="#495057"), row=1, col=2,
    )
    fig.update_xaxes(
        title_text="Cu (%) — copper grade", title_font=dict(color="#495057"), row=1, col=3,
    )
    fig.update_xaxes(
        title_text="Dip (°) from vertical", title_font=dict(color="#495057"), row=1, col=4,
    )

    fig.update_layout(**{
        **CHART_LAYOUT,
        "height": 750,
        "margin": dict(l=60, r=20, t=40, b=50),
        "hovermode": "y",
        "hoverdistance": 30,
        "bargap": 0,
        "bargroupgap": 0,
        "hoverlabel": dict(bgcolor="#ffffff", font_color="#212529", bordercolor="#dee2e6"),
    })

    return fig


def layout():
    collar, assay, lith, survey = load_data()
    hole_ids = sorted(collar["HOLEID"].tolist())
    default_hole = hole_ids[0]

    default_depth = int(collar.loc[collar["HOLEID"] == default_hole, "TOTDEPTH"].iloc[0])
    default_lith_count = int(lith[lith["HOLEID"] == default_hole].shape[0])

    things_to_try = dmc.Paper([
        dmc.Group(gap="xs", mb="sm", children=[
            DashIconify(icon="tabler:bulb", width=16, color="#e8a020"),
            dmc.Text("Things to Try", fw=600, size="sm", c="orange"),
        ]),
        dmc.Stack(gap="sm", children=[
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:arrow-move-down", width=14),
                    size="sm", variant="light", color="orange", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Hover to track depth", fw=600, size="xs"),
                    dmc.Text(
                        "The gold depth cursor tracks your mouse across all four panels simultaneously, "
                        "even over lithology rectangles and empty areas.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:vector-triangle", width=14),
                    size="sm", variant="light", color="grape", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Click once · click again to measure", fw=600, size="xs"),
                    dmc.Text(
                        "Click anywhere to mark a start depth (a gold line appears and the readout confirms it). "
                        "Click a second time — the shaded span and thickness annotation appear across all panels.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:rotate-2", width=14),
                    size="sm", variant="light", color="gray", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Clear and restart", fw=600, size="xs"),
                    dmc.Text(
                        "Hit the Clear button to dismiss the span and reset to a fresh measurement.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:adjustments-horizontal", width=14),
                    size="sm", variant="light", color="blue", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Switch drillholes", fw=600, size="xs"),
                    dmc.Text(
                        "Use the Hole Selector dropdown to jump between holes — all panels update together.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
        ]),
    ], p="md", radius="md", withBorder=True, className="tip-paper")

    return [
        dtc.DashTour(
            id="dl-tour",
            isOpen=False,
            accentColor="#e8a020",
            rounded=8,
            showNumber=True,
            steps=DL_TOUR_STEPS,
        ),
        dmc.Stack([
        things_to_try,

        dmc.SimpleGrid(
            cols={"base": 1, "sm": 2},
            spacing="md",
            children=[
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Current Hole Depth", size="xs", c="dimmed", tt="uppercase", fw=600),
                        DashIconify(icon="tabler:arrow-down-to-arc", width=16, color="#868e96"),
                    ], justify="space-between"),
                    dmc.Text(f"{default_depth} m", id="kpi-hole-depth", size="xl", fw=700, c="dark", mt=4),
                    dmc.Text("total drilled depth", size="xs", c="dimmed"),
                ], p="md", radius="md", withBorder=True, className="kpi-card"),
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Lithology Intervals", size="xs", c="dimmed", tt="uppercase", fw=600),
                        DashIconify(icon="tabler:layers-difference", width=16, color="#868e96"),
                    ], justify="space-between"),
                    dmc.Text(str(default_lith_count), id="kpi-lith-count", size="xl", fw=700, c="dark", mt=4),
                    dmc.Text("logged intervals for hole", size="xs", c="dimmed"),
                ], p="md", radius="md", withBorder=True, className="kpi-card"),
            ],
        ),

        # Strip log card
        dmc.Paper([
            dmc.Group([
                html.Div([
                    html.P("Downhole Strip Log", className="section-title"),
                    html.P(
                        "Four-panel strip log: lithology, Au (g/t), Cu (%), hole deviation. "
                        "Hover anywhere to track depth across all panels. Click once to start an interval, "
                        "click again to measure its thickness.",
                        className="section-description",
                    ),
                ], style={"flex": 1}),
                html.Div(children=dmc.Group(gap="xs", align="center", children=[
                    dmc.Button(
                        dmc.Group([DashIconify(icon="tabler:help", width=13), "Tour"],
                                  gap=4, align="center"),
                        id="dl-tour-btn",
                        variant="subtle",
                        color="gray",
                        size="xs",
                    ),
                    dmc.Select(
                        id="hole-selector",
                        label="Select Hole",
                        data=[{"value": h, "label": h} for h in hole_ids],
                        value=default_hole,
                        w=160,
                        size="xs",
                        styles={"label": {"color": "#6c757d", "fontSize": "0.75rem"}},
                    ),
                ])),
            ], justify="space-between", align="flex-end", wrap="nowrap", mb="xs"),
            dmc.Group(gap="xs", mt="xs", mb="xs", children=[
                dmc.Tooltip(
                    label=(
                        "Click once anywhere on the chart to mark a start depth — "
                        "a gold line appears. Click a second time to measure the interval "
                        "and see the thickness."
                    ),
                    multiline=True, w=300, withArrow=True, position="bottom",
                    children=dmc.Badge(
                        "⊕ Click to Measure", color="orange", variant="light", size="sm",
                        style={"cursor": "help"},
                    ),
                ),
            ]),

            # Measurement readout
            dmc.Group(gap="xs", mb="sm", children=[
                dmc.Text("Interval:", size="sm", c="dimmed"),
                html.Div(id="measure-readout", className="measure-readout",
                         children="Click a depth to start measuring"),
                dmc.Button("Clear", id="measure-clear-btn", variant="subtle",
                           color="gray", size="xs"),
            ]),

            dcc.Graph(
                id="strip-log-chart",
                figure=_strip_log_figure(default_hole, collar, assay, lith, survey),
                config={"displayModeBar": True, "scrollZoom": True},
                style={"height": "750px"},
            ),
        ], id="strip-log-chart-paper", p="md", radius="md", withBorder=True, className="chart-paper"),

        dmc.Paper([
            html.P("Lithology Key", className="section-title"),
            dmc.Group(gap="md", wrap="wrap", children=[
                dmc.Group(gap="xs", children=[
                    html.Span(className="lith-swatch", style={"backgroundColor": color}),
                    dmc.Text(lith_name, size="xs", c="dimmed"),
                ])
                for lith_name, color in LITH_COLORS.items()
            ]),
        ], p="md", radius="md", withBorder=True, className="chart-paper"),
        ], gap="md"),
    ]
