"""
Portfolio Stress Test & VaR

A comparison workbench for the risk of a made-up $1.6B multi-asset fund. The
app opens empty. Drag items from the sidebar onto the canvas to compare them:

- VaR models: historical, parametric, Monte Carlo and a crisis-regime Monte
  Carlo, compared on VaR, expected shortfall, P&L distribution and backtest
- Stress scenarios: historical-style replays, hypothetical shocks, the book's
  worst 10 days, or your own shocks, compared on P&L by asset class or factor
- Positions: compared on standalone risk, contribution to expected shortfall
  and P&L in every stress scenario

The Controls tab sets the confidence level, horizon, lookback and model stress
used by every comparison, and holds the custom scenario builder.

All data is synthetic, see risk.py.
"""

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash._hooks import HooksManager
from dash_iconify import DashIconify

import risk as rk

# Chart colors, kept in sync with assets/style.css (dark theme only)
SURFACE = "#1a1a19"
INK = "#f0efec"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
BODY = "#4b4a46"  # neutral marks: realized P&L in the backtest
CLASS_COLOR = dict(zip(rk.ASSET_CLASSES, ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]))
SLOT_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500"]  # an item keeps its slot while it is on the canvas
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
STATUS_ICON = {"good": "tabler:circle-check", "warning": "tabler:alert-triangle",
               "serious": "tabler:alert-octagon", "critical": "tabler:alert-octagon"}
ZONE = {"green": ("good", "Green zone"), "yellow": ("warning", "Yellow zone"), "red": ("critical", "Red zone")}

FONT = "Sora, system-ui, sans-serif"
MONO = "'Red Hat Mono', ui-monospace, monospace"
THEME = {"fontFamily": FONT, "headings": {"fontFamily": FONT}, "primaryColor": "blue", "defaultRadius": "md"}

MAX_ITEMS = 4
KINDS = ["var", "scenario", "position"]
KIND_TITLE = {"var": "VaR models", "scenario": "stress scenarios", "position": "positions"}
KIND_ICON = {"var": "tabler:chart-histogram", "scenario": "tabler:bolt", "position": "tabler:list-details"}
KIND_ONE = {"var": "VaR model", "scenario": "scenario", "position": "position"}
CUSTOM = "__custom__"

# VaR models you can compare: method, fixed stress overlay (None = use the Controls tab)
VAR_MODELS = {
    "historical": ("Historical", "historical", None, "Today's book revalued on past moves"),
    "parametric": ("Parametric", "parametric", None, "Delta-normal, ignores fat tails and convexity"),
    "montecarlo": ("Monte Carlo", "montecarlo", None, "20,000 Student-t draws, full revaluation"),
    "crisis_mc": ("Monte Carlo, crisis regime", "montecarlo", (2.0, 1.0), "2× volatility, crisis correlations"),
}
METHODS = {"historical": "Historical", "parametric": "Parametric", "montecarlo": "Monte Carlo"}

# Skip installed Dash plugins (such as the Plotly Studio Embedded chat) so the
# app renders on its own. Dash loads them once per process, on first app init
HooksManager._registered = True

app = dash.Dash(
    __name__,
    title="Portfolio Stress Test & VaR",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=Red+Hat+Mono:wght@400;500;600&display=swap"
    ],
)
server = app.server


# ---------------------------------------------------------------- formatting

def money(v, signed=False):
    """$M figure, e.g. $28.4M or −$1.2B."""
    sign = "−" if v < 0 else ("+" if signed and v > 0 else "")
    a = abs(v)
    return f"{sign}${a / 1000:.2f}B" if a >= 1000 else f"{sign}${a:.1f}M"


def pct(v, digits=2, signed=False):
    sign = "−" if v < 0 else ("+" if signed and v > 0 else "")
    return f"{sign}{abs(v):.{digits}f}%"


def shock_label(key, v):
    unit = rk.FUNIT[key]
    s = "−" if v < 0 else "+" if v > 0 else ""
    if unit == "return":
        return f"{s}{abs(v):g}%"
    return f"{s}{abs(v):g} {'bp' if unit == 'bp' else 'pts'}"


def scaled_limit(conf, horizon):
    """The 1-day 99% VaR limit, rescaled to the chosen confidence and horizon."""
    return rk.VAR_LIMIT_PCT * rk.z_score(conf) / rk.z_score(0.99) * np.sqrt(horizon)


def status_chip(status, label):
    return html.Span([DashIconify(icon=STATUS_ICON[status], width=14), label],
                     className="chip", style={"--chip": STATUS[status]})


# ---------------------------------------------------------------- chart helpers

def base_layout(fig, **kw):
    layout = dict(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2, "size": 12},
        margin={"l": 8, "r": 16, "t": 30, "b": 8},
        hoverlabel={"bgcolor": "#262624", "bordercolor": AXIS, "font": {"family": FONT, "color": INK, "size": 12}},
        showlegend=True, bargap=0.28, bargroupgap=0.08,
        legend={"orientation": "h", "x": 0, "y": 1.01, "yanchor": "bottom", "font": {"color": INK_2},
                "traceorder": "normal"},
    )
    fig.update_layout(**{**layout, **kw})
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=AXIS, linecolor=AXIS, tickfont={"color": MUTED, "family": MONO},
                     title_font={"color": MUTED, "size": 12})
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=AXIS, linecolor=AXIS, tickfont={"color": MUTED, "family": MONO},
                     title_font={"color": MUTED, "size": 12})
    return fig


def graph(graph_id, cls="graph"):
    return html.Div(
        dcc.Graph(id=graph_id, config={"displayModeBar": False, "responsive": True}, style={"height": "100%"}),
        className=cls,
    )


def color(item):
    return SLOT_COLORS[item["slot"]]


def compare_table(items, rows):
    """rows: [(label, [cell per item])]."""
    head = html.Tr([html.Th("")] + [
        html.Th(html.Span([html.Span(className="swatch", style={"background": color(it)}), it["label"]],
                          className="cmp-th"))
        for it in items
    ])
    body = [html.Tr([html.Th(label, className="cmp-rowhead")] + [html.Td(c) for c in cells]) for label, cells in rows]
    return html.Table([html.Thead(head), html.Tbody(body)], className="cmp-table")


def name_value(name, v):
    return html.Div([html.Div(name), html.Div(money(v, signed=True), className="cmp-num")])


def num(text, big=False):
    return html.Span(text, className="cmp-big" if big else "cmp-num")


# ---------------------------------------------------------------- VaR models

def var_result(key, conf, horizon, lookback, vol, corr):
    _, method, fixed, _ = VAR_MODELS[key]
    if fixed:
        vol, corr = fixed
    return rk.compute(method, conf, horizon, lookback, vol, corr)


def var_section(items, conf, horizon, lookback, vol, corr):
    results = [var_result(it["id"], conf, horizon, lookback, vol, corr) for it in items]

    # P&L distributions on one set of bins
    samples = [r.pnl for r in results if r.pnl is not None]
    spread = max([r.sigma for r in results])
    lo = min([np.quantile(s, 0.001) for s in samples] + [-4.5 * spread])
    hi = max([np.quantile(s, 0.999) for s in samples] + [4.0 * spread])
    edges = np.linspace(lo, hi, 81)
    mids = (edges[:-1] + edges[1:]) / 2
    dist = go.Figure()
    ymax = 0
    for it, r in zip(items, results):
        if r.pnl is None:
            y = np.exp(-0.5 * (mids / r.sigma) ** 2) / (r.sigma * np.sqrt(2 * np.pi))
        else:
            counts, _ = np.histogram(np.clip(r.pnl, lo, hi), edges)
            y = counts / len(r.pnl) / (edges[1] - edges[0])
        y = y * 100  # % of outcomes per $1M
        ymax = max(ymax, y.max())
        dist.add_trace(go.Scatter(
            x=mids, y=y, mode="lines", name=it["label"], line={"color": color(it), "width": 2, "shape": "spline"},
            hovertemplate=f"{it['label']}<br>" + "%{x:$,.1f}M: %{y:.2f}% per $1M<extra></extra>",
        ))
    for it, r in zip(items, results):
        dist.add_shape(type="line", x0=-r.var, x1=-r.var, y0=0, y1=ymax * 1.04,
                       line={"color": color(it), "width": 1.5, "dash": "dash"})
    base_layout(dist)
    dist.update_xaxes(title_text="Portfolio P&L, $M. Dashed lines are each model's VaR", tickprefix="$")
    dist.update_yaxes(title_text="Density", showticklabels=False, rangemode="tozero")

    # Backtest: realized P&L against each model's rolling VaR
    bt = go.Figure()
    bt_rows = []
    for i, (it, r) in enumerate(zip(items, results)):
        _, method, fixed, _ = VAR_MODELS[it["id"]]
        days, realized, var, breaches = rk.backtest(method, conf, lookback)
        if fixed:  # crisis regime: scale the base Monte Carlo line by today's stressed/base ratio
            var = var * r.var / rk.compute("montecarlo", conf, horizon, lookback).var
            breaches = realized < -var
        if i == 0:
            bt.add_trace(go.Bar(x=days, y=realized, name="Daily P&L", marker={"color": BODY, "line": {"width": 0}},
                                hovertemplate="%{x|%-d %b %Y}<br>P&L %{y:$,.1f}M<extra></extra>"))
        bt.add_trace(go.Scatter(x=days, y=-var, mode="lines", name=it["label"],
                                line={"color": color(it), "width": 2, "shape": "hv"},
                                hovertemplate=it["label"] + " %{y:$,.1f}M<extra></extra>"))
        nb = int(breaches.sum())
        bt_rows.append((nb, rk.traffic_light(rk.BACKTEST_DAYS, nb, conf), rk.kupiec(rk.BACKTEST_DAYS, nb, conf)))
    base_layout(bt, hovermode="x unified")
    bt.update_yaxes(tickprefix="$", ticksuffix="M")
    bt.update_xaxes(showgrid=False)

    limit = scaled_limit(conf, horizon)
    rows = [
        (f"VaR, {conf * 100:g}% {horizon}-day", [num(money(r.var), big=True) for r in results]),
        ("% of NAV", [num(pct(r.var / rk.NAV * 100)) for r in results]),
        (f"Limit use (limit {pct(limit)})", [
            status_chip(*(("good", f"{u:.0%}") if u < 0.8 else ("warning", f"{u:.0%}") if u <= 1 else ("critical", f"{u:.0%}")))
            for u in [r.var / rk.NAV * 100 / limit for r in results]]),
        ("Expected shortfall", [num(money(r.es)) for r in results]),
        ("ES ÷ VaR (tail weight)", [num(f"{r.es / r.var:.2f}×") for r in results]),
        ("Diversification benefit", [num(pct((1 - r.var / r.standalone.sum()) * 100, 0)) for r in results]),
        (f"Backtest exceptions ({rk.BACKTEST_DAYS * (1 - conf):.1f} expected)",
         [num(f"{nb} / {rk.BACKTEST_DAYS}") for nb, _, _ in bt_rows]),
        ("Basel traffic light", [status_chip(*ZONE[z]) for _, z, _ in bt_rows]),
        ("Kupiec p-value", [num(f"{p:.2f}" + (" · rejected" if p < 0.05 else "")) for _, _, p in bt_rows]),
    ]
    subs = [f"{money(r.var)} VaR · {pct(r.var / rk.NAV * 100)} of NAV" for r in results]
    return subs, html.Div(compare_table(items, rows), className="cmp-table-wrap"), dist, bt


# ---------------------------------------------------------------- scenarios

def scenario_summary(shock):
    pos = rk.scenario_pnl(shock)
    total = pos.sum()
    lin, nonlin = rk.factor_attribution(shock)
    drivers = np.append(lin, nonlin)
    labels = [rk.FLABEL[k] for k in rk.FKEYS] + ["Put overlay convexity & cap"]
    worst_i, best_i, drv = int(np.argmin(pos)), int(np.argmax(pos)), int(np.argmin(drivers))
    return {
        "total": total, "pct": total / rk.NAV * 100,
        "classes": np.array([pos[rk.CLASS_OF == i].sum() for i in range(len(rk.ASSET_CLASSES))]),
        "factors": drivers, "factor_labels": labels,
        "worst": (rk.NAMES[worst_i], pos[worst_i]), "best": (rk.NAMES[best_i], pos[best_i]),
        "driver": (labels[drv], drivers[drv]), "reverse": rk.reverse_stress(shock, rk.STRESS_LIMIT_PCT),
    }


def grouped_bars(items, cats, values, hover_unit="$M"):
    """Horizontal grouped bars: one group per category, one bar per compared item."""
    fig = go.Figure()
    keep = [i for i in range(len(cats)) if any(abs(v[i]) >= 0.5 for v in values)] or list(range(len(cats)))
    for it, v in zip(items, values):
        fig.add_trace(go.Bar(
            y=[cats[i] for i in keep], x=[v[i] for i in keep], orientation="h", name=it["label"],
            marker={"color": color(it), "cornerradius": 3, "line": {"color": SURFACE, "width": 1}},
            hovertemplate="<b>%{y}</b><br>" + it["label"] + ": %{x:$,.1f}M<extra></extra>",
        ))
    base_layout(fig, barmode="group")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont={"family": FONT, "color": INK_2})
    fig.update_xaxes(tickprefix="$", ticksuffix="M", zerolinecolor=AXIS, zerolinewidth=1.5)
    return fig


def scenario_section(items, view):
    sums = [scenario_summary(it["shock"]) for it in items]
    if view == "class":
        fig = grouped_bars(items, rk.ASSET_CLASSES, [s["classes"] for s in sums])
    else:
        fig = grouped_bars(items, sums[0]["factor_labels"], [s["factors"] for s in sums])

    def limit_cell(s):
        over = -s["pct"] > rk.STRESS_LIMIT_PCT
        return status_chip("critical" if over else "good", "Over limit" if over else "Within limit")

    rows = [
        ("Total P&L", [num(money(s["total"], signed=True), big=True) for s in sums]),
        ("% of NAV", [num(pct(s["pct"], 1, signed=True)) for s in sums]),
        (f"Stress limit (−{rk.STRESS_LIMIT_PCT:g}%)", [limit_cell(s) for s in sums]),
        ("Biggest loss driver", [name_value(*s["driver"]) for s in sums]),
        ("Hardest-hit position", [name_value(*s["worst"]) for s in sums]),
        ("Best offset", [name_value(*s["best"]) for s in sums]),
        ("Severity to hit the limit", [num(f"{s['reverse']:.2f}×" if s["reverse"] else "> 3×") for s in sums]),
    ]
    subs = [f"{pct(s['pct'], 1, signed=True)} of NAV" for s in sums]
    return subs, html.Div(compare_table(items, rows), className="cmp-table-wrap"), fig


# ---------------------------------------------------------------- positions

def position_section(items, res, conf):
    idx = [rk.NAMES.index(it["id"]) for it in items]
    scen_names = list(rk.SCENARIOS)
    scen = np.array([rk.scenario_pnl(rk.SCENARIOS[n]["shock"]) for n in scen_names])  # (scenarios, positions)
    fig = grouped_bars(items, scen_names, [scen[:, i] for i in idx])

    def scen_cell(i, worst):
        j = int(np.argmin(scen[:, i]) if worst else np.argmax(scen[:, i]))
        return name_value(scen_names[j], scen[j, i])

    rows = [
        ("Asset class", [html.Span([html.Span(className="swatch", style={"background": CLASS_COLOR[rk.POSITIONS[i].asset_class]}),
                                    rk.POSITIONS[i].asset_class], className="cmp-th plain") for i in idx]),
        ("Market value", [num(money(rk.MV[i]) if rk.MV[i] else "Unfunded", big=True) for i in idx]),
        ("Weight", [num(pct(rk.MV[i] / rk.NAV * 100, 1)) for i in idx]),
        (f"Standalone VaR, {conf * 100:g}%", [num(money(res.standalone[i])) for i in idx]),
        ("Contribution to ES", [num(money(res.contrib[i], signed=True)) for i in idx]),
        ("Share of ES", [num(pct(res.contrib[i] / res.es * 100, 1, signed=True) + (" · hedge" if res.contrib[i] < 0 else ""))
                         for i in idx]),
        ("Worst scenario", [scen_cell(i, True) for i in idx]),
        ("Best scenario", [scen_cell(i, False) for i in idx]),
        ("Note", [html.Span(rk.POSITIONS[i].note or "–", className="muted") for i in idx]),
    ]
    subs = [f"{money(rk.MV[i])} · {rk.POSITIONS[i].asset_class}" if rk.MV[i] else f"Unfunded · {rk.POSITIONS[i].asset_class}"
            for i in idx]
    return subs, html.Div(compare_table(items, rows), className="cmp-table-wrap"), fig


# ---------------------------------------------------------------- layout pieces

def control(label, component, hint=None):
    return html.Div([html.Div(label, className="ctl-label"), component,
                     html.Div(hint, className="ctl-hint") if hint is not None else None], className="ctl")


def item(kind, id_, label, sub, badge=None, icon=None, swatch=None):
    """A sidebar item: drag it onto the canvas, or click / press Enter to add it."""
    lead = (html.Div(DashIconify(icon=icon, width=16), className="lib-icon") if icon
            else html.Span(className="swatch lead", style={"background": swatch}) if swatch else None)
    return html.Div(
        [DashIconify(icon="tabler:grip-vertical", width=14, className="drag-grip"), lead,
         html.Div([html.Div(label, className="drag-name"), html.Div(sub, className="drag-sub")], className="drag-text"),
         html.Span(badge, className="drag-kind") if badge else None,
         html.Span(id={"type": "item-state", "kind": kind, "id": id_}, className="lib-state")],
        id={"type": "item", "kind": kind, "id": id_}, n_clicks=0, draggable="true", role="button", tabIndex="0",
        title="Drag onto the canvas to compare, or click to add", className="drag-item",
        **{"data-item-kind": kind, "data-item-id": id_},
    )


SLIDER_RANGE = {  # min, max, step in UI units
    "US_EQ": (-50, 30, 1), "DM_EQ": (-50, 30, 1), "EM_EQ": (-60, 40, 1), "UST10": (-250, 300, 5),
    "IG": (-50, 400, 5), "HY": (-200, 1200, 10), "OIL": (-70, 80, 1), "GOLD": (-30, 40, 1),
    "USD": (-25, 25, 0.5), "VIX": (-15, 80, 1),
}
DEFAULT_PRESET = "Global financial crisis"


def shock_slider(key):
    lo, hi, step = SLIDER_RANGE[key]
    return html.Div([
        html.Div([html.Span(rk.FLABEL[key], className="shock-name"),
                  html.Span(id={"type": "shock-val", "f": key}, className="shock-val")], className="shock-head"),
        dmc.Slider(id={"type": "shock", "f": key}, min=lo, max=hi, step=step,
                   value=rk.SCENARIOS[DEFAULT_PRESET]["shock"][key], size="sm", label=None, color="gray"),
    ], className="shock")


def group(title, hint, children):
    return dmc.AccordionItem([
        dmc.AccordionControl(html.Div([html.Span(title), html.Span(hint, className="rail-section-hint")],
                                      className="acc-title")),
        dmc.AccordionPanel(html.Div(children, className="drag-list")),
    ], value=title)


compare_tab = html.Div([
    html.Div("Drag items onto the canvas to compare them. Up to four of each kind.", className="ctl-hint"),
    dmc.Accordion(
        [
            group("VaR models", "4", [item("var", k, v[0], v[3], icon="tabler:chart-histogram")
                                      for k, v in VAR_MODELS.items()]),
            group("Stress scenarios", f"{len(rk.SCENARIOS) + 1}",
                  [item("scenario", CUSTOM, "Custom scenario", "Snapshot of the shocks in Controls", "Custom",
                        icon="tabler:adjustments")]
                  + [item("scenario", n, n, s["period"], s["kind"], icon="tabler:bolt") for n, s in rk.SCENARIOS.items()]),
            group("Positions", f"{len(rk.POSITIONS)}",
                  [item("position", p.name, p.name, f"{p.asset_class} · {money(p.mv)}" if p.mv else f"{p.asset_class} · unfunded",
                        swatch=CLASS_COLOR[p.asset_class]) for p in rk.POSITIONS]),
        ],
        multiple=True, value=["VaR models", "Stress scenarios", "Positions"], variant="default",
        chevronPosition="right", className="rail-acc",
    ),
], className="tab-body")

controls_tab = html.Div([
    html.Div("Risk model", className="rail-section"),
    html.Div("Used by the VaR model and position comparisons", className="ctl-hint section-hint"),
    control("Confidence", dmc.SegmentedControl(id="conf", value="0.99", fullWidth=True, size="xs",
                                               data=[{"label": f"{c}%", "value": str(c / 100)} for c in (95, 97.5, 99)])),
    control("Horizon", dmc.SegmentedControl(id="horizon", value="1", fullWidth=True, size="xs",
                                            data=[{"label": "1 day", "value": "1"}, {"label": "10 days", "value": "10"}])),
    control("Lookback window", dmc.SegmentedControl(id="lookback", value="250", fullWidth=True, size="xs",
                                                    data=[{"label": f"{n:,} d", "value": str(n)} for n in (250, 500, 1000)]),
            "Includes the spring 2025 sell-off from 500 days on"),
    control("Method for position risk", dmc.SegmentedControl(id="pos-method", value="historical", fullWidth=True, size="xs",
                                                             data=[{"label": v, "value": k} for k, v in METHODS.items()])),
    html.Div("Stress the model", className="rail-section"),
    control(html.Span(["Volatility multiplier", html.Span(id="vol-val", className="ctl-val")]),
            dmc.Slider(id="vol-mult", min=1, max=3, step=0.1, value=1, size="sm", label=None,
                       marks=[{"value": v, "label": f"{v}×"} for v in (1, 2, 3)], className="rail-slider")),
    control(html.Span(["Correlation stress", html.Span(id="corr-val", className="ctl-val")]),
            dmc.Slider(id="corr-stress", min=0, max=100, step=5, value=0, size="sm", label=None,
                       marks=[{"value": v, "label": f"{v}%"} for v in (0, 50, 100)], className="rail-slider"),
            "Moves every factor correlation towards its crisis value. History keeps its own correlations"),
    html.Div("Custom scenario", className="rail-section"),
    html.Div("Set the shocks, then drag Custom scenario from the Compare tab", className="ctl-hint section-hint"),
    html.Div([
        dmc.Select(id="preset", value=DEFAULT_PRESET, allowDeselect=False, size="xs", style={"flex": 1},
                   data=[{"label": n, "value": n} for n in rk.SCENARIOS], comboboxProps={"withinPortal": True}),
        dmc.Button("Reset", id="reset", variant="subtle", color="gray", size="xs",
                   leftSection=DashIconify(icon="tabler:refresh", width=14)),
    ], className="preset-row"),
    html.Div([shock_slider(k) for k in rk.FKEYS], className="shocks"),
], className="tab-body")

rail = html.Aside([
    html.Div([
        html.Div(DashIconify(icon="tabler:shield-half-filled", width=22), className="brand-mark"),
        html.Div([html.Div("Larkspur Multi-Asset Fund", className="brand-name"),
                  html.Div("Risk & stress testing", className="brand-sub")]),
    ], className="brand"),
    html.Div([
        html.Div("Net asset value", className="ctl-label"),
        html.Div(money(rk.NAV), className="nav-value"),
        html.Div(f"{len(rk.POSITIONS)} positions · 10 risk factors · as of {rk.AS_OF:%-d %b %Y}", className="ctl-hint"),
    ], className="nav-block"),
    dmc.Tabs(
        [
            dmc.TabsList([dmc.TabsTab("Compare", value="compare", leftSection=DashIconify(icon="tabler:columns-3", width=15)),
                          dmc.TabsTab("Controls", value="controls",
                                      leftSection=DashIconify(icon="tabler:adjustments-horizontal", width=15))],
                         grow=True),
            dmc.TabsPanel(compare_tab, value="compare"),
            dmc.TabsPanel(controls_tab, value="controls"),
        ],
        value="compare", color="blue", keepMounted=True, className="rail-tabs",
    ),
    html.Div("Synthetic data for demonstration only.", className="rail-foot"),
], className="rail")


def section(kind, sub, *body, extra=None):
    return html.Section([
        html.Div([
            html.Div([html.Div(f"Compare {KIND_TITLE[kind]}", className="card-title"),
                      html.Div(sub, id=f"sub-{kind}", className="card-sub")], className="panel-heading"),
            html.Div(extra, className="card-extra") if extra is not None else None,
            html.Button(DashIconify(icon="tabler:x", width=15), id={"type": "sec-clear", "kind": kind}, n_clicks=0,
                        className="panel-btn", title="Clear this comparison", **{"aria-label": "Clear this comparison"}),
        ], className="card-head"),
        html.Div(id=f"tiles-{kind}", className="tiles"),
        *body,
    ], id=f"sec-{kind}", className="card section")


canvas = html.Main([
    html.Div([
        html.Div(DashIconify(icon="tabler:drag-drop", width=34), className="empty-icon"),
        html.Div("Drag items here to compare them", className="empty-title"),
        html.Div("Pick VaR models, stress scenarios or positions from the Compare tab in the sidebar. "
                 "Drop them anywhere on this canvas, or click them.", className="empty-sub"),
        html.Div([
            html.Span([DashIconify(icon="tabler:chart-histogram", width=15), "VaR models"]),
            html.Span([DashIconify(icon="tabler:bolt", width=15), "Stress scenarios"]),
            html.Span([DashIconify(icon="tabler:circle-filled", width=10), "Positions"]),
        ], className="empty-kinds"),
    ], id="canvas-empty", className="canvas-empty"),
    dmc.Tabs([
    dmc.TabsList([
        dmc.TabsTab(html.Span(id=f"tablabel-{k}"), value=k, id=f"tab-{k}", style={"display": "none"},
                    leftSection=DashIconify(icon=KIND_ICON[k], width=16))
        for k in KINDS
    ], className="cmp-tablist"),
    dmc.TabsPanel(section("var", "VaR, expected shortfall, distribution and backtest under the Controls tab's settings",
            html.Div([
                html.Div([html.Div("P&L distribution", className="pane-title"), graph("var-dist")], className="pane"),
                html.Div([html.Div("Backtest: last 250 days of P&L against each model's 1-day VaR", className="pane-title"),
                          graph("var-bt")], className="pane"),
            ], className="pair"),
            html.Div(id="body-var")), value="var"),
    dmc.TabsPanel(section("scenario", "Instant shocks applied to today's book",
            html.Div([html.Div(graph("scenario-chart", "graph tall"), className="pane"),
                      html.Div(id="body-scenario")], className="pair"),
            extra=dmc.SegmentedControl(id="scenario-view", value="class", size="xs",
                                       data=[{"label": "By asset class", "value": "class"},
                                             {"label": "By risk factor", "value": "factor"}])), value="scenario"),
    dmc.TabsPanel(section("position", "Risk under the Controls tab's settings, and P&L in every stress scenario",
            html.Div([html.Div([html.Div("P&L in each stress scenario", className="pane-title"),
                                graph("position-chart", "graph tall")], className="pane"),
                      html.Div(id="body-position")], className="pair")), value="position"),
    ], id="cmp-tabs", value="var", keepMounted=True, color="blue", className="cmp-tabs", style={"display": "none"}),
    html.Div([DashIconify(icon="tabler:plus", width=18), html.Span("Drop another VaR model, scenario or position anywhere")],
             id="canvas-more", className="canvas-more", style={"display": "none"}),
], id="canvas", className="main canvas")

app.layout = dmc.MantineProvider(
    html.Div([rail, canvas, dcc.Store(id="item-drop"), dcc.Store(id="cmp", data={"order": [], **{k: [] for k in KINDS}})],
             className="shell"),
    theme=THEME, forceColorScheme="dark",
)


# ---------------------------------------------------------------- callbacks

def risk_params(conf, horizon, lookback, vol, corr):
    return float(conf), int(horizon), int(lookback), float(vol), float(corr) / 100


def current_shock(values):
    return dict(zip(rk.FKEYS, [float(v or 0) for v in values]))


def label_for(kind, id_):
    if kind == "var":
        return VAR_MODELS[id_][0]
    return id_


@app.callback(
    Output("cmp", "data"), Output("cmp-tabs", "value"),
    Input("item-drop", "data"), Input({"type": "item", "kind": ALL, "id": ALL}, "n_clicks"),
    Input({"type": "tile-remove", "kind": ALL, "slot": ALL}, "n_clicks"),
    Input({"type": "sec-clear", "kind": ALL}, "n_clicks"),
    State("cmp", "data"), State({"type": "shock", "f": ALL}, "value"), State("cmp-tabs", "value"),
    prevent_initial_call=True,
)
def edit_compare(drop, clicks, removes, clears, cmp, shock_values, tab):
    """Update the comparison, and open the tab of whatever was just added."""
    new = update_compare(drop, cmp, shock_values)
    if new is dash.no_update:
        return dash.no_update, dash.no_update
    added = [k for k in KINDS if len(new[k]) > len(cmp[k])]
    if added:
        return new, added[0]
    if tab not in new["order"] and new["order"]:
        return new, new["order"][-1]
    return new, dash.no_update


def update_compare(drop, cmp, shock_values):
    trig = ctx.triggered_id
    if trig == "item-drop":
        kind, id_ = (drop or {}).get("kind"), (drop or {}).get("id")
    elif isinstance(trig, dict) and ctx.triggered[0]["value"]:
        if trig["type"] == "item":
            kind, id_ = trig["kind"], trig["id"]
        elif trig["type"] == "tile-remove":
            items = [it for it in cmp[trig["kind"]] if it["slot"] != trig["slot"]]
            order = cmp["order"] if items else [k for k in cmp["order"] if k != trig["kind"]]
            return {**cmp, trig["kind"]: items, "order": order}
        else:  # sec-clear
            return {**cmp, trig["kind"]: [], "order": [k for k in cmp["order"] if k != trig["kind"]]}
    else:
        return dash.no_update

    valid = {"var": VAR_MODELS, "scenario": {**rk.SCENARIOS, CUSTOM: None}, "position": rk.NAMES}
    if kind not in valid or id_ not in valid[kind]:
        return dash.no_update
    items = cmp[kind]
    if len(items) >= MAX_ITEMS or (id_ != CUSTOM and any(it["id"] == id_ for it in items)):
        return dash.no_update
    new = {"id": id_, "slot": min(set(range(MAX_ITEMS)) - {it["slot"] for it in items}), "label": label_for(kind, id_)}
    if kind == "scenario":
        if id_ == CUSTOM:
            new["label"] = f"Custom {sum(it['id'] == CUSTOM for it in items) + 1}"
            new["shock"] = current_shock(shock_values)
        else:
            new["shock"] = rk.SCENARIOS[id_]["shock"]
    order = cmp["order"] if kind in cmp["order"] else cmp["order"] + [kind]
    return {**cmp, kind: items + [new], "order": order}


def tiles(kind, items, subs):
    out = [
        html.Div([
            html.Span(className="swatch", style={"background": color(it)}),
            html.Div([html.Div(it["label"], className="tile-name"), html.Div(sub, className="tile-sub")]),
            html.Button(DashIconify(icon="tabler:x", width=14), id={"type": "tile-remove", "kind": kind, "slot": it["slot"]},
                        n_clicks=0, className="tile-remove", title="Remove from comparison",
                        **{"aria-label": f"Remove {it['label']}"}),
        ], className="tile")
        for it, sub in zip(items, subs)
    ]
    if len(items) < MAX_ITEMS:
        out.append(html.Div([DashIconify(icon="tabler:plus", width=16),
                             html.Span(f"Add another {KIND_ONE[kind]}" if items else f"Drop a {KIND_ONE[kind]} here")],
                            className="tile-hint"))
    return out


@app.callback(
    Output("tab-var", "style"), Output("tab-scenario", "style"), Output("tab-position", "style"),
    Output("tablabel-var", "children"), Output("tablabel-scenario", "children"), Output("tablabel-position", "children"),
    Output("canvas-empty", "style"), Output("canvas-more", "style"), Output("cmp-tabs", "style"),
    Output({"type": "item", "kind": ALL, "id": ALL}, "className"),
    Output({"type": "item-state", "kind": ALL, "id": ALL}, "children"),
    Input("cmp", "data"),
)
def render_canvas(cmp):
    order = {k: i for i, k in enumerate(cmp["order"])}
    styles = [{"order": order[k]} if k in order else {"display": "none"} for k in KINDS]
    labels = [html.Span([KIND_TITLE[k][0].upper() + KIND_TITLE[k][1:], html.Span(str(len(cmp[k])), className="tab-count")])
              for k in KINDS]
    on = {(k, it["id"]) for k in KINDS for it in cmp[k] if it["id"] != CUSTOM}
    full = {k for k in KINDS if len(cmp[k]) >= MAX_ITEMS}
    cls, state = [], []
    for o in ctx.outputs_list[9]:
        key = (o["id"]["kind"], o["id"]["id"])
        if key in on:
            cls.append("drag-item on-board")
            state.append(DashIconify(icon="tabler:check", width=14))
        else:
            cls.append("drag-item is-full" if key[0] in full else "drag-item")
            state.append(DashIconify(icon="tabler:plus", width=14))
    empty = not cmp["order"]
    hidden = {"display": "none"}
    return (*styles, *labels, {} if empty else hidden, hidden if empty else {}, hidden if empty else {}, cls, state)


@app.callback(
    Output("tiles-var", "children"), Output("body-var", "children"), Output("var-dist", "figure"),
    Output("var-bt", "figure"),
    Input("cmp", "data"), Input("conf", "value"), Input("horizon", "value"), Input("lookback", "value"),
    Input("vol-mult", "value"), Input("corr-stress", "value"),
)
def render_var(cmp, *params):
    items = cmp["var"]
    if not items:
        return [], None, go.Figure(), go.Figure()
    conf, horizon, lookback, vol, corr = risk_params(*params)
    subs, table, dist, bt = var_section(items, conf, horizon, lookback, vol, corr)
    return tiles("var", items, subs), table, dist, bt


@app.callback(
    Output("tiles-scenario", "children"), Output("body-scenario", "children"), Output("scenario-chart", "figure"),
    Input("cmp", "data"), Input("scenario-view", "value"),
)
def render_scenarios(cmp, view):
    items = cmp["scenario"]
    if not items:
        return [], None, go.Figure()
    subs, table, fig = scenario_section(items, view)
    return tiles("scenario", items, subs), table, fig


@app.callback(
    Output("tiles-position", "children"), Output("body-position", "children"), Output("position-chart", "figure"),
    Input("cmp", "data"), Input("pos-method", "value"), Input("conf", "value"), Input("horizon", "value"),
    Input("lookback", "value"), Input("vol-mult", "value"), Input("corr-stress", "value"),
)
def render_positions(cmp, method, *params):
    items = cmp["position"]
    if not items:
        return [], None, go.Figure()
    conf, horizon, lookback, vol, corr = risk_params(*params)
    res = rk.compute(method, conf, horizon, lookback, vol, corr)
    subs, table, fig = position_section(items, res, conf)
    return tiles("position", items, subs), table, fig


@app.callback(Output("vol-val", "children"), Output("corr-val", "children"),
              Input("vol-mult", "value"), Input("corr-stress", "value"))
def slider_labels(vol, corr):
    return f"{float(vol):.1f}×", f"{float(corr):.0f}%"


@app.callback(Output({"type": "shock", "f": ALL}, "value"), Input("preset", "value"), Input("reset", "n_clicks"))
def load_preset(name, _):
    shock = rk.SCENARIOS[name]["shock"]
    return [shock[k] for k in rk.FKEYS]


@app.callback(Output({"type": "shock-val", "f": ALL}, "children"), Input({"type": "shock", "f": ALL}, "value"))
def shock_labels(values):
    shock = current_shock(values)
    return [shock_label(k, shock[k]) for k in rk.FKEYS]


if __name__ == "__main__":
    app.run(debug=True)
