"""Map View body: context bar, county map with legend overlay, stat-card column."""

import dash_mantine_components as dmc
from dash import dcc, html

from components.stat_cards import stats_column, swatch
from config import (
    AQI_CATEGORIES,
    CHORO_META,
    DEFAULT_CHORO,
    DEFAULT_POLLUTANT,
    FIRE_COLOR,
    FIRE_CONTAINED_COLOR,
    HEADER_HEIGHT,
    LOADER_COLOR,
    POLLUTANTS,
    SEASONS,
    SMOKE_LEVELS,
    STATS_WIDTH,
)
from utils.data import SMOKE_DAYS_AVAILABLE, health_year
from utils.formatting import fmt_day_long
from utils.map_figure import GRAPH_CONFIG, build_base_map, palette_to_gradient


def map_context_text(season: str, day: str, pollutant: str) -> str:
    smoke = "" if day in SMOKE_DAYS_AVAILABLE else " · no HMS smoke analysis this day"
    return f"{POLLUTANTS[pollutant]['label']} · {fmt_day_long(day)} · {SEASONS[season]['note']}{smoke}"


def context_bar(season: str, day: str) -> dmc.Group:
    return dmc.Group(
        [
            dmc.Badge(SEASONS[season]["label"], id="season-badge", color="charcoal", variant="light", size="lg", radius="xl"),
            dmc.Text(map_context_text(season, day, DEFAULT_POLLUTANT), id="map-context", size="sm", c="gray.7", fw=500),
        ],
        gap="md",
        px="md",
        py="xs",
        className="mode-bar",
        wrap="nowrap",
    )


def choro_legend(choro: str, season: str, z_max: float | None = None, age: str = "all") -> list:
    """Legend block for the county shading (empty for outlines only)."""
    if choro == "none":
        return []
    meta = CHORO_META[choro]
    if choro == "aq_mean":
        return [
            dmc.Text(meta["label"], className="legend-title"),
            dmc.Text("Shaded with the AQI colours below", className="legend-note"),
            dmc.Divider(my=4),
        ]
    if choro == "asthma":
        title = f"Asthma ED visits / 10k ({'children' if age == 'child' else 'all ages'}, {health_year(season)})"
    elif choro == "vuln":
        title = "Asthma rate × smoke days (0–100)"
    else:
        title = meta["label"]
    hi = "100" if choro == "vuln" else (f"{z_max:,.0f}" if z_max is not None else "")
    return [
        dmc.Text(title, className="legend-title"),
        html.Div(className="legend-gradient", style={"background": palette_to_gradient(meta["palette"])}),
        dmc.Group([dmc.Text("0", className="legend-text tabular-nums"), dmc.Text(hi, className="legend-text tabular-nums")], justify="space-between"),
        dmc.Divider(my=4),
    ]


def aqi_legend(pollutant: str) -> list:
    rows = []
    for (c_lo, c_hi, _i, _j), cat in zip(POLLUTANTS[pollutant]["breakpoints"], AQI_CATEGORIES):
        rows.append(
            dmc.Group([swatch(cat["color"], 10, border=True), dmc.Text(f"{cat['short']} ({c_lo:g}–{c_hi:g})", className="legend-text")], gap=6)
        )
    return [
        dmc.Text(f"Monitor AQI ({POLLUTANTS[pollutant]['unit']})", className="legend-title"),
        dmc.Stack(rows, gap=2),
        dmc.Text("Circle size = AQI", className="legend-note"),
    ]


def layers_legend() -> list:
    smoke_rows = [
        dmc.Group([swatch(m["color"], 10, "square"), dmc.Text(f"{m['label']} smoke", className="legend-text")], gap=6)
        for m in SMOKE_LEVELS.values()
    ]
    fire_rows = [
        dmc.Group([swatch(FIRE_COLOR, 10, "square"), dmc.Text("Fire burning", className="legend-text")], gap=6),
        dmc.Group([swatch(FIRE_CONTAINED_COLOR, 10, "square"), dmc.Text("Fire contained", className="legend-text")], gap=6),
    ]
    return [
        dmc.Divider(my=4),
        dmc.SimpleGrid([dmc.Stack(smoke_rows, gap=2), dmc.Stack(fire_rows, gap=2)], cols=2, spacing=4),
        dmc.Text("Fires show final perimeters", className="legend-note"),
    ]


def legend_overlay(season: str) -> dmc.Paper:
    return dmc.Paper(
        dmc.Stack(
            [
                html.Div(choro_legend(DEFAULT_CHORO, season), id="legend-choro"),
                html.Div(aqi_legend(DEFAULT_POLLUTANT), id="legend-aqi"),
                *layers_legend(),
            ],
            gap=4,
        ),
        className="map-legend",
        p="xs",
        shadow="sm",
        withBorder=True,
    )


def map_card(season: str, day: str) -> dmc.Paper:
    """Graph container follows the mosquito dashboard: a flex-column host, a Loading wrapper
    that flexes to fill it, and a 100%×100% dcc.Graph (see .map-container rules in styles.css)."""
    graph = dcc.Graph(
        id="map",
        figure=build_base_map(season, day),
        config=GRAPH_CONFIG,
        style={"height": "100%", "width": "100%"},
        className="graph-fill",
    )
    return dmc.Paper(
        [
            dcc.Loading(
                graph,
                delay_show=450,
                delay_hide=150,
                type="circle",
                color=LOADER_COLOR,
                parent_className="graph-loading-wrapper",
            ),
            legend_overlay(season),
        ],
        withBorder=True,
        radius="lg",
        className="map-container",
    )


def map_view(season: str, day: str) -> dmc.Flex:
    """Context bar sits over the map column only, so the dark stats pane runs full height."""
    return dmc.Flex(
        [
            dmc.Stack(
                [context_bar(season, day), dmc.Box(map_card(season, day), p="md", className="map-pane")],
                gap=0,
                flex=1,
                miw=0,
                mih=0,
            ),
            dmc.ScrollArea(stats_column(season, day), w=STATS_WIDTH, type="scroll", scrollbarSize=6, className="stats-column"),
        ],
        h=f"calc(100vh - {HEADER_HEIGHT}px)",
    )
