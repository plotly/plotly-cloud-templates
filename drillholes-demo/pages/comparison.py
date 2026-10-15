"""
Comparison page — compare Au/Cu/Ag grade profiles across multiple holes
side by side, with shared depth axis.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc
import dash_mantine_components as dmc
import plotly.express as px

from utils import load_data, CHART_LAYOUT, GRADE_COLORS, GRADE_LABELS


DEFAULT_HOLES  = ["DH001", "DH002", "DH003", "DH004", "DH005"]
DEFAULT_GRADE  = "Au_ppm"
SUBPLOT_COLORS = px.colors.qualitative.Set2


def build_comparison_figure(selected_holes, grade_col):
    collar, assay, lith, _ = load_data()

    if not selected_holes:
        fig = go.Figure()
        fig.update_layout(**{**CHART_LAYOUT, "height": 500,
                             "title_text": "Select at least one hole"})
        return fig

    n = len(selected_holes)
    grade_label = GRADE_LABELS.get(grade_col, grade_col)

    fig = make_subplots(
        rows=1, cols=n,
        shared_yaxes=True,
        subplot_titles=selected_holes,
        horizontal_spacing=max(0.01, 0.04 - 0.003 * n),
    )
    for ann in fig.layout.annotations:
        ann.font = dict(size=10, color="#495057")

    for i, hole_id in enumerate(selected_holes, start=1):
        hole_assay = assay[assay["HOLEID"] == hole_id].sort_values("FROM")
        if hole_assay.empty:
            continue

        mid_depths = (hole_assay["FROM"] + hole_assay["TO"]) / 2
        widths      = hole_assay["TO"] - hole_assay["FROM"]
        color       = SUBPLOT_COLORS[(i - 1) % len(SUBPLOT_COLORS)]

        grade_max = float(hole_assay[grade_col].quantile(0.98)) or 1.0

        fig.add_trace(go.Bar(
            x=hole_assay[grade_col],
            y=mid_depths,
            orientation="h",
            width=widths,
            marker=dict(
                color=hole_assay[grade_col],
                colorscale=[
                    [0,   "#f0f0f0"],
                    [0.4, color],
                    [1.0, "#212529"],
                ],
                cmin=0, cmax=grade_max,
                showscale=False,
                line_width=0,
            ),
            name=hole_id,
            showlegend=False,
            hovertemplate=f"<b>{hole_id}</b><br>Depth: %{{y:.1f}} m<br>{grade_label}: %{{x:.4g}}<extra></extra>",
        ), row=1, col=i)

        # Best intercept annotation
        peak_idx = hole_assay[grade_col].idxmax()
        peak_row = hole_assay.loc[peak_idx]
        fig.add_annotation(
            x=float(peak_row[grade_col]),
            y=float((peak_row["FROM"] + peak_row["TO"]) / 2),
            xref=f"x{i}" if i > 1 else "x",
            yref="y",
            text=f"  {peak_row[grade_col]:.2g} ←peak",
            showarrow=False,
            font=dict(size=8, color="#d48806"),
            xanchor="left",
        )

        fig.update_xaxes(
            title_text=grade_label,
            title_font=dict(color="#495057", size=10),
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d", size=8),
            zeroline=True, zerolinecolor="#ced4da",
            row=1, col=i,
        )

    fig.update_yaxes(
        autorange="reversed",
        title_text="Depth (m ↓)",
        showgrid=True, gridcolor="#e9ecef",
        tickfont=dict(color="#6c757d"),
        title_font=dict(color="#495057"),
        row=1, col=1,
    )
    fig.update_layout(**{
        **CHART_LAYOUT,
        "height": 650,
        "margin": dict(l=60, r=20, t=45, b=50),
        "bargap": 0, "bargroupgap": 0,
        "hoverlabel": dict(bgcolor="#ffffff", font_color="#212529", bordercolor="#dee2e6"),
        "title_text": f"{grade_label} Grade Profile Comparison",
        "title_font": dict(color="#212529", size=13),
    })
    return fig


def layout():
    collar, assay, _, _ = load_data()
    all_hole_ids = sorted(collar["HOLEID"].tolist())

    default_total_m = int(collar.loc[collar["HOLEID"].isin(DEFAULT_HOLES), "TOTDEPTH"].sum())

    badge_strip = dmc.Group(gap="sm", id="comparison-badges", children=[
        dmc.Badge(f"Holes selected: {len(DEFAULT_HOLES)}", color="orange", variant="light",
                  id="badge-hole-count", size="lg"),
        dmc.Badge(f"Combined meters: {default_total_m:,} m", color="gray", variant="light",
                  id="badge-total-meters", size="lg"),
        dmc.Badge(f"Grade: {GRADE_LABELS[DEFAULT_GRADE]}", color="orange", variant="filled",
                  id="badge-grade", size="lg"),
    ])

    return dmc.Stack([
        # Header + badge strip
        dmc.Group([
            html.Div([
                html.P("Grade Profile Comparison", className="section-title"),
                html.P(
                    "Side-by-side grade profiles across selected holes on a shared depth axis.",
                    className="section-description",
                ),
            ], style={"flex": 1}),
            badge_strip,
        ], justify="space-between", align="center", wrap="nowrap"),

        dmc.Grid(gutter="md", children=[
            # Controls panel
            dmc.GridCol(
                dmc.Paper([
                    html.P("Grade Type", className="section-title"),
                    html.P(
                        "Au = gold (g/t). Cu = copper (%). Ag = silver (ppm).",
                        className="section-description",
                    ),
                    dmc.SegmentedControl(
                        id="grade-selector",
                        data=[
                            {"value": "Au_ppm", "label": "Au (g/t)"},
                            {"value": "Cu_pct", "label": "Cu (%)"},
                            {"value": "Ag_ppm", "label": "Ag (ppm)"},
                        ],
                        value=DEFAULT_GRADE,
                        color="orange",
                        size="xs",
                        fullWidth=True,
                        mb="md",
                    ),
                    html.P("Select Holes (up to 10)", className="section-title"),
                    dmc.CheckboxGroup(
                        id="hole-checklist",
                        value=DEFAULT_HOLES,
                        children=dmc.Stack([
                            dmc.Checkbox(
                                label=h, value=h,
                                styles={"label": {"color": "#495057", "fontSize": "0.8rem"}},
                            )
                            for h in all_hole_ids[:20]
                        ], gap=6),
                    ),
                ], p="md", radius="md", withBorder=True, className="chart-paper",
                   style={"maxHeight": "700px", "overflowY": "auto"}),
                span={"base": 12, "md": 3},
            ),

            # Comparison chart
            dmc.GridCol(
                dmc.Paper([
                    html.P("Grade Profiles", className="section-title"),
                    html.P(
                        "Each panel is one hole's grade profile vs. downhole depth on a shared Y-axis. "
                        "Peak-grade interval is annotated.",
                        className="section-description",
                    ),
                    dcc.Graph(
                        id="comparison-chart",
                        figure=build_comparison_figure(DEFAULT_HOLES, DEFAULT_GRADE),
                        config={"displayModeBar": True, "scrollZoom": True},
                        style={"height": "650px"},
                    ),
                ], p="md", radius="md", withBorder=True, className="chart-paper"),
                span={"base": 12, "md": 9},
            ),
        ]),
    ], gap="md")
