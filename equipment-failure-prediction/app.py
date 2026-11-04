"""
Equipment Failure Prediction

Predicts which of the 36 pumps, compressors, fans, blowers and drive motors at a
made-up fertilizer plant are likely to break down in the next 7, 14 or 30 days,
from hourly vibration, bearing temperature, motor current and outlet pressure.

Fleet risk: a floor plan of the plant colored by risk, a ranked watchlist and,
for any asset, its sensor traces against the healthy baseline, what is driving
the prediction, the failure mode the signals look like and what to do about it.

Model & alert threshold: how the model did on four held-out months, and the
trade-off between catching failures early and sending crews to false alarms,
priced with your own breakdown, repair and inspection costs.

The sensor data and failures are synthetic, see plant.py.
"""

from datetime import timedelta
from functools import lru_cache

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from dash_iconify import DashIconify
from plotly.subplots import make_subplots

import plant as pl

# Chart colors, kept in sync with assets/style.css
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e9e8e2"
AXIS = "#c3c2b7"
SENSOR_COLOR = {"vib": "#2a78d6", "temp": "#eb6834", "current": "#1baf7a", "pressure": "#6250d6"}
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
DOWN_COLOR = "#52514e"
LEVELS = {
    "Alert": ("critical", "tabler:alert-triangle"),
    "Watch": ("warning", "tabler:eye"),
    "Healthy": ("good", "tabler:circle-check"),
    "Down for repair": (None, "tabler:tool"),
}

FONT = "'Schibsted Grotesk', system-ui, sans-serif"
MONO = "'Azeret Mono', ui-monospace, monospace"
THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": FONT},
    "primaryColor": "orange",
    "defaultRadius": "sm",
}

app = dash.Dash(
    __name__,
    title="Equipment Failure Prediction",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700;800&family=Azeret+Mono:wght@400;500;600&display=swap"
    ],
)
server = app.server

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
DEFAULT_COSTS = (180, 45, 8)  # unplanned breakdown, planned repair, inspection, $k
THRESHOLDS = np.round(np.arange(0.05, 0.951, 0.025), 3)


# ---------------------------------------------------------------- helpers

def fmt_money(k):
    """Format thousands of dollars."""
    sign = "−" if k < 0 else ""
    k = abs(k)
    return f"{sign}${k / 1000:.2f}M" if k >= 1000 else f"{sign}${k:,.0f}k"


def level(p, threshold, down):
    if down:
        return "Down for repair"
    if p >= threshold:
        return "Alert"
    if p >= threshold / 2:
        return "Watch"
    return "Healthy"


def level_color(name):
    key = LEVELS[name][0]
    return STATUS[key] if key else DOWN_COLOR


def base_layout(**kw):
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK_2, size=12),
        margin=dict(l=8, r=8, t=8, b=8),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=AXIS, font=dict(family=FONT, color=INK, size=12)),
        showlegend=False,
    )
    layout.update(kw)
    return layout


def axis(**kw):
    a = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED, size=11),
             title_font=dict(color=MUTED, size=11), ticks="", showline=True)
    a.update(kw)
    return a


@lru_cache(maxsize=512)
def evaluation(h, threshold):
    return pl.evaluate(h, threshold)


def savings(h, threshold, costs):
    unplanned, planned, inspect = costs
    events, false_alarms, alarms = evaluation(h, threshold)
    caught = sum(e["lead"] is not None for e in events)
    per_window = caught * (unplanned - planned) - alarms * inspect
    return per_window * 365 / (pl.DAYS - pl.TRAIN_DAYS)


def best_threshold(h, costs):
    vals = [savings(h, t, costs) for t in THRESHOLDS]
    return float(THRESHOLDS[int(np.argmax(vals))])


def costs_of(unplanned, planned, inspect):
    return (unplanned or 0, planned or 0, inspect or 0)


# Snapshot of every asset at each horizon, built once
SNAP = {}
for _h in pl.HORIZONS:
    risk, day = pl.current_risk(_h)
    SNAP[_h] = dict(risk=risk, day=day)
MODE_NOW = []
for _a in pl.ASSETS:
    d = SNAP[14]["day"][_a.i]
    MODE_NOW.append(pl.likely_mode(_a.i, d))


def stat_tile(label, value, sub=None, icon=None, tone=None):
    return html.Div(
        [
            html.Div([DashIconify(icon=icon, width=15) if icon else None, html.Span(label)], className="tile-label"),
            html.Div(value, className="tile-value"),
            html.Div(sub, className="tile-sub") if sub else None,
        ],
        className="tile" + (f" tile-{tone}" if tone else ""),
    )


def card(children, title=None, sub=None, className=""):
    head = None
    if title:
        head = html.Div([html.H3(title, className="card-title"), html.Div(sub, className="card-sub") if sub else None],
                        className="card-head")
    return html.Section([head, *children] if head else children, className=f"card {className}")


# ---------------------------------------------------------------- layout

header = html.Header(
    [
        html.Div(
            [
                html.Div(DashIconify(icon="tabler:settings-cog", width=22), className="brand-mark"),
                html.Div(
                    [
                        html.Div("Equipment Failure Prediction", className="brand-name"),
                        html.Div("Calder Bay Nitrogen Works · 36 rotating assets · 4 sensors each", className="brand-sub"),
                    ]
                ),
            ],
            className="brand",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Span("Predict failures within", className="ctl-label"),
                        dmc.SegmentedControl(
                            id="horizon",
                            value="14",
                            data=[{"label": f"{h} days", "value": str(h)} for h in pl.HORIZONS],
                            size="sm",
                            className="horizon",
                        ),
                    ],
                    className="ctl",
                ),
                html.Div(
                    [
                        html.Span(className="live-dot"),
                        html.Span(f"Sensor data to {pl.AS_OF:%b %-d, %Y %H:%M}"),
                    ],
                    className="as-of",
                ),
            ],
            className="header-right",
        ),
    ],
    className="header",
)

fleet_tab = html.Div(
    [
        html.Div(id="fleet-kpis", className="tiles"),
        html.Div(
            [
                card(
                    [
                        dcc.Graph(id="floor-map", config=GRAPH_CONFIG, className="floor-graph", style={"height": "470px"}),
                        html.Div(
                            [
                                html.Span([html.Span(className="key-swatch", style={"background": level_color(n)}),
                                           DashIconify(icon=LEVELS[n][1], width=13), n], className="key")
                                for n in LEVELS
                            ],
                            className="keys",
                        ),
                    ],
                    title="Plant floor",
                    sub="Click an asset to inspect it",
                    className="floor-card",
                ),
                card([html.Div(id="watchlist", className="watchlist")], title="Watchlist",
                     sub="Highest chance of failure first", className="watch-card"),
            ],
            className="row row-floor",
        ),
        html.Div(id="asset-head", className="asset-head"),
        html.Div(
            [
                card([dcc.Graph(id="sensor-chart", config=GRAPH_CONFIG, className="sensor-graph", style={"height": "520px"})],
                     title="Sensors, last 45 days",
                     sub="Hourly readings against what a healthy unit reads at the same load and ambient",
                     className="sensor-card"),
                html.Div(
                    [
                        card([html.Div(id="outlook")], title="Failure outlook", className="outlook-card"),
                        card([dcc.Graph(id="driver-chart", config=GRAPH_CONFIG, className="driver-graph", style={"height": "230px"})],
                             title="What is driving the prediction",
                             sub="Push on the odds of failure, today vs a typical day"),
                    ],
                    className="stack",
                ),
            ],
            className="row row-asset",
        ),
        card([dcc.Graph(id="risk-history", config=GRAPH_CONFIG, className="history-graph", style={"height": "240px"})],
             title="Predicted risk over the past year", sub=None, className="history-card"),
    ],
    className="tab-body",
)

model_tab = html.Div(
    [
        card(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div([html.Span("Alert when the chance of failure reaches"),
                                          html.Span(id="threshold-label", className="thr-value")], className="thr-head"),
                                dmc.Slider(id="threshold", min=0.05, max=0.95, step=0.025, value=0.5,
                                           marks=[{"value": v, "label": f"{v:.0%}"} for v in (0.1, 0.3, 0.5, 0.7, 0.9)],
                                           label=None, color="orange", size="md"),
                            ],
                            className="thr",
                        ),
                        html.Div(
                            [
                                dmc.NumberInput(id="cost-unplanned", label="Unplanned breakdown", value=DEFAULT_COSTS[0],
                                                prefix="$", suffix="k", min=0, step=10, size="sm"),
                                dmc.NumberInput(id="cost-planned", label="Planned repair instead", value=DEFAULT_COSTS[1],
                                                prefix="$", suffix="k", min=0, step=5, size="sm"),
                                dmc.NumberInput(id="cost-inspect", label="Crew check per alert", value=DEFAULT_COSTS[2],
                                                prefix="$", suffix="k", min=0, step=1, size="sm"),
                                dmc.Button("Use best threshold", id="best-btn", variant="filled", color="dark", size="sm",
                                           leftSection=DashIconify(icon="tabler:target-arrow", width=16)),
                            ],
                            className="costs",
                        ),
                    ],
                    className="controls",
                ),
            ],
            className="controls-card",
        ),
        html.Div(id="model-kpis", className="tiles"),
        html.Div(
            [
                card([dcc.Graph(id="savings-chart", config=GRAPH_CONFIG, className="half-graph", style={"height": "290px"})],
                     title="Net savings vs running to failure", sub="Per year, at each alert threshold"),
                card([dcc.Graph(id="tradeoff-chart", config=GRAPH_CONFIG, className="half-graph", style={"height": "290px"})],
                     title="Catching failures vs false alarms", sub="Each dot is one threshold"),
            ],
            className="row row-half",
        ),
        html.Div(
            [
                card([dcc.Graph(id="lead-chart", config=GRAPH_CONFIG, className="lead-graph", style={"height": "420px"})],
                     title="Warning before each held-out failure",
                     sub="Days between the first alert and the breakdown"),
                card([dcc.Graph(id="weights-chart", config=GRAPH_CONFIG, className="lead-graph", style={"height": "420px"})],
                     title="What the model learned", sub="Change in log-odds of failure for one standard deviation"),
            ],
            className="row row-half",
        ),
        html.Div(id="model-note", className="note"),
    ],
    className="tab-body",
)

app.layout = dmc.MantineProvider(
    html.Div(
        [
            header,
            dcc.Store(id="selected", data=pl.ASSETS[int(np.nanargmax(SNAP[14]["risk"]))].tag),
            dmc.Tabs(
                [
                    dmc.TabsList(
                        [
                            dmc.TabsTab("Fleet risk", value="fleet", leftSection=DashIconify(icon="tabler:building-factory-2", width=16)),
                            dmc.TabsTab("Model & alert threshold", value="model", leftSection=DashIconify(icon="tabler:adjustments-alt", width=16)),
                        ],
                        className="tabs-list",
                    ),
                    dmc.TabsPanel(fleet_tab, value="fleet"),
                    dmc.TabsPanel(model_tab, value="model"),
                ],
                value="fleet",
                variant="default",
                color="orange",
                keepMounted=True,
                className="tabs",
            ),
        ],
        className="page",
    ),
    theme=THEME,
)


# ---------------------------------------------------------------- fleet tab

def floor_figure(h, threshold, selected):
    risk = SNAP[h]["risk"]
    fig = go.Figure()
    for area, (x0, y0, x1, y1) in pl.AREAS.items():
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=AXIS, width=1),
                      fillcolor="rgba(137,135,129,0.06)", layer="below")
        fig.add_annotation(x=x0 + 1.2, y=y1 - 1.5, text=area.upper(), showarrow=False, xanchor="left", yanchor="top",
                           font=dict(size=10, color=MUTED, family=MONO))
    names = [level(risk[a.i], threshold, pl.is_down(a.i)) for a in pl.ASSETS]
    for n in LEVELS:
        idx = [a.i for a in pl.ASSETS if names[a.i] == n]
        if not idx:
            continue
        fig.add_trace(go.Scatter(
            x=[pl.ASSETS[i].x for i in idx], y=[pl.ASSETS[i].y for i in idx],
            mode="markers+text", text=[pl.ASSETS[i].tag for i in idx], textposition="bottom center",
            textfont=dict(family=MONO, size=10, color=INK_2),
            marker=dict(symbol="square" if n != "Down for repair" else "square-x-open", size=22, color=level_color(n),
                        line=dict(color=SURFACE if n != "Down for repair" else DOWN_COLOR, width=2)),
            customdata=[[pl.ASSETS[i].tag, pl.ASSETS[i].name, pl.ASSETS[i].kind, risk[i], n] for i in idx],
            hovertemplate="<b>%{customdata[0]}</b> %{customdata[1]}<br>%{customdata[2]}<br>"
                          f"Chance of failure in {h} days: " + "<b>%{customdata[3]:.0%}</b><br>%{customdata[4]}<extra></extra>",
            name=n,
        ))
    a = pl.BY_TAG.get(selected)
    if a:
        fig.add_trace(go.Scatter(x=[a.x], y=[a.y], mode="markers", hoverinfo="skip",
                                 marker=dict(symbol="square-open", size=31, color=INK, line=dict(width=2.5))))
    fig.update_layout(base_layout(margin=dict(l=4, r=4, t=4, b=4), dragmode=False, clickmode="event"))
    fig.update_xaxes(visible=False, range=[-1, 101], fixedrange=True)
    fig.update_yaxes(visible=False, range=[-2, 61], fixedrange=True)
    return fig


@app.callback(
    Output("fleet-kpis", "children"),
    Output("floor-map", "figure"),
    Output("watchlist", "children"),
    Input("horizon", "value"),
    Input("threshold", "value"),
    Input("selected", "data"),
    Input("cost-unplanned", "value"),
)
def update_fleet(h, threshold, selected, unplanned):
    h = int(h)
    risk = SNAP[h]["risk"]
    down = [a.i for a in pl.ASSETS if pl.is_down(a.i)]
    up = np.array([not pl.is_down(a.i) for a in pl.ASSETS])
    alerts = int(((risk >= threshold) & up).sum())
    watch = int(((risk >= threshold / 2) & (risk < threshold) & up).sum())
    expected = float(np.nansum(risk[up]))
    at_risk = expected * (unplanned or 0)
    events, false_alarms, _ = evaluation(h, threshold)
    caught = [e for e in events if e["lead"] is not None]
    kpis = [
        stat_tile("On alert", f"{alerts}", f"{watch} more on watch, {len(down)} down for repair",
                  "tabler:alert-triangle", "alert" if alerts else None),
        stat_tile(f"Expected breakdowns, next {h} days", f"{expected:.1f}", "Sum of each asset's chance of failure",
                  "tabler:chart-dots-3"),
        stat_tile("Breakdown cost at risk", fmt_money(at_risk), "Expected breakdowns × unplanned cost", "tabler:coin"),
        stat_tile("Held-out failures caught", f"{len(caught)} of {len(events)}",
                  f"Median {np.median([e['lead'] for e in caught]):.0f} days of warning" if caught else "No warnings",
                  "tabler:shield-check"),
    ]

    order = [i for i in np.argsort(-np.nan_to_num(risk, nan=-1)) if not pl.is_down(i)][:10]
    rows = []
    for i in order:
        a = pl.ASSETS[i]
        n = level(risk[i], threshold, False)
        mode, match, mag = MODE_NOW[i]
        rows.append(html.Button(
            [
                html.Span(a.tag, className="w-tag"),
                html.Span([html.Span(a.name, className="w-name"),
                           html.Span(f"Looks like {mode.lower()}" if mag > 2.5 and match > 0.6 else a.kind, className="w-mode")],
                          className="w-mid"),
                html.Span(html.Span(className="w-fill", style={"width": f"{risk[i] * 100:.0f}%", "background": level_color(n)}),
                          className="w-bar"),
                html.Span(f"{risk[i]:.0%}", className="w-pct"),
            ],
            id={"type": "watch", "tag": a.tag},
            className="w-row" + (" is-selected" if a.tag == selected else ""),
            n_clicks=0,
        ))
    for i in down:
        a = pl.ASSETS[i]
        rows.append(html.Button(
            [html.Span(a.tag, className="w-tag"),
             html.Span([html.Span(a.name, className="w-name"), html.Span("Down for repair", className="w-mode")], className="w-mid"),
             html.Span(DashIconify(icon="tabler:tool", width=16), className="w-down")],
            id={"type": "watch", "tag": a.tag}, className="w-row" + (" is-selected" if a.tag == selected else ""), n_clicks=0,
        ))
    return kpis, floor_figure(h, threshold, selected), rows


@app.callback(
    Output("selected", "data"),
    Input("floor-map", "clickData"),
    Input({"type": "watch", "tag": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_asset(click, _):
    trig = ctx.triggered_id
    if trig == "floor-map":
        if click and click["points"] and "customdata" in click["points"][0]:
            return click["points"][0]["customdata"][0]
        return no_update
    if isinstance(trig, dict) and ctx.triggered and ctx.triggered[0]["value"]:
        return trig["tag"]
    return no_update


def sensor_figure(a):
    sensors = [s for s in pl.SENSORS if not (s == "pressure" and pl.TYPES[a.kind]["pressure"] == 0)]
    hrs = 45 * 24
    sl = slice(pl.HOURS - hrs, pl.HOURS)
    t = pl.HOUR_TIMES[sl]
    L = pl.LOAD[a.i, sl]
    fig = make_subplots(rows=len(sensors), cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=[f"{pl.SENSOR_LABEL[s]} ({pl.SENSOR_UNIT[s]})" for s in sensors])
    for r, s in enumerate(sensors, start=1):
        y = pl.RAW[s][a.i, sl]
        base = pl.BASE[s][a.i]
        if s == "temp":
            exp = base + 0.35 * (pl.AMBIENT[sl] - 15) + 18 * L
        else:
            exp = base * pl.load_factor(s, L)
        exp = np.where(pl.RUNNING[a.i, sl], exp, np.nan)
        # Expected band: healthy baseline plus or minus three robust standard deviations of daily means
        band = 3 * pl.SCALE[s][a.i] * (1 if s == "temp" else pl.load_factor(s, L))
        fig.add_trace(go.Scatter(x=t, y=exp + band, mode="lines", line=dict(width=0), hoverinfo="skip"), row=r, col=1)
        fig.add_trace(go.Scatter(x=t, y=exp - band, mode="lines", line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(137,135,129,0.16)", hoverinfo="skip"), row=r, col=1)
        fig.add_trace(go.Scatter(x=t, y=exp, mode="lines", line=dict(color=MUTED, width=1, dash="dot"),
                                 name="Healthy at this load", hovertemplate="Healthy: %{y:.2f}<extra></extra>"), row=r, col=1)
        fig.add_trace(go.Scatter(x=t, y=y, mode="lines", line=dict(color=SENSOR_COLOR[s], width=1.4),
                                 name=pl.SENSOR_LABEL[s],
                                 hovertemplate=f"{pl.SENSOR_LABEL[s]}: " + "%{y:.2f} " + pl.SENSOR_UNIT[s] + "<extra></extra>"),
                      row=r, col=1)
        fig.update_yaxes(axis(), row=r, col=1)
    for f in a.failures:
        if pl.HOURS - hrs <= f.hour < pl.HOURS:
            ft = pl.START + timedelta(hours=f.hour)
            fig.add_vline(x=ft, line=dict(color=STATUS["critical"], width=1.5, dash="dash"))
            fig.add_annotation(x=ft, y=1.02, yref="paper", text=f"Breakdown: {f.mode.lower()}", showarrow=False,
                               xanchor="left", font=dict(size=11, color=INK_2))
    for ann in fig.layout.annotations[: len(sensors)]:
        ann.update(x=0, xanchor="left", font=dict(size=12, color=INK_2, family=FONT))
    fig.update_xaxes(axis(showgrid=False))
    fig.update_layout(base_layout(margin=dict(l=8, r=8, t=24, b=8), hovermode="x unified"))
    return fig


def driver_figure(h, a, d):
    m = pl.MODELS[h]
    c = m.contributions(a.i, d)
    order = np.argsort(-np.abs(c))[:6][::-1]
    labels = [pl.FEATURES[k][2] for k in order]
    colors = [SENSOR_COLOR.get(pl.FEATURES[k][1], MUTED) for k in order]
    fig = go.Figure(go.Bar(
        x=c[order], y=labels, orientation="h", marker=dict(color=colors, cornerradius=4, line=dict(width=0)),
        text=[f"{v:+.1f}" for v in c[order]], textposition="outside", textfont=dict(family=MONO, size=11, color=INK_2),
        cliponaxis=False,
        hovertemplate="%{y}: %{x:+.2f} log-odds<extra></extra>",
    ))
    lim = max(1.0, float(np.abs(c[order]).max()) * 1.3)
    fig.update_layout(base_layout(margin=dict(l=8, r=16, t=4, b=8), bargap=0.35))
    fig.update_xaxes(axis(range=[-lim, lim], zeroline=True, zerolinecolor=AXIS, title="← lowers risk     raises risk →"))
    fig.update_yaxes(axis(showgrid=False, showline=False, tickfont=dict(color=INK_2, size=12)))
    return fig


def history_figure(h, threshold, a):
    p = pl.MODELS[h].prob[a.i]
    dates = pl.DAY_DATES
    fig = go.Figure()
    fig.add_vrect(x0=dates[pl.TRAIN_DAYS], x1=dates[-1], fillcolor="rgba(137,135,129,0.08)", line_width=0, layer="below")
    fig.add_annotation(x=dates[pl.TRAIN_DAYS], y=1.0, yref="paper", text="Held out from training", showarrow=False,
                       xanchor="left", yanchor="top", xshift=6, font=dict(size=11, color=MUTED))
    fig.add_trace(go.Scatter(x=dates, y=p, mode="lines", line=dict(color=INK, width=2), name="Risk",
                             connectgaps=False, hovertemplate="%{x|%b %-d}: <b>%{y:.0%}</b><extra></extra>"))
    fig.add_hline(y=threshold, line=dict(color=STATUS["critical"], width=1, dash="dash"))
    fig.add_annotation(x=dates[0], y=threshold, text=f"Alert at {threshold:.0%}", showarrow=False, xanchor="left",
                       yanchor="bottom", font=dict(size=11, color=INK_2))
    fx = [pl.START + timedelta(hours=f.hour) for f in a.failures if f.hour < pl.HOURS]
    if fx:
        fig.add_trace(go.Scatter(
            x=fx, y=[1.04] * len(fx), mode="markers+text", text=["Breakdown"] * len(fx), textposition="top center",
            textfont=dict(size=10, color=INK_2), cliponaxis=False,
            marker=dict(symbol="x-thin", size=11, color=STATUS["critical"], line=dict(width=2.5, color=STATUS["critical"])),
            customdata=[f.mode for f in a.failures if f.hour < pl.HOURS],
            hovertemplate="%{x|%b %-d}: breakdown, %{customdata}<extra></extra>",
        ))
    fig.update_layout(base_layout(margin=dict(l=8, r=8, t=22, b=8), hovermode="closest"))
    fig.update_yaxes(axis(range=[0, 1.1], tickformat=".0%", tickvals=[0, 0.25, 0.5, 0.75, 1]))
    fig.update_xaxes(axis(showgrid=False))
    return fig


@app.callback(
    Output("asset-head", "children"),
    Output("sensor-chart", "figure"),
    Output("outlook", "children"),
    Output("driver-chart", "figure"),
    Output("risk-history", "figure"),
    Input("selected", "data"),
    Input("horizon", "value"),
    Input("threshold", "value"),
)
def update_asset(tag, h, threshold):
    h = int(h)
    a = pl.BY_TAG[tag]
    d = SNAP[h]["day"][a.i]
    risk = SNAP[h]["risk"][a.i]
    down = pl.is_down(a.i)
    n = level(risk, threshold, down)
    age = pl.X[a.i, d, -1]
    days_since = np.expm1(age) * 30
    ended = [f for f in a.failures if f.hour < pl.HOURS]

    head = html.Div(
        [
            html.Div([html.Span(a.tag, className="ah-tag"), html.H2(a.name, className="ah-name")], className="ah-title"),
            html.Div(
                [
                    html.Span(a.kind, className="chip"),
                    html.Span(a.area, className="chip"),
                    html.Span(f"{days_since:.0f} days since last repair", className="chip"),
                    html.Span(f"{len(ended)} breakdown{'s' if len(ended) != 1 else ''} in the past year", className="chip"),
                    html.Span([DashIconify(icon=LEVELS[n][1], width=14), n], className="badge",
                              style={"--badge": level_color(n)}),
                ],
                className="ah-chips",
            ),
        ]
    )

    probs = [SNAP[x]["risk"][a.i] for x in pl.HORIZONS]
    mode, match, mag = pl.likely_mode(a.i, d)
    signal = mag > 2.5 and match > 0.6
    outlook = html.Div(
        [
            html.Div(
                [
                    html.Div([html.Div(f"{x} days", className="ol-h"), html.Div(f"{p:.0%}", className="ol-p"),
                              html.Div(html.Div(style={"width": f"{p * 100:.0f}%"}, className="ol-fill"), className="ol-bar")],
                             className="ol-cell" + (" is-active" if x == h else ""))
                    for x, p in zip(pl.HORIZONS, probs)
                ],
                className="ol-grid",
            ),
            html.Div(
                [
                    html.Div("Likely failure mode", className="ol-k"),
                    html.Div(mode if signal else "No clear fault signature", className="ol-mode"),
                    html.Div(f"Sensor pattern matches {mode.lower()} at {match:.0%}" if signal
                             else "Sensors are close to this asset's healthy baseline.", className="ol-match"),
                ],
                className="ol-block",
            ),
            html.Div(
                [
                    html.Div("Recommended action", className="ol-k"),
                    html.Div(pl.MODES[mode]["action"] if signal and risk >= threshold / 2
                             else "Keep on routine condition monitoring.", className="ol-action"),
                ],
                className="ol-block",
            ),
        ]
    )
    if down:
        outlook.children.insert(0, html.Div([DashIconify(icon="tabler:tool", width=16),
                                              "Down for repair. Figures are from its last day running."], className="ol-down"))
    return head, sensor_figure(a), outlook, driver_figure(h, a, d), history_figure(h, threshold, a)


# ---------------------------------------------------------------- model tab

@app.callback(
    Output("threshold", "value"),
    Input("best-btn", "n_clicks"),
    Input("horizon", "value"),
    State("cost-unplanned", "value"),
    State("cost-planned", "value"),
    State("cost-inspect", "value"),
)
def set_best(_, h, cu, cp, ci):
    return best_threshold(int(h), costs_of(cu, cp, ci))


@app.callback(
    Output("threshold-label", "children"),
    Output("model-kpis", "children"),
    Output("savings-chart", "figure"),
    Output("tradeoff-chart", "figure"),
    Output("lead-chart", "figure"),
    Output("weights-chart", "figure"),
    Output("model-note", "children"),
    Input("horizon", "value"),
    Input("threshold", "value"),
    Input("cost-unplanned", "value"),
    Input("cost-planned", "value"),
    Input("cost-inspect", "value"),
)
def update_model(h, threshold, cu, cp, ci):
    h = int(h)
    costs = costs_of(cu, cp, ci)
    events, false_alarms, alarms = evaluation(h, threshold)
    caught = [e for e in events if e["lead"] is not None]
    months = pl.TEST_MONTHS
    net = savings(h, threshold, costs)
    best = best_threshold(h, costs)

    kpis = [
        stat_tile("Failures caught", f"{len(caught)} of {len(events)}",
                  f"{len(caught) / max(1, len(events)):.0%} flagged up to {h} days ahead", "tabler:shield-check"),
        stat_tile("Median warning", f"{np.median([e['lead'] for e in caught]):.1f} days" if caught else "–",
                  "From first alert to breakdown", "tabler:clock-hour-4"),
        stat_tile("False alarms", f"{false_alarms / months:.1f} / month",
                  f"{false_alarms} of {alarms} alerts had no failure behind them", "tabler:bell-x"),
        stat_tile("Net savings", fmt_money(net) + " / yr",
                  f"vs running to failure. Best threshold here is {best:.0%}", "tabler:coin",
                  "good" if net > 0 else "alert"),
    ]

    # Savings curve
    vals = np.array([savings(h, t, costs) for t in THRESHOLDS])
    sav = go.Figure()
    sav.add_hline(y=0, line=dict(color=AXIS, width=1))
    vals_m = vals / 1000
    sav.add_trace(go.Scatter(x=THRESHOLDS, y=vals_m, mode="lines", line=dict(color=INK, width=2, shape="hv"),
                             hovertemplate="Alert at %{x:.0%}: <b>%{customdata}</b> / yr<extra></extra>",
                             customdata=[fmt_money(v) for v in vals]))
    bi = int(np.argmax(vals))
    sav.add_trace(go.Scatter(x=[THRESHOLDS[bi]], y=[vals_m[bi]], mode="markers+text", text=["Best"], textposition="top center",
                             textfont=dict(size=11, color=INK_2), hoverinfo="skip",
                             marker=dict(size=10, color=STATUS["good"], line=dict(color=SURFACE, width=2))))
    sav.add_trace(go.Scatter(x=[threshold], y=[net / 1000], mode="markers", hoverinfo="skip",
                             marker=dict(size=13, color="rgba(0,0,0,0)", line=dict(color="#eb6834", width=2.5))))
    sav.update_layout(base_layout(margin=dict(l=8, r=12, t=16, b=8)))
    sav.update_xaxes(axis(tickformat=".0%", title="Alert threshold", showgrid=False))
    sav.update_yaxes(axis(tickprefix="$", ticksuffix="M", tickformat=".1f"))

    # Trade-off: catch rate against false alarms per month
    fa = np.array([evaluation(h, t)[1] / months for t in THRESHOLDS])
    cr = np.array([np.mean([e["lead"] is not None for e in evaluation(h, t)[0]]) for t in THRESHOLDS])
    tr = go.Figure()
    tr.add_trace(go.Scatter(x=fa, y=cr, mode="lines+markers", line=dict(color=AXIS, width=1.5),
                            marker=dict(size=8, color="#2a78d6", line=dict(color=SURFACE, width=2)),
                            customdata=THRESHOLDS,
                            hovertemplate="Alert at %{customdata:.0%}<br>%{y:.0%} caught, %{x:.1f} false alarms a month<extra></extra>"))
    cur_fa, cur_cr = false_alarms / months, len(caught) / max(1, len(events))
    tr.add_trace(go.Scatter(x=[cur_fa], y=[cur_cr], mode="markers+text", text=[f"{threshold:.0%}"], textposition="middle right",
                            textfont=dict(family=MONO, size=11, color=INK), hoverinfo="skip",
                            marker=dict(size=14, color="rgba(0,0,0,0)", line=dict(color="#eb6834", width=2.5))))
    tr.update_layout(base_layout(margin=dict(l=8, r=12, t=16, b=8)))
    # Very low thresholds alarm constantly; keep the axis on the useful part of the curve
    x_max = max(cur_fa * 1.5, float(np.min(fa[cr >= cr.max()])) * 1.6, 5)
    tr.update_xaxes(axis(title="False alarms per month", showgrid=False, range=[0, x_max]))
    tr.update_yaxes(axis(title="Failures caught", tickformat=".0%", range=[0, 1.05]))

    # Lead time per held-out failure
    ev = sorted(events, key=lambda e: (e["lead"] is None, -(e["lead"] or 0)))
    labels = [f"{pl.ASSETS[e['i']].tag} · {e['mode'].lower()} · {pl.START + timedelta(days=e['day']):%b %-d}" for e in ev]
    leads = [e["lead"] if e["lead"] is not None else 0 for e in ev]
    ld = go.Figure(go.Bar(
        x=leads, y=labels, orientation="h",
        marker=dict(color=["#2a78d6" if e["lead"] is not None else STATUS["critical"] for e in ev], cornerradius=4),
        text=[f"{e['lead']:.1f} d" if e["lead"] is not None else "Missed" for e in ev], textposition="outside",
        textfont=dict(family=MONO, size=11, color=INK_2), cliponaxis=False,
        customdata=[(pl.START + timedelta(days=e["day"])).strftime("%b %-d") for e in ev],
        hovertemplate="%{y}<br>Broke down %{customdata}<br>%{text} of warning<extra></extra>",
    ))
    ld.update_layout(base_layout(margin=dict(l=8, r=40, t=4, b=8), bargap=0.3))
    ld.update_xaxes(axis(title="Days of warning", range=[0, h + 2]))
    ld.update_yaxes(axis(showgrid=False, showline=False, autorange="reversed", tickfont=dict(family=MONO, size=11, color=INK_2)))

    # Global weights
    w = pl.MODELS[h].w[1:]
    order = np.argsort(np.abs(w))
    wt = go.Figure(go.Bar(
        x=w[order], y=[pl.FEATURES[k][2] for k in order], orientation="h",
        marker=dict(color=[SENSOR_COLOR.get(pl.FEATURES[k][1], MUTED) for k in order], cornerradius=4),
        hovertemplate="%{y}: %{x:+.2f}<extra></extra>",
    ))
    wt.update_layout(base_layout(margin=dict(l=8, r=12, t=4, b=8), bargap=0.3))
    wt.update_xaxes(axis(zeroline=True, zerolinecolor=AXIS, title="Weight (log-odds per std)"))
    wt.update_yaxes(axis(showgrid=False, showline=False, tickfont=dict(color=INK_2, size=12)))

    m = pl.MODELS[h]
    note = [
        html.Strong("How it works. "),
        f"A logistic regression trained on {m.n_train:,} asset-days from {pl.DAY_DATES[pl.WARMUP]:%b %Y} to "
        f"{pl.DAY_DATES[pl.TRAIN_DAYS - 1]:%b %Y}, scored on {pl.DAY_DATES[pl.TRAIN_DAYS]:%b %-d} to {pl.DAY_DATES[-1]:%b %-d, %Y}, "
        f"which it never saw. Each day it reads how far every sensor sits from that asset's own healthy, load-corrected "
        f"baseline, how fast that gap is changing, how erratic vibration is and time since the last repair. "
        f"Held-out ROC AUC is {m.test_auc:.2f} (1.0 is perfect, 0.5 is a coin flip); "
        f"{m.base_rate:.0%} of training days had a breakdown within {h} days. Savings assume every caught failure becomes a "
        f"planned repair and every alert, real or not, costs one crew check.",
    ]
    return f"{threshold:.0%}", kpis, sav, tr, ld, wt, note


if __name__ == "__main__":
    app.run(debug=True)
