"""
Store Demand Forecast

Forecasts daily unit sales for each store and department of Cascade Market, a
made-up 18-store grocery chain, for the next 12 weeks. Pick a store on the map
or the growth grid to see its forecast with uncertainty bands, what is driving
the change from last year, how the previous forecast did, and how much to order
each week. Try scenarios: move the department's circular promotions or change
the weather outlook.

The sales history is synthetic, see demand.py.
"""

import datetime as dt
from functools import lru_cache

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

import demand as dm

# Chart colors, kept in sync with assets/style.css
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e9e8e2"
AXIS = "#c3c2b7"
FORECAST = "#2a78d6"
BAND_80 = "rgba(42, 120, 214, 0.22)"
BAND_95 = "rgba(42, 120, 214, 0.10)"
LAST_YEAR = "#a3a29a"
PROMO = "rgba(237, 161, 0, 0.13)"
PROMO_INK = "#9a6a00"
UP = "#256abf"
DOWN = "#d03b3b"
DIVERGING = [[0, "#b8312f"], [0.25, "#ec9a96"], [0.5, "#f0efec"], [0.75, "#86b6ef"], [1, "#1c5cab"]]
GROWTH_CAP = 0.12  # color scale saturates at +/-12%

FONT = "Figtree, system-ui, sans-serif"
THEME = {"fontFamily": FONT, "headings": {"fontFamily": FONT}, "primaryColor": "indigo", "defaultRadius": "md"}

ALL = "all"
CHIP_HELP_ALL = "Pick a department to move its circular promotions."
TEMP_OUTLOOK = {"cold": -3.0, "normal": 0.0, "warm": 3.0}

app = dash.Dash(
    __name__,
    title="Store Demand Forecast",
    external_stylesheets=["https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap"],
)
server = app.server


# ---------- helpers ----------

def keys_for(store, dept):
    stores = [s.id for s in dm.STORES] if store == ALL else [store]
    depts = dm.DEPARTMENTS if dept == ALL else [dept]
    return [(s, d) for s in stores for d in depts]


def promo_override(dept, weeks):
    """Scenario promo calendar: only an individual department's circular can be edited."""
    return {} if dept == ALL or weeks is None else {dept: [int(w) for w in weeks]}


def planned_weeks(dept):
    return [i for i in range(dm.WEEKS) if dm.PROMO[dept][dm.WEEK[dm.N_HIST + 7 * i]]]


def fmt_units(x):
    x = float(x)
    if abs(x) >= 1e6:
        return f"{x / 1e6:.2f}M"
    if abs(x) >= 1e4:
        return f"{x / 1e3:.0f}k"
    if abs(x) >= 1e3:
        return f"{x / 1e3:.1f}k"
    return f"{x:,.0f}"


def fmt_pct(x, digits=1):
    if round(x * 100, digits) == 0:
        return f"{0:.{digits}f}%"  # no sign on a change that rounds to zero
    return f"{x * 100:+.{digits}f}%".replace("-", "−")


def short(d):
    return d.strftime("%b %-d")


def weekly(a):
    """Sum daily values (..., days) into weeks."""
    return a.reshape(*a.shape[:-1], -1, 7).sum(-1)


def selection_label(store, dept):
    where = "All stores" if store == ALL else dm.STORE[store].name
    what = "all departments" if dept == ALL else dept
    return f"{where} · {what}"


def style_axes(fig, height):
    axis = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
                title_font={"color": MUTED, "size": 12})
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    fig.update_layout(
        height=height,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12, "family": FONT}},
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"size": 12},
                "bgcolor": "rgba(0,0,0,0)"},
    )
    return fig


# Simulations are the slow part, so keep recent ones. The service level and the
# weekly/daily view only change how the same paths are summarised.

@lru_cache(maxsize=64)
def forecast_paths(store, dept, temp, weeks):
    models = [dm.MODELS[k] for k in keys_for(store, dept)]
    return dm.simulate(models, promo_override(dept, weeks), TEMP_OUTLOOK[temp])


@lru_cache(maxsize=64)
def backtest_paths(store, dept):
    return dm.simulate([dm.BACKTEST[k] for k in keys_for(store, dept)])


# ---------- figures ----------

def forecast_figure(store, dept, view, sims, promo_weeks):
    keys = keys_for(store, dept)
    hist = dm.actuals(keys)
    if view == "week":
        n_hist = 26
        x_hist = dm.DATES[dm.N_HIST - 7 * n_hist:dm.N_HIST:7]
        y_hist = weekly(hist[dm.N_HIST - 7 * n_hist:])
        x_fc = dm.WEEK_STARTS
        paths = weekly(sims)
        ly = weekly(dm.actuals(keys, dm.N_HIST - 364, dm.N_HIST - 364 + dm.HORIZON))
        hover_x = "Week of %{x|%b %-d}"
        shape = "linear"
    else:
        n_hist = 42
        x_hist = dm.DATES[dm.N_HIST - n_hist:dm.N_HIST]
        y_hist = hist[dm.N_HIST - n_hist:]
        x_fc = dm.FORECAST_DATES
        paths = sims
        ly = dm.actuals(keys, dm.N_HIST - 364, dm.N_HIST - 364 + dm.HORIZON)
        hover_x = "%{x|%a %b %-d}"
        shape = "linear"
    q = np.percentile(paths, [2.5, 10, 50, 90, 97.5], axis=0)

    fig = go.Figure()
    # Promotion weeks for the selected department
    if dept != ALL:
        for w in promo_weeks.get(dept, planned_weeks(dept)):
            x0 = dm.WEEK_STARTS[w]
            fig.add_vrect(x0=x0, x1=x0 + dt.timedelta(days=7), fillcolor=PROMO, line_width=0, layer="below")
            fig.add_annotation(x=x0 + dt.timedelta(days=3.5), y=1, yref="paper", yanchor="bottom",
                               text="Circular", showarrow=False, font={"size": 10, "color": PROMO_INK})
    for label, day in [("Thanksgiving", dm.CLOSED_DATES[0]), ("Christmas", dm.CLOSED_DATES[1])]:
        fig.add_shape(type="line", x0=day, x1=day, y0=0, y1=1, yref="paper",
                      line={"color": AXIS, "width": 1, "dash": "dot"}, layer="below")
        fig.add_annotation(x=day, y=0, yref="paper", yanchor="bottom", xanchor="right", textangle=-90,
                           text=label, showarrow=False, font={"size": 10, "color": MUTED})
    edge = dm.FORECAST_DATES[0] - dt.timedelta(days=0.5 if view == "day" else 3.5)
    fig.add_shape(type="line", x0=edge, x1=edge, y0=0, y1=1, yref="paper", line={"color": INK_2, "width": 1})
    fig.add_annotation(x=edge, y=1, yref="paper", yanchor="bottom", xanchor="right", text="Actuals",
                       showarrow=False, font={"size": 10, "color": MUTED}, xshift=-4)
    fig.add_annotation(x=edge, y=1, yref="paper", yanchor="bottom", xanchor="left", text="Forecast",
                       showarrow=False, font={"size": 10, "color": MUTED}, xshift=4)

    fig.add_trace(go.Scatter(x=list(x_fc) + list(x_fc)[::-1], y=list(q[4]) + list(q[0])[::-1], fill="toself",
                             fillcolor=BAND_95, line={"width": 0}, name="95% range", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=list(x_fc) + list(x_fc)[::-1], y=list(q[3]) + list(q[1])[::-1], fill="toself",
                             fillcolor=BAND_80, line={"width": 0}, name="80% range", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x_fc, y=ly, name="Last year", mode="lines",
                             line={"color": LAST_YEAR, "width": 1.5, "dash": "dot", "shape": shape},
                             hovertemplate=hover_x + "<br>Last year: %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=x_hist, y=y_hist, name="Actual", mode="lines",
                             line={"color": INK, "width": 2, "shape": shape},
                             hovertemplate=hover_x + "<br>Actual: %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=x_fc, y=q[2], name="Forecast", mode="lines+markers" if view == "week" else "lines",
        line={"color": FORECAST, "width": 2, "shape": shape}, marker={"size": 6},
        customdata=np.stack([q[1], q[3]], axis=1),
        hovertemplate=hover_x + "<br>Forecast: %{y:,.0f}<br>80% range: %{customdata[0]:,.0f} – "
                                "%{customdata[1]:,.0f}<extra></extra>"))
    fig.update_layout(margin={"l": 8, "r": 8, "t": 40, "b": 8}, hovermode="x unified")
    fig.update_yaxes(rangemode="tozero", tickformat="~s", title=None)
    fig.update_xaxes(showspikes=True, spikecolor=AXIS, spikethickness=1, spikedash="solid")
    return style_axes(fig, 400)


def bridge_figure(start, steps, end):
    labels = ["Last year"] + [s[0] for s in steps] + ["Forecast"]
    values = [start] + [s[1] for s in steps] + [end]
    measure = ["absolute"] + ["relative"] * len(steps) + ["total"]
    text = [fmt_units(start)] + [("+" if v >= 0 else "−") + fmt_units(abs(v)) for _, v in steps] + [fmt_units(end)]
    fig = go.Figure(go.Waterfall(
        y=labels, x=values, measure=measure, orientation="h", text=text, textposition="outside",
        textfont={"color": INK_2, "size": 11, "family": FONT}, cliponaxis=False,
        increasing={"marker": {"color": UP}}, decreasing={"marker": {"color": DOWN}},
        totals={"marker": {"color": "#6f6e69"}}, connector={"line": {"color": AXIS, "width": 1}},
        hovertemplate="%{y}: %{text}<extra></extra>"))
    lo = min(start, end) * 0.9
    hi = max(start, end, start + max(np.cumsum([v for _, v in steps]).max(), 0)) * 1.04
    fig.update_xaxes(range=[lo, hi], tickformat="~s", showgrid=True)
    fig.update_yaxes(autorange="reversed", showgrid=False, ticklabelstandoff=6)
    fig.update_layout(margin={"l": 8, "r": 48, "t": 8, "b": 8}, showlegend=False)
    return style_axes(fig, 300)


def backtest_figure(keys, sims):
    paths = weekly(sims)
    actual = weekly(dm.actuals(keys, dm.N_HIST - dm.HORIZON))
    q = np.percentile(paths, [10, 50, 90], axis=0)
    x = dm.DATES[dm.N_HIST - dm.HORIZON:dm.N_HIST:7]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(x) + list(x)[::-1], y=list(q[2]) + list(q[0])[::-1], fill="toself",
                             fillcolor=BAND_80, line={"width": 0}, name="80% range", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=q[1], name="Forecast", mode="lines", line={"color": FORECAST, "width": 2},
                             hovertemplate="Week of %{x|%b %-d}<br>Forecast: %{y:,.0f}<extra></extra>"))
    inside = (actual >= q[0]) & (actual <= q[2])
    fig.add_trace(go.Scatter(
        x=x, y=actual, name="Actual", mode="lines+markers", line={"color": INK, "width": 2},
        marker={"size": 8, "color": [SURFACE if i else INK for i in inside], "line": {"color": INK, "width": 2}},
        customdata=np.where(inside, "inside the 80% range", "outside the 80% range"),
        hovertemplate="Week of %{x|%b %-d}<br>Actual: %{y:,.0f} (%{customdata})<extra></extra>"))
    fig.update_yaxes(tickformat="~s", rangemode="tozero")
    fig.update_layout(margin={"l": 8, "r": 8, "t": 36, "b": 8}, hovermode="x unified")
    stats = {
        "wape": np.abs(q[1] - actual).sum() / actual.sum(),
        "bias": (q[1] - actual).sum() / actual.sum(),
        "coverage": inside.mean(),
    }
    return style_axes(fig, 260), stats


def growth_table(dept, promo_weeks, temp_shift):
    """Expected growth vs the same 12 weeks last year, per store x department (and in total)."""
    fc = {k: dm.expected(m, promo_weeks.get(k[1]), temp_shift).sum() for k, m in dm.MODELS.items()}
    ly = {k: dm.UNITS[k][dm.N_HIST - 364:dm.N_HIST - 364 + dm.HORIZON].sum() for k in dm.KEYS}
    cols = dm.DEPARTMENTS + [ALL]
    g = np.zeros((len(dm.STORES), len(cols)))
    vol = np.zeros(len(dm.STORES))
    for i, s in enumerate(dm.STORES):
        for j, d in enumerate(cols):
            ks = keys_for(s.id, d)
            g[i, j] = sum(fc[k] for k in ks) / sum(ly[k] for k in ks) - 1
        vol[i] = sum(fc[k] for k in keys_for(s.id, dept))
    return g, cols, vol


def heatmap_figure(g, cols, store, dept):
    names = [s.name for s in dm.STORES]
    labels = dm.DEPARTMENTS + ["All"]
    text = [[fmt_pct(v) for v in row] for row in g]
    fig = go.Figure(go.Heatmap(
        z=g, x=labels, y=names, text=text, texttemplate="%{text}", textfont={"size": 11, "family": FONT},
        colorscale=DIVERGING, zmin=-GROWTH_CAP, zmax=GROWTH_CAP, xgap=2, ygap=2, showscale=False,
        hovertemplate="%{y} · %{x}<br>%{text} vs last year<extra></extra>"))
    if store != ALL:
        i = [s.id for s in dm.STORES].index(store)
        j = len(cols) - 1 if dept == ALL else cols.index(dept)
        fig.add_shape(type="rect", x0=j - 0.5, x1=j + 0.5, y0=i - 0.5, y1=i + 0.5, line={"color": INK, "width": 2})
    fig.update_xaxes(side="top", showgrid=False, linecolor=SURFACE, tickfont={"color": INK_2, "size": 12})
    fig.update_yaxes(autorange="reversed", showgrid=False, linecolor=SURFACE, tickfont={"color": INK_2, "size": 12},
                     ticklabelstandoff=6)
    fig.update_layout(margin={"l": 8, "r": 8, "t": 8, "b": 8})
    fig = style_axes(fig, 560)
    fig.update_layout(plot_bgcolor=SURFACE)
    return fig


def fit_map(width=480, height=560, pad=0.1):
    """Center and zoom that fit every store in a map of about width x height pixels."""
    lats = np.array([s.lat for s in dm.STORES])
    lons = np.array([s.lon for s in dm.STORES])
    y = np.log(np.tan(np.pi / 4 + np.radians(lats) / 2))  # Web Mercator
    x_span = (lons.max() - lons.min()) / 360
    y_span = (y.max() - y.min()) / (2 * np.pi)
    zoom = np.log2(min(width / x_span, height / y_span) * (1 - 2 * pad) / 512)
    center_lat = np.degrees(2 * np.arctan(np.exp((y.max() + y.min()) / 2)) - np.pi / 2)
    return {"center": {"lat": float(center_lat), "lon": float((lons.max() + lons.min()) / 2)}, "zoom": float(zoom)}


MAP_VIEW = fit_map()


def map_figure(g, vol, store, dept):
    j = -1 if dept == ALL else dm.DEPARTMENTS.index(dept)
    growth = g[:, j]
    ids = [s.id for s in dm.STORES]
    size = 12 + 22 * np.sqrt(vol / vol.max())
    fig = go.Figure()
    # Scattermap markers have no outline, so a slightly larger gray marker underneath
    # keeps near-zero (near-white) stores visible on the light basemap
    fig.add_trace(go.Scattermap(lat=[s.lat for s in dm.STORES], lon=[s.lon for s in dm.STORES], mode="markers",
                                marker={"size": size + 3, "color": MUTED, "opacity": 0.55},
                                hoverinfo="skip", showlegend=False))
    if store != ALL:
        i = ids.index(store)
        fig.add_trace(go.Scattermap(lat=[dm.STORES[i].lat], lon=[dm.STORES[i].lon], mode="markers",
                                    marker={"size": size[i] + 10, "color": INK, "opacity": 0.85},
                                    hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scattermap(
        lat=[s.lat for s in dm.STORES], lon=[s.lon for s in dm.STORES], mode="markers",
        marker={"size": size, "color": growth, "colorscale": DIVERGING, "cmin": -GROWTH_CAP, "cmax": GROWTH_CAP,
                "opacity": 1},
        customdata=np.stack([ids, [s.name for s in dm.STORES], [s.format for s in dm.STORES],
                             [fmt_pct(v) for v in growth], [fmt_units(v) for v in vol]], axis=1),
        hovertemplate="<b>%{customdata[1]}</b> · %{customdata[2]}<br>"
                      "Next 12 weeks: %{customdata[4]} units<br>%{customdata[3]} vs last year<extra></extra>",
        showlegend=False))
    fig.update_layout(
        map={"style": "carto-positron", **MAP_VIEW},
        margin={"l": 0, "r": 0, "t": 0, "b": 0}, height=560, paper_bgcolor=SURFACE,
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12, "family": FONT}},
        clickmode="event",
    )
    return fig


# ---------- layout pieces ----------

def card(title, body, hint=None, extra=None, **kwargs):
    head = dmc.Group([dmc.Stack([dmc.Text(title, className="card-title"),
                                 hint and dmc.Text(hint, className="card-hint")], gap=2),
                      extra], justify="space-between", align="flex-start", wrap="nowrap", mb="sm")
    return dmc.Paper([head, body], className="card", **kwargs)


def kpi(label, value, sub, icon):
    return dmc.Paper([
        dmc.Group([DashIconify(icon=icon, width=16, className="kpi-icon"), dmc.Text(label, className="kpi-label")],
                  gap=6, wrap="nowrap"),
        html.Div(value, className="kpi-value"),
        html.Div(sub, className="kpi-sub"),
    ], className="card kpi")


def delta(x, good_when_up=True, suffix=" vs last year"):
    up = x >= 0
    if round(x * 100, 1) == 0:
        cls, icon = "delta-flat", "tabler:minus"
    else:
        cls = "delta-up" if up == good_when_up else "delta-down"
        icon = "tabler:arrow-up-right" if up else "tabler:arrow-down-right"
    return html.Span([DashIconify(icon=icon, width=14), fmt_pct(x), html.Span(suffix, className="kpi-sub")],
                     className=f"delta {cls}")


def week_chips(dept):
    planned = set(planned_weeks(dept)) if dept != ALL else set()
    return [dmc.Chip(short(w), value=str(i), size="xs", radius="sm", disabled=dept == ALL,
                     className="week-chip" + (" planned" if i in planned else ""))
            for i, w in enumerate(dm.WEEK_STARTS)]


store_options = [{"value": ALL, "label": "All stores"}] + [
    {"group": r, "items": [{"value": s.id, "label": s.name} for s in dm.STORES if s.region == r]}
    for r in dm.REGIONS]

header = html.Header([
    dmc.Group([
        html.Div(DashIconify(icon="tabler:basket", width=22), className="brand-mark"),
        dmc.Stack([dmc.Text("Cascade Market", className="brand-name"),
                   dmc.Text("Store demand forecast", className="brand-sub")], gap=0),
    ], gap="sm", wrap="nowrap"),
    dmc.Group([
        dmc.Badge(f"Actuals through {dm.AS_OF.strftime('%a, %b %-d %Y')}", variant="light", color="gray",
                  leftSection=DashIconify(icon="tabler:database", width=12), className="header-badge"),
        dmc.Badge(f"Forecast {short(dm.FORECAST_DATES[0])} – {short(dm.FORECAST_DATES[-1])}", variant="light",
                  color="gray", leftSection=DashIconify(icon="tabler:calendar-stats", width=12),
                  className="header-badge"),
    ], gap="xs", visibleFrom="sm"),
], className="topbar")

filters = dmc.Paper(
    dmc.Group([
        dmc.Select(id="store", label="Store", data=store_options, value=ALL, searchable=True, allowDeselect=False,
                   leftSection=DashIconify(icon="tabler:building-store", width=16), w=260, comboboxProps={"shadow": "md"}),
        dmc.Stack([dmc.Text("Department", className="field-label"),
                   dmc.SegmentedControl(id="dept", value=ALL, data=[{"value": ALL, "label": "All"}] + [
                       {"value": d, "label": d} for d in dm.DEPARTMENTS], className="dept-control")], gap=4,
                  className="dept-field"),
        dmc.Stack([dmc.Text("Show", className="field-label"),
                   dmc.SegmentedControl(id="view", value="week", data=[{"value": "week", "label": "Weekly"},
                                                                       {"value": "day", "label": "Daily"}])], gap=4),
    ], gap="lg", align="flex-end"),
    className="card filters",
)

scenario = card(
    "Scenario",
    dmc.Stack([
        dmc.Stack([
            dmc.Text("Weather outlook", className="field-label"),
            dmc.SegmentedControl(id="temp", value="normal", fullWidth=True, data=[
                {"value": "cold", "label": "Colder −3°C"}, {"value": "normal", "label": "Normal"},
                {"value": "warm", "label": "Warmer +3°C"}]),
            dmc.Text("Beverages and frozen sell more in warm weeks.", className="field-help"),
        ], gap=4),
        dmc.Stack([
            dmc.Text("Circular weeks", className="field-label"),
            dmc.ChipGroup(dmc.Group(week_chips(ALL), gap=6, id="chip-row"), id="weeks", multiple=True, value=[]),
            dmc.Text(CHIP_HELP_ALL, id="chip-help", className="field-help"),
        ], gap=6),
        dmc.Stack([
            dmc.Group([dmc.Text("Service level", className="field-label"),
                       dmc.Text("95%", id="service-label", className="field-value")], justify="space-between"),
            dmc.Slider(id="service", min=80, max=99, step=1, value=95, label=None, color="indigo",
                       marks=[{"value": v, "label": f"{v}%"} for v in (80, 90, 99)]),
            dmc.Text("Share of weeks the order should cover demand. Sets the order plan below.",
                     className="field-help", mt="md"),
        ], gap=4),
        dmc.Button("Reset scenario", id="reset", variant="subtle", color="gray", size="xs",
                   leftSection=DashIconify(icon="tabler:refresh", width=14), w="fit-content"),
    ], gap="lg"),
    hint="Change the plan and watch the forecast move.",
)

graph_config = {"displayModeBar": False}

def build_layout():
    """The layout with the default view already drawn, so the charts arrive with the page."""
    (kpis, forecast_fig, forecast_sub, bridge_fig, backtest_fig, backtest_stats, orders,
     service_label) = update_forecast(ALL, ALL, "week", "normal", [], 95)
    map_fig, grid_fig = update_network(ALL, ALL, "normal", [])
    return dmc.MantineProvider(
        theme=THEME, forceColorScheme="light",
        children=html.Div([
            header,
            html.Main([
                filters,
                html.Div(kpis, id="kpis", className="kpi-row"),
                dmc.Grid([
                    dmc.GridCol(card("Demand forecast", dcc.Graph(id="forecast", figure=forecast_fig, config=graph_config),
                                     hint=None, extra=dmc.Text(forecast_sub, id="forecast-sub", className="card-hint")),
                                span={"base": 12, "lg": 8}),
                    dmc.GridCol(scenario, span={"base": 12, "lg": 4}),
                    dmc.GridCol(card("What changed since last year",
                                     dcc.Graph(id="bridge", figure=bridge_fig, config=graph_config),
                                     hint="Expected units in the next 12 weeks vs the same weeks last year, "
                                          "one driver at a time."),
                                span={"base": 12, "md": 6}),
                    dmc.GridCol(card("How the last forecast did",
                                     html.Div([html.Div(backtest_stats, id="backtest-stats", className="stat-row"),
                                               dcc.Graph(id="backtest", figure=backtest_fig, config=graph_config)]),
                                     hint=f"Forecast made {short(dm.DATES[dm.N_HIST - dm.HORIZON])} for the 12 weeks "
                                          f"that have since closed. Hollow dots fell inside the 80% range."),
                                span={"base": 12, "md": 6}),
                    dmc.GridCol(card("Store network", dcc.Graph(id="map", figure=map_fig, config={**graph_config, "scrollZoom": False}),
                                     hint="Growth vs last year over the next 12 weeks. Size shows volume. "
                                          "Click a store to open it."),
                                span={"base": 12, "md": 5}),
                    dmc.GridCol(card("Growth by store and department", dcc.Graph(id="grid", figure=grid_fig, config=graph_config),
                                     hint="Next 12 weeks vs the same weeks last year. Click a cell to open it.",
                                     extra=html.Div([html.Span(fmt_pct(-GROWTH_CAP, 0)), html.Div(className="scale-bar"),
                                                     html.Span(fmt_pct(GROWTH_CAP, 0))], className="scale")),
                                span={"base": 12, "md": 7}),
                    dmc.GridCol(card("Weekly order plan", html.Div(orders, id="orders", className="table-wrap"),
                                     hint="Units to have on hand each week. The buffer covers forecast uncertainty "
                                          "at the chosen service level."),
                                span=12),
                ], gutter="md"),
                html.Footer("Synthetic data. Cascade Market and its stores are made up.", className="footer"),
            ], className="main"),
        ]),
    )


# ---------- callbacks ----------

@app.callback(
    Output("store", "value"),
    Output("dept", "value"),
    Input("map", "clickData"),
    Input("grid", "clickData"),
    State("dept", "value"),
    prevent_initial_call=True,
)
def open_from_charts(map_click, grid_click, dept):
    if ctx.triggered_id == "map" and map_click:
        point = map_click["points"][0]
        if "customdata" not in point:
            return dash.no_update, dash.no_update
        return point["customdata"][0], dept
    if ctx.triggered_id == "grid" and grid_click:
        point = grid_click["points"][0]
        store = next(s.id for s in dm.STORES if s.name == point["y"])
        return store, ALL if point["x"] == "All" else point["x"]
    return dash.no_update, dash.no_update


@app.callback(
    Output("weeks", "value"),
    Output("chip-row", "children"),
    Output("chip-help", "children"),
    Output("temp", "value"),
    Output("service", "value"),
    Input("dept", "value"),
    Input("reset", "n_clicks"),
    State("temp", "value"),
    State("service", "value"),
    prevent_initial_call=True,
)
def reset_scenario(dept, _, temp, service):
    if ctx.triggered_id == "reset":
        temp, service = "normal", 95
    if dept == ALL:
        return [], week_chips(ALL), CHIP_HELP_ALL, temp, service
    help_text = f"Checked weeks put {dept} on the chain-wide circular. Outlined weeks are the current plan."
    return [str(w) for w in planned_weeks(dept)], week_chips(dept), help_text, temp, service


@app.callback(
    Output("kpis", "children"),
    Output("forecast", "figure"),
    Output("forecast-sub", "children"),
    Output("bridge", "figure"),
    Output("backtest", "figure"),
    Output("backtest-stats", "children"),
    Output("orders", "children"),
    Output("service-label", "children"),
    Input("store", "value"),
    Input("dept", "value"),
    Input("view", "value"),
    Input("temp", "value"),
    Input("weeks", "value"),
    Input("service", "value"),
    prevent_initial_call=True,
)
def update_forecast(store, dept, view, temp, weeks, service):
    keys = keys_for(store, dept)
    promo_weeks = promo_override(dept, weeks)
    shift = TEMP_OUTLOOK[temp]
    models = [dm.MODELS[k] for k in keys]
    sims = forecast_paths(store, dept, temp, tuple(sorted(weeks or [])))
    weekly_paths = weekly(sims)
    totals = weekly_paths.sum(axis=1)
    ly_daily = dm.actuals(keys, dm.N_HIST - 364, dm.N_HIST - 364 + dm.HORIZON)
    ly_weekly = weekly(ly_daily)
    p10, p50, p90 = np.percentile(totals, [10, 50, 90])
    growth = p50 / ly_daily.sum() - 1
    wq = np.percentile(weekly_paths, [10, 50, 90, service], axis=0)
    peak = int(np.argmax(wq[1]))

    bt_fig, bt = backtest_figure(keys, backtest_paths(store, dept))

    kpis = [
        kpi("Next 12 weeks", fmt_units(p50) + " units", f"80% range {fmt_units(p10)} – {fmt_units(p90)}",
            "tabler:chart-line"),
        kpi("Vs same weeks last year", delta(growth, suffix=""), f"Last year {fmt_units(ly_daily.sum())} units",
            "tabler:calendar-repeat"),
        kpi("Busiest week", f"Week of {short(dm.WEEK_STARTS[peak])}",
            f"{fmt_units(wq[1][peak])} units, {fmt_pct(wq[1][peak] / wq[1].mean() - 1, 0)} vs an average week",
            "tabler:flame"),
        kpi("Last forecast's error", f"{bt['wape'] * 100:.1f}%",
            f"Weekly WAPE · bias {fmt_pct(bt['bias'])}", "tabler:target-arrow"),
    ]

    start, steps, end = dm.bridge(models, promo_weeks, shift)

    stats = [
        html.Div([html.Div("Weekly error (WAPE)", className="stat-label"),
                  html.Div(f"{bt['wape'] * 100:.1f}%", className="stat-value")], className="stat"),
        html.Div([html.Div("Bias", className="stat-label"),
                  html.Div(fmt_pct(bt["bias"]), className="stat-value"),
                  html.Div("over-forecast" if bt["bias"] > 0 else "under-forecast", className="stat-sub")],
                 className="stat"),
        html.Div([html.Div("Weeks inside 80% range", className="stat-label"),
                  html.Div(f"{round(bt['coverage'] * dm.WEEKS)} of {dm.WEEKS}", className="stat-value")],
                 className="stat"),
    ]

    planned = set(promo_weeks.get(dept, planned_weeks(dept) if dept != ALL else []))
    rows = []
    for i, w in enumerate(dm.WEEK_STARTS):
        order = wq[3][i]
        holiday = next((n for n, d in [("Thanksgiving", dm.CLOSED_DATES[0]), ("Christmas", dm.CLOSED_DATES[1])]
                        if w <= d < w + dt.timedelta(days=7)), None)
        notes = [dmc.Badge("Circular", size="xs", variant="light", color="yellow", radius="sm")] if i in planned else []
        if holiday:
            notes.append(dmc.Badge(holiday, size="xs", variant="light", color="gray", radius="sm"))
        rows.append(html.Tr([
            html.Td(f"{short(w)} – {short(w + dt.timedelta(days=6))}", className="week-col"),
            html.Td(dmc.Group(notes, gap=4) if notes else None),
            html.Td(f"{ly_weekly[i]:,.0f}", className="num"),
            html.Td(f"{wq[1][i]:,.0f}", className="num strong"),
            html.Td(f"{wq[0][i]:,.0f} – {wq[2][i]:,.0f}", className="num muted"),
            html.Td(f"{order - wq[1][i]:,.0f}", className="num muted"),
            html.Td(f"{order:,.0f}", className="num strong order"),
        ]))
    table = html.Table([
        html.Thead(html.Tr([html.Th("Week"), html.Th(""), html.Th("Last year", className="num"),
                            html.Th("Forecast", className="num"), html.Th("80% range", className="num"),
                            html.Th("Buffer", className="num"), html.Th(f"Order at {service}%", className="num")])),
        html.Tbody(rows),
        html.Tfoot(html.Tr([html.Td("12 weeks"), html.Td(), html.Td(f"{ly_weekly.sum():,.0f}", className="num"),
                            html.Td(f"{wq[1].sum():,.0f}", className="num strong"), html.Td(), html.Td(),
                            html.Td(f"{wq[3].sum():,.0f}", className="num strong order")])),
    ], className="orders-table")

    sub = selection_label(store, dept) + (" · units per week" if view == "week" else " · units per day")
    return (kpis, forecast_figure(store, dept, view, sims, promo_weeks), sub, bridge_figure(start, steps, end),
            bt_fig, stats, table, f"{service}%")


@app.callback(
    Output("map", "figure"),
    Output("grid", "figure"),
    Input("store", "value"),
    Input("dept", "value"),
    Input("temp", "value"),
    Input("weeks", "value"),
    prevent_initial_call=True,
)
def update_network(store, dept, temp, weeks):
    g, cols, vol = growth_table(dept, promo_override(dept, weeks), TEMP_OUTLOOK[temp])
    return map_figure(g, vol, store, dept), heatmap_figure(g, cols, store, dept)


app.layout = build_layout()

if __name__ == "__main__":
    app.run(debug=True, port=8082)
