# VitalSight — Clinical Intelligence Platform

A Plotly Dash demonstration of clinical data visualization, built to mirror the architecture of `dash-financial-report-v2`.

> **IMPORTANT:** All patient data is **synthetic and de-identified**. X-ray images are algorithmically generated grayscale placeholders. This application is for demonstration purposes only and is not intended for clinical use.

## Features

- **Clinical Dashboard** — Census KPIs + live ICU vitals streaming via WebSocket (mirrors the financial app's live stock feed)
- **Patient Vitals** — Multi-vital time-series with normal-range bands, moving averages, and period selectors
- **Cohort Explorer** — Crossfilter linked-brushing across 3 biomarker scatter plots (port of the crossfilter demo)
- **Imaging Workstation** — Interactive X-ray annotation (draw rectangles, lines, circles), window/level controls, AI-assist suggested findings, and radiology report PDF export

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Generate synthetic data and X-ray images
python scripts/generate_data.py
python scripts/generate_xrays.py

# Run the app
python app.py
# or for production
uvicorn app:server --host 0.0.0.0 --port 8000
```

App runs at http://localhost:8050 (debug) or http://localhost:8000 (uvicorn).

## Project Structure

```
medical-demo-app/
├── app.py                  Main entry point
├── pages/                  One layout module per page
│   ├── dashboard.py
│   ├── vitals.py
│   ├── cohort.py
│   └── imaging.py
├── callbacks/              One callback module per page
│   ├── dashboard.py        Includes live vitals WebSocket
│   ├── vitals.py
│   ├── cohort.py
│   ├── imaging.py
│   └── export_all.py       PDF export
├── components/             Reusable Plotly/Mantine components
│   ├── charts.py
│   ├── kpi_cards.py
│   ├── tables.py
│   └── imaging.py
├── utils/
│   ├── data_loader.py
│   └── pdf_export.py
├── data/                   Generated CSVs (run generate_data.py)
├── assets/
│   ├── styles.css
│   └── xrays/              Generated X-ray PNGs (run generate_xrays.py)
└── scripts/
    ├── generate_data.py
    └── generate_xrays.py
```

## Attribution

X-ray image generation is inspired by the NIH ChestX-ray14 dataset structure (CC0 Public Domain).
NIH Clinical Center: https://nihcc.app.box.com/v/ChestXray-NIHCC
