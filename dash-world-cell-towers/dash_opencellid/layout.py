"""
Page layout built with Dash Mantine Components
"""
from textwrap import dedent

import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

from dash_opencellid.figures import (
    HISTOGRAM_HEIGHT,
    MAP_HEIGHT,
    RADIO_HEIGHT,
    blank_figure,
)
from dash_opencellid.theme import FONT_FAMILY, RADIO_COLORS, RADIO_LABELS

THEME = {
    "fontFamily": FONT_FAMILY,
    "headings": {"fontFamily": FONT_FAMILY},
    "primaryColor": "dark",
    "defaultRadius": "md",
}

GRAPH_CONFIG = {"displayModeBar": False}

HELP = {
    "towers": """
        The number of towers that are visible on the **Locations** map and match the
        selections made in the **Radio**, **Signal range**, and **Year added** charts.

        **Reset all** clears every selection and recenters the map.
    """,
    "radio": """
        The number of towers using each radio technology, on a log scale. Colored
        bars show the towers in the current selection, and their colors match the map.

        Click a bar to select that technology, and shift-click to add more. You can
        also drag across several bars.
    """,
    "map": """
        Every selected tower, colored by radio technology. Drag to pan, scroll to
        zoom, and right-click drag to rotate or tilt the map.

        When 5,000 or fewer towers are in view, each one is drawn individually and
        you can hover it for details.
    """,
    "range": """
        The approximate signal range of each tower. Light bars show every tower in
        the dataset, and dark bars show the towers in the current selection.

        Drag across the chart to select a range.
    """,
    "created": """
        The year each tower was added to the OpenCelliD database. Light bars show
        every tower in the dataset, and dark bars show the towers in the current
        selection.

        Drag across the chart to select a period.
    """,
}


def help_popover(name):
    return dmc.Popover(
        [
            dmc.PopoverTarget(
                dmc.ActionIcon(
                    DashIconify(icon="tabler:info-circle", width=18),
                    variant="subtle",
                    color="gray",
                    size="sm",
                    **{"aria-label": "About this chart"},
                )
            ),
            dmc.PopoverDropdown(
                dcc.Markdown(dedent(HELP[name]), className="help-text"),
            ),
        ],
        width=300,
        position="bottom-end",
        withArrow=True,
        shadow="md",
    )


def card(title, name, body, action=None, aside=None):
    """
    Card with a title, a help popover, optional content shown next to the title
    (aside), and an optional action button
    """
    return dmc.Card(
        [
            dmc.Group(
                [
                    dmc.Group(
                        [
                            dmc.Group(
                                [dmc.Text(title, fw=600), help_popover(name)],
                                gap=4,
                                wrap="nowrap",
                            ),
                            aside,
                        ],
                        gap="lg",
                    ),
                    action,
                ],
                justify="space-between",
                mb="xs",
                wrap="nowrap",
            ),
            body,
        ],
        withBorder=True,
        padding="sm",
        px="md",
        h="100%",
    )


def clear_button(id, label="Clear selection"):
    return dmc.Button(
        label,
        id=id,
        variant="subtle",
        color="gray",
        size="compact-sm",
        leftSection=DashIconify(icon="tabler:x", width=14),
    )


def graph(id, height):
    return dcc.Graph(
        id=id,
        figure=blank_figure(height),
        config=GRAPH_CONFIG,
        style={"height": height},
    )


def radio_legend():
    """Legend of the map's colors"""
    return dmc.Group(
        [
            dmc.Group(
                [
                    html.Span(className="legend-dot", style={"background": color}),
                    dmc.Text(RADIO_LABELS[radio], size="xs", c="dimmed"),
                ],
                gap=6,
            )
            for radio, color in RADIO_COLORS.items()
        ],
        gap="md",
    )


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    dmc.ThemeIcon(
                        DashIconify(icon="tabler:antenna", width=22),
                        size="lg",
                        variant="light",
                        color="gray",
                        visibleFrom="sm",
                    ),
                    dmc.Stack(
                        [
                            dmc.Title("World Cell Towers", order=4),
                            dmc.Text(
                                "Every cell tower in the OpenCelliD database",
                                size="xs",
                                c="dimmed",
                                visibleFrom="sm",
                            ),
                        ],
                        gap=0,
                    ),
                ],
                gap="sm",
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "Reset all",
                        id="clear-all",
                        variant="default",
                        size="sm",
                        leftSection=DashIconify(icon="tabler:refresh", width=16),
                    ),
                    html.A(
                        html.Img(src="assets/dash-logo.png", height=32, alt="Dash"),
                        href="https://dash.plotly.com/",
                        className="dash-logo",
                    ),
                ],
                gap="md",
            ),
        ],
        justify="space-between",
        h="100%",
        px="lg",
        wrap="nowrap",
    )
)

loading_card = dmc.Card(
    dmc.Group(
        [
            dmc.Loader(size="sm", color="gray", id="data-loader"),
            dmc.Stack(
                [
                    dmc.Text("Preparing the dataset", fw=600, size="sm"),
                    dmc.Text("Starting...", id="data-status", size="sm", c="dimmed"),
                ],
                gap=2,
            ),
        ],
        wrap="nowrap",
    ),
    id="data-status-card",
    withBorder=True,
    padding="md",
    mb="md",
)

towers_card = card(
    "Selected towers",
    "towers",
    dmc.Stack(
        [
            dmc.Skeleton(
                dmc.Text("0", id="selected-count", className="hero-number"),
                id="selected-count-skeleton",
                visible=True,
            ),
            dmc.Text("Loading...", id="selected-share", size="sm", c="dimmed"),
            dmc.Progress(id="selected-progress", value=0, size="sm", color="dark", mt="xs"),
        ],
        gap=4,
        justify="center",
        style={"flex": 1},
    ),
)

radio_card = card(
    "Radio",
    "radio",
    graph("radio-histogram", RADIO_HEIGHT),
    clear_button("clear-radio"),
    aside=dmc.Text("Towers per technology, log scale", size="xs", c="dimmed", visibleFrom="sm"),
)

map_card = card(
    "Locations",
    "map",
    graph("map-graph", MAP_HEIGHT),
    clear_button("reset-map", "Reset view"),
    aside=radio_legend(),
)

range_card = card(
    "Signal range",
    "range",
    graph("range-histogram", HISTOGRAM_HEIGHT),
    clear_button("clear-range"),
)

created_card = card(
    "Year added",
    "created",
    graph("created-histogram", HISTOGRAM_HEIGHT),
    clear_button("clear-created"),
)

acknowledgements = dmc.Text(
    dcc.Markdown(
        "Built with [Dash](https://dash.plotly.com/) and "
        "[Datashader](https://datashader.org/). "
        "Tower data from [OpenCelliD](https://opencellid.org/), licensed under "
        "[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). "
        "Operator names from "
        "[mcc-mnc-list](https://github.com/pbakondy/mcc-mnc-list). "
        "Base map © [CARTO](https://carto.com/basemaps/), rendered with "
        "[MapLibre](https://maplibre.org/).",
        className="acknowledgements",
    ),
    size="xs",
    c="dimmed",
    ta="center",
    mt="lg",
)

layout = dmc.MantineProvider(
    dmc.AppShell(
        [
            header,
            dmc.AppShellMain(
                dmc.Container(
                    [
                        dcc.Interval(id="data-poll", interval=2000),
                        dcc.Store(id="data-ready", data=False),
                        loading_card,
                        dmc.Grid(
                            [
                                dmc.GridCol(towers_card, span={"base": 12, "md": 4}),
                                dmc.GridCol(radio_card, span={"base": 12, "md": 8}),
                                dmc.GridCol(map_card, span=12),
                                dmc.GridCol(range_card, span={"base": 12, "md": 6}),
                                dmc.GridCol(created_card, span={"base": 12, "md": 6}),
                            ],
                            gutter="md",
                        ),
                        acknowledgements,
                    ],
                    size="xl",
                    py="md",
                )
            ),
        ],
        header={"height": 64},
    ),
    theme=THEME,
    forceColorScheme="light",
)
