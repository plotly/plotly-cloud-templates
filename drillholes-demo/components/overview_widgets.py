"""Reusable widgets sourced from the retired Overview page."""

import pandas as pd
import plotly.graph_objects as go
from dash import html

from utils import CHART_LAYOUT


def best_au_intercept(assay: pd.DataFrame, min_width: float = 4.0) -> str:
    """Best consecutive Au composite across all holes (min cumulative width in m)."""
    best_grade, best_hole, best_from, best_to = 0.0, "", 0.0, 0.0
    for hole_id, grp in assay.groupby("HOLEID"):
        grp = grp.sort_values("FROM").reset_index(drop=True)
        for i in range(len(grp)):
            for j in range(i + 1, min(i + 20, len(grp) + 1)):
                sub = grp.iloc[i:j]
                width = sub["TO"].iloc[-1] - sub["FROM"].iloc[0]
                if width < min_width:
                    continue
                avg = sub["Au_ppm"].mean()
                if avg > best_grade:
                    best_grade = avg
                    best_hole = hole_id
                    best_from = sub["FROM"].iloc[0]
                    best_to = sub["TO"].iloc[-1]
    width = best_to - best_from
    return f"{best_grade:.2f} g/t / {width:.0f}m ({best_hole})"


def collar_map(collar: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=collar["EAST"],
        y=collar["NORTH"],
        mode="markers+text",
        text=collar["HOLEID"],
        textposition="top center",
        textfont=dict(size=8, color="#6c757d"),
        marker=dict(
            size=10,
            color=collar["TOTDEPTH"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(
                title=dict(text="Total Depth (m)", font=dict(color="#495057")),
                tickfont=dict(color="#495057"),
                bgcolor="#ffffff",
                bordercolor="#dee2e6",
            ),
            line=dict(width=1, color="#dee2e6"),
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Easting: %{x:.1f} m MGA94<br>"
            "Northing: %{y:.1f} m MGA94<br>"
            "Total Depth: %{marker.color:.0f} m"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(**{
        **CHART_LAYOUT,
        "margin": dict(l=60, r=20, t=20, b=50),
        "height": 460,
        "xaxis": dict(
            title="Easting (m MGA94 Zone 50)",
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d"),
            title_font=dict(color="#495057"),
        ),
        "yaxis": dict(
            title="Northing (m MGA94 Zone 50)",
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d"),
            title_font=dict(color="#495057"),
            scaleanchor="x", scaleratio=1,
        ),
        "hoverlabel": dict(bgcolor="#ffffff", font_color="#212529", bordercolor="#dee2e6"),
    })
    return fig


def summary_table(collar: pd.DataFrame, n: int = 20):
    cols = ["HOLEID", "EAST", "NORTH", "ELEV", "TOTDEPTH", "AZ", "DIP"]
    rows = []
    for _, r in collar[cols].head(n).iterrows():
        rows.append(html.Tr([
            html.Td(str(r["HOLEID"]), style={"color": "#d48806", "fontWeight": "600"}),
            html.Td(f"{r['EAST']:.0f}"),
            html.Td(f"{r['NORTH']:.0f}"),
            html.Td(f"{r['ELEV']:.0f} m RL"),
            html.Td(f"{r['TOTDEPTH']:.0f} m"),
            html.Td(f"{r['AZ']:.0f}°"),
            html.Td(f"{r['DIP']:.0f}°"),
        ]))
    return html.Table(
        [html.Thead(html.Tr([html.Th(c) for c in ["Hole", "East", "North", "RL", "Depth", "Az", "Dip"]]))]
        + [html.Tbody(rows)],
        className="data-table",
    )


def depth_histogram(collar: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=collar["TOTDEPTH"],
        nbinsx=15,
        marker=dict(color="#e8a020", line=dict(color="#ffffff", width=1)),
        hovertemplate="Depth: %{x:.0f} m<br>Number of holes: %{y}<extra></extra>",
        name="",
    ))
    fig.update_layout(**{
        **CHART_LAYOUT,
        "height": 200,
        "margin": dict(l=50, r=20, t=10, b=40),
        "xaxis": dict(
            title="Total Depth (m)",
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d"),
            title_font=dict(color="#495057"),
        ),
        "yaxis": dict(
            title="Number of Holes",
            showgrid=True, gridcolor="#e9ecef",
            tickfont=dict(color="#6c757d"),
            title_font=dict(color="#495057"),
        ),
        "bargap": 0.05,
        "showlegend": False,
        "hoverlabel": dict(bgcolor="#ffffff", font_color="#212529", bordercolor="#dee2e6"),
    })
    return fig
