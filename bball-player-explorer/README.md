# NBA Player Explorer

## About this app

Uses machine learning to help scouts look through what can be an overwhelming list
of players and metrics. It covers the 500 highest scoring NBA players with more than
2000 career minutes, combining their career statistics with their build (height,
weight and BMI).

Each view fits on one screen:

- **Similar players**: pick a player (from the dropdown or by clicking the map) to
  find the players most similar to them. The slider sets how much statistics and
  build count, and statistics can be compared per game or per 36 minutes.
  - **A map of NBA players** places every player by playing style and build
    (the first principal component of each).
  - **Most similar players** shows each one's statistical and build similarity.
  - **Player comparison** lists the stats of the closest matches.
- **Player groupings**: group players with K-means, by statistics, by build or by a
  custom set of stats, then compare the groups. Click a group in the charts to focus
  on it.

## How to run this app

Requires Python 3.13.

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050.

## Publishing to Plotly Cloud

Upload all the files in this folder to [Plotly Cloud](https://cloud.plotly.com).
It installs `requirements.txt` and serves `app:server`.

## Resources

- [Dash documentation](https://dash.plotly.com/)
- [Dash Mantine Components](https://www.dash-mantine-components.com/)
- [Basketball Reference](https://www.basketball-reference.com/)
