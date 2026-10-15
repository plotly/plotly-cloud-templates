"""
Cross-Section page — showcases Plotly.js multi-axis shapes.

Each geological formation contact is a line shape whose left endpoint
anchors to one subplot x-axis and the right endpoint anchors to a DIFFERENT
subplot x-axis, via the new xref array syntax: xref=["x", "x2"].
When the user pans or zooms col 1, only the left endpoint pixel moves;
the right endpoint stays locked to col 2's coordinate system — correct
geological cross-section behaviour.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import dash_tour_component as dtc
import numpy as np

from utils import load_data, CHART_LAYOUT, LITH_COLORS, compute_trace_easting_elevation, kpi_card
from components.overview_widgets import collar_map, summary_table, depth_histogram

# Formation contacts: approximate elevations (m RL) at deposit centre
FORMATION_CONTACTS = [
    {"name": "Alluvium / Weathered Granite",  "elev": 382, "color": "#8B6914", "dip_m_per_m": 0.04},
    {"name": "Weathered Granite / Granite",   "elev": 350, "color": "#7B5C2A", "dip_m_per_m": 0.06},
    {"name": "Granite / Quartz Diorite",      "elev": 290, "color": "#6B4E2A", "dip_m_per_m": 0.08},
    {"name": "Porphyry Top (mineralised)",    "elev": 220, "color": "#A0522D", "dip_m_per_m": 0.10},
]

AXIS_STYLE = dict(
    showgrid=True, gridcolor="#e9ecef",
    tickfont=dict(color="#6c757d"),
    title_font=dict(color="#495057"),
    zeroline=False,
)

CS_TOUR_STEPS = [
    {
        "selector": "#cs-chart-paper",
        "content": "Welcome to Cross-Section View! Step through to discover all the interactive features on this page.",
        "position": "bottom",
    },
    {
        "selector": "#cross-section-chart",
        "content": "Hover anywhere on the chart — a gold cursor line tracks your elevation across all three panels simultaneously. Click once to pin a start elevation, then click again to measure the vertical distance between any two contacts.",
        "position": "right",
    },
    {
        "selector": "#cross-section-chart",
        "content": "Drag the Elevation (Y) axis — hover the tick labels on the left edge, then drag up or down to pan the elevation range. Scroll over the axis to zoom into any elevation band. Double-click anywhere to reset.",
        "position": "right",
    },
    {
        "selector": "#cross-section-chart",
        "content": "Each of the three panels has its own independent X-axis. Scroll or drag within Section A to zoom its grade range — Sections B and C stay exactly where they are.",
        "position": "top",
    },
    {
        "selector": "#cs-formation-legend",
        "content": "These dotted formation contact lines span all three panels simultaneously. Each endpoint is anchored to its own panel axis — zoom Section A and only its segment moves, keeping the geology correct.",
        "position": "bottom",
    },
]


def _build_figure(collar, survey, orientation="EW"):
    """
    Build the cross-section figure with multi-axis formation shapes.
    orientation: "EW" groups holes by northing thirds; "NS" by easting thirds.
    """
    if orientation == "EW":
        sort_col, split_col = "NORTH", "EAST"
        x_title = "Easting (m)"
    else:
        sort_col, split_col = "EAST", "NORTH"
        x_title = "Northing (m)"

    sorted_collar = collar.sort_values(sort_col).reset_index(drop=True)
    n = len(sorted_collar)
    thirds = [
        sorted_collar.iloc[: n // 3],
        sorted_collar.iloc[n // 3: 2 * n // 3],
        sorted_collar.iloc[2 * n // 3:],
    ]
    section_labels = ["Section A (South)" if orientation == "EW" else "Section A (West)",
                      "Section B (Central)",
                      "Section C (North)" if orientation == "EW" else "Section C (East)"]

    fig = make_subplots(
        rows=1, cols=3,
        shared_yaxes=False,
        column_widths=[0.33, 0.34, 0.33],
        subplot_titles=section_labels,
        horizontal_spacing=0.04,
    )

    for ann in fig.layout.annotations:
        ann.font = dict(size=11, color="#495057")

    colors = ["#1971c2", "#2f9e44", "#e67700", "#c92a2a", "#862e9c",
              "#0c8599", "#1864ab", "#5c940d", "#e67700", "#a61e4d"]

    for col_idx, (section_holes, _) in enumerate(zip(thirds, section_labels), start=1):
        for hi, (_, hole) in enumerate(section_holes.iterrows()):
            east_list, elev_list = compute_trace_easting_elevation(
                hole["HOLEID"], collar, survey
            )
            x_vals = east_list if orientation == "EW" else [hole["NORTH"]] * len(east_list)

            fig.add_trace(go.Scatter(
                x=x_vals,
                y=elev_list,
                mode="lines",
                line=dict(color=colors[hi % len(colors)], width=2),
                name=hole["HOLEID"],
                hovertemplate=(
                    f"<b>{hole['HOLEID']}</b><br>"
                    f"{x_title[:-4]}: %{{x:.0f}} m<br>"
                    "Elevation RL: %{y:.0f} m<extra></extra>"
                ),
                legendgroup=hole["HOLEID"],
                showlegend=(col_idx == 1),
            ), row=1, col=col_idx)

            x0 = east_list[0] if orientation == "EW" else hole["NORTH"]
            fig.add_trace(go.Scatter(
                x=[x0],
                y=[elev_list[0]],
                mode="markers+text",
                marker=dict(color=colors[hi % len(colors)], size=7, symbol="triangle-down"),
                text=[hole["HOLEID"]] if hi == 0 else [],
                textposition="top center",
                textfont=dict(size=7, color="#6c757d"),
                showlegend=False,
                hoverinfo="skip",
                legendgroup=hole["HOLEID"],
            ), row=1, col=col_idx)

    # ─── Multi-axis formation contact shapes ─────────────────────────────────
    def section_x_range(section_holes):
        xs = section_holes["EAST"].tolist() if orientation == "EW" else section_holes["NORTH"].tolist()
        if not xs:
            return 350000, 350600
        return min(xs) - 20, max(xs) + 20

    x_ranges = [section_x_range(s) for s in thirds]
    mids     = [(lo + hi) / 2 for lo, hi in x_ranges]

    # ─── Sentinel traces for plot-wide hover ─────────────────────────────────
    # Invisible scatter points spanning the elevation range ensure hoverData
    # fires anywhere in the chart, not just near actual hole trace data.
    elev_sentinel = list(np.linspace(50, 450, 150))
    for col_idx, x_range in enumerate(x_ranges, start=1):
        x_mid = (x_range[0] + x_range[1]) / 2
        fig.add_trace(go.Scatter(
            x=[x_mid] * len(elev_sentinel),
            y=elev_sentinel,
            mode="markers",
            marker=dict(opacity=0, size=3),
            hoverinfo="skip",
            showlegend=False,
        ), row=1, col=col_idx)

    # ─── Elevation cursor + measure shapes (one per panel) ────────────────────
    # Each shape anchored to its own yref so they align correctly even when
    # panels are zoomed independently.
    for cidx, (xref, yref, x_range) in enumerate(
        zip(["x", "x2", "x3"], ["y", "y2", "y3"], x_ranges), start=1
    ):
        fig.add_shape(
            type="line",
            x0=x_range[0], x1=x_range[1],
            y0=-1000, y1=-1000,
            xref=xref, yref=yref,
            line=dict(color="#e8a020", width=1.5, dash="dash"),
            name=f"elev-cursor-{cidx}",
            visible=False,
        )
        fig.add_shape(
            type="rect",
            x0=x_range[0], x1=x_range[1],
            y0=0, y1=0,
            xref=xref, yref=yref,
            fillcolor="rgba(232,160,32,0.12)",
            line=dict(color="#e8a020", width=1),
            name=f"measure-span-{cidx}",
            visible=False,
        )

    for contact in FORMATION_CONTACTS:
        elev_base = contact["elev"]
        dip       = contact["dip_m_per_m"]
        color     = contact["color"]

        # Elevation at each panel's (lo, hi) x-edge, computed from the dip slope
        ys = [
            (elev_base + dip * (x_ranges[i][0] - mids[i]),
             elev_base + dip * (x_ranges[i][1] - mids[i]))
            for i in range(3)
        ]

        # Single multi-axis path traversing both panels and the gaps between them.
        # Each coordinate in the path maps to the matching xref entry.
        fig.add_shape(
            type="path",
            path=(
                f"M {x_ranges[0][0]} {ys[0][0]} "
                f"L {x_ranges[0][1]} {ys[0][1]} "
                f"L {x_ranges[1][0]} {ys[1][0]} "
                f"L {x_ranges[1][1]} {ys[1][1]} "
                f"L {x_ranges[2][0]} {ys[2][0]} "
                f"L {x_ranges[2][1]} {ys[2][1]}"
            ),
            xref=["x", "x",  "x2", "x2", "x3", "x3"],
            yref=["y", "y",  "y2", "y2", "y3", "y3"],
            line=dict(color=color, width=1.5, dash="dot"),
            layer="below",
        )

        # Label at right edge of col3, anchored to panel 3's own y-axis.
        x_col3_right = x_ranges[2][1]
        elev_label   = ys[2][1]
        fig.add_annotation(
            x=x_col3_right,
            y=elev_label,
            xref="x3", yref="y3",
            text=contact["name"],
            showarrow=False,
            xanchor="left",
            font=dict(size=9, color=color),
            bgcolor="rgba(255,255,255,0.85)",
        )

    # ─── Spanning Mineralised Porphyry Zone rect ─────────────────────────────
    porphyry_top    = 220
    porphyry_bottom = 90

    fig.add_shape(
        type="rect",
        xref=["x", "x3"],
        yref=["y", "y3"],
        x0=x_ranges[0][0], y0=porphyry_bottom,
        x1=x_ranges[2][1], y1=porphyry_top,
        fillcolor="rgba(232, 160, 32, 0.10)",
        line=dict(color="#e8a020", width=1, dash="dash"),
        layer="below",
        label=dict(
            text="Mineralised Porphyry Zone",
            textposition="top left",
            font=dict(size=10, color="#d48806", family="Inter, sans-serif"),
            padding=6,
        ),
    )

    # ─── Layout ──────────────────────────────────────────────────────────────
    fig.update_layout(**{
        **CHART_LAYOUT,
        "height": 600,
        "margin": dict(l=60, r=140, t=50, b=50),
        "hovermode": "closest",
        "legend": dict(
            bgcolor="#ffffff",
            bordercolor="#dee2e6",
            font=dict(color="#495057", size=9),
            orientation="v",
            x=1.01, y=1,
        ),
        "hoverlabel": dict(bgcolor="#ffffff", font_color="#212529", bordercolor="#dee2e6"),
    })

    for col_idx in range(1, 4):
        fig.update_yaxes(
            title_text="Elevation RL (m)" if col_idx == 1 else None,
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d"),
            title_font=dict(color="#495057"),
            zeroline=False,
            range=[150, 450],
            row=1, col=col_idx,
        )
        fig.update_xaxes(
            title_text=x_title,
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d"),
            title_font=dict(color="#495057"),
            zeroline=False,
            row=1, col=col_idx,
        )

    return fig


def layout():
    collar, assay, lith, survey = load_data()

    total_holes  = len(collar)
    total_meters = int(collar["TOTDEPTH"].sum())
    east_range   = collar["EAST"].max() - collar["EAST"].min()
    north_range  = collar["NORTH"].max() - collar["NORTH"].min()
    area_km2     = (east_range * north_range) / 1e6

    formation_legend = dmc.Group(
        id="cs-formation-legend",
        gap="md",
        children=[
            dmc.Group(gap="xs", children=[
                html.Span(style={
                    "display": "inline-block",
                    "width": "24px", "height": "3px",
                    "borderTop": f"2px dotted {c['color']}",
                    "verticalAlign": "middle",
                }),
                dmc.Text(c["name"], size="xs", c="dimmed"),
            ])
            for c in FORMATION_CONTACTS
        ],
    )

    feature_chips = dmc.Group(gap="xs", mt="xs", mb="xs", children=[
        dmc.Tooltip(
            label="Hover the Elevation (Y) axis tick labels and drag up/down to pan · scroll over the axis to zoom · double-click anywhere to reset",
            multiline=True, w=300, withArrow=True, position="bottom",
            children=dmc.Badge("↕ Drag Y-Axis", color="blue", variant="light", size="sm",
                               style={"cursor": "help"}),
        ),
    ])

    things_to_try = dmc.Paper([
        dmc.Group(gap="xs", mb="sm", children=[
            DashIconify(icon="tabler:bulb", width=16, color="#e8a020"),
            dmc.Text("Things to Try", fw=600, size="sm", c="orange"),
        ]),
        dmc.Stack(gap="sm", children=[
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:arrows-up-down", width=14),
                    size="sm", variant="light", color="blue", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Drag the Elevation (Y) axis", fw=600, size="xs"),
                    dmc.Text(
                        "Hover the tick labels on the left edge and drag up or down to pan. "
                        "Scroll over the axis to zoom into any elevation band.",
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
                    dmc.Text("Zoom any single panel independently", fw=600, size="xs"),
                    dmc.Text(
                        "Each section panel has its own X-axis. Scroll or drag within Section A — "
                        "Sections B and C are completely unaffected.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:line-dashed", width=14),
                    size="sm", variant="light", color="orange", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Watch the formation contacts span all panels", fw=600, size="xs"),
                    dmc.Text(
                        "Dotted lines and the Porphyry Zone rect are anchored to each panel's own axis "
                        "via xref/yref arrays. Zoom Section A — only its segment moves.",
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
                    dmc.Text("Double-click to reset view", fw=600, size="xs"),
                    dmc.Text(
                        "Double-click anywhere on the chart to reset all axes to their default range.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
            dmc.Group(gap="sm", wrap="nowrap", align="flex-start", children=[
                dmc.ThemeIcon(
                    DashIconify(icon="tabler:crosshair", width=14),
                    size="sm", variant="light", color="grape", radius="xl",
                    style={"flexShrink": 0},
                ),
                html.Div([
                    dmc.Text("Hover to track elevation · click to pin", fw=600, size="xs"),
                    dmc.Text(
                        "A gold cursor line tracks your elevation across all three panels simultaneously. "
                        "Click anywhere to pin the marker at that elevation.",
                        size="xs", c="dimmed",
                    ),
                ]),
            ]),
        ]),
    ], p="md", radius="md", withBorder=True, className="tip-paper")

    return [
        dtc.DashTour(
            id="cs-tour",
            isOpen=False,
            accentColor="#e8a020",
            rounded=8,
            showNumber=True,
            steps=CS_TOUR_STEPS,
        ),

        dmc.Stack([
            things_to_try,

            dmc.SimpleGrid(
                cols={"base": 2, "md": 4},
                spacing="md",
                children=[
                    kpi_card("Total Holes",    str(total_holes),      "drillholes in program",    icon="tabler:drone"),
                    kpi_card("Meters Drilled", f"{total_meters:,} m", "cumulative penetration",   icon="tabler:ruler-measure"),
                    kpi_card("Prospect Area",  f"{area_km2:.2f} km²", "surface footprint",        icon="tabler:map-pin"),
                    kpi_card("Section Panels", "3",                   "South · Central · North",  icon="tabler:chart-grid-dots"),
                ],
            ),

            # Cross-section chart card
            dmc.Paper([
                dmc.Group([
                    html.Div([
                        html.P("Cross-Section View", className="section-title"),
                        html.P(
                            "Three geographic panels. Drag the Elevation axis to pan · "
                            "scroll to zoom · hover a panel's X-axis to zoom grade independently.",
                            className="section-description",
                        ),
                    ], style={"flex": 1}),
                    html.Div(
                        id="cs-orientation-group",
                        children=dmc.Group(gap="xs", align="center", children=[
                            dmc.Button(
                                dmc.Group([DashIconify(icon="tabler:help", width=13), "Tour"],
                                          gap=4, align="center"),
                                id="cs-tour-btn",
                                variant="subtle",
                                color="gray",
                                size="xs",
                            ),
                            dmc.SegmentedControl(
                                id="section-orientation",
                                data=[
                                    {"value": "EW", "label": "E–W Sections"},
                                    {"value": "NS", "label": "N–S Sections"},
                                ],
                                value="EW",
                                color="orange",
                                size="xs",
                            ),
                        ]),
                    ),
                ], justify="space-between", align="flex-start", wrap="nowrap", mb="xs"),

                # Feature interaction chips
                feature_chips,

                formation_legend,

                # Chart with Y-axis hint overlay
                html.Div(
                    style={"position": "relative"},
                    children=[
                        html.Div(
                            id="cs-yaxis-hint",
                            className="y-axis-hint",
                            children=[
                                DashIconify(icon="tabler:arrows-up-down", width=10, color="#adb5bd"),
                                " drag · scroll to zoom",
                            ],
                        ),
                        dcc.Graph(
                            id="cross-section-chart",
                            figure=_build_figure(collar, survey, "EW"),
                            config={"displayModeBar": True, "scrollZoom": True},
                            style={"height": "600px", "marginTop": "8px"},
                        ),
                    ],
                ),
            ], id="cs-chart-paper", p="md", radius="md", withBorder=True, className="chart-paper"),

            dmc.Grid(gutter="md", children=[
                dmc.GridCol(
                    dmc.Paper([
                        html.P("Collar Plan Map", className="section-title"),
                        html.P(
                            "Plan view of drillhole collar positions. Marker colour = total depth drilled. "
                            "Equal-aspect projection preserves true spatial relationships.",
                            className="section-description",
                        ),
                        dcc.Graph(
                            figure=collar_map(collar),
                            config={"displayModeBar": False, "scrollZoom": True},
                        ),
                    ], p="md", radius="md", withBorder=True, className="chart-paper"),
                    span={"base": 12, "md": 8},
                ),
                dmc.GridCol(
                    dmc.Paper([
                        html.P("Hole Summary", className="section-title"),
                        html.P(
                            "AZ = azimuth from North. DIP = downhole inclination (negative = sub-vertical).",
                            className="section-description",
                        ),
                        html.Div(summary_table(collar), className="table-scroll"),
                        dmc.Text(
                            f"Showing 20 of {total_holes} holes · scroll for more",
                            size="xs", c="dimmed", mt="xs",
                        ),
                    ], p="md", radius="md", withBorder=True, className="chart-paper"),
                    span={"base": 12, "md": 4},
                ),
            ]),

            # Depth distribution
            dmc.Paper([
                html.P("Hole Depth Distribution", className="section-title"),
                html.P(
                    "Most holes target the 200–350 m depth range where the Au-Cu mineralized porphyry sits. "
                    "Shallower holes test the weathered zone; deeper holes test the fresh granite footwall.",
                    className="section-description",
                ),
                dcc.Graph(figure=depth_histogram(collar), config={"displayModeBar": False}),
            ], p="md", radius="md", withBorder=True, className="chart-paper"),
        ], gap="md"),
    ]
