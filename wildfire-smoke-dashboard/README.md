# California Wildfire Smoke & Respiratory Health Dashboard

A Dash + Dash Mantine Components dashboard of fine-particle (PM2.5) and ozone air
quality across California during three wildfire seasons, overlaid with NOAA satellite
smoke plumes and CAL FIRE fire perimeters, plus a county respiratory-health layer
(asthma emergency-department visit rates).

| Season | Window | Notable fires |
|---|---|---|
| 2020 | Aug 1 – Oct 31, 2020 | August Complex, SCU/LNU/CZU lightning complexes, Creek, North Complex |
| 2021 | Jul 1 – Sep 30, 2021 | Dixie, Caldor, Monument, River Complex |
| 2025 LA | Jan 1 – Feb 15, 2025 | Palisades, Eaton |

## What it shows

- **Map View**: monitors drawn as bubbles coloured by EPA AQI category (size ∝ AQI), on a
  MapLibre county map. Optional layers: HMS smoke plumes (Light/Medium/Heavy), fire
  perimeters (burning vs contained), and county shading (county-mean AQI, smoke days to
  date, asthma ED rate, or asthma burden × smoke days). A day slider with play/pause
  steps through the season. The stat cards show monitors reporting, Unhealthy+ monitors,
  statewide mean and peak, the AQI mix, day-over-day change, population-weighted exposure,
  residents in AQI>100 counties, Unhealthy+ days so far, and residents under smoke.
- **Time Series**: daily county-mean concentration for up to 5 counties against the
  population-weighted statewide mean, over AQI category bands. Below it is a strip
  showing the HMS smoke level for each county. Click a day to jump the map to it.
- **About the Data**: an editorial index of short articles, one per data source, each
  with a photograph. Every story opens as its own page at `/about/<slug>`, so articles
  can be linked to directly. The text lives in `content/articles.json`. Photos are in
  `assets/about/`; each is public domain or Creative Commons and credited in its caption.

## Data sources (all public, no API key)

| Layer | Source | URL |
|---|---|---|
| PM2.5 (88101, FRM/FEM 24-h mean) and ozone (44201, daily max 8-h) | U.S. EPA AirData pre-generated daily files | https://aqs.epa.gov/aqsweb/airdata/download_files.html (`daily_88101_<year>.zip`, `daily_44201_<year>.zip`) |
| Smoke plumes | NOAA NESDIS Hazard Mapping System smoke polygons | https://satepsanone.nesdis.noaa.gov/pub/FIRE/web/HMS/Smoke_Polygons/Shapefile/ |
| Fire perimeters (≥1,000 ac) | CAL FIRE FRAP California Fire Perimeters (yearly ArcGIS views) | https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services |
| Asthma ED visit rates by county, 2015–2023 | CDPH via CHHS Open Data | https://data.chhs.ca.gov/dataset/asthma-emergency-department-visit-rates |
| County population, 2020–2025 | U.S. Census Bureau Vintage 2025 estimates | https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv |
| County boundaries | plotly/datasets | https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json |

### Methods and caveats

- **AQI** is computed from the daily value using the EPA breakpoints (the May 2024
  PM2.5 revision), with the concentration truncated first. Ozone uses the 8-hour table,
  which stops at 200 ppb (AQI 300), so higher values are capped at 300.
- **County mean** is the average of the county's reporting monitors. **Population-weighted
  mean** weights each county mean by county population and only counts counties that
  have a monitor.
- **Smoke day**: the HMS density (or denser) covers ≥25% of the county's area. HMS
  shows smoke anywhere in the air column, so it can include smoke aloft that never
  reaches the ground.
- **Fire perimeters** are each fire's final mapped extent. A fire appears from its
  alarm date and turns grey after its containment date. The map doesn't show daily
  fire growth.
- **Asthma ED rates** are annual and age-adjusted, per 10,000 residents. The 2025 season
  uses the 2023 rates, which are the latest published. 2020–2021 ED use was lower than
  usual because of COVID-19. CDPH suppresses some small-county rates; those counties
  are ranked last.
- The **asthma burden × smoke days** map shading is a screening index, not an
  epidemiological risk estimate.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python app.py              # http://127.0.0.1:8050  (PORT=8054 to change)
.venv/bin/python -m pytest           # tests
```

## Refresh the data

```bash
.venv/bin/python -I scripts/fetch_data.py
```

The script downloads the raw files into `data_raw/`, which is gitignored. Downloads
are cached, so delete that folder to force a fresh download. It then writes the compact
snapshot to `data/`. The app only reads `data/`. To change the seasons, edit `SEASONS`
in both `scripts/fetch_data.py` and `config.py`.

## Layout

```
app.py            AppShell: header tabs, tab-aware sidebar, panels, URL location
config.py         paths, seasons, AQI breakpoints, palettes
theme.py          Mantine theme
components/       layout builders (header, sidebar, map panel, stat cards, tabs, about)
callbacks/        @callback registrations (routing, day/playback, map, stats, time series)
content/          articles.json: About the Data stories (text, photo credits)
utils/            data loading (once, at import) + pure stats / figure builders
scripts/          fetch_data.py: download + preprocess
tests/            pytest on the pure functions and callback glue
```
