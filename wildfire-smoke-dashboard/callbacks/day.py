"""Selected season/day + playback.

`set_day` is the only writer of the `selection` store ({"season", "day"}); every
control that moves the day (season switch, slider, arrows, skip buttons,
play-from-end, interval tick, a click on the Time Series chart) is an Input here,
so they can never disagree. Keeping season and day in one store means downstream
callbacks can never see a day from one season paired with another season.
"""

from dash import Input, Output, State, callback, ctx, no_update
from dash_iconify import DashIconify

from components.sidebar import day_ui
from config import SEASONS
from utils.data import SEASON_DAYS, peak_day

N_OUTPUTS = 15


def nearest_day(season: str, day: str) -> str:
    """Clamp an ISO day into the season window."""
    days = SEASON_DAYS[season]
    return min(max(day, days[0]), days[-1])


def day_from_click(season: str, click_data: dict | None) -> str | None:
    """Time Series click (line or smoke strip) → day in the season."""
    try:
        x = str(click_data["points"][0]["x"])[:10]
    except (TypeError, KeyError, IndexError):
        return None
    return nearest_day(season, x)


@callback(
    Output("selection", "data"),
    Output("day-slider", "value"),
    Output("day-slider", "max"),
    Output("day-slider", "marks"),
    Output("day-slider", "label"),
    Output("day-label", "children"),
    Output("day-progress", "value"),
    Output("day-progress-label", "children"),
    Output("day-prev", "disabled"),
    Output("day-next", "disabled"),
    Output("day-first", "disabled"),
    Output("day-last", "disabled"),
    Output("season-note", "children"),
    Output("playback-interval", "disabled", allow_duplicate=True),
    Output("ts-graph", "clickData"),
    Input("season", "value"),
    Input("day-slider", "value"),
    Input("day-prev", "n_clicks"),
    Input("day-next", "n_clicks"),
    Input("day-first", "n_clicks"),
    Input("day-last", "n_clicks"),
    Input("play-btn", "n_clicks"),
    Input("ts-graph", "clickData"),
    Input("playback-interval", "n_intervals"),
    State("selection", "data"),
    prevent_initial_call=True,
)
def set_day(season, slider, _prev, _next, _first, _last, _play, click, _tick, current):
    trigger = ctx.triggered_id
    days = SEASON_DAYS[season]
    last = len(days) - 1
    idx = days.index(current["day"]) if current["season"] == season else 0
    stop_playback = True  # any manual navigation pauses playback

    if trigger == "season":
        new = peak_day(season)  # open each season on its default (worst PM2.5) day
    elif trigger == "day-slider":
        if slider is None or slider == idx:
            return (no_update,) * N_OUTPUTS
        new = days[min(max(int(slider), 0), last)]
    elif trigger == "day-prev":
        new = days[max(idx - 1, 0)]
    elif trigger == "day-next":
        new = days[min(idx + 1, last)]
    elif trigger == "day-first":
        new = days[0]
    elif trigger == "day-last":
        new = days[last]
    elif trigger == "play-btn":
        if idx < last:  # toggle_playback handles start/pause
            return (no_update,) * N_OUTPUTS
        new, stop_playback = days[0], False  # play from the end → rewind
    elif trigger == "ts-graph":
        new = day_from_click(season, click)
        if new is None:
            return (no_update,) * N_OUTPUTS
    else:  # playback-interval tick
        if idx >= last:
            return (no_update,) * (N_OUTPUTS - 2) + (True, no_update)
        new = days[idx + 1]
        stop_playback = new == days[last]

    ui = day_ui(season, new)
    season_changed = trigger == "season"
    return (
        {"season": season, "day": new},
        ui["slider"],
        ui["slider_max"] if season_changed else no_update,
        ui["marks"] if season_changed else no_update,
        ui["slider_label"] if season_changed else no_update,
        ui["label"],
        ui["progress"],
        ui["progress_label"],
        ui["at_start"],
        ui["at_end"],
        ui["at_start"],
        ui["at_end"],
        SEASONS[season]["note"] if season_changed else no_update,
        True if stop_playback else no_update,
        None if trigger == "ts-graph" else no_update,  # let the same point be clicked again
    )


@callback(
    Output("playback-interval", "disabled"),
    Input("play-btn", "n_clicks"),
    Input("play-stop", "n_clicks"),
    State("playback-interval", "disabled"),
    prevent_initial_call=True,
)
def toggle_playback(_play, _stop, disabled):
    if ctx.triggered_id == "play-stop":
        return True
    return not disabled


@callback(
    Output("playback-interval", "interval"),
    Input("playback-speed", "value"),
)
def set_playback_speed(ms):
    return int(ms)


@callback(
    Output("play-btn", "children"),
    Output("play-btn", "leftSection"),
    Output("play-btn", "color"),
    Output("play-stop", "disabled"),
    Output("live-badge", "display"),
    Input("playback-interval", "disabled"),
)
def playback_ui(disabled):
    playing = not disabled
    icon = "tabler:player-pause-filled" if playing else "tabler:player-play-filled"
    return (
        "Pause" if playing else "Play",
        DashIconify(icon=icon, width=14),
        "peach.3" if playing else "charcoal",
        not playing,
        "inline-flex" if playing else "none",
    )
