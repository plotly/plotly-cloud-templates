"""
MLB Team & Player History

Explore Major League Baseball team and player statistics from 1903 to 2020, using the
Lahman Baseball Database.

Pick an era and a team in the sidebar; the year range follows the era and can be
adjusted. The Team view shows the team's record, titles, and batting, fielding and
pitching trends. The Batting and Pitching & fielding views break down the performance
of any player on that team's roster in the selected years.

Originally written by Matt Parra (https://devparra.github.io/) in 2021.
"""

import dash
import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import Input, Output, State, dcc, html
from dash_iconify import DashIconify

import data
import figures
from theme import FONT

THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": FONT},
    "primaryColor": "pink",
    "defaultRadius": "md",
    # Deep navy surfaces instead of Mantine's default charcoal (keep in sync with theme.py)
    "colors": {
        "dark": [
            "#E8EAF6", "#B8BCD6", "#8A90B0", "#5C6288", "#3A4066",
            "#262B45", "#1E2340", "#161A2E", "#0F1222", "#0A0C18",
        ],
    },
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
DEFAULT_ERA = "Dead Ball"
DEFAULT_TEAM = "NYA"
VIEWS = {"team": "Team", "batting": "Batting", "pitching": "Pitching & fielding"}

ERA_OPTIONS = [
    {"value": name, "label": f"{name} ('{start % 100:02d}–'{end % 100:02d})"}
    for name, start, end in data.ERAS
]
YEAR_MARKS = [
    {"value": start, "label": str(start) if start in (data.FIRST_YEAR, 1960) else None}
    for _, start, _ in data.ERAS
] + [{"value": data.LAST_YEAR, "label": str(data.LAST_YEAR)}]


def graph(graph_id):
    return html.Div(
        dcc.Loading(
            dcc.Graph(id=graph_id, config=GRAPH_CONFIG, style={"height": "100%"}),
            parent_style={"position": "absolute", "inset": 0},
            delay_show=300,
            overlay_style={"visibility": "visible", "opacity": 0.5},
        ),
        className="viz-body",
    )


def grid(grid_id, column_defs=None):
    return html.Div(
        dag.AgGrid(
            id=grid_id,
            columnDefs=column_defs or [],
            rowData=[],
            columnSize="responsiveSizeToFit",
            defaultColDef={"sortable": True, "resizable": True, "minWidth": 64},
            dashGridOptions={
                "theme": {
                    "function": "themeQuartz.withParams({fontFamily: 'Inter, system-ui, sans-serif', "
                    "fontSize: 12, headerFontWeight: 600, spacing: 5, wrapperBorder: false, "
                    "backgroundColor: '#161A2E', foregroundColor: '#E8EAF6', "
                    "headerBackgroundColor: '#1E2340', headerTextColor: '#00E5FF', "
                    "borderColor: '#262B45', rowHoverColor: 'rgba(255, 46, 151, 0.12)', "
                    "oddRowBackgroundColor: '#191D33', accentColor: '#FF2E97'})"
                },
                "localeText": {"noRowsToShow": "No seasons in this selection"},
                "suppressCellFocus": True,
            },
            style={"height": "100%"},
        ),
        className="viz-body",
    )


def card(title, body, action=None, area=None, subtitle=None):
    header = dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Text(title, fw=600, size="sm"),
                    dmc.Text(subtitle, size="xs", c="dimmed") if isinstance(subtitle, str) else subtitle,
                ],
                gap=0,
            ),
            action and html.Div(action, style={"flexShrink": 0}),
        ],
        justify="space-between",
        wrap="nowrap",
        gap="xs",
        mb="xs",
    )
    return dmc.Paper(
        [header, body],
        withBorder=True,
        p="sm",
        className="viz-card",
        style={"gridArea": area},
    )


def column(field, header, tooltip=None, fmt=None):
    col = {"field": field, "headerName": header, "headerTooltip": tooltip or header}
    if fmt:
        col["valueFormatter"] = {
            "function": f"params.value == null ? '' : d3.format('{fmt}')(params.value)"
        }
    return col


YEAR_COLUMN = {**column("year", "Year"), "pinned": "left", "sort": "asc", "minWidth": 70}
BATTING_COLUMNS = [
    YEAR_COLUMN,
    column("g", "G", "Games"),
    column("ab", "AB", "At bats"),
    column("r", "R", "Runs"),
    column("h", "H", "Hits"),
    column("double", "2B", "Doubles"),
    column("triple", "3B", "Triples"),
    column("hr", "HR", "Home runs"),
    column("rbi", "RBI", "Runs batted in", ".0f"),
    column("sb", "SB", "Stolen bases", ".0f"),
    column("bb", "BB", "Walks"),
    column("so", "SO", "Strikeouts", ".0f"),
    column("avg", "AVG", "Batting average", ".3f"),
    column("obp", "OBP", "On-base percentage", ".3f"),
    column("slg", "SLG", "Slugging average", ".3f"),
    column("ops", "OPS", "On-base plus slugging", ".3f"),
]
PITCHING_COLUMNS = [
    YEAR_COLUMN,
    column("w", "W", "Wins"),
    column("l", "L", "Losses"),
    column("g", "G", "Games"),
    column("gs", "GS", "Games started"),
    column("cg", "CG", "Complete games"),
    column("sho", "SHO", "Shutouts"),
    column("sv", "SV", "Saves"),
    column("ip", "IP", "Innings pitched", ".1f"),
    column("h", "H", "Hits allowed"),
    column("er", "ER", "Earned runs"),
    column("hr", "HR", "Home runs allowed"),
    column("bb", "BB", "Walks"),
    column("so", "SO", "Strikeouts"),
    column("era", "ERA", "Earned run average", ".2f"),
    column("whip", "WHIP", "Walks plus hits per inning pitched", ".3f"),
]
FIELDING_COLUMNS = [
    YEAR_COLUMN,
    {**column("pos", "Pos", "Position"), "sort": None},
    column("g", "G", "Games"),
    column("po", "PO", "Putouts"),
    column("a", "A", "Assists"),
    column("e", "E", "Errors", ".0f"),
    column("dp", "DP", "Double plays"),
    column("fld", "FLD%", "Fielding percentage", ".3f"),
]


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Burger(id="burger", size="sm", hiddenFrom="sm"),
                    dmc.ThemeIcon(
                        DashIconify(icon="tabler:ball-baseball", width=22),
                        size="lg",
                        variant="gradient",
                        gradient={"from": "pink", "to": "cyan", "deg": 135},
                        visibleFrom="sm",
                    ),
                    dmc.Stack(
                        [
                            dmc.Title("MLB Team & Player History", order=4, className="app-title"),
                            dmc.Text(
                                f"Major League Baseball statistics, {data.FIRST_YEAR}–{data.LAST_YEAR}",
                                size="xs",
                                c="dimmed",
                                visibleFrom="md",
                            ),
                        ],
                        gap=0,
                    ),
                ],
                gap="sm",
                wrap="nowrap",
                className="title-group",
            ),
            dmc.Group(
                [
                    dmc.SegmentedControl(
                        id="view",
                        data=[{"value": k, "label": v} for k, v in VIEWS.items()],
                        value="team",
                        size="sm",
                        className="view-control",
                    ),
                    dmc.ActionIcon(
                        DashIconify(icon="tabler:info-circle", width=20),
                        id="about-open",
                        variant="subtle",
                        color="gray",
                        size="lg",
                        **{"aria-label": "About this app"},
                    ),
                    html.A(
                        html.Img(src="assets/dash-logo.png", height=32, alt="Dash"),
                        href="https://dash.plotly.com/",
                        className="dash-logo",
                    ),
                ],
                gap="sm",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        h="100%",
        px="md",
        wrap="nowrap",
    )
)

navbar = dmc.AppShellNavbar(
    dmc.Stack(
        [
            dmc.Text("Filters", fw=600, size="sm"),
            dmc.Select(
                id="era",
                label="Era",
                data=ERA_OPTIONS,
                value=DEFAULT_ERA,
                allowDeselect=False,
                size="sm",
            ),
            dmc.Select(
                id="team",
                label="Team",
                value=DEFAULT_TEAM,
                searchable=True,
                allowDeselect=False,
                size="sm",
                description="Teams that played in the selected era.",
            ),
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Text("Years", size="sm", fw=500),
                            dmc.Text(id="years-label", size="xs", c="dimmed"),
                        ],
                        justify="space-between",
                    ),
                    dmc.RangeSlider(
                        id="years",
                        min=data.FIRST_YEAR,
                        max=data.LAST_YEAR,
                        value=data.ERA_RANGES[DEFAULT_ERA],
                        minRange=0,
                        marks=YEAR_MARKS,
                        label=None,
                        size="sm",
                        updatemode="mouseup",
                    ),
                ],
                gap=4,
                mb="md",
            ),
            html.Div(
                dmc.Stack(
                    [
                        dmc.Divider(),
                        dmc.Select(
                            id="player",
                            label="Player",
                            searchable=True,
                            allowDeselect=False,
                            size="sm",
                            maxDropdownHeight=320,
                            nothingFoundMessage="No players match",
                            description="Players on the roster in the selected years.",
                        ),
                        html.Div(id="player-profile"),
                    ],
                    gap="sm",
                ),
                id="player-section",
            ),
            dmc.Text(
                [
                    "Source: ",
                    html.A(
                        "Lahman Baseball Database",
                        href="https://sabr.org/lahman-database/",
                        target="_blank",
                    ),
                    ", CC BY-SA 3.0. Some historical team names were changed to match "
                    "their modern counterpart.",
                ],
                size="xs",
                c="dimmed",
                mt="auto",
                className="source",
            ),
        ],
        gap="md",
        h="100%",
    ),
    p="md",
)

team_view = html.Div(
    [
        card(
            "Win/loss record",
            graph("win-loss"),
            area="wl",
            subtitle="Games won and lost each season, with winning percentage",
        ),
        card("Titles", dmc.ScrollArea(id="titles", type="auto", className="viz-body"), area="titles"),
        card(
            "Batting",
            graph("team-batting"),
            area="bat",
            subtitle="BABIP: batting average on balls in play",
        ),
        card("Fielding", graph("team-fielding"), area="fld", subtitle="Errors and double plays"),
        card(
            "Pitching",
            graph("team-pitching"),
            action=dmc.SegmentedControl(
                id="team-pitching-mode",
                data=[
                    {"value": "kbb", "label": "K/BB"},
                    {"value": "finishes", "label": "Finishes"},
                ],
                value="kbb",
                size="xs",
            ),
            area="pitch",
            subtitle=dmc.Text(id="team-pitching-subtitle", size="xs", c="dimmed"),
        ),
    ],
    id="team-view",
    className="dashboard team-grid",
)

batting_view = html.Div(
    [
        card(
            "On-base percentage",
            graph("on-base"),
            area="obp",
            subtitle="Times on base, HBP: hit by pitch",
        ),
        card(
            "Slugging average",
            graph("slugging"),
            area="slg",
            subtitle="Hits, by number of bases (1B to HR)",
        ),
        card("On-base plus slugging", graph("ops"), area="ops", subtitle="OPS = OBP + SLG"),
        card(
            "Batting by season",
            grid("batting-table", BATTING_COLUMNS),
            area="table",
            subtitle="Some statistics were not tracked until the 1950s.",
        ),
    ],
    id="batting-view",
    className="dashboard batting-grid",
    style={"display": "none"},
)

pitching_view = html.Div(
    [
        card(
            "WHIP",
            graph("whip"),
            area="whip",
            subtitle="Walks plus hits per inning pitched, lower is better",
        ),
        card(
            "Strikeout to walk ratio",
            graph("strikeouts"),
            area="kbb",
            subtitle="Marker size shows the ERA",
        ),
        card("Winning percentage", graph("win-pct"), area="wpct", subtitle="Decisions won"),
        card(
            "Season stats",
            grid("season-table"),
            action=dmc.SegmentedControl(
                id="table-mode",
                data=[
                    {"value": "pitching", "label": "Pitching"},
                    {"value": "fielding", "label": "Fielding"},
                ],
                value="pitching",
                size="xs",
            ),
            area="table",
        ),
        card(
            "Fielding",
            graph("fielding"),
            action=dmc.Select(
                id="position",
                allowDeselect=False,
                size="xs",
                w=130,
                **{"aria-label": "Position"},
            ),
            area="fld",
            subtitle="Fielding percentage at the position",
        ),
    ],
    id="pitching-view",
    className="dashboard pitching-grid",
    style={"display": "none"},
)

about = dmc.Modal(
    dcc.Markdown(
        """
Explore Major League Baseball history from 1903 to 2020. Pick an **era** and a **team**
in the sidebar: the list of teams follows the era, and the year range can be adjusted
with the slider.

- **Team** shows the team's win/loss record, its titles, and its batting (slugging,
  BABIP, batting average), fielding (errors, double plays) and pitching (strikeout to
  walk ratio and ERA, complete games, shutouts and saves) performance.
- **Batting** breaks down the on-base percentage, slugging average and OPS of any
  player on the roster.
- **Pitching & fielding** shows a player's WHIP, strikeout to walk ratio and winning
  percentage as a pitcher, and fielding percentage by position.

Originally built by [Matt Parra](https://devparra.github.io/) with Plotly's Dash.

The data comes from the [Lahman Baseball Database](https://sabr.org/lahman-database/),
copyright 1996-2021 by Sean Lahman, via the
[Chadwick Baseball Bureau](https://github.com/chadwickbureau/baseballdatabank/). It is
licensed under a [Creative Commons Attribution-ShareAlike 3.0 Unported
License](https://creativecommons.org/licenses/by-sa/3.0/).
""",
        link_target="_blank",
        className="about",
    ),
    id="about",
    title=dmc.Text("About this app", fw=600),
    size="lg",
)

app = dash.Dash(
    __name__,
    title="MLB Team & Player History",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
)
server = app.server

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [
            header,
            navbar,
            dmc.AppShellMain([team_view, batting_view, pitching_view]),
            about,
        ],
        id="shell",
        header={"height": 60},
        navbar={
            "width": 290,
            "breakpoint": "sm",
            "collapsed": {"mobile": True, "desktop": False},
        },
        padding="md",
    ),
    theme=THEME,
    forceColorScheme="dark",
)


@app.callback(
    Output("shell", "navbar"),
    Output("team-view", "style"),
    Output("batting-view", "style"),
    Output("pitching-view", "style"),
    Output("player-section", "style"),
    Input("view", "value"),
    Input("burger", "opened"),
    State("shell", "navbar"),
)
def switch_view(view, burger_opened, navbar):
    navbar["collapsed"] = {"mobile": not burger_opened, "desktop": False}
    hidden = {"display": "none"}
    styles = [None if view == v else hidden for v in VIEWS]
    return navbar, *styles, hidden if view == "team" else None


@app.callback(
    Output("about", "opened"),
    Input("about-open", "n_clicks"),
    prevent_initial_call=True,
)
def open_about(_):
    return True


@app.callback(
    Output("team", "data"),
    Output("team", "value"),
    Output("years", "value"),
    Input("era", "value"),
    State("team", "value"),
)
def select_era(era, team):
    """List the era's teams, keeping the selected team if it played in that era."""
    options = data.team_options(era)
    values = [o["value"] for o in options]
    return options, team if team in values else values[0], data.ERA_RANGES[era]


@app.callback(Output("years-label", "children"), Input("years", "value"))
def update_years_label(years):
    start, end = years
    return str(start) if start == end else f"{start}–{end}"


def stat_tile(label, count):
    return dmc.Paper(
        [
            # Only pass c when dimming: c=None is sent as null, which Mantine rejects
            dmc.Text(str(count), className="hero-number", **({} if count else {"c": "dimmed"})),
            dmc.Text(label, size="xs", c="dimmed"),
        ],
        bg="dark.6",
        p="xs",
    )


def _title_years(years):
    return ", ".join(str(y) for y in years)


@app.callback(
    Output("win-loss", "figure"),
    Output("team-batting", "figure"),
    Output("team-fielding", "figure"),
    Output("titles", "children"),
    Input("team", "value"),
    Input("years", "value"),
)
def update_team(team, years):
    seasons = data.team_seasons(team, years)
    if seasons.empty:
        message = "No seasons in this range, try widening the years"
        return (
            figures.empty(message),
            figures.empty(message),
            figures.empty(message),
            dmc.Text(message, size="sm", c="dimmed"),
        )

    wins, losses = int(seasons["w"].sum()), int(seasons["l"].sum())
    titles = data.team_titles(seasons)
    summary = dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Text("Record", size="xs", c="dimmed"),
                            dmc.Text(f"{wins:,}–{losses:,}", className="hero-number"),
                        ],
                        gap=0,
                    ),
                    dmc.Stack(
                        [
                            dmc.Text("Win %", size="xs", c="dimmed"),
                            dmc.Text(
                                f"{wins / max(wins + losses, 1):.3f}".lstrip("0"),
                                className="hero-number",
                            ),
                        ],
                        gap=0,
                    ),
                ],
                gap="xl",
            ),
            dmc.Text(
                f"{len(seasons)} season{'s' if len(seasons) != 1 else ''} as "
                f"{seasons['name'].iloc[-1]}",
                size="xs",
                c="dimmed",
            ),
            dmc.SimpleGrid(
                [stat_tile(label, len(won)) for label, won in titles.items()],
                cols=2,
                spacing="xs",
            ),
            *(
                [
                    dmc.Text(
                        [dmc.Text(label, span=True, fw=600, size="xs"), f"  {_title_years(won)}"],
                        size="xs",
                    )
                    for label, won in titles.items()
                    if won
                ]
                or [dmc.Text("No titles in the selected years.", size="xs", c="dimmed")]
            ),
        ],
        gap="xs",
    )
    return (
        figures.win_loss(seasons),
        figures.team_batting(seasons),
        figures.team_fielding(seasons),
        summary,
    )


@app.callback(
    Output("team-pitching", "figure"),
    Output("team-pitching-subtitle", "children"),
    Input("team", "value"),
    Input("years", "value"),
    Input("team-pitching-mode", "value"),
)
def update_team_pitching(team, years, mode):
    seasons = data.team_seasons(team, years)
    if mode == "finishes":
        subtitle = "Complete games, shutouts, saves per game"
        fig = figures.game_finishes(seasons)
    else:
        subtitle = "Strikeouts per walk, marker size is ERA"
        fig = figures.strikeouts_to_walks(seasons, "era")
    if seasons.empty:
        fig = figures.empty("No seasons in this range")
    return fig, subtitle


@app.callback(
    Output("player", "data"),
    Output("player", "value"),
    Input("team", "value"),
    Input("years", "value"),
    State("player", "value"),
)
def update_player_options(team, years, player):
    options = data.player_options(team, years)
    keep = player in data.option_values(options)
    return options, player if keep else data.first_option(options)


@app.callback(Output("player-profile", "children"), Input("player", "value"))
def update_profile(player):
    profile = data.player_profile(player)
    if not profile:
        return None
    rows = [
        dmc.Group(
            [dmc.Text(label, size="xs", c="dimmed"), dmc.Text(value, size="xs", ta="right")],
            justify="space-between",
            wrap="nowrap",
            gap="xs",
        )
        for label, value in profile.items()
        if label != "name" and value
    ]
    return dmc.Paper(
        dmc.Stack([dmc.Text(profile["name"], fw=600, size="sm"), *rows], gap=4),
        bg="dark.6",
        p="sm",
    )


@app.callback(
    Output("on-base", "figure"),
    Output("slugging", "figure"),
    Output("ops", "figure"),
    Output("batting-table", "rowData"),
    Input("player", "value"),
    Input("team", "value"),
    Input("years", "value"),
)
def update_batting(player, team, years):
    seasons = data.player_batting(player, team, years)
    if seasons["ab"].sum() == 0:
        message = "No at bats for this player in the selected years"
        return (*(figures.empty(message) for _ in range(3)), data.records(seasons))
    return (
        figures.on_base(seasons),
        figures.slugging(seasons),
        figures.ops(seasons),
        data.records(seasons),
    )


@app.callback(
    Output("whip", "figure"),
    Output("strikeouts", "figure"),
    Output("win-pct", "figure"),
    Output("table-mode", "value"),
    Input("player", "value"),
    Input("team", "value"),
    Input("years", "value"),
)
def update_pitching(player, team, years):
    seasons = data.player_pitching(player, team, years)
    if seasons.empty:
        message = "No pitching record, pick a pitcher in the Player list"
        return (*(figures.empty(message) for _ in range(3)), "fielding")
    return (
        figures.whip(seasons),
        figures.strikeouts_to_walks(seasons, "era"),
        figures.win_pct(seasons),
        "pitching",
    )


@app.callback(
    Output("season-table", "columnDefs"),
    Output("season-table", "rowData"),
    Input("player", "value"),
    Input("team", "value"),
    Input("years", "value"),
    Input("table-mode", "value"),
)
def update_season_table(player, team, years, mode):
    if mode == "fielding":
        return FIELDING_COLUMNS, data.records(data.player_fielding(player, team, years))
    return PITCHING_COLUMNS, data.records(data.player_pitching(player, team, years))


@app.callback(
    Output("position", "data"),
    Output("position", "value"),
    Input("player", "value"),
    Input("team", "value"),
    Input("years", "value"),
)
def update_positions(player, team, years):
    """List the player's positions, starting with the one they played most."""
    options = data.position_options(data.player_fielding(player, team, years))
    return options, options[0]["value"] if options else None


@app.callback(
    Output("fielding", "figure"),
    Input("player", "value"),
    Input("team", "value"),
    Input("years", "value"),
    Input("position", "value"),
)
def update_fielding(player, team, years, position):
    seasons = data.player_fielding(player, team, years)
    seasons = seasons[seasons["pos"] == position]
    if seasons.empty:
        return figures.empty("No fielding record in the selected years")
    return figures.fielding_performance(seasons)


if __name__ == "__main__":
    app.run(debug=True)
