# MLB Team & Player History

## About this app

Explore Major League Baseball team and player statistics from 1903 to 2020, using the
Lahman Baseball Database.

Pick an **era** and a **team** in the sidebar. The list of teams follows the era, and
the year range can be adjusted with the slider. Each view fits on one screen:

- **Team**: win/loss record with winning percentage, titles won (World Series,
  pennants, division titles, wild cards), batting (slugging, BABIP, batting average),
  fielding (errors, double plays) and pitching (strikeout to walk ratio with ERA, or
  complete games, shutouts and saves per game).
- **Batting**: on-base percentage, slugging average and OPS of any player on the
  roster, with their season-by-season batting line.
- **Pitching & fielding**: a player's WHIP, strikeout to walk ratio and winning
  percentage as a pitcher, fielding percentage by position, and season stats.

Players are listed with pitchers and position players grouped separately, most games
played first. For continuity, some historical team names were changed to match their
modern counterpart.

Originally built by [Matt Parra](https://devparra.github.io/).

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

## Data

The data comes from the [Lahman Baseball Database](https://sabr.org/lahman-database/),
via the [Chadwick Baseball Bureau](https://github.com/chadwickbureau/baseballdatabank/).
This database is copyright 1996-2021 by Sean Lahman and is licensed under a
[Creative Commons Attribution-ShareAlike 3.0 Unported License](https://creativecommons.org/licenses/by-sa/3.0/).

## Resources

- [Dash documentation](https://dash.plotly.com/)
- [Dash Mantine Components](https://www.dash-mantine-components.com/)
- [Dash AG Grid](https://dash.plotly.com/dash-ag-grid)
