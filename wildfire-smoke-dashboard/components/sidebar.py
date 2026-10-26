"""Left filter sidebar — tab-aware.

Sections are shown per tab (SECTION_TABS). Season and Pollutant are the *same*
components on every tab that shows them, so all tabs always share state.

Control-type rule (UX review): ≤4 mutually exclusive options → SegmentedControl,
longer lists → Select, on/off layers → Switch. Labels have no trailing colons.
"""

from datetime import date

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

from config import (
    AGE_OPTIONS,
    CHORO_OPTIONS,
    DEFAULT_AGE,
    DEFAULT_CHORO,
    DEFAULT_OPACITY,
    DEFAULT_POLLUTANT,
    DEFAULT_SMOKE_THRESHOLD,
    DEFAULT_SPEED,
    DEFAULT_TS_COUNTIES_BY_SEASON,
    HEADER_HEIGHT,
    MAX_TS_COUNTIES,
    PLAYBACK_SPEEDS,
    POLLUTANT_OPTIONS,
    SEASONS,
    SMOKE_THRESHOLD_OPTIONS,
)
from utils.data import COUNTY_OPTIONS, SEASON_DAYS
from utils.formatting import fmt_day_long

# Which tabs show each sidebar section (read by the layout and callbacks/navigation.py).
SECTION_TABS: dict[str, set[str]] = {
    "sec-season": {"map", "timeseries"},
    "sec-time": {"map"},
    "sec-playback": {"map"},
    "sec-pollutant": {"map", "timeseries"},
    "sec-layer": {"map"},
    "sec-exposure": {"map"},
    "sec-counties": {"timeseries"},
}
TABS_WITH_SIDEBAR = {"map", "timeseries"}
DARK_SIDEBAR_TABS = {"timeseries"}  # these tabs get the dark prussian sidebar (.sidebar-dark)
INITIAL_TAB = "map"


def section_style(section_id: str, tab: str) -> dict:
    return {"display": "block" if tab in SECTION_TABS[section_id] else "none"}


def sidebar_class(tab: str) -> str:
    return "sidebar-dark" if tab in DARK_SIDEBAR_TABS else ""


def sidebar_section(title: str, *children, id_: str) -> html.Section:
    return html.Section(
        dmc.Stack([dmc.Text(title, className="sidebar-section-title"), *children], gap="xs"),
        id=id_,
        className="sidebar-section",
        style=section_style(id_, INITIAL_TAB),
    )


def _icon_button(icon: str, id_: str, label: str, disabled: bool = False) -> dmc.Tooltip:
    return dmc.Tooltip(
        dmc.ActionIcon(
            DashIconify(icon=icon, width=15),
            id=id_,
            size="md",
            variant="default",
            disabled=disabled,
            className="sidebar-icon-btn",
            **{"aria-label": label},
        ),
        label=label,
    )


def _labeled_row(label: str, control) -> dmc.Group:
    return dmc.Group(
        [dmc.Text(label, className="sidebar-label"), control],
        justify="space-between",
        wrap="nowrap",
    )


# ── Season & day ──────────────────────────────────────────────────────────────
def season_section(season: str) -> html.Section:
    return sidebar_section(
        "Fire Season",
        dmc.SegmentedControl(
            id="season",
            data=[{"value": k, "label": m["label"]} for k, m in SEASONS.items()],
            value=season,
            fullWidth=True,
        ),
        dmc.Text(SEASONS[season]["note"], id="season-note", className="sidebar-caption"),
        id_="sec-season",
    )


def month_marks(season: str) -> list[dict]:
    """One slider mark per month, on its first day ("Aug", "Sep", …)."""
    days = SEASON_DAYS[season]
    return [
        {"value": i, "label": date.fromisoformat(d).strftime("%b")}
        for i, d in enumerate(days)
        if i == 0 or d[5:7] != days[i - 1][5:7]
    ]


def day_ui(season: str, day: str) -> dict:
    """Derived state of the day controls; shared by the layout and `set_day`."""
    days = SEASON_DAYS[season]
    idx = days.index(day)
    last = len(days) - 1
    return {
        "label": html.B(fmt_day_long(day)),
        "slider": idx,
        "slider_max": last,
        "marks": month_marks(season),
        "slider_label": {"function": "dayLabel", "options": {"days": days}},
        "progress": round(100 * idx / last, 1) if last else 100,
        "progress_label": f"Day {idx + 1} of {len(days)}",
        "at_start": idx == 0,
        "at_end": idx == last,
    }


def time_period_section(season: str, day: str) -> html.Section:
    ui = day_ui(season, day)
    return sidebar_section(
        "Day",
        dmc.Group(
            [
                _icon_button("tabler:chevron-left", "day-prev", "Previous day", ui["at_start"]),
                dmc.Text(ui["label"], id="day-label", className="week-label"),
                _icon_button("tabler:chevron-right", "day-next", "Next day", ui["at_end"]),
            ],
            justify="space-between",
            wrap="nowrap",
            gap=4,
        ),
        dmc.Slider(
            id="day-slider",
            min=0,
            max=ui["slider_max"],
            value=ui["slider"],
            step=1,
            marks=ui["marks"],
            label=ui["slider_label"],
            size="sm",
            color="charcoal",
            updatemode="mouseup",
            className="sidebar-slider",
            mb="md",
        ),
        id_="sec-time",
    )


def playback_section(season: str, day: str) -> html.Section:
    ui = day_ui(season, day)
    return sidebar_section(
        "Playback",
        dmc.Stack(
            [
                dmc.Text("Speed (per day)", className="sidebar-label"),
                dmc.SegmentedControl(
                    id="playback-speed",
                    data=PLAYBACK_SPEEDS,
                    value=DEFAULT_SPEED,
                    fullWidth=True,
                ),
            ],
            gap=4,
        ),
        dmc.Group(
            [
                _icon_button("tabler:player-skip-back", "day-first", "Jump to first day", ui["at_start"]),
                dmc.Button(
                    "Play",
                    id="play-btn",
                    leftSection=DashIconify(icon="tabler:player-play-filled", width=14),
                    size="xs",
                    h=30,
                    color="charcoal",
                    flex=1,
                ),
                _icon_button("tabler:player-stop", "play-stop", "Stop", True),
                _icon_button("tabler:player-skip-forward", "day-last", "Jump to last day", ui["at_end"]),
            ],
            gap=6,
            wrap="nowrap",
        ),
        dmc.Stack(
            [
                dmc.Progress(id="day-progress", value=ui["progress"], size="sm", color="charcoal", className="week-progress"),
                dmc.Group(
                    [
                        dmc.Text(ui["progress_label"], id="day-progress-label", className="sidebar-caption"),
                        dmc.Badge("Live", id="live-badge", color="peach", variant="dot", size="xs", display="none"),
                    ],
                    justify="space-between",
                    h=18,
                ),
            ],
            gap=4,
        ),
        id_="sec-playback",
    )


# ── Filters & layers ──────────────────────────────────────────────────────────
def pollutant_section() -> html.Section:
    return sidebar_section(
        "Pollutant",
        dmc.SegmentedControl(id="pollutant", data=POLLUTANT_OPTIONS, value=DEFAULT_POLLUTANT, fullWidth=True),
        dmc.Text("Monitors coloured by EPA AQI category", className="sidebar-caption"),
        id_="sec-pollutant",
    )


def map_layer_section() -> html.Section:
    return sidebar_section(
        "Map Layers",
        dmc.Select(id="choro-metric", label="County shading", data=CHORO_OPTIONS, value=DEFAULT_CHORO),
        dmc.Stack(
            [
                _labeled_row(
                    "Shading opacity",
                    dmc.Text(f"{DEFAULT_OPACITY:.0%}", id="choro-opacity-label", className="sidebar-caption tabular-nums"),
                ),
                dmc.Slider(
                    id="choro-opacity",
                    min=0,
                    max=1,
                    step=0.05,
                    value=DEFAULT_OPACITY,
                    size="sm",
                    color="charcoal",
                    label=None,
                    updatemode="drag",
                    className="sidebar-slider",
                ),
            ],
            gap=6,
        ),
        dmc.Switch(id="show-smoke", label="HMS smoke plumes", checked=True, size="sm", color="charcoal", className="sidebar-switch"),
        dmc.Switch(id="show-fires", label="Fire perimeters (CAL FIRE)", checked=True, size="sm", color="charcoal", className="sidebar-switch"),
        id_="sec-layer",
    )


def exposure_section() -> html.Section:
    return sidebar_section(
        "Exposure & Health",
        dmc.Stack(
            [
                dmc.Text("Smoke day = county under", className="sidebar-label"),
                dmc.SegmentedControl(
                    id="smoke-threshold", data=SMOKE_THRESHOLD_OPTIONS, value=DEFAULT_SMOKE_THRESHOLD, fullWidth=True
                ),
            ],
            gap=4,
        ),
        dmc.Stack(
            [
                dmc.Text("Asthma ED rate", className="sidebar-label"),
                dmc.SegmentedControl(id="asthma-age", data=AGE_OPTIONS, value=DEFAULT_AGE, fullWidth=True),
            ],
            gap=4,
        ),
        id_="sec-exposure",
    )


def counties_section(season: str) -> html.Section:
    return sidebar_section(
        "Counties",
        dmc.MultiSelect(
            id="ts-counties",
            data=COUNTY_OPTIONS,
            value=DEFAULT_TS_COUNTIES_BY_SEASON[season],
            maxValues=MAX_TS_COUNTIES,
            searchable=True,
            clearable=True,
            placeholder="Pick up to 5 counties",
            **{"aria-label": "Counties"},
        ),
        dmc.Text(f"Up to {MAX_TS_COUNTIES}; resets to notable counties when the season changes", className="sidebar-caption"),
        id_="sec-counties",
    )


def sidebar(season: str, day: str) -> dmc.AppShellNavbar:
    return dmc.AppShellNavbar(
        dmc.ScrollArea(
            [
                season_section(season),
                time_period_section(season, day),
                playback_section(season, day),
                pollutant_section(),
                map_layer_section(),
                exposure_section(),
                counties_section(season),
            ],
            h=f"calc(100vh - {HEADER_HEIGHT}px)",
            type="scroll",
            scrollbarSize=6,
        ),
        id="sidebar",
        className=sidebar_class(INITIAL_TAB),
        withBorder=False,
    )
