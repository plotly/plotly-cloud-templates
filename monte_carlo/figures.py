"""Plotly figures built from the engine's run() output."""

import plotly.graph_objects as go

from theme import (
    BAND_INNER,
    BAND_OUTER,
    BASELINE,
    BRAND_PRIMARY,
    GRID_LINE,
    INK,
    KNOCKED,
    MUTED,
    REFERENCE,
    SAMPLE_PATH,
    SELECTED,
    SURFACE,
)

AXIS = {"gridcolor": GRID_LINE, "tickfont": {"color": MUTED}, "zeroline": False}
LEGEND = {
    "orientation": "h",
    "x": 0,
    "xanchor": "left",
    "y": 1,
    "yanchor": "bottom",
    "font": {"color": INK, "size": 11},
}


def _base_layout(fig: go.Figure, **layout):
    fig.update_layout(
        autosize=True,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        hoverlabel={"bgcolor": SURFACE, "bordercolor": GRID_LINE},
        legend=LEGEND,
        **layout,
    )
    return fig


def empty_figure(message: str = "") -> go.Figure:
    fig = go.Figure()
    if message:
        fig.add_annotation(
            text=message, showarrow=False, font={"color": MUTED, "size": 13}
        )
    return _base_layout(fig, xaxis={"visible": False}, yaxis={"visible": False})


def _reference_line(fig, y=None, x=None, label="", dash="dash"):
    kwargs = {"line": {"color": REFERENCE, "width": 1, "dash": dash}}
    if y is not None:
        fig.add_hline(
            y=y, annotation_text=label, annotation_position="top left", **kwargs
        )
    else:
        fig.add_vline(
            x=x, annotation_text=label, annotation_position="top right", **kwargs
        )


def fan_chart(result: dict) -> go.Figure:
    """Simulated price paths: 5-95% and 25-75% bands, median, sample paths."""
    fan = result["fan"]
    t = fan["t"]
    fig = go.Figure()
    for i, path in enumerate(fan["samples"]):
        fig.add_trace(
            go.Scatter(
                x=t,
                y=path,
                mode="lines",
                line={"color": SAMPLE_PATH, "width": 1},
                hoverinfo="skip",
                showlegend=i == 0,
                name="Sample paths",
                legendgroup="samples",
            )
        )
    for low, high, color, name in [
        ("p05", "p95", BAND_OUTER, "5–95%"),
        ("p25", "p75", BAND_INNER, "25–75%"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=t,
                y=fan[high],
                mode="lines",
                line={"width": 0},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=t,
                y=fan[low],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor=color,
                name=name,
                hoverinfo="skip",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=t,
            y=fan["p50"],
            mode="lines",
            line={"color": BRAND_PRIMARY, "width": 2},
            name="Median",
            hovertemplate="t = %{x:.2f}y<br>Median %{y:.2f}<extra></extra>",
        )
    )
    _reference_line(fig, y=result["strike"], label=f"Strike {result['strike']:g}")
    if result["barrier"]:
        _reference_line(
            fig, y=result["barrier"], label=f"Barrier {result['barrier']:g}", dash="dot"
        )
    return _base_layout(
        fig,
        hovermode="x",
        xaxis={
            **AXIS,
            "title": {"text": "Years", "font": {"color": MUTED, "size": 11}},
        },
        yaxis={**AXIS, "side": "right"},
    )


def distribution_chart(result: dict) -> go.Figure:
    """Histogram of S_T, stacked by outcome."""
    dist = result["distribution"]
    fig = go.Figure()
    layers = [
        ("pays", "Pays off", SELECTED),
        ("worthless", "Expires worthless", BASELINE),
    ]
    if result["barrier"]:
        layers.append(("knocked", "Knocked out", KNOCKED))
    for key, name, color in layers:
        fig.add_trace(
            go.Bar(
                x=dist["centers"],
                y=dist[key],
                width=dist["width"],
                name=name,
                marker={"color": color, "line": {"color": SURFACE, "width": 1}},
                hovertemplate=f"{name}<br>S_T ≈ %{{x:.1f}}: %{{y:,}} paths<extra></extra>",
            )
        )
    _reference_line(fig, x=result["strike"], label="K")
    if result["barrier"]:
        _reference_line(fig, x=result["barrier"], label="H", dash="dot")
    return _base_layout(
        fig,
        barmode="stack",
        bargap=0,
        xaxis={
            **AXIS,
            "title": {
                "text": "Terminal price S_T",
                "font": {"color": MUTED, "size": 11},
            },
        },
        yaxis={**AXIS, "side": "right", "tickformat": "~s"},
    )


def convergence_chart(result: dict, estimator_label: str) -> go.Figure:
    """Running price estimate with its 95% band, headline estimator vs plain."""
    conv = result["convergence"]
    fig = go.Figure()
    for key, name, color, fill in [
        ("plain", "Plain", BASELINE, "rgba(169, 184, 182, 0.25)"),
        ("selected", estimator_label, SELECTED, "rgba(42, 157, 143, 0.20)"),
    ]:
        if key == "plain" and result["estimator"] == "plain":
            continue
        c = conv[key]
        fig.add_trace(
            go.Scatter(
                x=c["paths"],
                y=c["high"],
                mode="lines",
                line={"width": 0},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=c["paths"],
                y=c["low"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor=fill,
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=c["paths"],
                y=c["mean"],
                mode="lines",
                line={"color": color, "width": 2},
                name=f"{name} ± 95% CI",
                hovertemplate=f"{name}<br>%{{x:,}} paths: %{{y:.4f}}<extra></extra>",
            )
        )
    if result["benchmark"] is not None:
        _reference_line(
            fig,
            y=result["benchmark"],
            label=f"{result['benchmark_label']} {result['benchmark']:.4f}",
        )
    return _base_layout(
        fig,
        hovermode="x",
        yaxis={**AXIS, "side": "right", "range": _settled_range(result)},
        xaxis={
            **AXIS,
            "type": "log",
            "title": {
                "text": "Paths (log scale)",
                "font": {"color": MUTED, "size": 11},
            },
        },
    )


def _settled_range(result: dict) -> list[float]:
    """Y-range from the estimates after the first 1% of paths.

    The first few dozen paths swing wildly; scaling to them would flatten the
    part of the chart where the band visibly tightens around the benchmark.
    """
    cutoff = max(500, result["n_paths"] / 100)
    values = []
    for c in result["convergence"].values():
        values += [
            v
            for paths, lo, hi in zip(c["paths"], c["low"], c["high"])
            if paths >= cutoff
            for v in (lo, hi)
        ]
    if result["benchmark"] is not None:
        values.append(result["benchmark"])
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.15 or abs(hi) * 0.01 or 1.0
    return [lo - pad, hi + pad]
