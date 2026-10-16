"""Plotly figures for the dashboard."""

import plotly.graph_objects as go

from theme import BASE_LAYOUT, CATEGORICAL, GRID, MUTED, NEUTRAL, SURFACE, TEXT, TINTS


def _layout(**kwargs):
    fig = go.Figure(layout=BASE_LAYOUT)
    fig.update_layout(**kwargs)
    return fig


def _rate_axis(**kwargs):
    """Right-hand axis for a rate drawn over count bars."""
    axis = dict(
        overlaying="y",
        side="right",
        showgrid=False,
        zeroline=False,
        fixedrange=True,
        tickmode="auto",
        nticks=6,
    )
    return axis | kwargs


def _year_ticks(fig, years):
    """Label every season when only a few are shown, so ticks are never repeated."""
    if len(years) and years.max() - years.min() < 8:
        fig.update_xaxes(dtick=1, range=[years.min() - 0.6, years.max() + 0.6])
    return fig


def empty(message):
    fig = _layout(xaxis_visible=False, yaxis_visible=False, hovermode=False)
    fig.add_annotation(text=message, showarrow=False, font=dict(color=MUTED, size=13))
    return fig


def _lines(df, series, yformat=".3f"):
    """One line per (column, name) in series, colored in categorical order."""
    fig = _layout(yaxis_tickformat=yformat)
    for i, (column, name) in enumerate(series):
        fig.add_scatter(
            x=df["year"],
            y=df[column],
            name=name,
            mode="lines+markers",
            line=dict(color=CATEGORICAL[i], width=2),
            marker=dict(size=5),
            hovertemplate=f"%{{y:{yformat}}}",
        )
    return _year_ticks(fig, df["year"])


def _bars_with_rate(df, bars, rate, rate_name, rate_format=".3f"):
    """Stacked count bars on the left axis, with the rate they add up to as a line
    on the right axis."""
    fig = _layout(
        barmode="stack",
        bargap=0.2,
        yaxis_title=dict(text="Count", font=dict(color=MUTED, size=11)),
        yaxis_rangemode="nonnegative",
        yaxis2=_rate_axis(
            tickformat=rate_format, title=dict(text=rate_name, font=dict(color=TEXT, size=11))
        ),
        legend_traceorder="normal",
    )
    for i, (column, name) in enumerate(bars):
        fig.add_bar(
            x=df["year"],
            y=df[column],
            name=name,
            marker_color=TINTS[i + 1],
            hovertemplate="%{y:,}",
        )
    fig.add_scatter(
        x=df["year"],
        y=df[rate],
        name=rate_name,
        yaxis="y2",
        mode="lines+markers",
        line=dict(color=CATEGORICAL[0], width=2.5),
        marker=dict(size=6),
        hovertemplate=f"%{{y:{rate_format}}}",
    )
    return _year_ticks(fig, df["year"])


# Team view


def win_loss(seasons):
    fig = _layout(barmode="group", bargap=0.2, bargroupgap=0.05)
    fig.add_bar(
        x=seasons["year"], y=seasons["w"], name="Wins", marker_color=CATEGORICAL[0]
    )
    fig.add_bar(x=seasons["year"], y=seasons["l"], name="Losses", marker_color=NEUTRAL)
    fig.add_scatter(
        x=seasons["year"],
        y=seasons["w"] / (seasons["w"] + seasons["l"]),
        name="Win %",
        yaxis="y2",
        mode="lines",
        line=dict(color=CATEGORICAL[1], width=2),
        hovertemplate="%{y:.3f}",
    )
    fig.update_layout(
        yaxis2=_rate_axis(range=[0, 1], tickformat=".3f", tickmode="linear", dtick=0.25)
    )
    return _year_ticks(fig, seasons["year"])


def team_batting(seasons):
    return _lines(
        seasons,
        [("slg", "Slugging"), ("babip", "BABIP"), ("avg", "Batting average")],
    )


def team_fielding(seasons):
    fig = _layout(barmode="group", bargap=0.2, bargroupgap=0.05)
    fig.add_bar(x=seasons["year"], y=seasons["e"], name="Errors", marker_color=CATEGORICAL[1])
    fig.add_bar(
        x=seasons["year"], y=seasons["dp"], name="Double plays", marker_color=CATEGORICAL[0]
    )
    return _year_ticks(fig, seasons["year"])


def strikeouts_to_walks(df, era):
    """K/BB ratio by season, with the marker area showing the ERA."""
    fig = _layout(showlegend=False, yaxis_title=dict(text="K/BB", font=dict(color=MUTED, size=11)))
    fig.add_scatter(
        x=df["year"],
        y=df["kbb"],
        mode="lines+markers",
        line=dict(color=GRID, width=1.5),
        marker=dict(
            size=df[era].fillna(0),
            sizemode="area",
            sizeref=2 * max(df[era].max(), 1) / 22**2,
            sizemin=3,
            color=CATEGORICAL[0],
            opacity=0.75,
            line=dict(color=SURFACE, width=1),
        ),
        customdata=df[era],
        hovertemplate="K/BB %{y:.2f}<br>ERA %{customdata:.2f}<extra></extra>",
    )
    return _year_ticks(fig, df["year"])


def game_finishes(seasons):
    return _lines(
        seasons,
        [("cg_rate", "Complete games"), ("sho_rate", "Shutouts"), ("sv_rate", "Saves")],
        yformat=".0%",
    )


# Batting view


def on_base(df):
    return _bars_with_rate(
        df,
        [("h", "Hits"), ("bb", "Walks"), ("hbp", "HBP"), ("sf", "Sac flies")],
        "obp",
        "OBP",
    )


def slugging(df):
    return _bars_with_rate(
        df,
        [("single", "1B"), ("double", "2B"), ("triple", "3B"), ("hr", "HR")],
        "slg",
        "SLG",
    )


def ops(df):
    return _lines(df, [("ops", "OPS"), ("obp", "OBP"), ("slg", "SLG")])


# Pitching and fielding view


def whip(df):
    fig = _lines(df, [("whip", "WHIP")], yformat=".2f")
    fig.update_layout(showlegend=False)
    return fig


def win_pct(df):
    fig = _layout(
        showlegend=False,
        yaxis=dict(range=[0, 1], tickformat=".3f"),
        bargap=0.25,
    )
    fig.add_bar(
        x=df["year"],
        y=df["wpct"],
        marker_color=CATEGORICAL[0],
        customdata=df[["w", "l"]],
        hovertemplate="%{y:.3f} (%{customdata[0]}–%{customdata[1]})<extra></extra>",
    )
    fig.add_hline(y=0.5, line=dict(color=MUTED, width=1, dash="dot"))
    return _year_ticks(fig, df["year"])


def fielding_performance(df):
    return _bars_with_rate(
        df, [("po", "Putouts"), ("a", "Assists"), ("e", "Errors")], "fld", "FLD%"
    )
