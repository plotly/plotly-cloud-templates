"""Compile timeline visualization data from FIFA match events."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

DEFAULT_PALETTE = {"winner": "#8b95a5", "loser": "#3a3a3a"}

# All known event types — unknown types from CSV still render with defaults.
EVENT_CONFIG: dict[str, dict] = {
    "Goal": {
        "symbol": "circle",
        "palette": {"winner": "#f5f7fa", "loser": "#f5f7fa"},
        "legend_class": "dot-goal",
        "legend_label": "Goal",
    },
    "Assist": {
        "symbol": "circle",
        "team_colored": True,
        "legend_class": "dot-assist",
        "legend_label": "Assist",
    },
    "Yellow Card": {
        "symbol": "circle",
        "palette": {"winner": "#ffd54f", "loser": "#ffd54f"},
        "legend_class": "dot-yellow",
        "legend_label": "Yellow Card",
    },
    "Red Card": {
        "symbol": "circle",
        "palette": {"winner": "#ff5252", "loser": "#ff5252"},
        "legend_class": "dot-red",
        "legend_label": "Red Card",
    },
    "VAR Review": {
        "symbol": "circle",
        "palette": {"winner": "#b388ff", "loser": "#3d2a4a"},
        "legend_class": "dot-var",
        "legend_label": "VAR Review",
    },
    "Penalty Shootout Goal": {
        "symbol": "circle",
        "palette": {"winner": "#f5f7fa", "loser": "#f5f7fa"},
        "legend_class": "dot-so-goal",
        "legend_label": "SO Goal",
    },
    "Penalty Shootout Miss": {
        "symbol": "circle",
        "palette": {"winner": "#78909c", "loser": "#2a3038"},
        "legend_class": "dot-so-miss",
        "legend_label": "SO Miss",
    },
}

LEGEND_ITEMS = [
    (cfg["legend_class"], cfg["legend_label"])
    for cfg in EVENT_CONFIG.values()
]

MARKER_BASE = 8
MARKER_STEP = 5
MARKER_OPACITY_WINNER = 0.75
MARKER_OPACITY_LOSER = 0.7


def event_style(event_type: str) -> dict:
    return EVENT_CONFIG.get(
        event_type,
        {
            "symbol": "circle",
            "palette": DEFAULT_PALETTE,
            "legend_class": "dot-default",
            "legend_label": event_type,
        },
    )

TEAM_ACCENT = {
    "Algeria": "#00acc1",
    "Argentina": "#40c4ff",
    "Australia": "#ffd54f",
    "Austria": "#ef9a9a",
    "Belgium": "#ffd600",
    "Bosnia and Herzegovina": "#2196f3",
    "Brazil": "#00e676",
    "Cabo Verde": "#7c4dff",
    "Canada": "#ff1744",
    "Colombia": "#ffea00",
    "Congo DR": "#00bfa5",
    "Croatia": "#f50057",
    "Curaçao": "#00bcd4",
    "Czechia": "#e040fb",
    "Côte d'Ivoire": "#ff6d00",
    "Ecuador": "#ffca28",
    "Egypt": "#c6a700",
    "England": "#90caf9",
    "France": "#2979ff",
    "Germany": "#eceff1",
    "Ghana": "#ff5722",
    "Haiti": "#1de9b6",
    "IR Iran": "#76ff03",
    "Iraq": "#cddc39",
    "Italy": "#4caf50",
    "Japan": "#d500f9",
    "Jordan": "#651fff",
    "Mexico": "#69f0ae",
    "Morocco": "#ff6e40",
    "Netherlands": "#ff9100",
    "New Zealand": "#f48fb1",
    "Norway": "#ea80fc",
    "Panama": "#4fc3f7",
    "Paraguay": "#536dfe",
    "Portugal": "#b2ff59",
    "Qatar": "#a1887f",
    "Saudi Arabia": "#26a69a",
    "Scotland": "#5c6bc0",
    "Senegal": "#18ffff",
    "South Africa": "#ff8a80",
    "South Korea": "#e91e63",
    "Spain": "#ff5252",
    "Sweden": "#82b1ff",
    "Switzerland": "#ff4081",
    "Tunisia": "#ce93d8",
    "Türkiye": "#e53935",
    "USA": "#b388ff",
    "Uruguay": "#5eb3ff",
    "Uzbekistan": "#8bc34a",
}


def parse_minute(raw: str | float | int | None) -> int | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text:
        return None
    if "+" in text:
        base, extra = text.split("+", 1)
        return int(base) + int(extra)
    return int(float(text))


def minute_to_x(minute_num: int, shootout_index: int | None = None) -> float:
    if minute_num >= 121:
        idx = shootout_index or 0
        return 122.0 + idx * (7.0 / 11)  # pack up to ~12 SO events in 122–129
    return float(minute_num)


def team_color(name: str, *, bright: bool) -> str:
    accent = TEAM_ACCENT.get(name, "#5eb3ff")
    if bright:
        return accent
    # muted / dark variant for losers
    muted = {
        "#40c4ff": "#1a3a4a",
        "#ffd54f": "#4a3d10",
        "#ffd600": "#4a4200",
        "#00e676": "#0a3a20",
        "#7c4dff": "#2a1a4a",
        "#ff1744": "#4a1020",
        "#ffea00": "#4a4200",
        "#00bfa5": "#0a3a35",
        "#f50057": "#4a1028",
        "#ff6d00": "#4a2800",
        "#c6a700": "#4a3d00",
        "#90caf9": "#1a3040",
        "#2979ff": "#102a5a",
        "#eceff1": "#3a3a3a",
        "#d500f9": "#3a1040",
        "#69f0ae": "#1a3a28",
        "#ff6e40": "#4a2010",
        "#ff9100": "#4a2800",
        "#ea80fc": "#3a1a40",
        "#536dfe": "#1a2040",
        "#b2ff59": "#2a4010",
        "#18ffff": "#0a4040",
        "#ff5252": "#4a2020",
        "#ff4081": "#4a1030",
        "#b388ff": "#2a1a40",
        "#5eb3ff": "#1a3040",
        "#e91e63": "#4a1030",
        "#4caf50": "#1a2e1a",
    }
    return muted.get(accent, "#3a3a3a")


def determine_winner_loser(
    match: pd.Series, teams: pd.DataFrame
) -> tuple[int, int, str, str, int, int]:
    home_id = int(match.home_team_id)
    away_id = int(match.away_team_id)
    home_name = teams.loc[teams.team_id == home_id, "team_name"].iloc[0]
    away_name = teams.loc[teams.team_id == away_id, "team_name"].iloc[0]
    home_score = int(match.home_score)
    away_score = int(match.away_score)

    home_pen, away_pen = match.home_penalty_score, match.away_penalty_score
    if pd.notna(home_pen) and pd.notna(away_pen):
        if home_pen > away_pen:
            return home_id, away_id, home_name, away_name, home_score, away_score
        return away_id, home_id, away_name, home_name, away_score, home_score

    if home_score > away_score:
        return home_id, away_id, home_name, away_name, home_score, away_score
    if away_score > home_score:
        return away_id, home_id, away_name, home_name, away_score, home_score
    return home_id, away_id, home_name, away_name, home_score, away_score


XMAX = 130.0


def axis_config(
    match: pd.Series, match_events: pd.DataFrame
) -> tuple[list[float], list[str], float]:
    tickvals = [45, 90, 120, 128]
    ticktext = ["45'", "90'", "120'", "SO"]
    return tickvals, ticktext, XMAX


def format_stage(stage_name: str) -> str:
    return stage_name.upper().replace(" ", "-")


def format_date(date_str: str) -> str:
    return pd.to_datetime(date_str).strftime("%d %b %Y").upper()


def build_timeline_dataframe(
    *,
    knockout_only: bool = True,
    completed_only: bool = True,
) -> pd.DataFrame:
    """One row per timeline event, with match context and marker fields."""
    matches = pd.read_csv(DATA_DIR / "matches.csv")
    details = pd.read_csv(DATA_DIR / "matches_detailed.csv")
    teams = pd.read_csv(DATA_DIR / "teams.csv")
    players = pd.read_csv(DATA_DIR / "squads_and_players.csv")

    events = pd.read_csv(DATA_DIR / "match_events.csv", dtype={"minute": str})
    events["minute_num"] = events["minute"].apply(parse_minute)
    events = events[events["minute_num"].notna()].copy()
    events["player_name"] = events["player_id"].map(
        players.set_index("player_id")["player_name"]
    )
    events["team_name"] = events["team_id"].map(teams.set_index("team_id")["team_name"])

    if completed_only:
        matches = matches[matches.status == "Completed"]
    if knockout_only:
        knockout_ids = details.loc[details.stage_name != "Group Stage", "match_id"]
        matches = matches[matches.match_id.isin(knockout_ids)]

    matches = matches.sort_values(["date", "kickoff_time_utc"]).reset_index(drop=True)
    match_order = {int(mid): idx for idx, mid in enumerate(matches.match_id)}

    rows: list[dict] = []

    for _, match in matches.iterrows():
        match_id = int(match.match_id)
        detail = details.loc[details.match_id == match_id].iloc[0]
        match_events = events[events.match_id == match_id]
        winner_id, loser_id, winner_name, loser_name, winner_score, loser_score = (
            determine_winner_loser(match, teams)
        )
        tickvals, ticktext, xmax = axis_config(match, match_events)

        type_cumulative: dict[tuple[int, str], int] = {}
        minute_offsets: dict[tuple[int, int], int] = {}
        shootout_counter = 0

        sorted_events = match_events.sort_values(["minute_num", "event_id"])
        for event_order, (_, event) in enumerate(sorted_events.iterrows()):
            team_id = int(event.team_id)
            if team_id not in {winner_id, loser_id}:
                continue

            event_type = event.event_type
            type_key = (team_id, event_type)
            type_cumulative[type_key] = type_cumulative.get(type_key, 0) + 1
            type_count = type_cumulative[type_key]

            shootout_idx = None
            if event.minute_num >= 121:
                shootout_idx = shootout_counter
                shootout_counter += 1

            offset_key = (event.minute_num, team_id)
            offset = minute_offsets.get(offset_key, 0)
            minute_offsets[offset_key] = offset + 1

            is_winner = team_id == winner_id
            is_penalty = event_type.startswith("Penalty Shootout")
            style = event_style(event_type)

            w_color = team_color(winner_name, bright=True)
            l_color = team_color(loser_name, bright=False)
            if style.get("team_colored"):
                marker_color = w_color if is_winner else l_color
            else:
                palette = style.get("palette", DEFAULT_PALETTE)
                marker_color = palette["winner"] if is_winner else palette["loser"]

            glow = max(2, (MARKER_BASE + MARKER_STEP * type_count) * 0.18)

            rows.append(
                {
                    "match_id": match_id,
                    "match_order": match_order[match_id],
                    "stage_label": format_stage(detail.stage_name),
                    "date_label": format_date(detail.date),
                    "match_title": (
                        f"{detail.home_team_name} {int(match.home_score)}-"
                        f"{int(match.away_score)} {detail.away_team_name}"
                    ),
                    "stage_name": detail.stage_name,
                    "date": detail.date,
                    "home_team_name": detail.home_team_name,
                    "away_team_name": detail.away_team_name,
                    "home_score": int(match.home_score),
                    "away_score": int(match.away_score),
                    "winner_team_name": winner_name.upper(),
                    "loser_team_name": loser_name.upper(),
                    "winner_score": winner_score,
                    "loser_score": loser_score,
                    "winner_team_color": team_color(winner_name, bright=True),
                    "loser_team_color": team_color(loser_name, bright=False),
                    "winner_team_id": winner_id,
                    "loser_team_id": loser_id,
                    "event_id": int(event.event_id),
                    "event_order": event_order,
                    "event_type": event_type,
                    "event_label": (
                        "PENALTY" if is_penalty else event_type.upper().replace(" CARD", " CARD")
                    ),
                    "minute": event.minute,
                    "minute_num": event.minute_num,
                    "team_id": team_id,
                    "team_name": event.team_name,
                    "player_name": event.player_name,
                    "is_winner": is_winner,
                    "cumulative_event_count": type_count,
                    "x": min(
                        minute_to_x(event.minute_num, shootout_idx) + offset * 0.35,
                        XMAX - 0.2,
                    ),
                    "y": 0,
                    "marker_size": MARKER_BASE + MARKER_STEP * type_count,
                    "marker_symbol": style["symbol"],
                    "marker_color": marker_color,
                    "marker_opacity": MARKER_OPACITY_WINNER if is_winner else MARKER_OPACITY_LOSER,
                    "marker_line_width": glow if is_winner else (3 if is_penalty else 0),
                    "marker_line_color": marker_color,
                    "x_max": xmax,
                    "x_tickvals": tickvals,
                    "x_ticktext": ticktext,
                }
            )

    return pd.DataFrame(rows)


timeline_df = build_timeline_dataframe()
