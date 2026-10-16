# Manufacturing SPC Dashboard

A dashboard for monitoring real-time process quality along a manufacturing line,
built with [Dash](https://dash.plotly.com/) and
[Dash Mantine Components](https://www.dash-mantine-components.com/).

It replays mock measurement data for seven process parameters and tracks each one
with a [Shewhart individuals control chart](https://en.wikipedia.org/wiki/Shewhart_individuals_control_chart).
Measurements outside the control limits are flagged as **out of control (OOC)**.

## Features

- **Live replay**: Start, pause and resume a replay of one batch per second.
- **Process control metrics**: a trend sparkline, OOC rate and Pass / Warn / Fail
  status for every parameter (Warn above 5% OOC, Fail above 7%).
- **Live SPC chart**: click any parameter to chart it, with its mean, control
  limits (UCL/LCL), specification limits (USL/LSL), OOC points and a distribution.
- **Specification settings**: override any parameter's limits or reset them to the
  historical values (mean ± 1σ for specification, mean ± 3σ for control).

The whole dashboard fits in one screen on desktop and stacks on mobile.

## Project structure

```
app.py              # Layout and callbacks
spc.py              # Data loading, control-limit math and chart builders
assets/style.css    # Page layout and styling
data/spc_data.csv   # Mock measurements, one row per batch
```

## Publish to Plotly Cloud

Upload all of the files in this folder to [Plotly Cloud](https://cloud.plotly.com).
Plotly Cloud installs the dependencies from `requirements.txt`.

## Run locally

Requires Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050.
