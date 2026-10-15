"""Plotly figures: the quilt and the growth-of-$10k chart."""

import pandas as pd
import plotly.graph_objects as go

from data import PORTFOLIO, label_for, year_labels
from theme import (
    ASSET_COLORS,
    BRAND_DARK,
    FONT_BODY,
    FONT_MONO,
    GRID_LINE,
    INK,
    MUTED,
    PORTFOLIO_FILL,
    PORTFOLIO_LINE,
    SURFACE,
)

DIM_MIX = 0.8  # how far non-highlighted cells fade toward the paper surface


def asset_color(asset: str) -> str:
    return PORTFOLIO_FILL if asset == PORTFOLIO else ASSET_COLORS[asset]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _tint(hex_color: str, mix: float) -> str:
    r, g, b = (
        round(c + (p - c) * mix) for c, p in zip(_rgb(hex_color), _rgb(SURFACE))
    )
    return f"#{r:02X}{g:02X}{b:02X}"


def _rounded_rect(x0: float, x1: float, y0: float, y1: float) -> str:
    """SVG path for a rectangle with softly rounded corners (data units)."""
    rx, ry = 0.08, 0.1
    return (
        f"M{x0 + rx},{y0} L{x1 - rx},{y0} Q{x1},{y0} {x1},{y0 + ry} "
        f"L{x1},{y1 - ry} Q{x1},{y1} {x1 - rx},{y1} "
        f"L{x0 + rx},{y1} Q{x0},{y1} {x0},{y1 - ry} "
        f"L{x0},{y0 + ry} Q{x0},{y0} {x0 + rx},{y0} Z"
    )


def _luminance(hex_color: str) -> float:
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def label_ink(fill: str) -> str:
    """White or dark ink, whichever contrasts more with the cell fill."""
    lum = _luminance(fill)
    return SURFACE if (1.05 / (lum + 0.05)) > ((lum + 0.05) / 0.05) else INK


def empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font={"color": MUTED, "size": 14, "family": FONT_BODY},
    )
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"t": 10},
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
    )
    return fig


def build_quilt(
    annual: pd.DataFrame, equity_pct: int, highlight: str | None
) -> go.Figure:
    """Periodic table of returns: one column per year, ranked best to worst."""
    if annual.empty:
        return empty_figure("Pick at least one asset class")

    years = year_labels(annual.index)
    n_rows = int(annual.notna().sum(axis=1).max())
    highlight = highlight if highlight in annual.columns else None

    fig = go.Figure()
    shapes, annotations = [], []
    hover_x, hover_y, hover_text, hover_asset = [], [], [], []
    path_x, path_y = [], []

    for col, year in enumerate(annual.index):
        ranked = annual.loc[year].dropna().sort_values(ascending=False)
        for rank, (asset, ret) in enumerate(ranked.items()):
            is_portfolio = asset == PORTFOLIO
            dimmed = highlight is not None and asset != highlight
            fill = asset_color(asset)
            if dimmed:
                fill = _tint(fill, DIM_MIX)

            # Rounded tiles that stop short of each other, so a strip of
            # surface separates them.
            shapes.append(
                {
                    "type": "path",
                    "path": _rounded_rect(
                        col - 0.46, col + 0.46, rank - 0.42, rank + 0.42
                    ),
                    "fillcolor": fill,
                    "line": {"width": 0},
                    "layer": "below",
                }
            )
            ink = MUTED if dimmed else label_ink(fill)
            short = "BAL" if is_portfolio else asset
            annotations.append(
                {
                    "x": col,
                    "y": rank,
                    "text": f"<b>{short}</b><br>{ret:+.1%}",
                    "showarrow": False,
                    "font": {"size": 11, "color": ink, "family": FONT_MONO},
                }
            )
            hover_x.append(col)
            hover_y.append(rank)
            hover_asset.append(asset)
            hover_text.append(
                f"<b>{label_for(asset, equity_pct)}</b><br>"
                f"{years[col]}: {ret:+.2%}<br>Rank {rank + 1} of {len(ranked)}"
            )
            if asset == highlight:
                path_x.append(col)
                path_y.append(rank)

    if highlight:
        # The highlighted asset's journey through the rankings.
        fig.add_trace(
            go.Scatter(
                x=path_x,
                y=path_y,
                mode="lines+markers",
                line={"color": BRAND_DARK, "width": 1.5, "dash": "dot"},
                marker={"size": 5, "color": BRAND_DARK},
                opacity=0.7,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Invisible markers over every cell carry hover text and click targets.
    fig.add_trace(
        go.Scatter(
            x=hover_x,
            y=hover_y,
            mode="markers",
            marker={"symbol": "square", "size": 40, "opacity": 0},
            customdata=hover_asset,
            hovertext=hover_text,
            hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
        )
    )

    # Legend: one swatch per asset class shown.
    for asset in annual.columns:
        is_portfolio = asset == PORTFOLIO
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=label_for(asset, equity_pct),
                marker={
                    "symbol": "square",
                    "size": 12,
                    "color": asset_color(asset),
                    "line": {
                        "color": PORTFOLIO_LINE if is_portfolio else asset_color(asset),
                        "width": 2,
                    },
                },
            )
        )

    fig.update_layout(
        shapes=shapes,
        annotations=annotations,
        autosize=True,
        margin={"l": 40, "r": 4, "t": 28, "b": 8},
        font={"family": FONT_BODY, "color": INK},
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        hoverlabel={
            "bgcolor": INK,
            "bordercolor": INK,
            "font": {"color": SURFACE, "family": FONT_BODY},
        },
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": -0.01,
            "yanchor": "top",
            "itemclick": False,
            "itemdoubleclick": False,
            "font": {"color": INK},
        },
        xaxis={
            "side": "top",
            "tickvals": list(range(len(years))),
            "ticktext": years,
            "range": [-0.5, len(years) - 0.5],
            "showgrid": False,
            "zeroline": False,
            "fixedrange": True,
            "tickfont": {"color": INK, "family": FONT_MONO, "size": 11},
        },
        yaxis={
            "tickvals": list(range(n_rows)),
            "ticktext": [f"{i + 1:02d}" for i in range(n_rows)],
            "range": [n_rows - 0.5, -0.5],
            "showgrid": False,
            "zeroline": False,
            "fixedrange": True,
            "tickfont": {"color": MUTED, "family": FONT_MONO, "size": 10},
        },
    )
    return fig


def build_growth(
    growth: pd.DataFrame, equity_pct: int, highlight: str | None
) -> go.Figure:
    """Growth of $10,000 across the selected window, one line per asset."""
    if growth.empty or growth.shape[1] == 0:
        return empty_figure("Pick at least one asset class")

    highlight = highlight if highlight in growth.columns else None
    fig = go.Figure()
    for asset in growth.columns:
        emphasized = highlight is None or asset == highlight
        color = BRAND_DARK if asset == PORTFOLIO else asset_color(asset)
        fig.add_trace(
            go.Scatter(
                x=growth.index,
                y=growth[asset],
                mode="lines",
                name=label_for(asset, equity_pct),
                line={
                    "color": color if emphasized else _tint(color, DIM_MIX),
                    "width": 3 if asset == highlight else 2,
                    "dash": "dot" if asset == PORTFOLIO else "solid",
                },
                hovertemplate="%{fullData.name}: $%{y:,.0f}<extra></extra>",
            )
        )
    fig.update_layout(
        autosize=True,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        hovermode="x unified",
        font={"family": FONT_BODY, "color": INK},
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        hoverlabel={"bgcolor": SURFACE, "bordercolor": INK},
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": 1,
            "yanchor": "bottom",
            "font": {"color": INK, "size": 11},
        },
        xaxis={
            "showgrid": False,
            "showline": True,
            "linecolor": GRID_LINE,
            "tickfont": {"color": MUTED, "family": FONT_MONO, "size": 10},
        },
        yaxis={
            "side": "right",
            "tickprefix": "$",
            "tickformat": "~s",
            "gridcolor": GRID_LINE,
            "zeroline": False,
            "tickfont": {"color": MUTED, "family": FONT_MONO, "size": 10},
        },
    )
    return fig
