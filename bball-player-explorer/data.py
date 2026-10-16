"""Player data, similarity scores and K-means groupings."""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path(__file__).parent / "srcdata" / "player_stats_proc.csv"

POSITIONS = ["PG", "SG", "SF", "PF", "C"]
POSITION_NAMES = {
    "PG": "Point guard",
    "SG": "Shooting guard",
    "SF": "Small forward",
    "PF": "Power forward",
    "C": "Center",
}

BUILD_STATS = ["height", "weight", "bmi"]
PER_36_STATS = [
    "fg_per_mp",
    "fga_per_mp",
    "fg3_per_mp",
    "fg3a_per_mp",
    "fg2_per_mp",
    "fg2a_per_mp",
    "ft_per_mp",
    "fta_per_mp",
    "orb_per_mp",
    "drb_per_mp",
    "trb_per_mp",
    "ast_per_mp",
    "stl_per_mp",
    "blk_per_mp",
    "tov_per_mp",
    "pf_per_mp",
]
RATE_STATS = ["fg_pct", "fg2_pct", "fg3_pct", "ft_pct"]
GROUPING_STATS = BUILD_STATS + PER_36_STATS + RATE_STATS

# Stats used to compare players, and the "Statistics" grouping preset
PROFILE_STATS = [
    "fg2_per_mp",
    "fg2a_per_mp",
    "fg3_per_mp",
    "fg3a_per_mp",
    "trb_per_mp",
    "ast_per_mp",
    "blk_per_mp",
]

_SHORT = {
    "fg": "FG",
    "fga": "FGA",
    "fg3": "3P",
    "fg3a": "3PA",
    "fg2": "2P",
    "fg2a": "2PA",
    "ft": "FT",
    "fta": "FTA",
    "orb": "OREB",
    "drb": "DREB",
    "trb": "REB",
    "ast": "AST",
    "stl": "STL",
    "blk": "BLK",
    "tov": "TOV",
    "pf": "PF",
}
_BUILD_LABELS = {"height": "Height (cm)", "weight": "Weight (kg)", "bmi": "BMI"}


def short_label(stat):
    """Column heading, e.g. "3PA" for fg3a_per_mp."""
    return _SHORT.get(stat.split("_per_")[0], stat.upper())


def stat_label(stat):
    """Full label, e.g. "3PA per 36 min" for fg3a_per_mp."""
    if stat in _BUILD_LABELS:
        return _BUILD_LABELS[stat]
    if stat.endswith("_pct"):
        return _SHORT[stat[:-4]] + "%"
    base, per = stat.split("_per_")
    return f"{_SHORT[base]} per {'36 min' if per == 'mp' else 'game'}"


def per_game(stats):
    return [s.replace("_per_mp", "_per_game") for s in stats]


def _load():
    df = pd.read_csv(DATA_PATH, index_col=0)
    # The 500 highest scoring players with more than 2000 career minutes
    df = df[df["mp"] > 2000].nlargest(500, "ppg")
    df[RATE_STATS] = df[RATE_STATS].fillna(0)
    return df.reset_index(drop=True)


PLAYERS = _load()
PLAYER_NAMES = sorted(PLAYERS["name"])
DEFAULT_PLAYER = "Stephen Curry"

# Well known players that are always labeled on the player map
LANDMARK_PLAYERS = [
    "Shaquille O'Neal",
    "Hakeem Olajuwon",
    "Stephen Curry",
    "Spud Webb",
    "Michael Jordan",
    "Magic Johnson",
    "LeBron James",
]


def player(name):
    return PLAYERS[PLAYERS["name"] == name].iloc[0]


def _scaled(columns):
    return StandardScaler().fit_transform(PLAYERS[columns])


def _first_component(scaled, align_with):
    """First principal component, signed so that it grows with `align_with`."""
    component = PCA(n_components=1).fit_transform(scaled)[:, 0]
    if np.corrcoef(component, PLAYERS[align_with])[0, 1] < 0:
        component = -component
    return component


@lru_cache(maxsize=2)
def _profiles(stat_type):
    stats = PROFILE_STATS if stat_type == "per_36" else per_game(PROFILE_STATS)
    stat_scaled = _scaled(stats)
    build_scaled = _scaled(BUILD_STATS)
    return (
        stats,
        stat_scaled,
        build_scaled,
        _first_component(stat_scaled, "fg3a_per_mp"),
        _first_component(build_scaled, "height"),
    )


def _distance(scaled, i):
    dist = np.square(scaled - scaled[i]).sum(axis=1)
    return dist / (dist.max() - dist.min())


@lru_cache(maxsize=64)
def similarity(name, build_weight, stat_type):
    """Every player's similarity to `name`, most similar first.

    `build_weight` (0 to 1) sets how much build counts compared to statistics.
    Returns the player table with stat_sim, build_sim, match (all 0 to 1), and the
    stat_dim / build_dim coordinates of the player map, plus the compared stats.
    """
    stats, stat_scaled, build_scaled, stat_dim, build_dim = _profiles(stat_type)
    i = PLAYERS.index[PLAYERS["name"] == name][0]
    stat_dist = _distance(stat_scaled, i)
    build_dist = _distance(build_scaled, i)
    # Weighted root mean square of the two distances, so match is on the same scale
    dist = np.sqrt(stat_dist**2 * (1 - build_weight) + build_dist**2 * build_weight)
    df = PLAYERS.assign(
        stat_sim=1 - stat_dist,
        build_sim=1 - build_dist,
        match=1 - dist,
        stat_dim=stat_dim,
        build_dim=build_dim,
    )
    return df.sort_values("match", ascending=False), stats


@lru_cache(maxsize=32)
def groups(stats, n_groups):
    """Group players with K-means on the (standardized) `stats`.

    Groups are numbered from 1 by increasing average height. Returns the player
    table with a `group` column and dim_a / dim_b coordinates of a 2D PCA map.
    """
    scaled = _scaled(list(stats))
    labels = KMeans(n_clusters=n_groups, n_init=10, random_state=0).fit_predict(scaled)
    order = PLAYERS.groupby(labels)["height"].mean().sort_values().index
    renumber = {old: new for new, old in enumerate(order, start=1)}
    dims = PCA(n_components=2).fit_transform(scaled)
    return PLAYERS.assign(
        group=[renumber[label] for label in labels],
        dim_a=dims[:, 0],
        dim_b=dims[:, 1],
    )
