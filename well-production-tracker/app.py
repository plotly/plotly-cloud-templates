"""
Well Production Tracker

Daily oil, gas and water production for the 48 horizontal wells of a made-up
field. Shows field totals by formation with a two-year forecast, which wells are
falling short of their decline curve and why, a map of the laterals colored by
how each well is doing against forecast, and for any well its rate-time history,
Arps decline fit, EUR and how it compares with the formation type curve.

The production data is synthetic, see wells.py.
"""

from datetime import date, timedelta

import dash
import dash_ag_grid as dag
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, ctx, dcc, html
from dash_iconify import DashIconify

import wells as wl

# Chart colors, kept in sync with assets/style.css
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#7a7974"
GRID = "#ecebe7"
AXIS = "#d6d5d0"
NEUTRAL = "#a3a29a"
STREAM_COLOR = {"Oil": "#008300", "Gas": "#e34948", "Water": "#2a78d6", "BOE": "#6250d6"}
FORMATION_COLOR = dict(zip(wl.FORMATIONS, ["#6250d6", "#eda100", "#1baf7a"]))
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
WELL_STATUS = {
    "Producing": ("good", "tabler:circle-check"),
    "Ramping up": ("good", "tabler:trending-up"),
    "Underperforming": ("serious", "tabler:alert-octagon"),
    "Shut in": ("critical", "tabler:player-stop"),
}
# Performance against forecast, red below and blue above, gray midpoint
VARIANCE_BINS = [
    (-np.inf, -0.25, "#b8322f", "25%+ below"),
    (-0.25, -0.10, "#e98a85", "10–25% below"),
    (-0.10, 0.10, NEUTRAL, "Within 10%"),
    (0.10, 0.25, "#86b6ef", "10–25% above"),
    (0.25, np.inf, "#256abf", "25%+ above"),
]
SHUT_IN_COLOR = "#2b2a27"

FONT = "'IBM Plex Sans', system-ui, sans-serif"
THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": FONT},
    "primaryColor": "dark",
    "defaultRadius": "md",
}

app = dash.Dash(
    __name__,
    title="Well Production Tracker",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap"
    ],
)
server = app.server

FORECAST_DAYS = 730
MONTH_KEY = np.array([d.year * 12 + d.month - 1 for d in wl.DAYS])
FC_DAYS = [wl.AS_OF + timedelta(days=i + 1) for i in range(FORECAST_DAYS)]
FC_MONTH_KEY = np.array([d.year * 12 + d.month - 1 for d in FC_DAYS])

# Field totals per formation and stream: daily history and daily forecast, built once
FIELD, FIELD_FC = {}, {}
for f in wl.FORMATIONS:
    group = [w for w in wl.WELLS if w.formation == f]
    for s in wl.STREAMS:
        FIELD[f, s] = np.nansum([wl.stream_series(w, s) for w in group], axis=0)
        FIELD_FC[f, s] = np.sum([wl.stream_forecast(w, s, FORECAST_DAYS) for w in group], axis=0)


# Open on the well with the biggest shortfall against forecast
DEFAULT_WELL = min(wl.WELLS, key=lambda w: np.nan_to_num(w.stats["oil"] - w.stats["expected"])).name


def month_avg(daily, keys):
    """Calendar-day average rate per month."""
    uniq = np.unique(keys)
    return [date(k // 12, k % 12 + 1, 1) for k in uniq], np.array([daily[keys == k].mean() for k in uniq])


def wells_in(formation):
    return [w for w in wl.WELLS if formation == "All" or w.formation == formation]


def formations_in(formation):
    return list(wl.FORMATIONS) if formation == "All" else [formation]


def variance_color(w):
    if w.stats["status"] == "Shut in":
        return SHUT_IN_COLOR
    v = w.stats["variance"]
    if np.isnan(v):
        return NEUTRAL
    return next(c for lo, hi, c, _ in VARIANCE_BINS if lo <= v < hi)


def rgba(hex_color, alpha):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def fmt_rate(v):
    return f"{v:,.0f}" if v >= 10 or v == 0 else f"{v:,.1f}"


def shortfall(w):
    """Oil rate below forecast over the last 30 days, 0 when on or above it or when there's no forecast."""
    return max(np.nan_to_num(w.stats["expected"] - w.stats["oil"]), 0)


def effective_decline(fit):
    """Arps nominal Di as the effective first-year decline engineers quote."""
    return 1 - (1 + fit["b"] * fit["di"]) ** (-1 / fit["b"])


def style_axes(fig):
    for axis in (fig.update_xaxes, fig.update_yaxes):
        axis(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
             title_font={"color": MUTED, "size": 12})
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12}},
    )
    return fig


def field_chart(formation, stream):
    fig = go.Figure()
    unit = wl.STREAMS[stream]
    total_hist, total_fc = 0, 0
    for f in formations_in(formation):
        x, y = month_avg(FIELD[f, stream], MONTH_KEY)
        xf, yf = month_avg(FIELD_FC[f, stream], FC_MONTH_KEY)
        total_hist, total_fc = total_hist + y, total_fc + yf
        fig.add_trace(go.Scatter(
            x=x, y=y, name=f, stackgroup="hist", mode="lines",
            line={"color": FORMATION_COLOR[f], "width": 1.5}, fillcolor=rgba(FORMATION_COLOR[f], 0.7),
            hovertemplate=f"%{{y:,.0f}} {unit}<extra>{f}</extra>",
        ))
    fig.add_trace(go.Scatter(
        x=[x[-1], *xf], y=[total_hist[-1], *total_fc], name="Forecast", mode="lines",
        line={"color": INK_2, "width": 2, "dash": "dot"},
        hovertemplate=f"%{{y:,.0f}} {unit}<extra>Forecast</extra>",
    ))
    today = wl.AS_OF.replace(day=1)
    fig.add_vline(x=today, line={"color": AXIS, "width": 1})
    fig.add_annotation(x=today, y=1, yref="paper", text="Today", showarrow=False, xanchor="left", xshift=4,
                       yanchor="top", font={"color": MUTED, "size": 11})
    fig.add_annotation(x=xf[-1], y=total_fc[-1], text=f"{total_fc[-1]:,.0f}", showarrow=False, xanchor="left",
                       xshift=6, font={"color": INK_2, "size": 11})
    fig.update_yaxes(title=f"{stream}, {unit}", rangemode="tozero")
    fig.update_xaxes(range=[wl.START, xf[-1] + timedelta(days=60)])
    fig.update_layout(
        margin={"l": 64, "r": 48, "t": 8, "b": 32}, hovermode="x unified",
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2},
                "traceorder": "normal"},
    )
    return style_axes(fig)


def map_figure(formation, selected):
    fig = go.Figure()
    shown = wells_in(formation)
    # One trace per color bin, laterals separated by None so they draw as separate lines
    groups = {}
    for w in shown:
        groups.setdefault(variance_color(w), []).append(w)
    names = {c: label for _, _, c, label in VARIANCE_BINS} | {SHUT_IN_COLOR: "Shut in"}
    for color in [c for *_, c, _ in VARIANCE_BINS] + [SHUT_IN_COLOR]:
        group = groups.get(color)
        if not group:
            continue
        lat, lon, cd = [], [], []
        for w in group:
            s = w.stats
            mid = ((w.heel[0] + w.toe[0]) / 2, (w.heel[1] + w.toe[1]) / 2)
            vs = "too new to compare" if np.isnan(s["variance"]) else f"{s['variance']:+.0%} vs forecast"
            info = [w.name, w.formation, s["oil"], vs, s["status"]]
            for p in (w.heel, mid, w.toe):
                lat.append(p[0])
                lon.append(p[1])
                cd.append(info)
            lat.append(None)
            lon.append(None)
            cd.append(info)
        fig.add_trace(go.Scattermap(
            lat=lat, lon=lon, mode="lines+markers", name=names[color],
            line={"color": color, "width": 4}, marker={"size": 6, "color": color},
            customdata=cd,
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]:,.0f} bbl/d oil"
                          "<br>%{customdata[3]} · %{customdata[4]}<extra></extra>",
        ))
    pads = {}
    for w in shown:
        pads.setdefault(w.pad, []).append(w)
    fig.add_trace(go.Scattermap(
        lat=[np.mean([w.heel[0] for w in g]) for g in pads.values()],
        lon=[np.mean([w.heel[1] for w in g]) for g in pads.values()],
        mode="markers+text", text=list(pads), textposition="top right",
        textfont={"color": INK_2, "size": 11}, marker={"size": 9, "color": INK},
        hoverinfo="skip", showlegend=False,
    ))
    if selected in wl.BY_NAME:
        w = wl.BY_NAME[selected]
        fig.add_trace(go.Scattermap(
            lat=[w.heel[0], w.toe[0]], lon=[w.heel[1], w.toe[1]], mode="lines", hoverinfo="skip",
            line={"color": "#f2c200", "width": 10}, showlegend=False, opacity=0.6,
        ))
        fig.data = (fig.data[-1],) + fig.data[:-1]  # highlight underneath the lateral
    lats = [p[0] for w in wl.WELLS for p in (w.heel, w.toe)]
    lons = [p[1] for w in wl.WELLS for p in (w.heel, w.toe)]
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        map={"style": "carto-positron", "center": {"lat": np.mean(lats), "lon": np.mean(lons)}, "zoom": 10.9,
             "domain": {"x": [0, 1], "y": [0.13, 1]}},
        legend={"orientation": "h", "x": 0, "y": 0, "yanchor": "bottom", "font": {"color": INK_2, "size": 11},
                "title": {"text": "Oil vs forecast", "font": {"size": 11, "color": MUTED}, "side": "top"}},
        uirevision="map", font={"family": FONT}, paper_bgcolor=SURFACE,
    )
    return fig


def rate_chart(w):
    fig = go.Figure()
    i0 = (w.first_prod - wl.START).days
    days = wl.DAYS[i0:]
    cut = wl.DAYS[-wl.FIT_CUTOFF]
    for name in ("Oil", "Gas", "Water"):
        y = getattr(w, name.lower())[i0:].copy()
        y[y <= 0] = np.nan  # gaps for downtime on a log axis
        fig.add_trace(go.Scatter(
            x=days, y=y, mode="lines", name=name, line={"color": STREAM_COLOR[name], "width": 1.25},
            opacity=0.85, connectgaps=False,
            hovertemplate=f"%{{y:,.0f}} {wl.STREAMS[name]}<extra>{name}</extra>",
        ))
        last = y[~np.isnan(y)][-1] if np.any(~np.isnan(y)) else None
        if last:
            fig.add_annotation(x=days[-1], y=np.log10(last), text=name, showarrow=False, xanchor="left", xshift=4,
                               font={"color": INK_2, "size": 11})
    if w.fit:
        t = np.arange(len(days))
        fit = wl.arps(t, **wl._fit_args(w.fit))
        fig.add_trace(go.Scatter(
            x=days[30:], y=fit[30:], mode="lines",
            name="Formation decline" if w.fit.get("borrowed") else "Oil decline fit", line={"color": INK, "width": 2},
            hovertemplate="%{y:,.0f} bbl/d<extra>Fit</extra>",
        ))
        fc = wl.forecast(w, 3 * 365)
        fig.add_trace(go.Scatter(
            x=[wl.AS_OF + timedelta(days=i + 1) for i in range(len(fc))], y=fc, mode="lines",
            name="Oil forecast", line={"color": INK, "width": 2, "dash": "dot"},
            hovertemplate="%{y:,.0f} bbl/d<extra>Forecast</extra>",
        ))
    for a, b, label in w.events:
        if b - a < 3:
            continue  # one- and two-day outages would clutter the chart; they show as gaps
        fig.add_vrect(x0=wl.DAYS[a], x1=wl.DAYS[min(b, wl.N_DAYS - 1)], fillcolor="rgba(122,121,116,0.13)",
                      line={"width": 0}, layer="below")
        if b - a >= 9 or label == "Pump failure":
            fig.add_annotation(x=wl.DAYS[a], y=1, yref="paper", text=label, showarrow=False, textangle=-90,
                               xanchor="right", yanchor="top", font={"color": MUTED, "size": 10})
    fig.add_vline(x=cut, line={"color": AXIS, "width": 1, "dash": "dot"})
    fig.add_annotation(x=cut, y=0, yref="paper", text="Fit cutoff", showarrow=False, xanchor="right", xshift=-4,
                       yanchor="bottom", font={"color": MUTED, "size": 10})
    ticks = [v * m for m in (1, 10, 100, 1000) for v in (10, 20, 50)]
    fig.update_yaxes(type="log", title="Rate (bbl/d, mcf/d)", tickvals=ticks, tickformat=",.0f")
    fig.update_xaxes(range=[w.first_prod - timedelta(days=15), wl.AS_OF + timedelta(days=3 * 365 + 60)])
    fig.update_layout(
        margin={"l": 64, "r": 48, "t": 8, "b": 32}, hovermode="x unified", uirevision=w.name,
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2}},
    )
    return style_axes(fig)


def type_curve_chart(w):
    peers = [p for p in wl.WELLS if p.formation == w.formation]
    m, p10, p50, p90 = wl.type_curve(peers)
    color = FORMATION_COLOR[w.formation]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=np.concatenate([m, m[::-1]]), y=np.concatenate([p10, p90[::-1]]), fill="toself",
        fillcolor=rgba(color, 0.2), line={"width": 0}, hoverinfo="skip", name="P10–P90",
    ))
    fig.add_trace(go.Scatter(
        x=m, y=p50, mode="lines", name=f"{w.formation} P50", line={"color": color, "width": 2},
        customdata=np.column_stack([p90, p10]),
        hovertemplate="P50 %{y:,.0f} (P90 %{customdata[0]:,.0f} – P10 %{customdata[1]:,.0f})<extra></extra>",
    ))
    t, q = wl.monthly(w.oil)
    fig.add_trace(go.Scatter(
        x=(t // 30.4375 + 1)[:36], y=(q / w.lateral_ft * 1000)[:36], mode="lines+markers", name=w.name,
        line={"color": INK, "width": 2}, marker={"size": 8, "color": INK, "line": {"color": SURFACE, "width": 2}},
        hovertemplate="%{y:,.0f} bbl/d per 1,000 ft<extra>" + w.name + "</extra>",
    ))
    fig.update_yaxes(type="log", title="Oil, bbl/d per 1,000 ft", tickvals=[5, 10, 20, 50, 100, 200, 500])
    fig.update_xaxes(title="Months on production", range=[0, 37])
    fig.update_layout(
        margin={"l": 56, "r": 12, "t": 8, "b": 40}, hovermode="x unified", uirevision=w.name,
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2, "size": 11}},
    )
    return style_axes(fig)


def graph(graph_id, cls="graph"):
    return html.Div(
        dcc.Graph(id=graph_id, config={"displayModeBar": False, "responsive": True}, style={"height": "100%"}),
        className=cls,
    )


def card(title, *children, extra=None, **kwargs):
    return dmc.Paper(
        [dmc.Group([dmc.Text(title, className="card-title"), extra], justify="space-between", mb="sm", wrap="nowrap"),
         *children],
        className="card",
        **kwargs,
    )


def status_badge(status, size="sm"):
    level, icon = WELL_STATUS[status]
    return dmc.Badge(status, color=STATUS[level], variant="light", size=size, radius="sm",
                     leftSection=DashIconify(icon=icon, width=12), className="status-badge")


def kpi(label, value, unit, delta=None, sub=None, good_up=True):
    delta_el = None
    if delta is not None and not np.isnan(delta):
        up = delta >= 0
        good = up == good_up
        delta_el = dmc.Text(
            [DashIconify(icon="tabler:arrow-up-right" if up else "tabler:arrow-down-right", width=14),
             f"{delta:+.1%}"],
            className="kpi-delta " + ("good" if good else "bad"),
        )
    return html.Div(
        [
            dmc.Text(label, className="kpi-label"),
            dmc.Group([dmc.Text(value, className="kpi-value"), dmc.Text(unit, className="kpi-unit")], gap=6,
                      align="baseline", wrap="nowrap"),
            dmc.Group([delta_el, sub and dmc.Text(sub, className="kpi-sub")], gap=8, wrap="nowrap"),
        ],
        className="kpi",
    )


def kpis(formation):
    last = slice(wl.N_DAYS - 30, wl.N_DAYS)
    prior = slice(wl.N_DAYS - 60, wl.N_DAYS - 30)

    def total(stream, window):
        return sum(FIELD[f, stream][window].mean() for f in formations_in(formation))

    vals = {s: (total(s, last), total(s, prior)) for s in wl.STREAMS}
    oil, water = vals["Oil"][0], vals["Water"][0]
    shown = wells_in(formation)
    online = sum(w.stats["status"] != "Shut in" for w in shown)
    flagged = [w for w in shown if w.stats["status"] in ("Underperforming", "Shut in")]
    lost = sum(shortfall(w) for w in flagged)
    cum = sum(w.stats["cum_oil"] for w in shown)
    return [
        kpi("Oil", f"{oil:,.0f}", "bbl/d", vals["Oil"][0] / vals["Oil"][1] - 1, "vs prior 30 days"),
        kpi("Gas", f"{vals['Gas'][0] / 1000:,.1f}", "MMcf/d", vals["Gas"][0] / vals["Gas"][1] - 1),
        kpi("Water", f"{water:,.0f}", "bbl/d", vals["Water"][0] / vals["Water"][1] - 1,
            f"{water / (water + oil):.0%} water cut", good_up=False),
        kpi("Wells online", f"{online}", f"of {len(shown)}", sub=f"{cum / 1e6:,.2f} MMbbl oil to date"),
        kpi("Deferred oil", f"{lost:,.0f}", "bbl/d", sub=f"{len(flagged)} wells below forecast or shut in"),
    ]


def attention_list(formation, selected):
    flagged = [w for w in wells_in(formation) if w.stats["status"] in ("Underperforming", "Shut in")]
    flagged.sort(key=shortfall, reverse=True)
    if not flagged:
        return dmc.Text("Every well is within 15% of its decline forecast.", className="empty")
    items = []
    for w in flagged:
        s = w.stats
        items.append(html.Div(
            [
                dmc.Group([dmc.Text(w.name, className="att-name"), status_badge(s["status"], "xs")],
                          justify="space-between", wrap="nowrap"),
                dmc.Text(s["issue"], className="att-issue"),
                dmc.Group(
                    [dmc.Text(f"{s['oil']:,.0f} bbl/d", className="att-num"),
                     np.isnan(s["expected"]) or dmc.Text(f"forecast {s['expected']:,.0f}", className="att-sub"),
                     dmc.Text(f"−{shortfall(w):,.0f} bbl/d", className="att-lost")],
                    gap=8, wrap="nowrap",
                ),
            ],
            id={"type": "att", "name": w.name}, n_clicks=0,
            className="att-item" + (" selected" if w.name == selected else ""),
        ))
    return items


def grid_rows(formation):
    rows = []
    for w in wells_in(formation):
        s = w.stats
        rows.append({
            "well": w.name, "formation": w.formation, "status": s["status"], "days_on": s["days_on"],
            "oil": round(s["oil"], 1), "gas": round(s["gas"], 1), "wc": round(s["wc"] * 100, 1),
            "gor": round(s["gor"], 2) if not np.isnan(s["gor"]) else None,
            "variance": round(s["variance"] * 100, 1) if not np.isnan(s["variance"]) else None,
            "cum_oil": round(s["cum_oil"] / 1000, 1), "eur": round(s["eur"] / 1000), "lateral": w.lateral_ft,
        })
    return rows


def num(fmt):
    return {"function": f"params.value == null ? '–' : d3.format('{fmt}')(params.value)"}


COLUMNS = [
    {"field": "well", "headerName": "Well", "pinned": "left", "width": 110, "cellClass": "mono"},
    {"field": "formation", "headerName": "Formation", "width": 150,
     "cellRenderer": "FormationCell"},
    {"field": "status", "headerName": "Status", "width": 150, "cellRenderer": "StatusCell"},
    {"field": "oil", "headerName": "Oil bbl/d", "type": "numericColumn", "valueFormatter": num(",.0f"), "width": 105,
     "sort": "desc"},
    {"field": "variance", "headerName": "vs forecast", "type": "numericColumn", "width": 115,
     "valueFormatter": {"function": "params.value == null ? '–' : d3.format('+.0f')(params.value) + '%'"},
     "cellClassRules": {"neg": "params.value <= -15", "pos": "params.value >= 10"}},
    {"field": "gas", "headerName": "Gas mcf/d", "type": "numericColumn", "valueFormatter": num(",.0f"), "width": 110},
    {"field": "wc", "headerName": "Water cut", "type": "numericColumn", "width": 105,
     "valueFormatter": {"function": "d3.format('.0f')(params.value) + '%'"}},
    {"field": "gor", "headerName": "GOR mcf/bbl", "type": "numericColumn", "valueFormatter": num(".2f"), "width": 120},
    {"field": "cum_oil", "headerName": "Cum oil Mbbl", "type": "numericColumn", "valueFormatter": num(",.0f"),
     "width": 125},
    {"field": "eur", "headerName": "EUR Mbbl", "type": "numericColumn", "valueFormatter": num(",.0f"), "width": 105},
    {"field": "days_on", "headerName": "Days on", "type": "numericColumn", "valueFormatter": num(",.0f"), "width": 95},
    {"field": "lateral", "headerName": "Lateral ft", "type": "numericColumn", "valueFormatter": num(",.0f"),
     "width": 105},
]


def well_stats(w):
    s, f = w.stats, w.fit

    def item(label, value, sub=None):
        return html.Div([dmc.Text(label, className="stat-label"), dmc.Text(value, className="stat-value"),
                         sub and dmc.Text(sub, className="stat-sub")], className="stat")

    var = s["variance"]
    if f.get("borrowed"):
        fit_item = item("Decline", f"b {f['b']:.2f} · De {effective_decline(f):.0%}", "Formation median, too new to fit")
    else:
        fit_item = item("Arps fit", f"b {f['b']:.2f} · De {effective_decline(f):.0%}",
                        f"qi {f['qi']:,.0f} bbl/d · R² {f['r2']:.2f}")
    return [
        item("Oil, last 30 days", f"{fmt_rate(s['oil'])} bbl/d",
             f"{var:+.0%} vs forecast" if not np.isnan(var) else "Too new to judge"),
        item("IP30", f"{s['ip30']:,.0f} bbl/d" if not np.isnan(s["ip30"]) else "–", "Best 30-day average"),
        item("Cumulative oil", f"{s['cum_oil'] / 1000:,.0f} Mbbl", f"{s['cum_gas'] / 1e6:,.2f} Bcf gas"),
        item("Oil EUR", f"{s['eur'] / 1000:,.0f} Mbbl", f"{s['eur_per_ft']:.0f} bbl per ft of lateral"),
        fit_item,
        item("GOR · Water cut", "–" if np.isnan(s["gor"]) else f"{s['gor']:.2f} · {s['wc']:.0%}",
             "Last 30 days" if not np.isnan(s["gor"]) else "Not producing"),
    ]


header = html.Header(
    dmc.Group(
        [
            dmc.Group(
                [
                    html.Div(DashIconify(icon="tabler:droplet-filled", width=20), className="brand-mark"),
                    dmc.Stack([dmc.Text("Red Mesa Unit", className="brand-name"),
                               dmc.Text("Production by well", className="brand-sub")], gap=0),
                ],
                gap="sm", wrap="nowrap",
            ),
            dmc.Group(
                [
                    dmc.Stack([dmc.Text("Formation", className="ctl-label"),
                               dmc.SegmentedControl(id="formation", value="All", size="xs",
                                                    data=["All", *wl.FORMATIONS])], gap=2),
                    dmc.Stack([dmc.Text("Field chart", className="ctl-label"),
                               dmc.SegmentedControl(id="stream", value="Oil", size="xs", data=list(wl.STREAMS))],
                              gap=2),
                    dmc.Text(f"Data to {wl.AS_OF:%-d %b %Y}", className="asof"),
                ],
                gap="lg", align="flex-end", className="controls",
            ),
        ],
        justify="space-between", align="center", className="header-inner",
    ),
    className="header",
)

app.layout = dmc.MantineProvider(
    [
        dcc.Store(id="selected", data=DEFAULT_WELL),
        header,
        html.Main(
            [
                html.Div(id="kpis", className="kpis"),
                dmc.Grid(
                    [
                        dmc.GridCol(card("Field production", graph("field-chart"), id="field-card"),
                                    span={"base": 12, "lg": 8}),
                        dmc.GridCol(card("Needs attention", html.Div(id="attention", className="att-list"),
                                         extra=dmc.Text("Biggest shortfall first", className="card-hint")),
                                    span={"base": 12, "lg": 4}),
                        dmc.GridCol(card("Laterals", graph("map", "graph map"),
                                         extra=dmc.Text("Click a well", className="card-hint")),
                                    span={"base": 12, "lg": 5}),
                        dmc.GridCol(card(
                            "All wells",
                            dag.AgGrid(
                                id="grid", columnDefs=COLUMNS, rowData=[],
                                defaultColDef={"sortable": True, "resizable": True, "suppressMovable": True},
                                dashGridOptions={"theme": {"function": "prodTheme(themeQuartz)"},
                                                 "rowSelection": {"mode": "singleRow", "checkboxes": False,
                                                                  "enableClickSelection": True},
                                                 "getRowId": {"function": "params.data.well"},
                                                 "animateRows": False, "rowHeight": 36, "headerHeight": 36},
                                className="grid", style={"height": "100%"},
                            ),
                        ), span={"base": 12, "lg": 7}),
                    ],
                    gutter="md",
                ),
                dmc.Paper(
                    [
                        dmc.Group(
                            [
                                dmc.Group([dmc.Title(id="well-title", order=2, className="well-title"),
                                           html.Div(id="well-badges")], gap="sm", align="center"),
                                dmc.Text(id="well-meta", className="well-meta"),
                            ],
                            justify="space-between", align="center", mb="md",
                        ),
                        html.Div(id="well-stats", className="stats"),
                        dmc.Grid(
                            [
                                dmc.GridCol([dmc.Text("Rate vs time", className="card-title"),
                                             graph("rate-chart", "graph tall")], span={"base": 12, "lg": 8}),
                                dmc.GridCol([dmc.Text("Against the formation type curve", className="card-title"),
                                             graph("type-chart", "graph tall")], span={"base": 12, "lg": 4}),
                            ],
                            gutter="lg", mt="md",
                        ),
                    ],
                    className="card well-card",
                ),
                dmc.Text(
                    "All wells, pads and production volumes are synthetic. Forecasts are modified Arps declines "
                    f"fitted to monthly oil rates up to {wl.FIT_CUTOFF} days ago, with an {wl.D_MIN:.0%} per year "
                    f"terminal decline and an economic limit of {wl.ECON_LIMIT:.0f} bbl/d.",
                    className="foot",
                ),
            ],
            className="main",
        ),
    ],
    theme=THEME,
    forceColorScheme="light",
)


@app.callback(
    Output("kpis", "children"),
    Output("field-chart", "figure"),
    Output("grid", "rowData"),
    Input("formation", "value"),
    Input("stream", "value"),
)
def update_field(formation, stream):
    return kpis(formation), field_chart(formation, stream), grid_rows(formation)


@app.callback(
    Output("selected", "data"),
    Input("map", "clickData"),
    Input("grid", "cellClicked"),
    Input({"type": "att", "name": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_well(map_click, cell, _):
    trigger = ctx.triggered_id
    if trigger == "map" and map_click:
        cd = map_click["points"][0].get("customdata")
        return cd[0] if cd else dash.no_update
    if trigger == "grid" and cell:
        return cell["rowId"]
    if isinstance(trigger, dict) and ctx.triggered[0]["value"]:
        return trigger["name"]
    return dash.no_update


@app.callback(
    Output("map", "figure"),
    Output("attention", "children"),
    Output("grid", "selectedRows"),
    Input("formation", "value"),
    Input("selected", "data"),
)
def update_selection(formation, selected):
    return map_figure(formation, selected), attention_list(formation, selected), {"ids": [selected]}


@app.callback(
    Output("well-title", "children"),
    Output("well-badges", "children"),
    Output("well-meta", "children"),
    Output("well-stats", "children"),
    Output("rate-chart", "figure"),
    Output("type-chart", "figure"),
    Input("selected", "data"),
)
def update_well(name):
    w = wl.BY_NAME[name]
    s = w.stats
    badges = dmc.Group(
        [status_badge(s["status"]),
         dmc.Badge(w.formation, variant="outline", color="gray", size="sm", radius="sm",
                   leftSection=html.Span(className="swatch", style={"background": FORMATION_COLOR[w.formation]}))],
        gap=6,
    )
    meta = f"API {w.api} · Pad {w.pad} · {w.lateral_ft:,} ft lateral · First oil {w.first_prod:%-d %b %Y}"
    return w.name, badges, meta, well_stats(w), rate_chart(w), type_curve_chart(w)


if __name__ == "__main__":
    app.run(debug=True, dev_tools_ui=False, port=8051)
