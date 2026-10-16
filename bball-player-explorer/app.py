"""
NBA Player Explorer

Uses machine learning to help scouts look through the careers of the 500 highest
scoring NBA players (with more than 2000 career minutes), combining their career
statistics with their build (height, weight and BMI).

The Similar players view finds the players most similar to a chosen player, by
statistics, by build, or by a mix of both. The Player groupings view groups players
with K-means on a set of stats, and compares the groups.

Originally written for Plotly by JP Hwang in 2020.
"""

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

import data
import figures
from theme import CATEGORICAL, FONT, HEADING_FONT

THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": HEADING_FONT},
    "primaryColor": "orange",
    "primaryShade": 7,
    "defaultRadius": "xs",
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
STAT_OPTIONS = [{"value": s, "label": data.stat_label(s)} for s in data.GROUPING_STATS]
PRESETS = {"stats": data.PROFILE_STATS, "build": data.BUILD_STATS}
TABLE_ROWS = 7


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


def card(title, body, area, subtitle=None, card_id=None):
    header = dmc.Stack(
        [
            dmc.Text(title, className="card-title", **({"id": card_id} if card_id else {})),
            subtitle and dmc.Text(subtitle, size="xs", c="dimmed"),
        ],
        gap=0,
        mb="xs",
    )
    return dmc.Paper(
        [header, body],
        withBorder=True,
        p="sm",
        className="viz-card",
        style={"gridArea": area},
    )


def labeled(label, control, value_id=None):
    """A control with its label above, and optionally its current value on the right."""
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text(label, size="sm", fw=500, className="control-label"),
                    value_id and dmc.Text(id=value_id, size="xs", c="dimmed"),
                ],
                justify="space-between",
            ),
            control,
        ],
        gap=6,
    )


def stat_select(select_id, label, value):
    return dmc.Select(
        id=select_id,
        label=label,
        data=STAT_OPTIONS,
        value=value,
        searchable=True,
        allowDeselect=False,
        size="sm",
    )


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Burger(id="burger", size="sm", hiddenFrom="sm"),
                    dmc.ThemeIcon(
                        DashIconify(icon="tabler:ball-basketball", width=22),
                        size="lg",
                        variant="filled",
                        color="orange",
                        visibleFrom="sm",
                    ),
                    dmc.Stack(
                        [
                            dmc.Title("NBA Player Explorer", order=4, className="app-title"),
                            dmc.Text(
                                "Scout similar players and player groupings with machine learning",
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
                        color="orange",
                        id="view",
                        data=[
                            {"value": "similar", "label": "Similar players"},
                            {"value": "groups", "label": "Player groupings"},
                        ],
                        value="similar",
                        size="sm",
                    ),
                    html.A(
                        html.Img(src="assets/dash-logo.png", height=32, alt="Dash"),
                        href="https://dash.plotly.com/",
                        className="dash-logo",
                    ),
                ],
                gap="md",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        h="100%",
        px="md",
        wrap="nowrap",
    )
)

similar_controls = dmc.Stack(
    [
        dmc.Select(
            id="player",
            label="Player",
            data=data.PLAYER_NAMES,
            value=data.DEFAULT_PLAYER,
            searchable=True,
            allowDeselect=False,
            size="sm",
            leftSection=DashIconify(icon="tabler:search", width=16),
            description="Or click a player on the map.",
        ),
        labeled(
            "Compare by",
            dmc.Slider(
                id="build-weight",
                min=0,
                max=100,
                step=25,
                value=50,
                marks=[
                    {"value": 0, "label": "Stats"},
                    {"value": 50},
                    {"value": 100, "label": "Build"},
                ],
                label=None,
                size="sm",
                mb="md",
                mx="xs",
            ),
            value_id="build-weight-label",
        ),
        labeled(
            "Statistics",
            dmc.SegmentedControl(
                color="orange",
                id="stat-type",
                data=[
                    {"value": "per_game", "label": "Per game"},
                    {"value": "per_36", "label": "Per 36 min"},
                ],
                value="per_game",
                size="xs",
                fullWidth=True,
            ),
        ),
        dmc.Divider(),
        dmc.Stack(id="player-summary", gap=4),
    ],
    id="similar-controls",
    gap="lg",
)

groups_controls = dmc.Stack(
    [
        labeled(
            "Group players by",
            dmc.SegmentedControl(
                color="orange",
                id="preset",
                data=[
                    {"value": "stats", "label": "Statistics"},
                    {"value": "build", "label": "Build"},
                ],
                value="stats",
                size="xs",
                fullWidth=True,
            ),
        ),
        dmc.MultiSelect(
            id="group-stats",
            label="Stats used",
            description="Pick at least 2.",
            data=STAT_OPTIONS,
            value=data.PROFILE_STATS,
            searchable=True,
            clearable=False,
            hidePickedOptions=True,
            size="xs",
        ),
        labeled(
            "Number of groups",
            dmc.Slider(
                id="group-count",
                min=3,
                max=len(CATEGORICAL),
                value=6,
                marks=[{"value": v} for v in range(3, len(CATEGORICAL) + 1)],
                label=None,
                size="sm",
                updatemode="mouseup",
            ),
            value_id="group-count-label",
        ),
        dmc.Divider(),
        dmc.Select(
            id="focus-group",
            label="Group in focus",
            description="Or click a group in the charts.",
            value="1",
            allowDeselect=False,
            size="sm",
        ),
        stat_select("stat-a", "First stat", "fg3a_per_mp"),
        stat_select("stat-b", "Second stat", "fg2a_per_mp"),
    ],
    id="groups-controls",
    gap="md",
    style={"display": "none"},
)

navbar = dmc.AppShellNavbar(
    dmc.ScrollArea(
        dmc.Stack(
            [
                similar_controls,
                groups_controls,
                dmc.Text(
                    [
                        "Source: ",
                        html.A(
                            "Basketball Reference",
                            href="https://www.basketball-reference.com/",
                            target="_blank",
                        ),
                        ". Career totals of the 500 highest scoring players.",
                    ],
                    size="xs",
                    c="dimmed",
                    mt="auto",
                    className="source",
                ),
            ],
            gap="lg",
            mih="100%",
            p="md",
        ),
        type="auto",
        scrollbars="y",
        h="100%",
    ),
)

similar_view = html.Div(
    [
        card(
            "A map of NBA players",
            graph("player-map"),
            area="map",
            subtitle="Players close together play and are built alike. Outlined: the 10 most similar. Click a player to compare.",
        ),
        card(
            "Most similar players",
            graph("similar-players"),
            area="similar",
            subtitle="Similarity to the chosen player, sorted by the overall match",
        ),
        card(
            "Player comparison",
            html.Div(id="comparison-table", className="viz-body table-body"),
            area="table",
            card_id="comparison-title",
        ),
    ],
    id="similar-view",
    className="dashboard similar-grid",
)

groups_view = html.Div(
    [
        card(
            "Player groupings",
            graph("group-map"),
            area="map",
            subtitle="The 100 top scorers, placed by the stats used and sized by career minutes",
        ),
        card(
            "Positions in each group",
            graph("group-positions"),
            area="positions",
        ),
        card("Stat in focus", graph("group-box"), area="box", card_id="box-title"),
        card("First vs second stat", graph("group-scatter"), area="scatter", card_id="scatter-title"),
        card("Player builds", graph("group-builds"), area="builds"),
    ],
    id="groups-view",
    className="dashboard groups-grid",
    style={"display": "none"},
)

app = dash.Dash(
    __name__,
    title="NBA Player Explorer",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap"
    ],
)
server = app.server

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [header, navbar, dmc.AppShellMain([similar_view, groups_view])],
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
    forceColorScheme="light",
)


@app.callback(
    Output("shell", "navbar"),
    Output("similar-view", "style"),
    Output("groups-view", "style"),
    Output("similar-controls", "style"),
    Output("groups-controls", "style"),
    Input("view", "value"),
    Input("burger", "opened"),
    State("shell", "navbar"),
)
def switch_view(view, burger_opened, navbar):
    navbar["collapsed"] = {"mobile": not burger_opened, "desktop": False}
    hidden = {"display": "none"}
    similar = view == "similar"
    shown = [None if similar else hidden, hidden if similar else None]
    return navbar, *shown, *shown


# ===== Similar players =====


def build_weight_label(value):
    if value == 0:
        return "Statistics only"
    if value == 100:
        return "Build only"
    return f"{100 - value}% stats, {value}% build"


def player_summary(name):
    row = data.player(name)
    facts = [
        ("Position", data.POSITION_NAMES[row["pos"]]),
        ("Seasons", row["season"].replace("-", "–")),
        ("Height / weight", f"{row['height']:.0f} cm · {row['weight']:.0f} kg"),
        ("Games", f"{row['g']:,}"),
    ]
    return [
        dmc.Text("Points per game", className="eyebrow"),
        dmc.Text(f"{row['ppg']:.1f}", className="hero-number"),
        dmc.SimpleGrid(
            [
                dmc.Stack(
                    [dmc.Text(k, size="xs", c="dimmed"), dmc.Text(v, size="sm", fw=500)],
                    gap=0,
                )
                for k, v in facts
            ],
            cols=2,
            spacing="sm",
            verticalSpacing="xs",
            mt="xs",
        ),
    ]


def comparison_table(df, name, stats):
    rows = df.head(TABLE_ROWS + 1)  # the chosen player is always the best match
    columns = [("Player", "name", None), ("Pos", "pos", None), ("Match", "match", "{:.0%}")]
    columns += [("Height", "height", "{:.1f}"), ("Weight", "weight", "{:.1f}"), ("BMI", "bmi", "{:.1f}")]
    columns += [(data.short_label(s), s, "{:.2f}") for s in stats]

    head = dmc.TableThead(
        dmc.TableTr(
            [
                dmc.TableTh(title, className="num" if fmt else None)
                for title, key, fmt in columns
            ]
        )
    )
    body = dmc.TableTbody(
        [
            dmc.TableTr(
                [
                    dmc.TableTd(
                        fmt.format(row[key]) if fmt else row[key],
                        className="num" if fmt else None,
                    )
                    for _, key, fmt in columns
                ],
                className="chosen-row" if row["name"] == name else None,
            )
            for _, row in rows.iterrows()
        ]
    )
    return dmc.Table(
        [head, body],
        striped=False,
        highlightOnHover=True,
        verticalSpacing=4,
        horizontalSpacing="xs",
        fz="xs",
        stickyHeader=True,
        className="comparison-table",
    )


@app.callback(
    Output("player", "value"),
    Input("player-map", "clickData"),
    prevent_initial_call=True,
)
def select_player_from_map(click):
    point = click["points"][0]
    if "customdata" not in point:
        return dash.no_update
    return point["customdata"][0]


@app.callback(
    Output("player-map", "figure"),
    Output("similar-players", "figure"),
    Output("comparison-table", "children"),
    Output("comparison-title", "children"),
    Output("player-summary", "children"),
    Output("build-weight-label", "children"),
    Input("player", "value"),
    Input("build-weight", "value"),
    Input("stat-type", "value"),
)
def update_similar(name, build_weight, stat_type):
    df, stats = data.similarity(name, build_weight / 100, stat_type)
    per = "per game" if stat_type == "per_game" else "per 36 minutes"
    return (
        figures.player_map(df, name),
        figures.similar_players(df, name),
        comparison_table(df, name, stats),
        f"{name} and the {TABLE_ROWS} most similar players ({per})",
        player_summary(name),
        build_weight_label(build_weight),
    )


# ===== Player groupings =====


@app.callback(
    Output("group-stats", "value"),
    Input("preset", "value"),
    prevent_initial_call=True,
)
def apply_preset(preset):
    return PRESETS[preset]


@app.callback(
    Output("group-count-label", "children"),
    Output("focus-group", "data"),
    Output("focus-group", "value"),
    Input("group-count", "value"),
    Input("group-map", "clickData"),
    Input("group-positions", "clickData"),
    State("focus-group", "value"),
)
def update_focus_group(n_groups, map_click, positions_click, focus):
    options = [{"value": str(g), "label": f"Group {g}"} for g in range(1, n_groups + 1)]
    if ctx.triggered_id == "group-map" and map_click:
        point = map_click["points"][0]
        if "customdata" in point:
            focus = str(point["customdata"][3])
    elif ctx.triggered_id == "group-positions" and positions_click:
        focus = str(positions_click["points"][0]["x"])
    if int(focus) > n_groups:
        focus = "1"
    return f"{n_groups} groups", options, focus


def _grouping_stats(stats):
    """The stats to group by, or None if fewer than 2 are picked."""
    return tuple(stats) if stats and len(stats) >= 2 else None


@app.callback(
    Output("group-map", "figure"),
    Output("group-positions", "figure"),
    Input("group-stats", "value"),
    Input("group-count", "value"),
)
def update_groups(stats, n_groups):
    stats = _grouping_stats(stats)
    if stats is None:
        message = figures.empty("Pick at least 2 stats to group players")
        return message, message
    df = data.groups(stats, n_groups)
    return figures.group_map(df), figures.group_positions(df)


@app.callback(
    Output("group-box", "figure"),
    Output("group-scatter", "figure"),
    Output("group-builds", "figure"),
    Output("box-title", "children"),
    Output("scatter-title", "children"),
    Input("group-stats", "value"),
    Input("group-count", "value"),
    Input("focus-group", "value"),
    Input("stat-a", "value"),
    Input("stat-b", "value"),
)
def update_group_details(stats, n_groups, focus, stat_a, stat_b):
    titles = (
        f"{data.stat_label(stat_a)} by group",
        f"{data.stat_label(stat_a)} vs {data.stat_label(stat_b)}",
    )
    stats = _grouping_stats(stats)
    if stats is None:
        message = figures.empty("Pick at least 2 stats to group players")
        return message, message, message, *titles
    df = data.groups(stats, n_groups)
    focus = min(int(focus), n_groups)
    return (
        figures.group_box(df, stat_a, focus),
        figures.group_scatter(df, stat_b, stat_a, focus),
        figures.group_scatter(df, "weight", "height", focus),
        *titles,
    )


if __name__ == "__main__":
    app.run(debug=True)
