"""Download and preprocess the dashboard's data snapshot.

Run:  .venv/bin/python -I scripts/fetch_data.py

Raw downloads land in `data_raw/` (gitignored, treated as untrusted input); compact
outputs are written to `data/`, which is all the app ever reads. Every source is
public and key-free. The script is self-contained (no project imports) so it can
run under `python -I`; downloads are cached, so re-running only fetches what's missing.

Outputs (data/):
    counties.geojson        58 CA counties (plotly geojson-counties-fips, FIPS 06xxx)
    monitors.csv            one row per AQS site: id, name, lat/lon, county FIPS
    aq_daily.csv            daily site values per season: PM2.5 24-h mean (µg/m³), ozone daily max 8-h (ppb)
    smoke.geojson           NOAA HMS smoke polygons per day, dissolved by density, clipped & simplified
    county_smoke.csv        per county/day: highest HMS density covering ≥25% of the county
    fires.geojson           CAL FIRE perimeters (≥1,000 ac) burning during each season, simplified
    county_health.csv       CDPH age-adjusted asthma ED visit rates per 10k (all ages, 0–17), 2015–2023
    county_population.csv   Census Vintage 2025 county population estimates, 2020–2025
    manifest.json           source URLs, seasons and fetch timestamp
"""

import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data_raw"
OUT = ROOT / "data"

# Must match config.SEASONS (the app); kept here so the script has no project imports.
SEASONS = {
    "2020": ("2020-08-01", "2020-10-31"),  # August Complex, SCU/LNU/CZU lightning, Creek, North Complex
    "2021": ("2021-07-01", "2021-09-30"),  # Dixie, Caldor, Monument, River Complex
    "2025": ("2025-01-01", "2025-02-15"),  # Los Angeles: Palisades & Eaton
}

AIRDATA_URL = "https://aqs.epa.gov/aqsweb/airdata/daily_{param}_{year}.zip"
PARAMS = {"pm25": "88101", "ozone": "44201"}
HMS_URL = "https://satepsanone.nesdis.noaa.gov/pub/FIRE/web/HMS/Smoke_Polygons/Shapefile/{y}/{m:02d}/hms_smoke{ymd}.zip"
COUNTIES_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
ASTHMA_URL = (
    "https://data.chhs.ca.gov/dataset/34f3464e-b2eb-4f74-9ef9-f378711aa0f5/resource/"
    "94d84508-8046-40a7-b8d9-0ed73b13b697/download/asthma-emergency-department-visit-rates-by-county-2015_2023.csv"
)
POP_URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv"
FIRES_URL = (
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/{service}/FeatureServer/0/query"
    "?where=GIS_ACRES%3E%3D1000&outFields=FIRE_NAME,ALARM_DATE,CONT_DATE,GIS_ACRES"
    "&outSR=4326&maxAllowableOffset=0.004&geometryPrecision=4&f=geojson"
)
FIRE_SERVICES = {"2021": "2021_California_Fire_Perimeters"}  # other years use "<year>_California_Fire_Perimeters_View"

# CA bounding box with a margin for smoke drifting just offshore / over the border.
CA_BBOX = (-125.5, 32.0, -113.5, 42.5)
CA_ALBERS = 3310  # equal-area CRS for coverage fractions
SMOKE_COVER_FRAC = 0.25
SMOKE_SIMPLIFY_DEG = 0.03
DENSITY_LEVELS = {"Light": 1, "Medium": 2, "Heavy": 3}
# Pre-2022 HMS files sometimes encode density as the analysts' µg/m³ bin centre.
NUMERIC_DENSITY = {5: "Light", 16: "Medium", 27: "Heavy"}


# ── Download helpers ──────────────────────────────────────────────────────────
class _StripDefaultPort(urllib.request.HTTPRedirectHandler):
    """data.chhs.ca.gov redirects to a presigned S3 URL written as `host:443`; urllib
    would send that port in the Host header and S3 rejects the signature (403)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, newurl.replace(".com:443/", ".com/", 1))


_OPENER = urllib.request.build_opener(_StripDefaultPort)


def download(url: str, dest: Path, retries: int = 3) -> Path | None:
    """Fetch `url` to `dest` once (cached). Returns None on a 404 / persistent failure."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wildfire-smoke-dashboard/1.0"})
            with _OPENER.open(req, timeout=120) as resp:
                dest.write_bytes(resp.read())
            return dest
        except urllib.error.HTTPError as err:
            if err.code == 404:
                print(f"  404 {url}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 * (attempt + 1))
    print(f"  FAILED {url}", file=sys.stderr)
    return None


def season_days(season: str) -> list[date]:
    start, end = (date.fromisoformat(d) for d in SEASONS[season])
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


# ── Counties ──────────────────────────────────────────────────────────────────
def build_counties() -> gpd.GeoDataFrame:
    path = download(COUNTIES_URL, RAW / "geojson-counties-fips.json")
    gj = json.loads(path.read_text())
    features = [
        {"type": "Feature", "id": f["id"], "properties": {"fips": f["id"], "name": f["properties"]["NAME"]}, "geometry": f["geometry"]}
        for f in gj["features"]
        if f["properties"]["STATE"] == "06"
    ]
    gdf = gpd.GeoDataFrame.from_features(features, crs=4326).sort_values("fips").reset_index(drop=True)
    gdf["geometry"] = shapely.set_precision(gdf.geometry.values, 1e-4, mode="pointwise")
    (OUT / "counties.geojson").write_text(gdf.to_json(drop_id=True, separators=(",", ":")))
    print(f"counties: {len(gdf)}")
    return gdf


# ── EPA AirData ───────────────────────────────────────────────────────────────
AIRDATA_COLS = [
    "State Code", "County Code", "Site Num", "POC", "Latitude", "Longitude", "Date Local",
    "Sample Duration", "Arithmetic Mean", "1st Max Value", "Local Site Name", "County Name",
]


def read_airdata(param: str, year: str) -> pd.DataFrame:
    path = download(AIRDATA_URL.format(param=param, year=year), RAW / f"daily_{param}_{year}.zip")
    if path is None:
        return pd.DataFrame()
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            df = pd.read_csv(fh, usecols=AIRDATA_COLS, dtype={"State Code": str, "County Code": str, "Site Num": str})
    return df[df["State Code"] == "06"]


def build_air_quality() -> pd.DataFrame:
    frames, sites = [], []
    for season, (start, end) in SEASONS.items():
        for pollutant, param in PARAMS.items():
            df = read_airdata(param, season)
            if df.empty:
                continue
            df = df[(df["Date Local"] >= start) & (df["Date Local"] <= end)].copy()
            df["site_id"] = df["State Code"] + "-" + df["County Code"] + "-" + df["Site Num"]
            df["county_fips"] = df["State Code"] + df["County Code"]
            if pollutant == "pm25":
                # 24-h mean; the file repeats rows per NAAQS standard, so dedupe per instrument first.
                df = df.drop_duplicates(["site_id", "POC", "Date Local", "Sample Duration"])
                df["value"] = df["Arithmetic Mean"]
            else:
                # Ozone AQI uses the daily maximum 8-hour average (ppm → ppb).
                df = df[df["Sample Duration"].str.startswith("8-HR")]
                df = df.drop_duplicates(["site_id", "POC", "Date Local"])
                df["value"] = df["1st Max Value"] * 1000
            daily = df.groupby(["site_id", "Date Local"], as_index=False)["value"].mean()
            daily = daily.rename(columns={"Date Local": "date"}).assign(season=season, pollutant=pollutant)
            frames.append(daily)
            sites.append(df[["site_id", "Local Site Name", "Latitude", "Longitude", "county_fips"]].assign(pollutant=pollutant))
            print(f"airdata {season} {pollutant}: {daily['site_id'].nunique()} sites, {len(daily)} site-days")

    aq = pd.concat(frames, ignore_index=True)
    aq["value"] = aq["value"].round(1)
    aq = aq[["season", "date", "pollutant", "site_id", "value"]].sort_values(["season", "pollutant", "date", "site_id"])
    aq.to_csv(OUT / "aq_daily.csv", index=False)

    mon = pd.concat(sites, ignore_index=True)
    pollutants = mon.groupby("site_id")["pollutant"].agg(lambda s: "|".join(sorted(set(s))))
    mon = (
        mon.drop_duplicates("site_id", keep="last")
        .set_index("site_id")
        .assign(pollutants=pollutants)
        .rename(columns={"Local Site Name": "name", "Latitude": "lat", "Longitude": "lon"})
        .reset_index()[["site_id", "name", "lat", "lon", "county_fips", "pollutants"]]
        .sort_values("site_id")
    )
    mon["name"] = mon["name"].fillna(mon["site_id"]).str.strip()
    mon.to_csv(OUT / "monitors.csv", index=False)
    print(f"monitors: {len(mon)}")
    return aq


# ── NOAA HMS smoke ────────────────────────────────────────────────────────────
def _density_label(value) -> str | None:
    if isinstance(value, str):
        value = value.strip().title()
        return value if value in DENSITY_LEVELS else None
    try:
        return NUMERIC_DENSITY.get(int(round(float(value))))
    except (TypeError, ValueError):
        return None


def read_hms_day(day: date) -> gpd.GeoDataFrame | None:
    ymd = day.strftime("%Y%m%d")
    url = HMS_URL.format(y=day.year, m=day.month, ymd=ymd)
    path = download(url, RAW / "hms" / f"hms_smoke{ymd}.zip")
    if path is None:
        return None
    try:
        gdf = gpd.read_file(f"zip://{path}")
    except Exception as err:  # malformed archive → skip the day, never invent one
        print(f"  unreadable HMS {ymd}: {err}", file=sys.stderr)
        return None
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    gdf["density"] = gdf["Density"].map(_density_label) if "Density" in gdf else None
    gdf = gdf[gdf["density"].notna() & gdf.geometry.notna()]
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf.clip(CA_BBOX)


def build_smoke(counties: gpd.GeoDataFrame) -> None:
    county_eq = counties.to_crs(CA_ALBERS)
    county_area = county_eq.geometry.area.values
    features, rows = [], []
    for season in SEASONS:
        missing = 0
        for day in season_days(season):
            gdf = read_hms_day(day)
            if gdf is None:
                missing += 1
                continue
            iso = day.isoformat()
            # Union per density, then cumulative "at least this dense" unions for coverage.
            unions = {
                d: shapely.union_all(gdf.geometry[gdf["density"] == d].values) if (gdf["density"] == d).any() else None
                for d in DENSITY_LEVELS
            }
            for d, geom in unions.items():
                if geom is None or geom.is_empty:
                    continue
                simple = shapely.set_precision(geom.simplify(SMOKE_SIMPLIFY_DEG, preserve_topology=True), 1e-3, mode="pointwise")
                if simple.is_empty:
                    continue
                features.append(
                    {"type": "Feature", "properties": {"season": season, "date": iso, "density": d}, "geometry": shapely.geometry.mapping(simple)}
                )
            level = [0] * len(counties)
            frac_any = [0.0] * len(counties)
            for d, lvl in DENSITY_LEVELS.items():
                at_least = [g for k, g in unions.items() if g is not None and DENSITY_LEVELS[k] >= lvl]
                if not at_least:
                    continue
                cover = gpd.GeoSeries([shapely.union_all(at_least)], crs=4326).to_crs(CA_ALBERS).iloc[0]
                fracs = county_eq.geometry.intersection(cover).area.values / county_area
                for i, f in enumerate(fracs):
                    if lvl == 1:
                        frac_any[i] = round(float(f), 3)
                    if f >= SMOKE_COVER_FRAC:
                        level[i] = lvl
            rows.extend(
                {"season": season, "date": iso, "fips": fips, "smoke": lvl, "frac_any": fa}
                for fips, lvl, fa in zip(counties["fips"], level, frac_any)
            )
        print(f"smoke {season}: {len(season_days(season)) - missing} days ({missing} missing)")

    (OUT / "smoke.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    pd.DataFrame(rows).to_csv(OUT / "county_smoke.csv", index=False)


# ── CAL FIRE perimeters ───────────────────────────────────────────────────────
def build_fires() -> None:
    features = []
    for season, (start, end) in SEASONS.items():
        service = FIRE_SERVICES.get(season, f"{season}_California_Fire_Perimeters_View")
        path = download(FIRES_URL.format(service=service), RAW / f"fires_{season}.geojson")
        if path is None:
            continue
        gj = json.loads(path.read_text())
        kept = 0
        for f in gj.get("features", []):
            p = f["properties"]
            if not f.get("geometry") or not p.get("ALARM_DATE"):
                continue
            alarm = datetime.fromtimestamp(p["ALARM_DATE"] / 1000, tz=timezone.utc).date().isoformat()
            cont = datetime.fromtimestamp(p["CONT_DATE"] / 1000, tz=timezone.utc).date().isoformat() if p.get("CONT_DATE") else None
            if alarm > end or (cont is not None and cont < start):
                continue  # not burning during the season window
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "season": season,
                        "name": (p.get("FIRE_NAME") or "Unnamed").strip().title(),
                        "alarm": alarm,
                        "cont": cont,
                        "acres": round(float(p.get("GIS_ACRES") or 0)),
                    },
                    "geometry": f["geometry"],
                }
            )
            kept += 1
        print(f"fires {season}: {kept}")
    (OUT / "fires.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))


# ── Health & population ───────────────────────────────────────────────────────
def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce")


def build_health(counties: gpd.GeoDataFrame) -> None:
    path = download(ASTHMA_URL, RAW / "asthma_ed_by_county.csv")
    df = pd.read_csv(path, encoding="cp1252")  # the CDPH export is Windows-1252 (en dashes)
    df.columns = [c.strip().upper() for c in df.columns]
    df["AGE GROUP"] = df["AGE GROUP"].str.replace("–", "-")
    name_to_fips = dict(zip(counties["name"], counties["fips"]))
    df = df[df["COUNTY"].isin(name_to_fips) & df["STRATA"].isin(["Total population", "Child vs. adult"])]
    df = df.assign(fips=df["COUNTY"].map(name_to_fips), rate=_num(df["AGE-ADJUSTED ED VISIT RATE"]), visits=_num(df["NUMBER OF ED VISITS"]))
    # Suppressed / unstable rates are blank in the source; keep them missing.
    total = df[df["STRATA"] == "Total population"].set_index(["fips", "YEAR"])
    child = df[(df["STRATA"] == "Child vs. adult") & (df["AGE GROUP"] == "0-17 years")].set_index(["fips", "YEAR"])
    out = pd.DataFrame(
        {
            "county": total["COUNTY"],
            "asthma_ed_rate": total["rate"],
            "asthma_ed_visits": total["visits"],
            "asthma_ed_rate_child": child["rate"],
        }
    ).reset_index().rename(columns={"YEAR": "year"}).sort_values(["fips", "year"])
    out.to_csv(OUT / "county_health.csv", index=False)
    print(f"health: {out['fips'].nunique()} counties, years {out['year'].min()}–{out['year'].max()}")

    path = download(POP_URL, RAW / "co-est2025-alldata.csv")
    pop = pd.read_csv(path, encoding="latin-1", dtype={"STATE": str, "COUNTY": str})
    pop = pop[(pop["STATE"] == "06") & (pop["COUNTY"] != "000")]
    years = [c for c in pop.columns if c.startswith("POPESTIMATE") and c[11:].isdigit()]
    long = pop.assign(fips=pop["STATE"] + pop["COUNTY"]).melt(id_vars="fips", value_vars=years, var_name="year", value_name="population")
    long["year"] = long["year"].str[11:].astype(int)
    long.sort_values(["fips", "year"]).to_csv(OUT / "county_population.csv", index=False)
    print(f"population: {long['fips'].nunique()} counties, years {long['year'].min()}–{long['year'].max()}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    counties = build_counties()
    build_health(counties)
    build_air_quality()
    build_fires()
    build_smoke(counties)
    manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seasons": SEASONS,
        "sources": {
            "air_quality": [AIRDATA_URL.format(param=p, year=y) for y in SEASONS for p in PARAMS.values()],
            "smoke": "https://satepsanone.nesdis.noaa.gov/pub/FIRE/web/HMS/Smoke_Polygons/Shapefile/",
            "fires": [FIRES_URL.split("?")[0].format(service=FIRE_SERVICES.get(y, f"{y}_California_Fire_Perimeters_View")) for y in SEASONS],
            "asthma": ASTHMA_URL,
            "population": POP_URL,
            "counties": COUNTIES_URL,
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name:24s} {f.stat().st_size / 1e6:6.2f} MB")


if __name__ == "__main__":
    main()
