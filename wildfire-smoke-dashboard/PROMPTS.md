# Prompts

These are the prompts used in the [From Figma to Dash](https://plotly.com/webinars/figma-to-dash/)
webinar to turn a Figma Make prototype into this Dash app with an AI coding agent. They run in
order: the first builds the theme, the second builds the Map View screen, and the third makes
it interactive. The finished app adds more layers and tabs using the same approach. See the
[README](README.md) for what the app shows, its data sources, and how to run it.

The agent also had two files in the project folder, both included here:

- [AGENTS.md](AGENTS.md): the conventions for a Dash project (structure, callbacks, styling,
  patterns to avoid), plus notes for this project.
- [llms.txt](llms.txt): the full Dash Mantine Components documentation, from
  <https://www.dash-mantine-components.com/assets/llms.txt>. The agent searches it for each
  component instead of reading the whole file.

## 1. Theme

```text
Here's the Figma Make prototype for our dashboard:
https://www.figma.com/make/gJM0Nlh9th5jPnlF523KKL

Read its colors, fonts and shadows and create theme.py for a Dash
app:
- each brand color scale becomes a Mantine color
- use IBM Plex Sans and the shadow tokens
- keep the AQI, smoke and fire colors as separate constants: they're
  data colors, not brand colors
```

## 2. Map View screen

```text
Now build the Map View screen from the same prototype as a Dash app
that uses theme.py. Follow AGENTS.md for the project structure.
- download the prototype's code from Figma Make into ~/prototype-code,
  then copy the JSON files from its src/data folder into data/. Don't
  read them whole; its src/app/lib/data.ts shows how they fit together
- use dmc.AppShell: a header with tabs, a left sidebar of controls, and
  a right stats rail
- show the real monitors on the map for the first day of the 2020
  season, colored by AQI category; port the AQI formula from the
  prototype.
- under the map, add a short caption crediting the data sources: U.S.
  EPA AirData, NOAA HMS, CAL FIRE, CDPH and the U.S. Census Bureau
- keep placeholder values in the stat cards for now
- use app.run(debug=True) so the page reloads on changes; I'll start
  the app myself
- build the requirements.txt and create a venv
Look up each DMC component in llms.txt before you use it, and check
the Dash docs for anything in core Dash.
```

## 3. Interactivity

```text
Now make the Map View interactive:
- wire the season, pollutant and day controls with callbacks, so the
  map shows the selected day
- make the play button step through the days, with pause
- fill in the stat cards: port the calculations from the prototype's
  src/app/lib/stats.ts
Filter in Python and send only the selected day's points to the browser.
```
