"""Loads the Lahman Baseball Database extracts and computes the statistics shown in the app.

The CSV files in data/ were prepared from the original database. For continuity, some
historical team names were changed to match their modern counterpart.
"""

import numpy as np
import pandas as pd

FIRST_YEAR = 1903

# Eras of the modern game, (label, first year, last year)
ERAS = [
    ("Dead Ball", 1903, 1919),
    ("Live Ball", 1920, 1941),
    ("Integration", 1942, 1960),
    ("Expansion", 1961, 1976),
    ("Free Agency", 1977, 1993),
    ("Steroid", 1994, 2005),
    ("Post-Steroid", 2006, 2015),
    ("Statcast", 2016, 2020),
]
ERA_RANGES = {name: [start, end] for name, start, end in ERAS}
POSITIONS = {
    "P": "Pitcher",
    "C": "Catcher",
    "1B": "First base",
    "2B": "Second base",
    "3B": "Third base",
    "SS": "Shortstop",
    "OF": "Outfield",
}


def _load(name, **kwargs):
    df = pd.read_csv(f"data/{name}.csv", **kwargs)
    if "year" in df:
        df = df[df["year"] >= FIRST_YEAR].astype({"year": int})
    return df.reset_index(drop=True)


teams = _load("update_team")
batting = _load("update_batting")
fielding = _load("update_fielding")
pitching = _load("update_pitching")
players = _load("update_player").set_index("player_id")
team_players = _load("player_team")

LAST_YEAR = int(teams["year"].max())
NAMES = team_players.drop_duplicates("player_id").set_index("player_id")["known_name"]
PITCHER_IDS = set(pitching["player_id"])


def _ratio(numerator, denominator):
    """Divide, leaving gaps (NaN) where the denominator is zero or missing."""
    return (numerator / denominator.where(denominator > 0)).astype(float)


def _in_range(df, team, years):
    start, end = years
    return df[(df["team_id"] == team) & df["year"].between(start, end)]


def _by_year(df, columns):
    """Sum a player's stints with the same team in the same season."""
    return df.groupby("year", as_index=False)[columns].sum(min_count=1)


def team_options(era):
    """Teams that played in the era, labelled with their most recent name in it."""
    start, end = ERA_RANGES[era]
    in_era = teams[teams["year"].between(start, end)].sort_values("year")
    spans = in_era.groupby("team_id").agg(
        name=("name", "last"), first=("year", "min"), last=("year", "max")
    )
    duplicated = spans["name"].duplicated(keep=False)
    spans["label"] = spans["name"].where(
        ~duplicated,
        spans["name"] + " (" + spans["first"].astype(str) + "–" + spans["last"].astype(str) + ")",
    )
    spans = spans.sort_values("label")
    return [{"value": team_id, "label": label} for team_id, label in spans["label"].items()]


def team_seasons(team, years):
    df = _in_range(teams, team, years).sort_values("year").copy()
    singles = df["h"] - df["double"] - df["triple"] - df["hr"]
    df["avg"] = _ratio(df["h"], df["ab"])
    df["slg"] = _ratio(singles + 2 * df["double"] + 3 * df["triple"] + 4 * df["hr"], df["ab"])
    df["babip"] = _ratio(df["h"] - df["hr"], df["ab"] - df["so"] - df["hr"])
    df["kbb"] = _ratio(df["soa"], df["bba"])
    for stat in ("cg", "sho", "sv"):
        df[f"{stat}_rate"] = _ratio(df[stat], df["g"])
    return df


def team_titles(seasons):
    """Seasons in which the team won each kind of title."""
    return {
        "World Series": seasons.loc[seasons["ws_win"] == "Y", "year"].tolist(),
        "Pennants": seasons.loc[seasons["lg_win"] == "Y", "year"].tolist(),
        "Division titles": seasons.loc[seasons["div_win"] == "Y", "year"].tolist(),
        "Wild cards": seasons.loc[seasons["wc_win"] == "Y", "year"].tolist(),
    }


def player_options(team, years):
    """Players on the roster in the range, pitchers and position players grouped
    separately, most games played first."""
    roster = _in_range(team_players, team, years)["player_id"].unique()
    games = (
        _in_range(batting, team, years)
        .groupby("player_id")["g"]
        .sum()
        .reindex(roster, fill_value=0)
        .sort_values(ascending=False, kind="stable")
    )
    is_pitcher = _in_range(pitching, team, years).groupby("player_id")["g"].sum()
    groups = {"Position players": [], "Pitchers": []}
    for player_id in games.index:
        # Two-way players go with whichever role they played more games in
        pitched = is_pitcher.get(player_id, 0)
        group = "Pitchers" if pitched and pitched >= games[player_id] / 2 else "Position players"
        groups[group].append({"value": player_id, "label": NAMES.get(player_id, player_id)})
    return [{"group": name, "items": items} for name, items in groups.items() if items]


def first_option(options):
    return options[0]["items"][0]["value"] if options else None


def option_values(options):
    return {item["value"] for group in options for item in group["items"]}


def player_profile(player_id):
    if player_id not in players.index:
        return None
    row = players.loc[player_id]

    def known(value):
        return value if pd.notna(value) and value != "" else None

    birthplace = ", ".join(
        str(v) for v in (row["birth_city"], row["birth_state"], row["birth_country"]) if known(v)
    )
    height = (
        f"{int(row['height']) // 12}′ {int(row['height']) % 12}″" if known(row["height"]) else None
    )
    return {
        "name": NAMES.get(player_id, f"{row['name_first']} {row['name_last']}"),
        "Born": " in ".join(
            str(v) for v in (known(row["birth_year"]) and int(row["birth_year"]), birthplace) if v
        )
        or None,
        "Bats / throws": "/".join(str(v) for v in (row["bats"], row["throws"]) if known(v)) or None,
        "Height, weight": ", ".join(
            v for v in (height, known(row["weight"]) and f"{int(row['weight'])} lb") if v
        )
        or None,
        "MLB career": " – ".join(
            str(v)[:4] for v in (row["debut"], row["final_game"]) if known(v)
        )
        or None,
    }


BATTING_COLUMNS = ["g", "ab", "r", "h", "double", "triple", "hr", "rbi", "sb", "bb", "so", "hbp", "sf"]


def player_batting(player_id, team, years):
    df = _in_range(batting, team, years)
    df = _by_year(df[df["player_id"] == player_id], BATTING_COLUMNS)
    # Hit-by-pitch and sacrifice flies weren't tracked in early seasons
    hbp, sf = df["hbp"].fillna(0), df["sf"].fillna(0)
    df["single"] = df["h"] - df["double"] - df["triple"] - df["hr"]
    df["avg"] = _ratio(df["h"], df["ab"])
    df["obp"] = _ratio(df["h"] + df["bb"] + hbp, df["ab"] + df["bb"] + hbp + sf)
    df["slg"] = _ratio(
        df["single"] + 2 * df["double"] + 3 * df["triple"] + 4 * df["hr"], df["ab"]
    )
    df["ops"] = df["obp"] + df["slg"]
    return df


PITCHING_COLUMNS = ["w", "l", "g", "gs", "cg", "sho", "sv", "ipouts", "h", "er", "hr", "bb", "so"]


def player_pitching(player_id, team, years):
    df = _in_range(pitching, team, years)
    df = _by_year(df[df["player_id"] == player_id], PITCHING_COLUMNS)
    df["ip"] = df["ipouts"] / 3
    df["era"] = _ratio(27 * df["er"], df["ipouts"])
    df["whip"] = _ratio(df["bb"] + df["h"], df["ip"])
    df["kbb"] = _ratio(df["so"], df["bb"])
    df["wpct"] = _ratio(df["w"], df["w"] + df["l"])
    return df


def player_fielding(player_id, team, years):
    df = _in_range(fielding, team, years)
    df = df[df["player_id"] == player_id]
    df = df.groupby(["year", "pos"], as_index=False)[["g", "po", "a", "e", "dp"]].sum(min_count=1)
    df["fld"] = _ratio(df["po"] + df["a"], df["po"] + df["a"] + df["e"])
    return df


def position_options(fielding_seasons):
    games = fielding_seasons.groupby("pos")["g"].sum().sort_values(ascending=False)
    return [{"value": pos, "label": POSITIONS.get(pos, pos)} for pos in games.index]


def records(df):
    """Rows for AG Grid, with NaN/inf as empty cells."""
    df = df.replace([np.inf, -np.inf], np.nan)
    return df.astype(object).where(df.notna(), None).to_dict("records")
