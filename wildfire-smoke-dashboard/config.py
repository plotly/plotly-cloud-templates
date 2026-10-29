"""App-wide constants — paths, seasons, AQI breakpoints, palettes and labels.

AQI breakpoints and category colours follow the EPA Technical Assistance Document
for the Reporting of Daily Air Quality (May 2024 PM2.5 revision).
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
COUNTIES_GEOJSON = DATA_DIR / "counties.geojson"
MONITORS_CSV = DATA_DIR / "monitors.csv"
AQ_CSV = DATA_DIR / "aq_daily.csv"
SMOKE_GEOJSON = DATA_DIR / "smoke.geojson"
COUNTY_SMOKE_CSV = DATA_DIR / "county_smoke.csv"
FIRES_GEOJSON = DATA_DIR / "fires.geojson"
HEALTH_CSV = DATA_DIR / "county_health.csv"
POPULATION_CSV = DATA_DIR / "county_population.csv"

# About the Data articles (content/articles.json, photos in assets/about/)
ARTICLES_JSON = Path(__file__).parent / "content" / "articles.json"
ABOUT_IMAGE_DIR = Path(__file__).parent / "assets" / "about"
IMAGE_LICENSES = {"Public domain", "CC BY 2.0", "CC BY 4.0", "CC BY-SA 4.0"}  # all credited in captions

APP_TITLE = "Wildfire Smoke & Respiratory Health Dashboard"

# ── Chrome (palette lives in theme.py; these are for components that need a raw hex) ─
LOADER_COLOR = "#294c60"  # charcoal-blue

HEADER_HEIGHT = 56  # single row: brand, nav tabs
SIDEBAR_WIDTH = 260
STATS_WIDTH = 316  # 16px gutters either side of 284px cards

# ── Fire seasons ──────────────────────────────────────────────────────────────
# Must match scripts/fetch_data.py SEASONS (date windows of the snapshot).
SEASONS = {
    "2020": {"label": "2020", "start": "2020-08-01", "end": "2020-10-31", "note": "August Complex · SCU/LNU lightning · Creek"},
    "2021": {"label": "2021", "start": "2021-07-01", "end": "2021-09-30", "note": "Dixie · Caldor · Monument"},
    # `default_day` overrides the "worst statewide PM2.5 day" default: in Jan 2025 that is
    # a fireworks / Central Valley inversion day, while LA monitors peaked on Jan 8.
    "2025": {"label": "2025 LA", "start": "2025-01-01", "end": "2025-02-15", "note": "Palisades · Eaton", "default_day": "2025-01-08"},
}
DEFAULT_SEASON = "2020"

# ── Pollutants & AQI ──────────────────────────────────────────────────────────
# Breakpoints: (C_lo, C_hi, I_lo, I_hi) in the pollutant's display unit, after truncation.
POLLUTANTS = {
    "pm25": {
        "label": "PM2.5",
        "long": "PM2.5 (24-h mean)",
        "unit": "µg/m³",
        "decimals": 1,
        "breakpoints": [
            (0.0, 9.0, 0, 50),
            (9.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 125.4, 151, 200),
            (125.5, 225.4, 201, 300),
            (225.5, 325.4, 301, 500),
        ],
    },
    "ozone": {
        "label": "Ozone",
        "long": "Ozone (daily max 8-h)",
        "unit": "ppb",
        "decimals": 0,
        # The 8-hour ozone AQI is defined up to 200 ppb (AQI 300); higher values are capped.
        "breakpoints": [
            (0, 54, 0, 50),
            (55, 70, 51, 100),
            (71, 85, 101, 150),
            (86, 105, 151, 200),
            (106, 200, 201, 300),
        ],
    },
}
POLLUTANT_OPTIONS = [{"value": k, "label": m["label"]} for k, m in POLLUTANTS.items()]
DEFAULT_POLLUTANT = "pm25"

# Upper bounds are inclusive AQI values (EPA categories). `short` labels fit the stat rows.
AQI_CATEGORIES = [
    {"key": "good", "label": "Good", "short": "Good", "min": 0, "max": 50, "color": "#00e400"},
    {"key": "moderate", "label": "Moderate", "short": "Moderate", "min": 51, "max": 100, "color": "#ffff00"},
    {"key": "usg", "label": "Unhealthy for Sensitive Groups", "short": "USG", "min": 101, "max": 150, "color": "#ff7e00"},
    {"key": "unhealthy", "label": "Unhealthy", "short": "Unhealthy", "min": 151, "max": 200, "color": "#ff0000"},
    {"key": "very", "label": "Very Unhealthy", "short": "Very Unhealthy", "min": 201, "max": 300, "color": "#8f3f97"},
    {"key": "hazardous", "label": "Hazardous", "short": "Hazardous", "min": 301, "max": 500, "color": "#7e0023"},
]
UNHEALTHY_AQI = 150  # "Unhealthy+" means AQI > 150
USG_AQI = 100

# ── Smoke (NOAA HMS analyst density) ──────────────────────────────────────────
# Warm taupe ramp (reads as haze, not a grey wash); passes the dataviz ordinal check.
SMOKE_LEVELS = {
    1: {"label": "Light", "color": "#c2b29d", "opacity": 0.22},
    2: {"label": "Medium", "color": "#a08a72", "opacity": 0.30},
    3: {"label": "Heavy", "color": "#7d6550", "opacity": 0.38},
}
SMOKE_THRESHOLD_OPTIONS = [
    {"value": "1", "label": "Any"},
    {"value": "2", "label": "Medium+"},
    {"value": "3", "label": "Heavy"},
]
DEFAULT_SMOKE_THRESHOLD = "2"
SMOKE_COVER_FRAC = 0.25  # county counts as smoke-covered when ≥25% of its area is under a plume

FIRE_COLOR = "#e8590c"
FIRE_CONTAINED_COLOR = "#868e96"

# ── County choropleth ─────────────────────────────────────────────────────────
CHORO_META = {
    "none": {"label": "Outlines only", "palette": None},
    "aq_mean": {"label": "County mean AQI (today)", "palette": None},  # uses AQI category colours
    "smoke_days": {"label": "Smoke days, season to date", "palette": ["#faf7f3", "#e3d8ca", "#bfa98f", "#8e7358", "#5a4533"]},
    "asthma": {"label": "Asthma ED visit rate", "palette": ["#f3f0ff", "#d0bfff", "#9775fa", "#7048e8", "#4c2a85"]},
    "vuln": {"label": "Asthma burden × smoke days", "palette": ["#fff4e6", "#ffd8a8", "#ffa94d", "#f76707", "#c2410c"]},
}
CHORO_OPTIONS = [{"value": k, "label": m["label"]} for k, m in CHORO_META.items()]
DEFAULT_CHORO = "none"
DEFAULT_OPACITY = 0.6

AGE_OPTIONS = [{"value": "all", "label": "All ages"}, {"value": "child", "label": "Children"}]
DEFAULT_AGE = "all"

# ── Time series ───────────────────────────────────────────────────────────────
# Muted moss, plum, clay, blue, ochre; this order passes the dataviz palette validator
# (adjacent CVD ΔE ≥ 16, normal-vision ΔE ≥ 19, ≥ 3:1 on white). Re-run it before re-ordering.
TS_COLORS = ["#4f8a45", "#8a5aa6", "#c0623a", "#2a6ea8", "#a8801f"]
STATE_LINE_COLOR = "#2f3f50"  # slate.8
MAX_TS_COUNTIES = 5
DEFAULT_TS_COUNTIES = ["06019", "06067", "06075"]  # Fresno, Sacramento, San Francisco
DEFAULT_TS_COUNTIES_BY_SEASON = {
    "2020": ["06019", "06067", "06075"],
    "2021": ["06063", "06017", "06067"],  # Plumas, El Dorado, Sacramento
    "2025": ["06037", "06059", "06071"],  # Los Angeles, Orange, San Bernardino
}

# ── Map ───────────────────────────────────────────────────────────────────────
MAP_CENTER = {"lat": 37.25, "lon": -119.6}
MAP_ZOOM = 4.9
MAP_STYLE = "carto-positron"
NO_DATA_COLOR = "#e5e7eb"
# Map-only colours, frozen independently of the app chrome so restyles leave the map as is.
MAP_OUTLINE_COLOR = "#294c60"  # charcoal-blue
MAP_HOVER_BORDER = "#001b2e"  # prussian-blue

BUBBLE_MIN_SIZE = 7
BUBBLE_MAX_SIZE = 30
BUBBLE_AQI_CAP = 300  # fixed size scale so bubbles compare across days

# ── Playback ──────────────────────────────────────────────────────────────────
PLAYBACK_SPEEDS = [
    {"label": "2s", "value": "2000"},
    {"label": "1s", "value": "1000"},
    {"label": "½s", "value": "500"},
    {"label": "¼s", "value": "250"},
]
DEFAULT_SPEED = "500"
