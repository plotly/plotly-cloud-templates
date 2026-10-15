# Ternary Map Explorer

A dashboard for mineral composition evaluations from natural gas wells. By pairing a geographic map of well locations with a ternary diagram, it helps geologists relate well results to formations and rock types.

Built with [Dash](https://dash.plotly.com/) and Dash Design Kit.

## Run locally

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8050/ in your browser.

## Publish to Plotly Cloud

Drag and drop the contents of this folder into a new app on [cloud.plotly.com](https://cloud.plotly.com).

## How to use the app

Select a subset of data points from the well map, ternary map or bar graph to cross-filter the other plots.
Click individual points, or use the lasso tool to capture multiple points or bars. Hold SHIFT while clicking and dragging to select multiple regions.

## Data source

Historical shale gas production data for selected Devonian Ohio Shale wells: http://www.uky.edu/KGS/emsweb/kyogfaq/kyogfaq10.html
