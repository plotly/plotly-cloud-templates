"""Time Series tab — daily county-mean concentration vs the HMS smoke-day flag.

Controls live in the tab-aware sidebar (Fire Season, Pollutant, Counties); this
panel holds the chart and a one-line summary of smoke days for the selection.
"""

import dash_mantine_components as dmc
import pandas as pd
from dash import dcc, html

from components.stat_cards import info_tip
from config import DEFAULT_POLLUTANT, DEFAULT_SMOKE_THRESHOLD, HEADER_HEIGHT, LOADER_COLOR, POLLUTANTS, SEASONS, SMOKE_LEVELS, TS_COLORS
from utils.data import COUNTY_NAMES
from utils.timeseries import smoke_strip
from utils.timeseries_figure import TS_GRAPH_CONFIG, build_timeseries_figure


# ── View helpers (shared by the layout and callbacks/timeseries.py) ──────────
def ts_subtitle(season: str, pollutant: str) -> str:
    return f"{POLLUTANTS[pollutant]['long']} · {SEASONS[season]['label']} season ({SEASONS[season]['note']})"


def smoke_summary(season: str, counties: list[str], threshold: int = int(DEFAULT_SMOKE_THRESHOLD)) -> list:
    """One badge per selected county: smoke days at or above the threshold."""
    if not counties:
        return []
    strip = smoke_strip(season, counties)
    label = SMOKE_LEVELS[threshold]["label"] + ("+" if threshold < 3 else "")
    items = [dmc.Text(f"{label} smoke days", size="xs", fw=500, c="gray.7")]
    for i, fips in enumerate(counties):
        n = int((strip[fips] >= threshold).sum())
        color = TS_COLORS[i % len(TS_COLORS)]
        items.append(
            dmc.Badge(
                f"{COUNTY_NAMES[fips]} · {n}",
                leftSection=html.Span(className="pin-dot", style={"background": color}),
                color="gray",
                variant="light",
                size="sm",
                radius="sm",
            )
        )
    missing = int(strip.isna().all(axis=1).sum()) if isinstance(strip, pd.DataFrame) else 0
    if missing:
        items.append(dmc.Text(f"({missing} days without HMS data)", size="xs", c="dimmed"))
    return items


# ── Layout ────────────────────────────────────────────────────────────────────
def timeseries_view(season: str, day: str, counties: list[str]) -> dmc.Box:
    figure = build_timeseries_figure(season, DEFAULT_POLLUTANT, counties, day)
    header = dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Title("Daily Air Quality by County", order=2, fz="md", fw=700),
                            info_tip(
                                "Lines: daily mean of each county's monitors (gaps = no monitor reported). "
                                "Dotted: population-weighted statewide mean. Background bands: EPA AQI categories. "
                                "Bottom strip: NOAA HMS smoke density over ≥25% of the county. Click a day to select it on the map."
                            ),
                        ],
                        gap=6,
                    ),
                    dmc.Text(ts_subtitle(season, DEFAULT_POLLUTANT), id="ts-subtitle", size="xs", c="dimmed"),
                ],
                gap=2,
            ),
            dmc.Group(smoke_summary(season, counties), id="ts-smoke-summary", gap=8),
        ],
        justify="space-between",
        align="flex-start",
    )
    chart = html.Div(
        dcc.Loading(
            dcc.Graph(id="ts-graph", figure=figure, config=TS_GRAPH_CONFIG, className="graph-fill"),
            delay_show=450,
            delay_hide=150,
            type="circle",
            color=LOADER_COLOR,
            parent_className="graph-loading-wrapper",
        ),
        className="chart-container",
    )
    return dmc.Box(
        dmc.Card([header, chart], shadow="xs", className="ts-card"),
        p="md",
        h=f"calc(100vh - {HEADER_HEIGHT}px)",
    )
