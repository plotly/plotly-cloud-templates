# Alignment Chart

View multiple sequence alignments of genomic or proteomic sequences with the
[Dash Bio](https://dash.plotly.com/dash-bio) `AlignmentChart` component.

## Features

- **Sample datasets**: Three bundled FASTA files (in `data/`) to explore right away
- **File upload**: Load your own FASTA alignment file
- **Customization**: Colorscales, overview (heatmap/slider), consensus, conservation and gap bars, labels and IDs
- **Event data**: Inspect hover and click events from the chart

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050.

## Publish to Plotly Cloud

Upload all files in this folder to [Plotly Cloud](https://cloud.plotly.com).
The app exposes `server` in `app.py` for gunicorn (`gunicorn app:server`).
