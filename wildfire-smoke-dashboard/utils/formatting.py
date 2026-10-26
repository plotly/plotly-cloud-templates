"""Presentation helpers for stat cards — number formatting, trends, dates."""

from datetime import date

from utils.stats import Change, Direction

PLACEHOLDER = "—"
MINUS = "−"  # typographic minus lines up with "+" in tabular figures

TREND_ICON: dict[Direction, str] = {
    "up": "tabler:trending-up",
    "down": "tabler:trending-down",
    "flat": "tabler:minus",
    "na": "tabler:minus",
}


def fmt_number(value: float | None, decimals: int = 0) -> str:
    """Thousands-separated number; "—" for missing values."""
    if value is None:
        return PLACEHOLDER
    text = f"{abs(value):,.{decimals}f}"
    negative = value < 0 and text.strip("0.,") != ""
    return f"{MINUS}{text}" if negative else text


def fmt_signed(value: float, decimals: int = 0) -> str:
    """Explicit sign: +1.2 / −1.2 / 0."""
    text = f"{abs(value):,.{decimals}f}"
    if text.strip("0.,") == "":
        return text
    return f"+{text}" if value > 0 else f"{MINUS}{text}"


def fmt_change(change: Change, decimals: int = 0, unit: str = "", show_pct: bool = True) -> str:
    """e.g. "+12.4 µg/m³ (+38.0%)"."""
    if change.delta is None:
        return PLACEHOLDER
    text = fmt_signed(change.delta, decimals)
    if unit:
        text += f" {unit}"
    if show_pct and change.pct is not None:
        text += f" ({fmt_signed(change.pct, 1)}%)"
    return text


def fmt_people(value: int | None) -> str:
    """Compact population: 1.2M / 845K / 950."""
    if value is None:
        return PLACEHOLDER
    if value >= 1_000_000:
        return f"{value / 1e6:.1f}M"
    if value >= 10_000:
        return f"{value / 1e3:.0f}K"
    return f"{value:,}"


def trend_color(direction: Direction, up: str = "peach.3", down: str = "charcoal.2", flat: str = "gray.4") -> str:
    """Mantine colour token for a trend; flat / missing stay neutral. Defaults suit the dark stats pane."""
    return {"up": up, "down": down}.get(direction, flat)


def css_color(token: str) -> str:
    """Mantine token "red.6" → CSS variable (for non-Mantine props like DashIconify.color)."""
    name, shade = token.split(".")
    return f"var(--mantine-color-{name}-{shade})"


def fmt_day_short(day: str | None) -> str:
    """2020-09-12 → "Sep 12" (portable; avoids %-d)."""
    if not day:
        return ""
    d = date.fromisoformat(day)
    return f"{d:%b} {d.day}"


def fmt_day_long(day: str) -> str:
    """2020-09-12 → "Sat, Sep 12 2020"."""
    d = date.fromisoformat(day)
    return f"{d:%a}, {d:%b} {d.day} {d.year}"
