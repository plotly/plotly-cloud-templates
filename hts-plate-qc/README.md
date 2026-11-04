# Screening Plate QC

A quality control review app for a high-throughput screening campaign: 72
384-well plates, 23,040 compounds, read over six runs. It answers the questions a
screening scientist has before hits go to confirmation: which plates can be
trusted, which broke a QC rule and why, and are the hits on a plate real
chemistry or an artifact of the plate.

The app shows:

- **A strip of every plate in run order** in the header, colored by its QC
  result, with plates still awaiting review outlined. Click a tile to open it
- **Campaign totals**: plates read, the share that passed auto QC, median Z′,
  hit rate on accepted plates and how many plates are waiting for review
- **A review queue** of every plate that broke a QC rule, open items first,
  with the rules it broke and the decision taken
- **Plate quality across the campaign** in run order: Z′-factor against the
  review and fail limits, control signal (mean ± 3 SD) or hit rate. The reagent
  lot change and run boundaries are marked, so drift and lot effects show up
- **For the selected plate**:
  - Z′, robust Z′, signal window, control CVs, edge-vs-interior ratio and hits
  - A plate map in % inhibition, raw signal or B-score, with the median of each
    row and column alongside and hits outlined
  - Why it was flagged, in words
  - Control separation: DMSO and reference-inhibitor wells with their ±3 SD
    bands, against the compound distribution
  - The hits on the plate, with a caution when one sits in a suspect row or
    edge well
  - **Accept, Re-run or Reject** buttons. Decisions update the queue, KPIs and
    table, and are kept for the browser session
- **A table of every plate** with all QC metrics, reader, dispenser and
  reagent lot

Click a plate in the header strip, the queue, the chart or the table to open it.

## The data

The data is synthetic. `screening.py` generates a TR-FRET kinase assay with
DMSO controls in columns 1–2, a reference inhibitor in columns 23–24 and
compounds in 3–22, about 0.6% real actives, weak binders and a few fluorescent
compounds that read high. It plants the faults a screening lab actually meets:

| Fault | Where | What the QC sees |
| --- | --- | --- |
| Evaporation at the plate edge | last plates of run 2, last plate of run 6 | Edge effect |
| Clogged dispenser nozzle under-filling row K | run 3, Multidrop-2 | Row K stripe, high hit rate, control outliers |
| New detection reagent lot with a smaller window | runs 4–6 | Lower S/B in the controls chart |
| Reference inhibitor missing from half of column 24 | ZK7-407 | Negative Z′, robust Z′ still fine |
| Signal decay as plates wait for the reader | run 5 | Z′ falling through the run |

None of the QC code knows about these; every flag is computed from the well
values.

## QC rules

| Rule | Review | Fail |
| --- | --- | --- |
| Z′-factor | below 0.5 | below 0.4 |
| DMSO control CV | above 10% | |
| Control outliers (robust z > 4 within their group) | 2 or more | |
| Outer compound wells vs interior median | more than ±6% | |
| Median % inhibition of a row or column | beyond ±20% | |
| Hit rate (≥ 50% inhibition) | above 2% | |

Percent inhibition is normalised to the medians of each plate's own controls.
B-scores are Tukey median-polish residuals of the compound wells scaled by
their MAD, which removes row, column and edge patterns: a hit in a stripe row
keeps a high % inhibition but a B-score near zero.

Built with [Dash](https://dash.plotly.com/),
[Dash Mantine Components](https://www.dash-mantine-components.com/) and
[Dash AG Grid](https://dash.plotly.com/dash-ag-grid).

![Screenshot of app](assets/screenshot.png)

## Running locally

Requires Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050.

## Deploying to Plotly Cloud

The app exposes `server` for gunicorn (see `Procfile`) and the Python version is
pinned in `.python-version`. The campaign is generated with a fixed seed at
import, so every worker shows the same plates.

## Using real data

Replace `build_campaign()` in `screening.py` with a loader that returns `Plate`
objects from your plate reader exports or LIMS: a 16 × 24 array of raw values,
the compound ID in each well, and the run, read time, reader, dispenser and
reagent lot. `qc()` computes everything else. Change `HIGH_COLS`, `LOW_COLS`
and the thresholds to match your plate layout and SOP.
