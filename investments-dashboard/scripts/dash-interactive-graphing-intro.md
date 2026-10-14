# Video Script: Interactive Visualizations — Dash Fundamentals Chapter 3
**Target length:** Under 5 minutes  
**Format:** Screen recording with voiceover, code running live  
**Narration word count:** ~490 words (~3:45–4:00 at 130 wpm + visual pauses)

---

## Beat 1 — Hook `[0:00–0:20]`

**[VISUAL]** World indicators app running — scatter plot on the left, two time series on the right. Slowly move the mouse over different country dots. The time series update in real time with each hover.

**[NARRATION]**
> "In the last chapter, callbacks reacted to controls — dropdowns, sliders, buttons. This chapter goes further. Here, the chart itself is the input. Hover over a country, and the graphs on the right update instantly. Let me show you how this works."

---

## Beat 2 — The Why: Charts as Inputs `[0:20–0:50]`

**[VISUAL]** Stay on the world indicators app, or briefly show a traditional BI tool for contrast.

**[NARRATION]**
> "Most charting tools are one-way: data goes in, chart comes out. Dash flips this. Every interaction a user has with a chart — hovering over a point, clicking it, drawing a selection box, zooming — all of that is data you can feed into a callback.
>
> This is how you build crossfiltered dashboards and linked charts. Not with a specialized tool — just callbacks."

---

## Beat 3 — The 4 Interactive Properties `[0:50–1:40]`

**[VISUAL]** Show the debug app running. Hover over points, click points, use the lasso tool, zoom — watch the JSON panels update on screen.

**[NARRATION]**
> "The `dcc.Graph` component has four properties that update through user interaction: `hoverData`, `clickData`, `selectedData`, and `relayoutData`.
>
> This debug app prints them live so you can see exactly what you're working with. Hover over a point — `hoverData` gets the coordinates, the point index, and any custom data you attached. Click — same thing in `clickData`. Draw a selection — `selectedData` gives you every point inside the box. Zoom or pan — `relayoutData` captures the new axis ranges.
>
> Any of these can be an `Input` in a callback."

---

## Beat 4 — Hover → Time Series `[1:40–3:05]`

**[VISUAL]** Open the world indicators `app.py`. Highlight the scatter callback first, then the `update_x_timeseries` callback.

**[NARRATION]**
> "Let's look at the hover example. The scatter plot on the left has `id='crossfilter-indicator-scatter'`. The two time series have their own IDs.
>
> The key line is here — `hoverData` of the scatter is an `Input`. Whenever the mouse moves to a new point, this callback fires.
>
> Now, how does the callback know which country was hovered? That's what `customdata` is for. When building the scatter, we attach the country name to each point with `fig.update_traces(customdata=...)`. Then inside the callback, we pull it out with `hoverData['points'][0]['customdata']`.
>
> From there it's just pandas filtering and returning a new figure — the same pattern as Chapter 2, just with hover as the trigger instead of a slider."

**[VISUAL]** Show the `create_time_series` helper function briefly.

> "The `create_time_series` function is a reusable helper — the kind of thing you build once and call from multiple callbacks. Clean Python."

---

## Beat 5 — Crossfilter Pattern `[3:05–3:45]`

**[VISUAL]** Switch to the 3-chart crossfilter app running. Use the lasso tool to select a cluster of points in one chart. Show the other two charts dim the unselected points and update the dashed selection rectangle.

**[NARRATION]**
> "Here's the crossfilter pattern. Three scatter plots, each with `selectedData` as an input to a shared callback. Select a region in any chart, and all three update — the selected points stay highlighted, everything else fades.
>
> The callback takes the intersection of all three selections and rerenders all three figures. The charts are both inputs and outputs at the same time.
>
> You don't need a BI tool for this. It's a Python function."

---

## Beat 6 — Summary + CTA `[3:45–4:00]`

**[VISUAL]** Quick cut back to the hover → time series demo.

**[NARRATION]**
> "Dash charts expose hover, click, selection, and zoom as callback inputs. Same decorator, same Python function — you just use the chart as the trigger instead of a control.
>
> Chapter 4 covers something that comes up quickly in real apps: sharing data between callbacks without running the same query twice. Link's in the description."

---

## Production Notes
- Beat 1: move the mouse slowly and deliberately over 3–4 countries — let the time series settle between moves so the update is clear
- Beat 3: use the debug app for this beat — it's the best way to show what `hoverData` actually contains; pause on the hover JSON so viewers can read it
- Beat 4: hover over the `customdata` line in the code and also the `hoverData['points'][0]['customdata']` extraction — this is the non-obvious part
- Beat 5: start the crossfilter demo with no selection (all bright), then lasso select — the visual contrast of highlighted vs dimmed is the whole story
- Beat 5: don't walk through the crossfilter code — the running demo is enough; the docs page has the full code for reference
- Outro card: link to [Dash Fundamentals Part 4: Sharing Data Between Callbacks](https://dash.plotly.com/docs/sharing-data-between-callbacks)
