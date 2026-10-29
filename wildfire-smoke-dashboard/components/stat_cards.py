"""Right-hand stat cards (Map View).

Data flow:  utils.stats (numbers) → *_view() (formatted strings/props) → layout or callback.
The same view builders seed the initial layout and feed callbacks/stat_cards.py,
so the first render never shows placeholders and formatting lives in one place.

Each view is a dict keyed exactly like the callback's output names. Pattern-matching
slots (ids like {"type": "aq-kpi", "key": "mean"}) are nested dicts keyed by `key`.

Conventions
- Numbers use `tabular-nums` so they don't jitter during playback.
- Trend direction is always carried by icon + sign, never colour alone.
  Colour semantics: pollution up = peach / down = pale charcoal (tuned for the dark pane).
- Definitions live behind info tooltips to keep the cards compact.
"""

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from config import AQI_CATEGORIES, DEFAULT_POLLUTANT, POLLUTANTS, SMOKE_LEVELS
from utils.aqi import category
from utils.formatting import (
    PLACEHOLDER,
    TREND_ICON,
    css_color,
    fmt_change,
    fmt_day_long,
    fmt_day_short,
    fmt_number,
    fmt_people,
    trend_color,
)
from utils.stats import AirStats, Change, ExposureStats, air_stats, exposure_stats

AQ_TRENDS = [("mean", "Statewide mean"), ("peak", "Peak monitor")]


# ── View builders (pure: stats → display values) ──────────────────────────────
def _display(show: bool) -> str:
    return "block" if show else "none"


def _compare_label(prev_day: str | None) -> str:
    return f"vs {fmt_day_short(prev_day)}" if prev_day else "first day of season"


def _trend_fields(texts: dict[str, str], changes: dict[str, Change]) -> dict:
    """Icon, icon colour, text and text colour for each trend key."""
    colors = {k: trend_color(ch.direction) for k, ch in changes.items()}
    return {
        "trend_icon": {k: TREND_ICON[ch.direction] for k, ch in changes.items()},
        "trend_icon_color": {k: css_color(c) for k, c in colors.items()},
        "trend_text": texts,
        "trend_text_color": colors,
    }


def _aqi_caption(index: int | None) -> str:
    cat = category(index)
    return f"AQI {index} · {cat['short']}" if cat else ""


def air_view(stats: AirStats) -> dict:
    meta = POLLUTANTS[stats.pollutant]
    dec, unit = meta["decimals"], meta["unit"]
    changes = {"mean": stats.mean_change, "peak": stats.peak_change}
    texts = {k: fmt_change(ch, dec, unit) for k, ch in changes.items()}
    return {
        "subtitle": f"{meta['long']} · {fmt_day_long(stats.day)}",
        "kpis": {
            "reporting": fmt_number(stats.reporting),
            "unhealthy": fmt_number(stats.unhealthy_plus),
            "mean": fmt_number(stats.mean, dec),
            "peak": fmt_number(stats.peak, dec),
        },
        "units": {"mean": unit, "peak": unit},
        "peak_site": f"{stats.peak_site} · {_aqi_caption(stats.peak_aqi)}" if stats.peak_site else "",
        "levels": {c["key"]: f"{n}" for c, n in zip(AQI_CATEGORIES, stats.level_counts)},
        **_trend_fields(texts, changes),
        "compare": _compare_label(stats.prev_day),
        "empty": _display(not stats.has_data),
    }


def exposure_view(stats: ExposureStats) -> dict:
    meta = POLLUTANTS[stats.pollutant]
    return {
        "kpis": {
            "popmean": fmt_number(stats.pop_weighted, meta["decimals"]),
            "popusg": fmt_people(stats.pop_usg_plus),
            "days": fmt_number(stats.days_unhealthy),
            "popsmoke": fmt_people(stats.pop_smoke) if stats.smoke_available else PLACEHOLDER,
        },
        "popmean_caption": _aqi_caption(stats.pop_weighted_aqi) or meta["unit"],
        "days_caption": f"of {stats.days_elapsed} days so far",
        "smoke_levels": {
            str(lvl): (f"{n} counties" if stats.smoke_available else PLACEHOLDER)
            for lvl, n in zip(SMOKE_LEVELS, stats.smoke_counties)
        },
        "smoke_empty": _display(not stats.smoke_available),
    }


# ── Primitives ────────────────────────────────────────────────────────────────
def card_header(title: str, subtitle_id: str | None = None, subtitle: str = "") -> dmc.Stack:
    sub = dmc.Text(subtitle, id=subtitle_id, size="xs", c="dimmed") if subtitle_id else dmc.Text(subtitle, size="xs", c="dimmed")
    return dmc.Stack([dmc.Title(title, order=2, fz="sm", fw=600), sub], gap=4)


def info_tip(text: str, color: str = "gray") -> dmc.Tooltip:
    return dmc.Tooltip(
        dmc.Box(
            DashIconify(icon="tabler:info-circle", width=12, color=f"var(--mantine-color-{color}-5)"),
            className="info-tip",
        ),
        label=text,
        multiline=True,
        w=220,
        position="top",
    )


def stat_cell(
    label: str,
    id_: dict,
    value: str = PLACEHOLDER,
    info: str | None = None,
    size: str = "xl",
    caption: tuple[str | dict, str] | None = None,
) -> dmc.Box:
    """One cell of a hairline-divided stat grid (see .stat-grid in styles.css).
    `caption` is an optional (id, text) line under the value."""
    label_row = dmc.Group(
        [dmc.Text(label, size="xs", c="dimmed", lh=1.25)] + ([info_tip(info)] if info else []),
        gap=4,
        wrap="nowrap",
        align="center",
    )
    children = [label_row, dmc.Text(value, id=id_, fw=600, fz=size, lh=1.2, className="tabular-nums")]
    if caption:
        caption_id, caption_text = caption
        children.append(dmc.Text(caption_text, id=caption_id, size="xs", c="dimmed", lh=1.2, className="tabular-nums"))
    return dmc.Box(dmc.Stack(children, gap=4), className="stat-cell")


def section_label(text: str, info: str | None = None, suffix: tuple[str, str] | None = None) -> dmc.Group:
    """Section heading; `suffix` is an optional (id, text) dimmed note, e.g. "vs Sep 11"."""
    children = [dmc.Text(text, size="xs", fw=500, c="dimmed")]
    if info:
        children.append(info_tip(info))
    if suffix:
        suffix_id, suffix_text = suffix
        children.append(dmc.Text(suffix_text, id=suffix_id, size="xs", c="dimmed", ml="auto"))
    return dmc.Group(children, gap=4, wrap="nowrap")


def swatch(color: str, size: int = 10, shape: str = "circle", border: bool = False) -> dmc.Box:
    style = {"background": color}
    if border:
        style["boxShadow"] = "inset 0 0 0 1px rgba(0,0,0,0.25)"
    return dmc.Box(w=size, h=size, className=f"swatch swatch-{shape}", style=style)


def level_row(cat: dict, value: str = PLACEHOLDER) -> dmc.Group:
    return dmc.Group(
        [
            swatch(cat["color"], border=True),
            dmc.Text(cat["short"], size="xs", flex=1),
            dmc.Text(f"{cat['min']}–{cat['max']}", size="xs", c="dimmed", className="tabular-nums"),
            dmc.Text(value, id={"type": "aq-level", "key": cat["key"]}, size="xs", fw=500, w=36, ta="right", className="tabular-nums"),
        ],
        gap=8,
        wrap="nowrap",
    )


def smoke_row(level: int, value: str = PLACEHOLDER) -> dmc.Group:
    meta = SMOKE_LEVELS[level]
    return dmc.Group(
        [
            swatch(meta["color"], 10, "square"),
            dmc.Text(meta["label"], size="xs", flex=1),
            dmc.Text(value, id={"type": "smoke-level", "key": str(level)}, size="xs", fw=500, ta="right", className="tabular-nums"),
        ],
        gap=8,
        wrap="nowrap",
    )


def trend_row(label: str, type_: str, key: str, view: dict) -> dmc.Group:
    return dmc.Group(
        [
            dmc.Text(label, size="xs", c="dimmed"),
            dmc.Group(
                [
                    DashIconify(
                        icon=view["trend_icon"][key],
                        width=14,
                        color=view["trend_icon_color"][key],
                        id={"type": f"{type_}-icon", "key": key},
                    ),
                    dmc.Text(
                        view["trend_text"][key],
                        id={"type": f"{type_}-value", "key": key},
                        size="xs",
                        fw=500,
                        c=view["trend_text_color"][key],
                        className="tabular-nums",
                    ),
                ],
                gap=4,
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        wrap="nowrap",
    )


def empty_state(text: str, id_: str, display: str = "none") -> dmc.Text:
    return dmc.Text(text, id=id_, size="xs", c="dimmed", ta="center", py="xs", display=display)


# ── Cards ─────────────────────────────────────────────────────────────────────
def air_card(view: dict) -> dmc.Card:
    kpis = view["kpis"]
    body = dmc.Stack(
        [
            card_header("Air Quality Monitors", "aq-subtitle", view["subtitle"]),
            dmc.SimpleGrid(
                [
                    stat_cell("Monitors reporting", {"type": "aq-kpi", "key": "reporting"}, kpis["reporting"],
                             "EPA AQS sites (FRM/FEM) with a valid daily value for this pollutant."),
                    stat_cell("Unhealthy+ monitors", {"type": "aq-kpi", "key": "unhealthy"}, kpis["unhealthy"],
                             "Monitors with a daily AQI above 150 (Unhealthy, Very Unhealthy or Hazardous)."),
                    stat_cell("Statewide mean", {"type": "aq-kpi", "key": "mean"}, kpis["mean"],
                             "Simple mean across reporting monitors.", caption=({"type": "aq-unit", "key": "mean"}, view["units"]["mean"])),
                    stat_cell("Peak monitor", {"type": "aq-kpi", "key": "peak"}, kpis["peak"],
                             "Highest single-monitor daily value.", caption=({"type": "aq-unit", "key": "peak"}, view["units"]["peak"])),
                ],
                cols=2,
                spacing=0,
                verticalSpacing=0,
                className="stat-grid",
            ),
            dmc.Text(view["peak_site"], id="aq-peak-site", size="xs", c="dimmed", lh=1.3),
            empty_state("No monitor data for this day", "aq-empty", view["empty"]),
            dmc.Divider(),
            dmc.Stack(
                [section_label("AQI distribution", "Monitors grouped by EPA AQI category; colours match the map bubbles.")]
                + [level_row(c, view["levels"][c["key"]]) for c in AQI_CATEGORIES],
                gap=6,
            ),
            dmc.Divider(),
            dmc.Stack(
                [
                    section_label("Day-over-day", "Change versus the previous calendar day.", suffix=("aq-compare", view["compare"])),
                    *[trend_row(label, "aq-trend", key, view) for key, label in AQ_TRENDS],
                ],
                gap=6,
            ),
        ],
        gap="sm",
    )
    return dmc.Card(body, shadow="xs")


def exposure_card(view: dict) -> dmc.Card:
    kpis = view["kpis"]
    body = dmc.Stack(
        [
            card_header("Smoke & Population Exposure", subtitle="County means weighted by Census population"),
            dmc.SimpleGrid(
                [
                    stat_cell("Pop-weighted mean", {"type": "ex-kpi", "key": "popmean"}, kpis["popmean"],
                             "County-mean concentration weighted by county population, over counties with a reporting monitor.",
                             caption=("ex-popmean-caption", view["popmean_caption"])),
                    stat_cell("Residents, AQI > 100", {"type": "ex-kpi", "key": "popusg"}, kpis["popusg"],
                             "Population of counties whose county-mean AQI is Unhealthy for Sensitive Groups or worse."),
                    stat_cell("Unhealthy+ days", {"type": "ex-kpi", "key": "days"}, kpis["days"],
                             "Season to date: days on which at least one monitor exceeded AQI 150.",
                             caption=("ex-days-caption", view["days_caption"])),
                    stat_cell("Residents under smoke", {"type": "ex-kpi", "key": "popsmoke"}, kpis["popsmoke"],
                             "Population of counties with Medium or Heavy HMS smoke over ≥25% of their area today."),
                ],
                cols=2,
                spacing=0,
                verticalSpacing=0,
                className="stat-grid",
            ),
            dmc.Divider(),
            dmc.Stack(
                [section_label("Counties under smoke today", "Highest NOAA HMS density covering ≥25% of the county's area.")]
                + [smoke_row(lvl, view["smoke_levels"][str(lvl)]) for lvl in SMOKE_LEVELS],
                gap=6,
            ),
            empty_state("No HMS smoke analysis for this day", "smoke-empty", view["smoke_empty"]),
        ],
        gap="sm",
    )
    return dmc.Card(body, shadow="xs")


def stats_column(season: str, day: str) -> dmc.Stack:
    """Both cards, server-seeded with the default pollutant (callbacks use prevent_initial_call)."""
    air = air_view(air_stats(season, day, DEFAULT_POLLUTANT))
    exposure = exposure_view(exposure_stats(season, day, DEFAULT_POLLUTANT))
    return dmc.Stack([air_card(air), exposure_card(exposure)], gap="md", p="md")
