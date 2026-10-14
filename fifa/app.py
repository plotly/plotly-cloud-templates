"""Knockout goals timeline — all scored shots on one axis."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html

from timeline_data import (
    DATA_DIR,
    XMAX,
    format_stage,
    minute_to_x,
    parse_minute,
    team_color,
)

BG = "#05070a"
PLOT_BG = "#05070a"
AXIS_LINE = "#2a3140"
TEXT_MUTED = "#6b7280"
TEXT_WHITE = "#f5f7fa"
HOVER_ACCENT = "#72bcd4"
GOAL_TYPES = ("Goal", "Penalty Shootout Goal")
GOAL_MARKER_BASE = 9
GOAL_MARKER_STEP = 10
GOAL_MARKER_LINE_WIDTH = 1.6
GOAL_MARKER_OPACITY = 0.75
X_AXIS_PADDING = 12
COLOR_MUTE = 0.22


def mute_color(hex_color: str, amount: float = COLOR_MUTE) -> str:
    """Slightly desaturate a hex color toward its luminance."""
    text = hex_color.lstrip("#")
    if len(text) != 6:
        return hex_color
    r, g, b = int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    r = int(round(r * (1 - amount) + gray * amount))
    g = int(round(g * (1 - amount) + gray * amount))
    b = int(round(b * (1 - amount) + gray * amount))
    return f"#{r:02x}{g:02x}{b:02x}"


def goal_team_color(name: str) -> str:
    return mute_color(team_color(name, bright=True))


def build_goals_dataframe() -> pd.DataFrame:
    matches = pd.read_csv(DATA_DIR / "matches.csv")
    details = pd.read_csv(DATA_DIR / "matches_detailed.csv")
    teams = pd.read_csv(DATA_DIR / "teams.csv")
    players = pd.read_csv(DATA_DIR / "squads_and_players.csv")

    events = pd.read_csv(DATA_DIR / "match_events.csv", dtype={"minute": str})
    events["minute_num"] = events["minute"].apply(parse_minute)
    events = events[events["minute_num"].notna()].copy()

    knockout_ids = details.loc[details.stage_name != "Group Stage", "match_id"]
    matches = matches[
        (matches.status == "Completed") & matches.match_id.isin(knockout_ids)
    ].sort_values(["date", "kickoff_time_utc"])

    team_names = teams.set_index("team_id")["team_name"]
    player_names = players.set_index("player_id")["player_name"]
    detail_by_match = details.set_index("match_id")

    completed_ids = set(matches.match_id)
    goals = events[
        events.event_type.isin(GOAL_TYPES)
        & events.match_id.isin(completed_ids)
    ].copy()
    goals = goals.merge(
        matches[["match_id", "date", "kickoff_time_utc"]],
        on="match_id",
        how="left",
    )

    rows: list[dict] = []
    shootout_counters: dict[int, int] = {}

    for _, event in goals.iterrows():
        match_id = int(event.match_id)
        match = matches.loc[matches.match_id == match_id].iloc[0]
        detail = detail_by_match.loc[match_id]
        team_id = int(event.team_id)
        team_name = team_names.get(team_id, "Unknown")
        minute_num = int(event.minute_num)
        home_id = int(match.home_team_id)
        away_id = int(match.away_team_id)
        opponent_id = away_id if team_id == home_id else home_id
        opponent_name = team_names.get(opponent_id, "Unknown")

        shootout_idx = None
        if minute_num >= 121:
            shootout_idx = shootout_counters.get(match_id, 0)
            shootout_counters[match_id] = shootout_idx + 1

        player = player_names.get(event.player_id)
        player_label = str(player).upper() if pd.notna(player) else ""
        is_penalty = event.event_type == "Penalty Shootout Goal"
        color = goal_team_color(team_name)
        opponent_color = goal_team_color(opponent_name)

        rows.append(
            {
                "event_id": int(event.event_id),
                "team_id": team_id,
                "date": event.date,
                "kickoff_time_utc": event.kickoff_time_utc,
                "match_id": match_id,
                "stage_label": format_stage(detail.stage_name),
                "match_label": (
                    f"{detail.home_team_name} {int(match.home_score)}–"
                    f"{int(match.away_score)} {detail.away_team_name}"
                ),
                "team_name": team_name,
                "opponent_name": opponent_name,
                "player_name": player_label,
                "minute": event.minute,
                "minute_num": minute_num,
                "event_type": event.event_type,
                "event_label": "PENALTY" if is_penalty else "GOAL",
                "x": min(minute_to_x(minute_num, shootout_idx), XMAX - 0.2),
                "y": 0,
                "marker_color": color,
                "opponent_color": opponent_color,
            }
        )

    return apply_cumulative_sizing(pd.DataFrame(rows))


def apply_cumulative_sizing(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    sized = df.copy()
    sized["cumulative_goal_count"] = (
        sized.sort_values(["team_id", "x", "date", "kickoff_time_utc", "event_id"])
        .groupby("team_id")
        .cumcount()
        + 1
    )
    sized["marker_size"] = (
        GOAL_MARKER_BASE + GOAL_MARKER_STEP * sized["cumulative_goal_count"]
    )
    return sized.sort_values(["x", "date", "kickoff_time_utc", "event_id"]).reset_index(
        drop=True
    )


def hover_customdata(df: pd.DataFrame) -> list[list]:
    return [
        [
            f"{row['minute']}'",
            row["player_name"],
            row["event_label"],
            row["team_name"].upper(),
            row["cumulative_goal_count"],
            row["stage_label"],
            row["match_label"],
        ]
        for _, row in df.iterrows()
    ]


HOVER_TEMPLATE = (
    f"<span style='font-size:9px;color:{TEXT_MUTED}'>%{{customdata[0]}}</span><br>"
    f"<span style='font-size:17px;font-weight:700;color:{TEXT_WHITE};"
    f"letter-spacing:0.04em'>%{{customdata[1]}}</span><br>"
    f"<span style='font-size:10px;color:{HOVER_ACCENT};letter-spacing:0.08em'>"
    f"%{{customdata[2]}} • %{{customdata[3]}} • #%{{customdata[4]}}</span><br>"
    f"<span style='font-size:9px;color:{TEXT_MUTED}'>%{{customdata[5]}} · "
    f"%{{customdata[6]}}</span>"
    "<extra></extra>"
)


def axis_padding(df: pd.DataFrame) -> tuple[float, float]:
    if df.empty:
        return 2.0, X_AXIS_PADDING
    pad = max(X_AXIS_PADDING, df["marker_size"].max() / 10)
    return 2.0, pad


FIG_HEIGHT = 280
MARGIN_TOP = 28
MARGIN_BOTTOM = 36
MARGIN_LEFT = 12
MARGIN_RIGHT = 28


def empty_marker_trace() -> go.Scatter:
    return go.Scatter(
        x=[],
        y=[],
        mode="markers",
        showlegend=False,
        hoverinfo="skip",
        cliponaxis=False,
    )


def regular_goal_trace(df: pd.DataFrame) -> go.Scatter:
    if df.empty:
        return empty_marker_trace()
    return go.Scatter(
        x=df["x"],
        y=df["y"],
        mode="markers",
        showlegend=False,
        cliponaxis=False,
        marker=dict(
            size=df["marker_size"],
            color="rgba(0,0,0,0)",
            opacity=GOAL_MARKER_OPACITY,
            symbol="circle",
            line=dict(
                width=GOAL_MARKER_LINE_WIDTH,
                color=df["marker_color"],
            ),
            sizemode="diameter",
        ),
        hovertemplate=HOVER_TEMPLATE,
        customdata=hover_customdata(df),
    )


def shootout_goal_trace(df: pd.DataFrame) -> go.Scatter:
    if df.empty:
        return empty_marker_trace()
    return go.Scatter(
        x=df["x"],
        y=df["y"],
        mode="markers",
        showlegend=False,
        cliponaxis=False,
        marker=dict(
            size=df["marker_size"],
            color="rgba(0,0,0,0)",
            opacity=GOAL_MARKER_OPACITY,
            symbol="circle",
            line=dict(
                width=GOAL_MARKER_LINE_WIDTH,
                color=df["marker_color"],
                dash=["dot"] * len(df),
            ),
            sizemode="diameter",
        ),
        hovertemplate=HOVER_TEMPLATE,
        customdata=hover_customdata(df),
    )


def build_goal_traces(df: pd.DataFrame) -> list[go.Scatter]:
    regular = df[df.event_type == "Goal"]
    shootout = df[df.event_type == "Penalty Shootout Goal"]
    return [regular_goal_trace(regular), shootout_goal_trace(shootout)]


def build_figure(df: pd.DataFrame, teams: list[str] | None = None) -> go.Figure:
    fig = go.Figure()
    x_pad_left, x_pad_right = axis_padding(df)
    x_max = XMAX + x_pad_right
    if teams:
        if len(teams) == 1:
            subtitle = teams[0].upper()
        elif len(teams) <= 3:
            subtitle = " · ".join(t.upper() for t in teams)
        else:
            subtitle = f"{len(teams)} TEAMS"
    else:
        subtitle = "KNOCKOUT STAGE"

    y_pad = 0.75 if not df.empty else 0.35

    if df.empty:
        fig.add_traces(build_goal_traces(df))
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="No goals for this selection",
            showarrow=False,
            font=dict(size=12, color=TEXT_MUTED),
        )
    else:
        ordered = df.sort_values(
            ["x", "date", "kickoff_time_utc", "event_id"]
        ).reset_index(drop=True)
        fig.add_traces(build_goal_traces(ordered))

    fig.add_shape(
        type="line",
        x0=0,
        x1=XMAX,
        y0=0,
        y1=0,
        line=dict(color=AXIS_LINE, width=1.5),
        layer="below",
    )
    fig.add_shape(
        type="line",
        x0=45,
        x1=45,
        y0=-0.08,
        y1=0.08,
        line=dict(color=AXIS_LINE, width=1, dash="dash"),
        layer="below",
    )
    fig.add_annotation(
        x=42,
        y=0.12,
        text="HT",
        showarrow=False,
        xanchor="right",
        font=dict(size=8, color=TEXT_MUTED),
    )
    fig.add_annotation(
        x=0.0,
        y=1.08,
        xref="paper",
        yref="paper",
        text=f"{len(df)} GOALS · {subtitle}",
        showarrow=False,
        xanchor="left",
        font=dict(size=8, color=TEXT_MUTED, family="monospace"),
    )

    fig.update_xaxes(
        range=[-x_pad_left, x_max],
        tickvals=[0, 15, 30, 45, 60, 75, 90, 105, 120, 128],
        ticktext=["0'", "15'", "30'", "45'", "60'", "75'", "90'", "105'", "120'", "SO"],
        showticklabels=True,
        ticks="outside",
        ticklen=4,
        tickwidth=1,
        tickcolor=AXIS_LINE,
        showgrid=False,
        showline=False,
        side="bottom",
        tickfont=dict(size=9, color=TEXT_MUTED),
        zeroline=False,
    )
    fig.update_yaxes(
        range=[-y_pad, y_pad],
        showgrid=False,
        showline=False,
        showticklabels=False,
        zeroline=False,
    )
    fig.update_layout(
        paper_bgcolor=BG,
        plot_bgcolor=PLOT_BG,
        height=FIG_HEIGHT,
        margin=dict(l=MARGIN_LEFT, r=MARGIN_RIGHT, t=MARGIN_TOP, b=MARGIN_BOTTOM),
        showlegend=False,
        hoverlabel=dict(
            bgcolor="#0d1118",
            bordercolor="#2a3544",
            font=dict(
                size=12,
                color=TEXT_WHITE,
                family="Helvetica Neue, Arial, sans-serif",
            ),
            align="left",
        ),
    )
    return fig


def country_cards(df: pd.DataFrame, selected: list[str] | None = None) -> html.Div:
    selected_set = set(selected or [])
    summaries: list[dict] = []
    for team_name, team_df in df.groupby("team_name"):
        opponent_counts = (
            team_df.groupby("opponent_name")
            .size()
            .sort_values(ascending=False)
        )
        summaries.append(
            {
                "team_name": team_name,
                "team_color": team_df.iloc[0]["marker_color"],
                "total_goals": len(team_df),
                "selected": team_name in selected_set,
                "opponents": [
                    {
                        "name": opponent,
                        "count": int(count),
                        "color": goal_team_color(opponent),
                    }
                    for opponent, count in opponent_counts.items()
                ],
            }
        )

    summaries.sort(key=lambda row: (-row["total_goals"], row["team_name"]))

    return html.Div(
        className="country-cards-section",
        children=[
            html.H2("Goals by Country", className="cards-heading"),
            html.P(
                "Click a country to filter the chart. Click more to compare. "
                "Click again to remove. With none selected, all goals are shown.",
                className="cards-hint",
            ),
            html.Div(
                id="country-cards-grid",
                className="country-cards-grid",
                children=[
                    html.Div(
                        className=(
                            "country-card country-card-selected"
                            if row["selected"]
                            else "country-card"
                        ),
                        **{"data-team": row["team_name"]},
                        style=(
                            {"borderColor": row["team_color"]}
                            if row["selected"]
                            else None
                        ),
                        children=[
                            html.Div(
                                className="country-card-header",
                                children=[
                                    html.Span(
                                        className="country-card-dot",
                                        style={
                                            "borderColor": row["team_color"],
                                            "boxShadow": f"0 0 8px {row['team_color']}55",
                                        },
                                    ),
                                    html.Span(
                                        row["team_name"].upper(),
                                        className="country-card-name",
                                        style={"color": row["team_color"]},
                                    ),
                                    html.Span(
                                        str(row["total_goals"]),
                                        className="country-card-total",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="country-card-breakdown",
                                children=[
                                    html.Div(
                                        className="country-card-opponent",
                                        children=[
                                            html.Span(
                                                className="country-card-opponent-dot",
                                                style={"borderColor": opp["color"]},
                                            ),
                                            html.Span(
                                                f"vs {opp['name']}",
                                                className="country-card-opponent-name",
                                            ),
                                            html.Span(
                                                str(opp["count"]),
                                                className="country-card-opponent-count",
                                            ),
                                        ],
                                    )
                                    for opp in row["opponents"]
                                ],
                            ),
                        ],
                    )
                    for row in summaries
                ],
            ),
        ],
    )


goals_df = build_goals_dataframe()

app = Dash(__name__)
app.layout = html.Div(
    className="app-shell",
    children=[
        dcc.Store(id="selected-teams", data=[]),
        dcc.Store(id="card-click-listener", data=0),
        html.P("FIFA WORLD CUP 2026 · USA", className="eyebrow"),
        html.H1("Knockout Goals", className="title"),
        html.P(
            "Every goal and penalty shootout goal from completed knockout matches. "
            "Click countries below to filter. Bubble size grows with each team's "
            "cumulative tally.",
            className="subtitle",
        ),
        html.Hr(className="title-rule"),
        html.Div(
            className="graph-wrap goals-graph-wrap",
            children=[
                dcc.Graph(
                    id="knockout-goals",
                    figure=build_figure(goals_df),
                    config={
                        "scrollZoom": False,
                        "displayModeBar": False,
                        "responsive": True,
                    },
                    style={"height": f"{FIG_HEIGHT}px", "width": "100%"},
                ),
            ],
        ),
        html.Div(
            id="country-cards-container",
            children=country_cards(goals_df).children,
        ),
    ],
)


@callback(
    Output("knockout-goals", "figure"),
    Output("country-cards-container", "children"),
    Input("selected-teams", "data"),
)
def update_selected_teams(selected: list[str] | None) -> tuple[go.Figure, list]:
    selected = selected or []
    if not selected:
        filtered = goals_df
        teams = None
    else:
        filtered = goals_df[goals_df.team_name.isin(selected)]
        teams = selected
    return (
        build_figure(filtered, teams=teams),
        country_cards(goals_df, selected=selected).children,
    )


app.clientside_callback(
    """
    function(children) {
        const grid = document.getElementById("country-cards-grid");
        if (!grid) {
            return window.dash_clientside.no_update;
        }

        if (!window.__selectedTeams) {
            window.__selectedTeams = [];
        }

        if (!grid.__clickBound) {
            grid.__clickBound = true;

            grid.addEventListener("click", function(event) {
                const card = event.target.closest(".country-card");
                if (!card || !card.dataset.team) {
                    return;
                }

                const team = card.dataset.team;
                let selected = window.__selectedTeams.slice();

                if (selected.includes(team)) {
                    selected = selected.filter(function(name) { return name !== team; });
                } else {
                    selected.push(team);
                }

                window.__selectedTeams = selected;
                dash_clientside.set_props("selected-teams", {data: selected});
            });
        }

        return window.dash_clientside.no_update;
    }
    """,
    Output("card-click-listener", "data"),
    Input("country-cards-container", "children"),
)

if __name__ == "__main__":
    app.run(debug=True, port=8060)
