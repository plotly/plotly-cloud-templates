"""Data layer — everything is loaded once at import and treated as read-only.

The snapshot under data/ is small (a few MB), so module-level frames are simpler
and faster than a cache. Callbacks must never mutate these objects; helpers return
new Series/DataFrames (cached helpers hand out copies).

Keys used throughout:
    season   "2020" | "2021" | "2025"  (config.SEASONS)
    day      ISO date "YYYY-MM-DD" inside the season window
    fips     5-digit county FIPS string ("06037")
"""

import json
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
import shapely
from shapely.geometry import shape

from config import (
    AQ_CSV,
    COUNTIES_GEOJSON,
    COUNTY_SMOKE_CSV,
    FIRES_GEOJSON,
    HEALTH_CSV,
    MONITORS_CSV,
    POLLUTANTS,
    POPULATION_CSV,
    SEASONS,
    SMOKE_GEOJSON,
)
from utils.aqi import aqi_series

# ── Counties ──────────────────────────────────────────────────────────────────
COUNTY_GEOJSON = json.loads(COUNTIES_GEOJSON.read_text())
COUNTY_FIPS: list[str] = sorted(f["properties"]["fips"] for f in COUNTY_GEOJSON["features"])
COUNTY_NAMES: dict[str, str] = {f["properties"]["fips"]: f["properties"]["name"] for f in COUNTY_GEOJSON["features"]}
COUNTY_OPTIONS = [{"value": f, "label": COUNTY_NAMES[f]} for f in sorted(COUNTY_FIPS, key=COUNTY_NAMES.get)]

# ── Seasons ───────────────────────────────────────────────────────────────────
def _days(start: str, end: str) -> list[str]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


SEASON_DAYS: dict[str, list[str]] = {s: _days(m["start"], m["end"]) for s, m in SEASONS.items()}

# ── Monitors & daily air quality (EPA AirData) ────────────────────────────────
MONITORS = pd.read_csv(MONITORS_CSV, dtype={"county_fips": str}).set_index("site_id")

AQ = pd.read_csv(AQ_CSV, dtype={"season": str})
AQ["aqi"] = pd.concat([aqi_series(g["value"], p) for p, g in AQ.groupby("pollutant")]).reindex(AQ.index)
AQ["county_fips"] = AQ["site_id"].map(MONITORS["county_fips"])

_SITE_COLS = ["name", "lat", "lon", "county_fips"]
_AQ_BY_KEY: dict[tuple[str, str, str], pd.DataFrame] = {
    key: g.set_index("site_id")[["value", "aqi"]].join(MONITORS[_SITE_COLS])
    for key, g in AQ.groupby(["season", "pollutant", "date"])
}
_EMPTY_SITES = pd.DataFrame(columns=["value", "aqi", *_SITE_COLS])

# ── Smoke (NOAA HMS) ──────────────────────────────────────────────────────────
# The snapshot clips plumes to a lon/lat box (scripts/fetch_data.py CA_BBOX). Trim them to the
# state outline so the map shows smoke over California, not a rectangle over ocean and Nevada.
# The small buffer closes slivers between the simplified county shapes; low quad_segs + simplify
# keep the outline at ~1k vertices so the one-off clip at import stays around a second.
CA_OUTLINE = shapely.union_all([shape(f["geometry"]) for f in COUNTY_GEOJSON["features"]]).buffer(0.005, quad_segs=1).simplify(0.002)


def _clip_to_state(features: list[dict]) -> list[dict]:
    """Features with geometry trimmed to CA_OUTLINE (polygonal parts only); empty results dropped.

    make_valid first: the snapshot's pointwise coordinate snapping leaves a few self-touching rings.
    """
    geoms = shapely.make_valid(shapely.from_geojson([json.dumps(f["geometry"]) for f in features]))
    out = []
    for f, clipped in zip(features, shapely.intersection(geoms, CA_OUTLINE)):
        polys = [p for g in shapely.get_parts(clipped) for p in shapely.get_parts(g) if p.geom_type == "Polygon"]
        if not polys:
            continue
        geom = shapely.set_precision(shapely.multipolygons(polys), 1e-3)
        if not geom.is_empty:
            out.append({**f, "geometry": json.loads(shapely.to_geojson(geom))})
    return out


_SMOKE_GJ = json.loads(SMOKE_GEOJSON.read_text())
SMOKE_BY_DAY: dict[str, list[dict]] = {}
for _f in _clip_to_state(_SMOKE_GJ["features"]):
    SMOKE_BY_DAY.setdefault(_f["properties"]["date"], []).append(_f)

COUNTY_SMOKE = pd.read_csv(COUNTY_SMOKE_CSV, dtype={"season": str, "fips": str})
SMOKE_DAYS_AVAILABLE: set[str] = set(COUNTY_SMOKE["date"])

# ── Fire perimeters (CAL FIRE) ────────────────────────────────────────────────
FIRES: list[dict] = json.loads(FIRES_GEOJSON.read_text())["features"]

# ── Health & population ───────────────────────────────────────────────────────
HEALTH = pd.read_csv(HEALTH_CSV, dtype={"fips": str})
HEALTH_LAST_YEAR = int(HEALTH["year"].max())
POPULATION = pd.read_csv(POPULATION_CSV, dtype={"fips": str})


# ── Lookups ───────────────────────────────────────────────────────────────────
def health_year(season: str) -> int:
    """Asthma data year shown for a season: the same year, or the latest available."""
    return min(int(season[:4]), HEALTH_LAST_YEAR)


def asthma_rates(season: str, age: str = "all") -> pd.Series:
    """Age-adjusted asthma ED visits per 10,000 residents, per county (NaN = suppressed)."""
    col = "asthma_ed_rate_child" if age == "child" else "asthma_ed_rate"
    df = HEALTH[HEALTH["year"] == health_year(season)]
    return df.set_index("fips")[col].reindex(COUNTY_FIPS)


def population(season: str) -> pd.Series:
    year = min(int(season[:4]), int(POPULATION["year"].max()))
    df = POPULATION[POPULATION["year"] == year]
    return df.set_index("fips")["population"].reindex(COUNTY_FIPS)


def site_values(season: str, day: str, pollutant: str) -> pd.DataFrame:
    """One row per reporting monitor: value, aqi, name, lat, lon, county_fips."""
    return _AQ_BY_KEY.get((season, pollutant, day), _EMPTY_SITES).copy()


def county_means(season: str, day: str, pollutant: str) -> pd.Series:
    """Mean of the county's monitors for one day (NaN where no monitor reported)."""
    return county_mean_matrix(season, pollutant).loc[day]


@lru_cache(maxsize=16)
def _county_mean_matrix(season: str, pollutant: str) -> pd.DataFrame:
    df = AQ[(AQ["season"] == season) & (AQ["pollutant"] == pollutant)]
    return (
        df.groupby(["date", "county_fips"])["value"]
        .mean()
        .unstack()
        .reindex(index=SEASON_DAYS[season], columns=COUNTY_FIPS)
    )


def county_mean_matrix(season: str, pollutant: str) -> pd.DataFrame:
    """Days × counties of county-mean concentration (display units)."""
    return _county_mean_matrix(season, pollutant).copy()


def county_aqi_matrix(season: str, pollutant: str) -> pd.DataFrame:
    """Days × counties of the AQI of the county-mean concentration."""
    means = _county_mean_matrix(season, pollutant)
    return means.apply(lambda col: aqi_series(col, pollutant))


@lru_cache(maxsize=8)
def _smoke_matrix(season: str) -> pd.DataFrame:
    df = COUNTY_SMOKE[COUNTY_SMOKE["season"] == season]
    return df.pivot(index="date", columns="fips", values="smoke").reindex(index=SEASON_DAYS[season], columns=COUNTY_FIPS)


def smoke_matrix(season: str) -> pd.DataFrame:
    """Days × counties of HMS smoke level (0 none … 3 heavy); NaN on days without an HMS file."""
    return _smoke_matrix(season).copy()


def county_smoke(season: str, day: str) -> pd.Series:
    return _smoke_matrix(season).loc[day].copy()


def smoke_days_to_date(season: str, day: str, threshold: int = 2) -> pd.Series:
    """Per county: days from season start through `day` with smoke ≥ `threshold`."""
    m = _smoke_matrix(season)
    return (m.loc[:day] >= threshold).sum().astype(int)


def smoke_features(day: str) -> list[dict]:
    return SMOKE_BY_DAY.get(day, [])


def fires_on(season: str, day: str) -> tuple[list[dict], list[dict]]:
    """(burning, contained) perimeters of fires discovered on or before `day`.

    Perimeters are each fire's *final* mapped extent, not its footprint on that day.
    """
    burning, contained = [], []
    for f in FIRES:
        p = f["properties"]
        if p["season"] != season or p["alarm"] > day:
            continue
        (contained if p["cont"] and p["cont"] < day else burning).append(f)
    return burning, contained


@lru_cache(maxsize=8)
def peak_day(season: str) -> str:
    """Default view for a season: `default_day` if configured, else the highest statewide mean PM2.5."""
    if "default_day" in SEASONS[season]:
        return SEASONS[season]["default_day"]
    df = AQ[(AQ["season"] == season) & (AQ["pollutant"] == "pm25")]
    if df.empty:
        return SEASON_DAYS[season][-1]
    return str(df.groupby("date")["value"].mean().idxmax())


def pollutant_unit(pollutant: str) -> str:
    return POLLUTANTS[pollutant]["unit"]
