"""Measurement data, control-limit math and chart builders for the SPC dashboard."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

df = pd.read_csv(Path(__file__).parent / "data" / "spc_data.csv")

BATCHES = df["Batch"].to_numpy()
PARAMS = [c for c in df.columns if c != "Batch"]
VALUES = {p: df[p].to_numpy(dtype=float) for p in PARAMS}
MAX_BATCH = len(df)

# Measurements replay one batch per tick, starting part way in so the charts have history
START_BATCH = 50

# OOC% thresholds for the per-parameter status, and the scale of the OOC bars
WARN_AT = 5
FAIL_AT = 7
OOC_BAR_MAX = 15

# Chart colors (light surface). Status colors are reserved for limits and OOC points.
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#ecebe8"
SURFACE = "#ffffff"
SERIES = "#2a78d6"
SERIES_FILL = "rgba(42, 120, 214, 0.35)"
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"
FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"

LIMITS = {
    "usl": "Upper specification limit",
    "lsl": "Lower specification limit",
    "ucl": "Upper control limit",
    "lcl": "Lower control limit",
}


def _round(x):
    """Round to at least four significant figures, whatever the magnitude."""
    if x == 0:
        return 0.0
    return round(float(x), max(0, 3 - math.floor(math.log10(abs(x)))))


def historical_specs():
    """Specification (mean ± 1σ) and control (mean ± 3σ) limits from the full history."""
    specs = {}
    for p in PARAMS:
        mean, std = VALUES[p].mean(), VALUES[p].std(ddof=1)
        specs[p] = {
            "mean": _round(mean),
            "usl": _round(mean + std),
            "lsl": _round(mean - std),
            "ucl": _round(mean + 3 * std),
            "lcl": _round(mean - 3 * std),
            "step": 10 ** math.floor(math.log10(std / 2)),
        }
    return specs


HISTORICAL = historical_specs()


def visible(batch):
    return max(0, min(int(batch or 0), MAX_BATCH))


def ooc_mask(param, n, spec):
    y = VALUES[param][:n]
    return (y >= spec["ucl"]) | (y <= spec["lcl"])


def ooc_percent(param, n, spec):
    return float(ooc_mask(param, n, spec).mean() * 100) if n else 0.0


def status(pct):
    if pct > FAIL_AT:
        return "Fail", CRITICAL
    if pct > WARN_AT:
        return "Warn", WARNING
    return "Pass", GOOD


def sparkline(param, n):
    fig = go.Figure(
        go.Scatter(
            x=BATCHES[:n],
            y=VALUES[param][:n],
            mode="lines",
            line={"color": SERIES, "width": 1.5},
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 2, "b": 2},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


def control_chart(param, n, spec):
    x, y = BATCHES[:n], VALUES[param][:n]
    ooc = ooc_mask(param, n, spec)

    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        column_widths=[0.84, 0.16],
        horizontal_spacing=0.015,
    )
    fig.add_scatter(
        x=x,
        y=y,
        mode="lines+markers",
        name="Measurement",
        line={"color": SERIES, "width": 1.5},
        marker={"size": 5, "color": SERIES},
        hovertemplate=f"Batch %{{x}}<br>{param} %{{y}}<extra></extra>",
        row=1,
        col=1,
    )
    fig.add_scatter(
        x=x[ooc],
        y=y[ooc],
        mode="markers",
        name="Out of control",
        marker={
            "size": 10,
            "color": CRITICAL,
            "symbol": "diamond",
            "line": {"color": SURFACE, "width": 2},
        },
        hovertemplate=f"Batch %{{x}}<br>{param} %{{y}}<br>Out of control<extra></extra>",
        row=1,
        col=1,
    )
    fig.add_histogram(
        y=y,
        name="Distribution",
        marker={"color": SERIES_FILL, "line": {"color": SURFACE, "width": 1}},
        showlegend=False,
        hovertemplate="%{y}<br>%{x} batches<extra></extra>",
        row=1,
        col=2,
    )

    lines = [
        ("ucl", "UCL", CRITICAL, "dash"),
        ("usl", "USL", SERIOUS, "dot"),
        ("mean", "Mean", INK_2, "solid"),
        ("lsl", "LSL", SERIOUS, "dot"),
        ("lcl", "LCL", CRITICAL, "dash"),
    ]
    for key, label, color, dash in lines:
        value = HISTORICAL[param]["mean"] if key == "mean" else spec[key]
        fig.add_hline(
            y=value,
            line={"color": color, "width": 1.25, "dash": dash},
            annotation={
                "text": f"{label} {value:g}",
                "font": {"size": 11, "color": INK_2},
                "bgcolor": "rgba(255,255,255,0.8)",
            },
            annotation_position="bottom right" if key in ("mean", "lcl", "lsl") else "top right",
            row=1,
            col=1,
        )

    axis = {
        "showgrid": True,
        "gridcolor": GRID,
        "zeroline": False,
        "linecolor": GRID,
        "tickfont": {"color": MUTED, "size": 11},
    }
    fig.update_xaxes(axis)
    fig.update_yaxes(axis)
    fig.update_xaxes(title={"text": "Batch", "font": {"color": INK_2, "size": 12}}, row=1, col=1)
    fig.update_xaxes(showgrid=False, showticklabels=False, row=1, col=2)
    fig.update_yaxes(title={"text": param, "font": {"color": INK_2, "size": 12}}, row=1, col=1)
    fig.update_layout(
        uirevision=param,
        margin={"l": 56, "r": 8, "t": 28, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT, "color": INK},
        hovermode="closest",
        hoverlabel={"bgcolor": SURFACE, "bordercolor": GRID, "font": {"color": INK}},
        bargap=0.05,
        legend={
            "orientation": "h",
            "x": 0,
            "y": 1.02,
            "yanchor": "bottom",
            "font": {"size": 11, "color": INK_2},
        },
    )
    return fig
