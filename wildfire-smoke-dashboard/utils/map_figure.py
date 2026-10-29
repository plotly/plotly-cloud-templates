"""County map — one pure `map_state()` feeds both the initial figure and Patch updates.

Trace order is fixed so callbacks can Patch by index:
    0    = county choropleth (holds the only copy of the county GeoJSON)
    1    = fire markers (hover target at each perimeter's label point)
    2    = white halo under the monitor bubbles (Scattermap markers have no stroke)
    3..8 = monitor bubbles, one trace per AQI category
Smoke plumes and fire perimeters are drawn as `layout.map.layers`, below the traces.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shapely

from config import (
    AQI_CATEGORIES,
    BUBBLE_AQI_CAP,
    BUBBLE_MAX_SIZE,
    BUBBLE_MIN_SIZE,
    CHORO_META,
    DEFAULT_AGE,
    DEFAULT_CHORO,
    DEFAULT_OPACITY,
    DEFAULT_POLLUTANT,
    DEFAULT_SMOKE_THRESHOLD,
    FIRE_COLOR,
    FIRE_CONTAINED_COLOR,
    MAP_CENTER,
    MAP_HOVER_BORDER,
    MAP_OUTLINE_COLOR,
    MAP_STYLE,
    MAP_ZOOM,
    POLLUTANTS,
    SMOKE_LEVELS,
)
from utils.aqi import aqi, category
from utils.data import (
    COUNTY_FIPS,
    COUNTY_GEOJSON,
    COUNTY_NAMES,
    asthma_rates,
    county_means,
    county_smoke,
    fires_on,
    population,
    site_values,
    smoke_days_to_date,
    smoke_features,
)
from utils.exposure import vulnerability_score

# Mirrors the mosquito dashboard's map config.
GRAPH_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "doubleClick": "reset",
    "scrollZoom": True,
    "responsive": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "toImage"],
}

CHORO, FIRE_PTS, HALO = 0, 1, 2
# One bubble trace per AQI category: a Scattermap with per-point sizes *and*
# per-point colours fails to render in MapLibre, so each category gets a scalar
# colour + per-point sizes.
BUBBLE_TRACES = tuple(range(3, 3 + len(AQI_CATEGORIES)))
TRANSPARENT = [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]]
SMOKE_LABELS = {0: "None", 1: "Light", 2: "Medium", 3: "Heavy"}


def palette_to_colorscale(palette: list[str]) -> list[list]:
    step = 1 / (len(palette) - 1)
    return [[round(i * step, 4), c] for i, c in enumerate(palette)]


def palette_to_gradient(palette: list[str]) -> str:
    return f"linear-gradient(to right, {', '.join(palette)})"


def aqi_colorscale() -> list[list]:
    """Stepped AQI colours on a 0–500 index (each category a flat band)."""
    scale = []
    for c in AQI_CATEGORIES:
        lo, hi = max(c["min"] - 0.5, 0) / 500, min(c["max"] + 0.5, 500) / 500
        scale += [[round(lo, 4), c["color"]], [round(hi, 4), c["color"]]]
    return scale


def bubble_sizes(aqi_values: pd.Series) -> pd.Series:
    """Area ∝ AQI on a fixed 0–300 scale, so sizes compare across days."""
    frac = aqi_values.astype(float).clip(0, BUBBLE_AQI_CAP) / BUBBLE_AQI_CAP
    return (BUBBLE_MIN_SIZE + (BUBBLE_MAX_SIZE - BUBBLE_MIN_SIZE) * np.sqrt(frac)).round(1)


def choropleth_values(choro: str, season: str, day: str, pollutant: str, threshold: int, age: str) -> pd.Series:
    """z per county (aligned to COUNTY_FIPS) for the chosen choropleth metric."""
    if choro == "aq_mean":
        means = county_means(season, day, pollutant)
        return means.map(lambda v: aqi(v, pollutant)).astype(float)
    if choro == "smoke_days":
        return smoke_days_to_date(season, day, threshold).astype(float)
    if choro == "asthma":
        return asthma_rates(season, age)
    if choro == "vuln":
        return vulnerability_score(asthma_rates(season, age), smoke_days_to_date(season, day, threshold))
    return pd.Series(0.0, index=COUNTY_FIPS)


def choropleth_range(choro: str, z: pd.Series) -> tuple[float, float]:
    if choro == "aq_mean":
        return 0.0, 500.0
    if choro == "vuln":
        return 0.0, 100.0
    hi = z.max()
    return 0.0, float(hi) if pd.notna(hi) and hi > 0 else 1.0


def _fmt(v, decimals: int = 1, suffix: str = "") -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{decimals}f}{suffix}"


def _county_customdata(season, day, pollutant, threshold, age) -> pd.DataFrame:
    meta = POLLUTANTS[pollutant]
    means = county_means(season, day, pollutant)
    county_aqi = means.map(lambda v: aqi(v, pollutant))
    smoke = county_smoke(season, day)
    return pd.DataFrame(
        {
            "name": [COUNTY_NAMES[f] for f in COUNTY_FIPS],
            "mean": means.map(lambda v: _fmt(v, meta["decimals"], f" {meta['unit']}")).values,
            "aqi": county_aqi.map(lambda v: "—" if pd.isna(v) else f"{int(v)} · {category(v)['label']}").values,
            "smoke": smoke.map(lambda v: "no HMS data" if pd.isna(v) else SMOKE_LABELS[int(v)]).values,
            "smoke_days": smoke_days_to_date(season, day, threshold).values,
            "asthma": asthma_rates(season, age).map(lambda v: _fmt(v, 1, " / 10k")).values,
            "pop": population(season).map(lambda v: _fmt(v, 0)).values,
        },
        index=COUNTY_FIPS,
    )


def _county_hovertemplate(pollutant: str, threshold: int, age: str) -> str:
    label = POLLUTANTS[pollutant]["label"]
    smoke_label = SMOKE_LEVELS[threshold]["label"] + ("+" if threshold < 3 else "")
    age_label = "children" if age == "child" else "all ages"
    return (
        "<b>%{customdata[0]} County</b><br><br>"
        f"<span style='color:#1c7ed6'><b>{label} today</b></span><br>"
        "County mean  %{customdata[1]}<br>AQI  %{customdata[2]}<br><br>"
        "<span style='color:#495057'><b>Smoke</b></span><br>"
        f"Today  %{{customdata[3]}}<br>{smoke_label} days to date  %{{customdata[4]}}<br><br>"
        "<span style='color:#7048e8'><b>Respiratory health</b></span><br>"
        f"Asthma ED rate ({age_label})  %{{customdata[5]}}<br>Population  %{{customdata[6]}}"
        "<extra></extra>"
    )


def _layers(day: str, season: str, show_smoke: bool, show_fires: bool) -> list[dict]:
    layers = []
    if show_smoke:
        feats = smoke_features(day)
        for lvl, meta in SMOKE_LEVELS.items():
            source = {"type": "FeatureCollection", "features": [f for f in feats if f["properties"]["density"] == meta["label"]]}
            if source["features"]:
                layers.append(
                    {"sourcetype": "geojson", "source": source, "type": "fill", "color": meta["color"], "opacity": meta["opacity"], "below": "traces"}
                )
    if show_fires:
        burning, contained = fires_on(season, day)
        for feats, color, opacity in ((contained, FIRE_CONTAINED_COLOR, 0.35), (burning, FIRE_COLOR, 0.55)):
            if not feats:
                continue
            source = {"type": "FeatureCollection", "features": feats}
            layers.append({"sourcetype": "geojson", "source": source, "type": "fill", "color": color, "opacity": opacity, "below": "traces"})
            layers.append({"sourcetype": "geojson", "source": source, "type": "line", "color": color, "line": {"width": 1.2}, "below": "traces"})
    return layers


def _fire_points(season: str, day: str, show_fires: bool) -> dict:
    burning, contained = fires_on(season, day) if show_fires else ([], [])
    lat, lon, custom, colors = [], [], [], []
    for feats, status, color in ((burning, "Burning", FIRE_COLOR), (contained, "Contained", FIRE_CONTAINED_COLOR)):
        for f in feats:
            pt = shapely.geometry.shape(f["geometry"]).representative_point()
            p = f["properties"]
            lat.append(round(pt.y, 4))
            lon.append(round(pt.x, 4))
            colors.append(color)
            custom.append([p["name"], f"{p['acres']:,}", p["alarm"], p["cont"] or "—", status])
    return {
        "lat": lat,
        "lon": lon,
        "customdata": custom,
        "marker": {"color": colors},
        "visible": bool(lat),
    }


def map_state(
    season: str,
    day: str,
    pollutant: str = DEFAULT_POLLUTANT,
    choro: str = DEFAULT_CHORO,
    show_smoke: bool = True,
    show_fires: bool = True,
    threshold: int = int(DEFAULT_SMOKE_THRESHOLD),
    age: str = DEFAULT_AGE,
    opacity: float = DEFAULT_OPACITY,
) -> dict:
    """Everything data-dependent about the map, keyed by trace index / layout field."""
    meta = POLLUTANTS[pollutant]

    # County layer
    z = choropleth_values(choro, season, day, pollutant, threshold, age)
    zmin, zmax = choropleth_range(choro, z)
    if choro == "none":
        colorscale = TRANSPARENT
    elif choro == "aq_mean":
        colorscale = aqi_colorscale()
    else:
        colorscale = palette_to_colorscale(CHORO_META[choro]["palette"])
    customdata = _county_customdata(season, day, pollutant, threshold, age)

    # Monitor bubbles
    sites = site_values(season, day, pollutant).dropna(subset=["aqi", "lat", "lon"])
    sizes = bubble_sizes(sites["aqi"])
    cat_of = sites["aqi"].map(lambda v: category(v)["key"])
    site_custom = pd.DataFrame(
        {
            "name": sites["name"],
            "county": sites["county_fips"].map(COUNTY_NAMES).fillna("—"),
            "value": sites["value"].map(lambda v: _fmt(v, meta["decimals"], f" {meta['unit']}")),
            "aqi": sites["aqi"].astype(int),
            "cat": sites["aqi"].map(lambda v: category(v)["label"]),
        }
    )
    site_hover = (
        "<b>%{customdata[0]}</b><br>%{customdata[1]} County<br><br>"
        f"{meta['long']}  %{{customdata[2]}}<br>AQI  <b>%{{customdata[3]}}</b> · %{{customdata[4]}}<extra></extra>"
    )

    def bubble_trace(mask) -> dict:
        return {
            "lat": sites["lat"][mask].tolist(),
            "lon": sites["lon"][mask].tolist(),
            "marker": {"size": sizes[mask].tolist()},
            "customdata": site_custom[mask].values.tolist(),
            "hovertemplate": site_hover,
            "visible": bool(mask.any()),
        }

    return {
        CHORO: {
            "z": [None if pd.isna(v) else float(v) for v in z],
            "zmin": zmin,
            "zmax": zmax,
            "colorscale": colorscale,
            "customdata": customdata.values.tolist(),
            "hovertemplate": _county_hovertemplate(pollutant, threshold, age),
            "marker": {"opacity": opacity},
        },
        FIRE_PTS: _fire_points(season, day, show_fires),
        HALO: {
            "lat": sites["lat"].tolist(),
            "lon": sites["lon"].tolist(),
            "marker": {"size": (sizes + 3).tolist()},
            "visible": len(sites) > 0,
        },
        **{idx: bubble_trace((cat_of == c["key"]).values) for idx, c in zip(BUBBLE_TRACES, AQI_CATEGORIES)},
        "layers": _layers(day, season, show_smoke, show_fires),
    }


def build_base_map(season: str, day: str) -> go.Figure:
    """Initial figure: the only place the county GeoJSON is serialised."""
    state = map_state(season, day)
    fig = go.Figure(
        [
            go.Choroplethmap(
                geojson=COUNTY_GEOJSON,
                featureidkey="properties.fips",
                locations=COUNTY_FIPS,
                showscale=False,
                marker_line={"color": MAP_OUTLINE_COLOR, "width": 0.7},
                **{k: v for k, v in state[CHORO].items() if k != "marker"},
                marker_opacity=state[CHORO]["marker"]["opacity"],
            ),
            go.Scattermap(
                mode="markers",
                name="Fires",
                marker={"size": 9, "color": state[FIRE_PTS]["marker"]["color"], "opacity": 0.95},
                lat=state[FIRE_PTS]["lat"],
                lon=state[FIRE_PTS]["lon"],
                customdata=state[FIRE_PTS]["customdata"],
                hovertemplate=(
                    "<b>%{customdata[0]} Fire</b> · %{customdata[4]}<br>"
                    "Final size  %{customdata[1]} ac<br>Started  %{customdata[2]}<br>Contained  %{customdata[3]}<extra></extra>"
                ),
                visible=state[FIRE_PTS]["visible"],
            ),
            go.Scattermap(
                mode="markers",
                hoverinfo="skip",
                marker={"color": "white", "opacity": 0.95},
                lat=state[HALO]["lat"],
                lon=state[HALO]["lon"],
                marker_size=state[HALO]["marker"]["size"],
                visible=state[HALO]["visible"],
            ),
            *[
                go.Scattermap(
                    mode="markers",
                    name=c["label"],
                    marker={"color": c["color"], "opacity": 0.9},
                    lat=state[idx]["lat"],
                    lon=state[idx]["lon"],
                    marker_size=state[idx]["marker"]["size"],
                    customdata=state[idx]["customdata"],
                    hovertemplate=state[idx]["hovertemplate"],
                    visible=state[idx]["visible"],
                )
                for idx, c in zip(BUBBLE_TRACES, AQI_CATEGORIES)
            ],
        ]
    )
    fig.update_layout(
        template="mantine_light",
        autosize=True,
        map=go.layout.Map(
            style=MAP_STYLE,
            center=go.layout.map.Center(lat=MAP_CENTER["lat"], lon=MAP_CENTER["lon"]),
            zoom=MAP_ZOOM,
            layers=state["layers"],
        ),
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        showlegend=False,
        uirevision="county-map",  # keep user pan/zoom across updates
        hoverlabel={"bgcolor": "white", "bordercolor": MAP_HOVER_BORDER, "font": {"size": 12, "color": "#1f2937"}},
    )
    return fig


def apply_map_state(patch, state: dict) -> None:
    """Write a `map_state()` result into a dash.Patch without resending the county GeoJSON."""
    for idx in (CHORO, FIRE_PTS, HALO, *BUBBLE_TRACES):
        for key, value in state[idx].items():
            if key == "marker":
                for mk, mv in value.items():
                    patch["data"][idx]["marker"][mk] = mv
            else:
                patch["data"][idx][key] = value
    patch["layout"]["map"]["layers"] = state["layers"]
