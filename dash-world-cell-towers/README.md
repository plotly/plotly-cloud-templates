## World Cell Towers Dash App
A [Dash](https://dash.plotly.com/) app for exploring every cell tower in the
[OpenCelliD](https://www.opencellid.org/) database: about 50 million towers, filtered
live by location, radio technology (2G to 5G), signal range, and the year each tower
was added.

## Technical Details
The towers are rendered on the server with [Datashader](https://datashader.org/), so the
full dataset can be shown on the map at once. When 5,000 or fewer towers are in view,
the map switches to drawing each tower individually, with a tooltip showing its operator,
radio, range, and location. The interface is built with
[Dash Mantine Components](https://www.dash-mantine-components.com/), and the base map
is CARTO's free Positron style rendered with MapLibre, so no Mapbox token is needed.

The code is organized as:
 - `app.py`: creates the Dash app
 - `dash_opencellid/layout.py`: the page layout
 - `dash_opencellid/callbacks.py`: filtering the towers and updating the charts
 - `dash_opencellid/figures.py`: the map and chart figures
 - `dash_opencellid/theme.py`: colors and the Plotly chart template
 - `dash_opencellid/data.py` and `download_data.py`: downloading, processing, and
   loading the dataset (see below)

## Data setup
The dataset is too large to publish with the app. Instead, the first time the app
starts it downloads the raw [OpenCellid](https://www.opencellid.org/) `cell_towers.csv`
(~4 GB) from a [copy hosted on Google Drive](https://drive.google.com/file/d/1lCvFgEIANGQWwypVs8Irbc46k0MiMt7L/view),
processes it into a parquet dataset with `dash_opencellid/download_data.py`, and loads
it in the background, showing a loading banner until it is ready. To use a different
copy, set `CELL_TOWERS_CSV_URL` to any public URL (optionally gzipped), including a
Google Drive file shared as "Anyone with the link". The partly downloaded CSV is kept in
the data directory (`cell_towers.csv.partial`), so if the app restarts or the connection
drops, the download resumes where it left off.

On Plotly Cloud the dataset is saved in the persistent `/data` directory, so it is only
downloaded once; later restarts load it straight from disk. To download a fresh copy,
delete `/data/cell_towers.parq` and restart the app. Locally it is saved under `./data`.

The download can also be run by hand:
```
$ python -m dash_opencellid.download_data
```

## Publish to Plotly Cloud
1. Go to [cloud.plotly.com](https://cloud.plotly.com) and select **Publish**.
2. Upload all of the files in this folder (the `data/` folder is not needed).
3. Set **Main file** to `app.py` and **Python version** to 3.12.
4. Select **Save & publish**, then in the app's **Compute** tab set the app size to
   **Performance M** (8 GB RAM). The full dataset needs about 4-5 GB of memory once
   loaded, so smaller sizes run out of memory and keep restarting. `gunicorn.conf.py`
   runs a single worker (with threads) so the dataset is only loaded once.
5. The first start takes a while as the dataset is downloaded and processed (watch the
   logs for `Cell towers dataset ready`). Keep the app open in a browser tab until then,
   since apps in **Automatically sleep** mode go to sleep after 15 minutes without
   requests.

## Run locally
```
$ pip install -r requirements.txt
$ python app.py
```

## Using the app
 - **Radio**: click a bar to show only that technology, and shift-click to add more.
 - **Signal range** and **Year added**: drag across a chart to select a range.
 - **Locations**: pan and zoom the map; the other charts update to the towers in view.
 - Each panel's **Clear selection** button clears its own selection, and **Reset all**
   in the header clears everything and recenters the map.
 - The info icon next to each panel title explains the panel.
