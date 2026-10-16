"""Plotly figures for the dashboard."""

import pandas as pd
import plotly.graph_objects as go

from data import LANDMARK_PLAYERS, POSITION_NAMES, POSITIONS, stat_label
from theme import (
    BASE_LAYOUT,
    CATEGORICAL,
    GRID,
    MUTED,
    NEUTRAL,
    SURFACE,
    SYMBOLS,
    TEXT,
)

N_SIMILAR = 10
TOP_LEGEND = dict(
    orientation="h", yanchor="bottom", y=1, xanchor="left", x=0, title_text=""
)
PLAYER_HOVER = "<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}"


def _layout(**kwargs):
    fig = go.Figure(layout=BASE_LAYOUT)
    fig.update_layout(**kwargs)
    return fig


def _axis(title=None, **kwargs):
    return dict(
        title=dict(text=title, font=dict(color=MUTED, size=11)),
        gridcolor=GRID,
        zeroline=False,
        automargin=True,
        **kwargs,
    )


def _customdata(df):
    return df[["name", "pos", "season"]].to_numpy()


def empty(message):
    fig = _layout(xaxis_visible=False, yaxis_visible=False)
    fig.add_annotation(text=message, showarrow=False, font=dict(color=MUTED, size=13))
    return fig


def _spread_labels(x, y, width=0.14, height=0.07):
    """Mask of the points that can be labeled without labels overlapping.

    Points are considered in order, so put the most important ones first. `width`
    and `height` are the label size as a share of each axis range.
    """
    x = (x - x.min()) / ((x.max() - x.min()) or 1)
    y = (y - y.min()) / ((y.max() - y.min()) or 1)
    placed, mask = [], []
    for xi, yi in zip(x, y):
        free = all(abs(xi - px) > width or abs(yi - py) > height for px, py in placed)
        if free:
            placed.append((xi, yi))
        mask.append(free)
    return mask


def _label(fig, x, y, text, size=11, color=MUTED, yshift=12):
    fig.add_annotation(
        x=x,
        y=y,
        text=text,
        showarrow=False,
        yshift=yshift,
        font=dict(size=size, color=color),
        bgcolor="rgba(255,255,255,0.75)",
        borderpad=1,
    )


def player_map(df, name):
    """Every player placed by statistical profile and build.

    The most similar players are drawn solid and outlined, the rest faded.
    """
    fig = _layout(
        xaxis=_axis("Playing style  →  more perimeter", showticklabels=False),
        yaxis=_axis("Build  →  bigger", showticklabels=False),
        legend=TOP_LEGEND,
        hovermode="closest",
    )
    similar_names = set(df[df["name"] != name].head(N_SIMILAR)["name"])
    for i, pos in enumerate(POSITIONS):
        sub = df[df["pos"] == pos]
        similar = sub["name"].isin(similar_names)
        fig.add_scatter(
            x=sub["stat_dim"],
            y=sub["build_dim"],
            mode="markers",
            name=POSITION_NAMES[pos],
            marker=dict(
                color=CATEGORICAL[i],
                symbol=SYMBOLS[i],
                size=[11 if s else 7 for s in similar],
                opacity=[1 if s else 0.3 for s in similar],
                line=dict(
                    color=[TEXT if s else SURFACE for s in similar],
                    width=[1.5 if s else 0.5 for s in similar],
                ),
            ),
            customdata=_customdata(sub),
            hovertemplate=PLAYER_HOVER + "<extra></extra>",
        )

    chosen = df[df["name"] == name]
    fig.add_scatter(
        x=chosen["stat_dim"],
        y=chosen["build_dim"],
        mode="markers",
        name=name,
        marker=dict(color=TEXT, symbol="star", size=18, line=dict(color=SURFACE, width=2)),
        customdata=_customdata(chosen),
        hovertemplate=PLAYER_HOVER + "<extra></extra>",
        showlegend=False,
    )
    row = chosen.iloc[0]
    _label(fig, row["stat_dim"], row["build_dim"], f"<b>{name}</b>", size=13, color=TEXT, yshift=16)

    # Landmark players far enough from the chosen player that labels don't collide
    landmarks = df[df["name"].isin(LANDMARK_PLAYERS) & (df["name"] != name)]
    labeled = pd.concat([chosen, landmarks])
    keep = _spread_labels(labeled["stat_dim"], labeled["build_dim"])
    for _, lm in labeled[keep].iloc[1:].iterrows():
        _label(fig, lm["stat_dim"], lm["build_dim"], lm["name"])
    return fig


def similar_players(df, name):
    """Statistical and build similarity of the most similar players."""
    similar = df[df["name"] != name].head(N_SIMILAR).iloc[::-1]
    fig = _layout(
        xaxis=_axis(tickformat=".0%"),
        yaxis=dict(ticks="", automargin=True, showgrid=False),
        legend=TOP_LEGEND,
        hovermode="y unified",
    )
    # Connect each player's two dots
    for _, row in similar.iterrows():
        fig.add_scatter(
            x=[row["stat_sim"], row["build_sim"]],
            y=[row["name"]] * 2,
            mode="lines",
            line=dict(color=GRID, width=2),
            showlegend=False,
            hoverinfo="skip",
        )
    for i, (column, label) in enumerate(
        [("stat_sim", "Statistics"), ("build_sim", "Build")]
    ):
        fig.add_scatter(
            x=similar[column],
            y=similar["name"],
            mode="markers",
            name=label,
            marker=dict(
                color=CATEGORICAL[i],
                symbol=SYMBOLS[i],
                size=10,
                line=dict(color=SURFACE, width=1.5),
            ),
            hovertemplate=f"{label}: %{{x:.1%}}<extra></extra>",
        )
    return fig


def group_map(df, n_players=100):
    """The top scorers placed on a 2D map of the grouping stats, colored by group.

    Bubbles are sized by career minutes, and as many players are labeled as fit.
    """
    df = df.head(n_players)  # players are sorted by points per game
    fig = _layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        legend=TOP_LEGEND,
        hovermode="closest",
    )
    sizeref = 2 * df["mp"].max() / 26**2
    for group, sub in df.groupby("group"):
        fig.add_scatter(
            x=sub["dim_a"],
            y=sub["dim_b"],
            mode="markers",
            name=f"Group {group}",
            marker=dict(
                color=CATEGORICAL[group - 1],
                symbol=SYMBOLS[group - 1],
                size=sub["mp"],
                sizemode="area",
                sizeref=sizeref,
                sizemin=4,
                opacity=0.7,
                line=dict(color=SURFACE, width=1),
            ),
            customdata=[[*row, group] for row in _customdata(sub)],
            hovertemplate=PLAYER_HOVER + "<br>Group %{customdata[3]}<extra></extra>",
        )

    keep = _spread_labels(df["dim_a"], df["dim_b"], width=0.15, height=0.09)
    for _, row in df[keep].iterrows():
        _label(fig, row["dim_a"], row["dim_b"], row["name"].split()[-1], color=TEXT)
    return fig


def group_positions(df):
    """Share of each position within each group, as 100% stacked bars."""
    counts = df.groupby(["group", "pos"]).size().unstack(fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0)
    fig = _layout(
        barmode="stack",
        bargap=0.3,
        xaxis=_axis("Group", showgrid=False, tickmode="linear", tickangle=0),
        yaxis=_axis(tickformat=".0%", range=[0, 1]),
        legend=dict(TOP_LEGEND, traceorder="normal"),
    )
    for i, pos in enumerate(POSITIONS):
        if pos not in shares:
            continue
        fig.add_bar(
            x=shares.index,
            y=shares[pos],
            name=pos,
            marker=dict(color=CATEGORICAL[i], line=dict(color=SURFACE, width=2)),
            customdata=counts[pos],
            hovertemplate=(
                f"Group %{{x}}<br>{POSITION_NAMES[pos]}: %{{y:.0%}}"
                " (%{customdata} players)<extra></extra>"
            ),
        )
    return fig


def _focus_color(group):
    return CATEGORICAL[group - 1]


def group_box(df, stat, focus):
    """Distribution of `stat` in every group, with the focus group highlighted."""
    fig = _layout(
        xaxis=_axis("Group", showgrid=False, tickangle=0),
        yaxis=_axis(stat_label(stat)),
        showlegend=False,
        boxgap=0.35,
    )
    for group, sub in df.groupby("group"):
        color = _focus_color(group) if group == focus else NEUTRAL
        fig.add_box(
            x=[str(group)] * len(sub),
            y=sub[stat],
            name=f"Group {group}",
            marker=dict(color=color, size=4, opacity=0.7),
            line=dict(color=color, width=1.5),
            fillcolor="rgba(0,0,0,0)",
            boxpoints="all",
            jitter=0.5,
            pointpos=0,
            customdata=_customdata(sub),
            hovertemplate=PLAYER_HOVER + "<br>%{y:.2f}<extra></extra>",
        )
    return fig


def group_scatter(df, x, y, focus, x_title=None, y_title=None):
    """Players by two stats, with the focus group highlighted."""
    fig = _layout(
        xaxis=_axis(x_title or stat_label(x)),
        yaxis=_axis(y_title or stat_label(y)),
        legend=TOP_LEGEND,
        hovermode="closest",
    )
    others = df[df["group"] != focus]
    chosen = df[df["group"] == focus]
    for sub, name, color, opacity in [
        (others, "Other groups", NEUTRAL, 0.6),
        (chosen, f"Group {focus}", _focus_color(focus), 0.9),
    ]:
        fig.add_scatter(
            x=sub[x],
            y=sub[y],
            mode="markers",
            name=name,
            marker=dict(
                color=color, size=8, opacity=opacity, line=dict(color=SURFACE, width=1)
            ),
            customdata=_customdata(sub),
            hovertemplate=PLAYER_HOVER + "<br>%{x:.2f}, %{y:.2f}<extra></extra>",
        )
    return fig

