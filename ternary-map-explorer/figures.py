"""Figure builders. Each takes the wells in view and the selected well IDs
(a set, or None when nothing is selected) and returns a plotly Figure."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from data import production, wells
from rock_types import ROCK_TYPES
from theme import (
    BASE_LAYOUT,
    FORMATION_GROUPS,
    GRID,
    MUTED,
    ROCK_TYPE_FILLS,
    SURFACE,
    formation_color,
)

MAP_CENTER = dict(lat=wells["lat"].mean(), lon=wells["lon"].mean())
UNSELECTED = dict(marker=dict(opacity=0.15))
LEGEND = dict(
    orientation="h",
    x=0,
    y=1,
    yanchor="bottom",
    title=None,
    font=dict(size=11),
    bgcolor="rgba(0,0,0,0)",
)


def empty_figure(message="No wells match the current filters"):
    fig = go.Figure(layout=BASE_LAYOUT)
    fig.add_annotation(
        text=message, showarrow=False, font=dict(color=MUTED, size=13)
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _selected_points(group_df, selected):
    if selected is None:
        return None
    return np.flatnonzero(group_df["well_id"].isin(selected)).tolist()


def _groups(dff):
    for group in FORMATION_GROUPS:
        group_df = dff[dff["group"] == group]
        if not group_df.empty:
            yield group, group_df


def well_map(dff, selected):
    if dff.empty:
        return empty_figure()

    fig = go.Figure()
    for group, g in _groups(dff):
        fig.add_trace(
            go.Scattermap(
                lat=g["lat"],
                lon=g["lon"],
                mode="markers",
                name=group,
                marker=dict(size=10, color=formation_color(group)),
                customdata=g[["well_id", "operator", "formation"]],
                hovertemplate="<b>Well %{customdata[0]}</b><br>"
                "%{customdata[2]}<br>%{customdata[1]}<extra></extra>",
                selectedpoints=_selected_points(g, selected),
                unselected=UNSELECTED,
            )
        )
    fig.update_layout(
        BASE_LAYOUT,
        map=dict(style="carto-positron", center=MAP_CENTER, zoom=7.5),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(LEGEND, y=0.99, yanchor="top", x=0.01, bgcolor="rgba(255,255,255,0.85)"),
        dragmode="lasso",
        clickmode="event+select",
        uirevision="well-map",
    )
    return fig


def _rock_type_traces(visible):
    traces = []
    for name, family, vertices in ROCK_TYPES:
        quartz, carbonate, clay = zip(*vertices)
        traces.append(
            go.Scatterternary(
                a=quartz,
                b=carbonate,
                c=clay,
                mode="lines",
                fill="toself",
                fillcolor=ROCK_TYPE_FILLS[family],
                line=dict(color=SURFACE, width=1.5),
                name=name,
                hoveron="fills",
                hoverinfo="name",
                showlegend=False,
                visible=visible,
            )
        )
        traces.append(
            go.Scatterternary(
                a=[np.mean(quartz)],
                b=[np.mean(carbonate)],
                c=[np.mean(clay)],
                mode="text",
                text=[name.replace(" ", "<br>")],
                textfont=dict(size=8, color=MUTED),
                cliponaxis=False,
                hoverinfo="skip",
                showlegend=False,
                visible=visible,
            )
        )
    return traces


def ternary(dff, selected, show_wells=True, show_rock_types=True):
    fig = go.Figure(_rock_type_traces(show_rock_types))
    for group, g in _groups(dff):
        fig.add_trace(
            go.Scatterternary(
                a=g["Quartz"],
                b=g["Carbonate"],
                c=g["Clay"],
                mode="markers",
                name=group,
                marker=dict(
                    size=9,
                    color=formation_color(group),
                    line=dict(color=SURFACE, width=1),
                ),
                customdata=g[["well_id", "formation"]],
                hovertemplate="<b>Well %{customdata[0]}</b> · %{customdata[1]}<br>"
                "Quartz %{a:.0f}% · Carbonate %{b:.0f}% · Clay %{c:.0f}%"
                "<extra></extra>",
                selectedpoints=_selected_points(g, selected),
                unselected=UNSELECTED,
                visible=show_wells,
            )
        )

    axis = dict(
        min=0,
        linewidth=1,
        linecolor=GRID,
        gridcolor=GRID,
        ticks="outside",
        tickcolor=GRID,
        tickfont=dict(color=MUTED, size=10),
    )
    fig.update_layout(
        BASE_LAYOUT,
        ternary=dict(
            sum=100,
            bgcolor="rgba(0,0,0,0)",
            aaxis=dict(axis, title=dict(text="Quartz")),
            baxis=dict(axis, title=dict(text="Carbonate")),
            caxis=dict(axis, title=dict(text="Clay")),
        ),
        margin=dict(l=40, r=40, t=28, b=44),
        showlegend=False,
        dragmode="lasso",
        clickmode="event+select",
        uirevision="ternary",
    )
    return fig


def formation_bar(dff, selected):
    if dff.empty:
        return empty_figure()

    counts = dff["formation"].value_counts(ascending=True)
    group_of = dff.drop_duplicates("formation").set_index("formation")["group"]
    colors = [formation_color(group_of[f]) for f in counts.index]

    fig = go.Figure()
    hover = "<b>%{y}</b><br>%{x} wells<extra></extra>"
    if selected is None:
        fig.add_trace(
            go.Bar(
                x=counts.values,
                y=counts.index,
                orientation="h",
                marker_color=colors,
                text=counts.values,
                hovertemplate=hover,
            )
        )
    else:
        in_selection = (
            dff[dff["well_id"].isin(selected)]["formation"]
            .value_counts()
            .reindex(counts.index, fill_value=0)
        )
        fig.add_trace(
            go.Bar(
                x=counts.values,
                y=counts.index,
                orientation="h",
                marker_color=GRID,
                name="In view",
                hovertemplate=hover,
            )
        )
        fig.add_trace(
            go.Bar(
                x=in_selection.values,
                y=counts.index,
                orientation="h",
                marker_color=colors,
                name="Selected",
                text=[
                    f"{s} of {t}" if s else ""
                    for s, t in zip(in_selection.values, counts.values)
                ],
                hovertemplate="<b>%{y}</b><br>%{x} selected<extra></extra>",
            )
        )

    fig.update_traces(textposition="outside", cliponaxis=False, textfont_color=MUTED)
    fig.update_layout(
        BASE_LAYOUT,
        barmode="overlay",
        barcornerradius=4,
        bargap=0.35,
        showlegend=False,
        margin=dict(l=8, r=56, t=4, b=32),
        xaxis=dict(title="Wells", gridcolor=GRID, zeroline=False),
        yaxis=dict(ticks="", ticksuffix="  ", automargin=True),
        dragmode=False,
        clickmode="event",
        uirevision="formation-bar",
    )
    return fig


def production_lines(dff, selected):
    well_ids = dff["well_id"] if selected is None else dff["well_id"][dff["well_id"].isin(selected)]
    if well_ids.empty:
        return empty_figure()

    prod = production[production["well_id"].isin(well_ids) & (production["mcf"] > 0)]
    prod = prod.merge(dff[["well_id", "group", "formation"]], on="well_id")
    few_wells = prod["well_id"].nunique() <= 12

    fig = go.Figure()
    for group in FORMATION_GROUPS:
        g = prod[prod["group"] == group].sort_values(["well_id", "Year"])
        if g.empty:
            continue
        color = formation_color(group)
        # One trace per formation group; a blank row between wells breaks the line
        breaks = g.drop_duplicates("well_id", keep="last").assign(Year=None, mcf=None)
        lines = pd.concat([g, breaks]).sort_values(
            ["well_id", "Year"], na_position="last"
        )
        fig.add_trace(
            go.Scatter(
                x=lines["Year"],
                y=lines["mcf"],
                mode="lines",
                name=group,
                legendgroup=group,
                showlegend=few_wells,
                line=dict(color=color, width=2 if few_wells else 1),
                opacity=1 if few_wells else 0.18,
                customdata=lines[["well_id", "formation"]],
                hovertemplate="<b>Well %{customdata[0]}</b> · %{customdata[1]}<br>"
                "%{x}: %{y:,.0f} Mcf<extra></extra>",
                connectgaps=False,
            )
        )
        if not few_wells:
            # Median across wells, only for years with enough wells to mean something
            by_year = g.groupby("Year")["mcf"].agg(["median", "size"])
            by_year = by_year[by_year["size"] >= 3]
            fig.add_trace(
                go.Scatter(
                    x=by_year.index,
                    y=by_year["median"],
                    mode="lines",
                    name=group,
                    legendgroup=group,
                    line=dict(color=color, width=2.5),
                    customdata=by_year["size"],
                    hovertemplate=f"<b>{group} median</b><br>"
                    "%{x}: %{y:,.0f} Mcf · %{customdata} wells<extra></extra>",
                )
            )
    fig.update_layout(
        BASE_LAYOUT,
        legend=LEGEND,
        margin=dict(l=8, r=8, t=24, b=32),
        xaxis=dict(title="Year", gridcolor=GRID, zeroline=False),
        yaxis=dict(
            title="Gas production (Mcf/yr)",
            type="log",
            dtick=1,
            tickformat="~s",
            gridcolor=GRID,
            zeroline=False,
            automargin=True,
        ),
        hovermode="closest",
        uirevision="production",
    )
    return fig
