"""
Peak Demand Outlook

Forecasts daily and hourly peak electricity demand for Lakeshore Power Pool, a
made-up summer-peaking grid, over the next 14 days. A 120-member weather
ensemble runs through the load model, so every forecast comes with a range and
a chance of running short of operating reserve. Pick a day on the outlook, the
weather chart or the risk calendar to see its hourly load against available
supply. Try scenarios: shift the heat wave, take power plants offline or call
demand response.

The load, weather and fleet are synthetic, see grid.py.
"""

from functools import lru_cache

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify
from plotly.subplots import make_subplots

import grid as gd

# Chart colors, kept in sync with assets/style.css
SURFACE = "#fdfdfc"
INK = "#111014"
INK_2 = "#4f4d57"
MUTED = "#8a8893"
GRID = "#ebeae6"
AXIS = "#c6c4bd"
FORECAST = "#2a78d6"
BAND = "rgba(42, 120, 214, 0.20)"
MEMBER = "rgba(42, 120, 214, 0.10)"
ACTUAL = "#9a98a1"
SELECT = "rgba(245, 179, 1, 0.16)"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
STATUS_TEXT = {"good": "#0a6e0a", "warning": "#8a5a00", "serious": "#a94418", "critical": "#b42323"}
# Fixed resource order; adjacent pairs checked for colorblind separation as a stack
RESOURCE_COLORS = dict(zip(gd.RESOURCES, ["#6250d6", "#eb6834", "#2a78d6", "#1baf7a", "#eda100", "#e87ba4"]))

FONT = "Manrope, system-ui, sans-serif"
NUM_FONT = "Space Grotesk, Manrope, sans-serif"
THEME = {"fontFamily": FONT, "headings": {"fontFamily": NUM_FONT}, "primaryColor": "yellow", "defaultRadius": "md"}

app = dash.Dash(
    __name__,
    title="Peak Demand Outlook",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800"
        "&family=Space+Grotesk:wght@500;600;700&display=swap"
    ],
)
server = app.server


# ---------- helpers ----------

@lru_cache(maxsize=64)
def run(temp_shift, outages, dr_mw):
    return gd.forecast(temp_shift, list(outages), dr_mw)


def scenario(temp, outages, dr):
    return run(float(temp or 0), tuple(sorted(outages or [])), float(dr or 0))


def fmt_mw(x):
    return f"{x:,.0f} MW".replace("-", "−")


def fmt_gw(x):
    return f"{x / 1000:.1f}"


def fmt_hour(h):
    h = int(h) % 24
    return f"{12 if h % 12 == 0 else h % 12} {'am' if h < 12 else 'pm'}"


def day_label(d, long=False):
    date = gd.FC_DATES[d]
    return date.strftime("%A, %B %-d" if long else "%a %b %-d")


def default_day(f):
    return int(np.argmax(f["risk"] + 1e-6 * f["peak_q"][1]))


def base_layout(fig, height, **kw):
    fig.update_layout(
        height=height, margin={"l": 8, "r": 12, "t": 8, "b": 8},
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2, "size": 12},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"family": FONT, "color": INK, "size": 12}},
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"size": 12, "color": INK_2},
                "bgcolor": "rgba(0,0,0,0)"},
        **kw,
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, ticks="outside", ticklen=4,
                     tickfont={"color": MUTED}, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont={"color": MUTED}, title_font={"color": MUTED, "size": 11})
    return fig


# ---------- figures ----------

def outlook_figure(f, sel):
    """Daily peak: last two weeks of actuals, 14-day forecast with 80% range, and headroom below."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32], vertical_spacing=0.07)
    hist_x = gd.HIST_DATES[-14:]
    hist_y = gd.HIST_DAILY_PEAK[-14:]
    p10, p50, p90 = f["peak_q"]
    x = gd.FC_DATES
    hours = [fmt_hour(h) for h in f["peak_hour"]]

    fig.add_trace(go.Scatter(
        x=hist_x, y=hist_y, name="Actual peak", mode="lines+markers", line={"color": ACTUAL, "width": 2},
        marker={"size": 6, "color": ACTUAL}, customdata=[fmt_hour(h) for h in gd.HIST_PEAK_HOUR[-14:]],
        hovertemplate="%{x|%a %b %-d}<br>Actual peak <b>%{y:,.0f} MW</b> at %{customdata}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=x, y=p90 - p10, base=p10, name="80% range", marker={"color": BAND, "cornerradius": 4},
        width=86_400_000 * 0.42, customdata=np.stack([p10, p90], axis=1),
        hovertemplate="%{x|%a %b %-d}<br>80% range %{customdata[0]:,.0f} – %{customdata[1]:,.0f} MW<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=x, y=p50, name="Forecast peak (median)", mode="lines+markers", line={"color": FORECAST, "width": 2},
        marker={"size": 8, "color": FORECAST, "line": {"color": SURFACE, "width": 2}}, customdata=hours,
        hovertemplate="%{x|%a %b %-d}<br>Forecast peak <b>%{y:,.0f} MW</b> around %{customdata}<extra></extra>",
    ), row=1, col=1)
    fig.add_hline(y=gd.SEASON_RECORD, line={"color": INK_2, "width": 1, "dash": "dot"}, row=1, col=1)
    fig.add_annotation(x=hist_x[0], y=gd.SEASON_RECORD, text=f"All-time peak {gd.SEASON_RECORD:,} MW",
                       showarrow=False, xanchor="left", yanchor="bottom", font={"size": 11, "color": INK_2},
                       row=1, col=1)

    # headroom at the tightest hour, colored by alert level
    lv = [gd.level(r) for r in f["risk"]]
    fig.add_trace(go.Bar(
        x=x, y=f["margin"], name="Headroom", showlegend=False,
        marker={"color": [STATUS[c] for _, c, _ in lv], "cornerradius": 4}, width=86_400_000 * 0.62,
        customdata=np.stack([[fmt_hour(h) for h in f["tight_hour"]], [n for n, _, _ in lv],
                             [f"{r:.0%}" for r in f["risk"]]], axis=1),
        hovertemplate="%{x|%a %b %-d}<br>Headroom <b>%{y:,.0f} MW</b> at %{customdata[0]}"
                      "<br>%{customdata[1]} · %{customdata[2]} chance of a reserve shortfall<extra></extra>",
    ), row=2, col=1)
    fig.add_hline(y=0, line={"color": AXIS, "width": 1}, row=2, col=1)

    d = gd.FC_DATES[sel]
    for r in (1, 2):
        fig.add_vrect(x0=d - gd.dt.timedelta(hours=14), x1=d + gd.dt.timedelta(hours=14),
                      fillcolor=SELECT, line_width=0, layer="below", row=r, col=1)
    edge = gd.FC_DATES[0] - gd.dt.timedelta(hours=12)
    fig.add_vline(x=edge, line={"color": AXIS, "width": 1})
    fig.add_annotation(x=edge, y=1, yref="paper", text="Forecast →", showarrow=False, xanchor="left",
                       yanchor="top", xshift=6, font={"size": 11, "color": MUTED})

    base_layout(fig, 400, bargap=0, hovermode="closest", clickmode="event")
    fig.update_yaxes(title="Daily peak, MW", tickformat=",", row=1, col=1)
    fig.update_yaxes(title="Headroom, MW", tickformat=",", row=2, col=1)
    fig.update_xaxes(tickformat="%b %-d", dtick=86_400_000 * 2, row=2, col=1)
    lo = min(hist_y.min(), p10.min())
    fig.update_yaxes(range=[lo - 800, max(p90.max(), gd.SEASON_RECORD) + 600], row=1, col=1)
    return fig


def hourly_figure(f, sel, view):
    hrs = gd.FC_HOURS[sel * 24:(sel + 1) * 24]
    q = f["q"][:, sel]
    limit = f["limit"][sel]
    fig = go.Figure()
    if view == "supply":
        stack = f["stacks"][sel]
        for name in gd.RESOURCES:
            fig.add_trace(go.Scatter(
                x=hrs, y=stack[name], name=name, stackgroup="supply", mode="lines",
                line={"width": 0.5, "color": SURFACE}, fillcolor=RESOURCE_COLORS[name],
                hovertemplate=f"{name} %{{y:,.0f}} MW<extra></extra>",
            ))
        fig.add_trace(go.Scatter(x=hrs, y=q[2], name="Load, 1-in-10 high", mode="lines",
                                 line={"color": INK, "width": 1.5, "dash": "dot"},
                                 hovertemplate="Load, 1-in-10 high %{y:,.0f} MW<extra></extra>"))
        fig.add_trace(go.Scatter(x=hrs, y=q[1], name="Load, median", mode="lines",
                                 line={"color": INK, "width": 2.5},
                                 hovertemplate="Load, median %{y:,.0f} MW<extra></extra>"))
        base_layout(fig, 340, hovermode="x unified")
        fig.update_yaxes(title="MW", tickformat=",", rangemode="tozero")
    else:
        members = f["load"][:40, sel]
        for i, m in enumerate(members):
            fig.add_trace(go.Scatter(x=hrs, y=m, mode="lines", line={"color": MEMBER, "width": 1},
                                     hoverinfo="skip", showlegend=i == 0, name="Ensemble members",
                                     legendgroup="members"))
        fig.add_trace(go.Scatter(x=list(hrs) + list(hrs)[::-1], y=list(q[2]) + list(q[0])[::-1], fill="toself",
                                 fillcolor=BAND, line={"width": 0}, name="80% range", hoverinfo="skip"))
        if f["dr_days"][sel]:
            before = np.median(f["load_before"][:, sel], axis=0)
            fig.add_trace(go.Scatter(x=hrs, y=before, name="Before demand response", mode="lines",
                                     line={"color": MUTED, "width": 1.5, "dash": "dot"},
                                     hovertemplate="Before demand response %{y:,.0f} MW<extra></extra>"))
        fig.add_trace(go.Scatter(x=hrs, y=q[1], name="Forecast (median)", mode="lines",
                                 line={"color": FORECAST, "width": 2.5}, customdata=np.stack([q[0], q[2]], axis=1),
                                 hovertemplate="Forecast %{y:,.0f} MW<br>80% range %{customdata[0]:,.0f} – "
                                               "%{customdata[1]:,.0f} MW<extra></extra>"))
        fig.add_trace(go.Scatter(x=hrs, y=limit, name="Supply less reserve", mode="lines",
                                 line={"color": STATUS["critical"], "width": 1.5, "dash": "dash", "shape": "hv"},
                                 hovertemplate="Supply less reserve %{y:,.0f} MW<extra></extra>"))
        t = int(f["tight_hour"][sel])
        m = f["margin"][sel]
        fig.add_trace(go.Scatter(x=[hrs[t]], y=[q[1][t]], mode="markers", showlegend=False, hoverinfo="skip",
                                 marker={"size": 10, "color": FORECAST, "line": {"color": SURFACE, "width": 2}}))
        fig.add_annotation(x=hrs[t], y=q[1][t], ax=-40, ay=-34, arrowcolor=AXIS, arrowwidth=1,
                           text=f"Tightest at {fmt_hour(t)}<br><b>{fmt_mw(abs(m))} {'short' if m < 0 else 'spare'}</b>",
                           font={"size": 11, "color": INK}, bgcolor="rgba(253,253,252,0.85)", align="right")
        base_layout(fig, 340, hovermode="x unified")
        lo = min(q[0].min(), members.min())
        fig.update_yaxes(title="MW", tickformat=",", range=[lo - 600, max(q[2].max(), limit.max()) + 600])
    fig.update_xaxes(tickformat="%-I %p", dtick=3 * 3_600_000, hoverformat="%-I %p")
    return fig


def sensitivity_figure(f, sel):
    """Daily peak against the day's high temperature: history, fitted curve and the forecast days."""
    t_hist, y_hist = gd.HIST_TMAX, gd.HIST_DAILY_PEAK
    coef = np.polyfit(t_hist, y_hist, 2)
    t_fc = f["tmax_q"][1]
    p10, p50, p90 = f["peak_q"]
    xs = np.linspace(min(t_hist.min(), f["tmax_q"][0].min()), max(t_hist.max(), f["tmax_q"][2].max()), 60)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t_hist, y=y_hist, mode="markers", name="Past 120 days",
        marker={"size": 7, "color": "rgba(138, 136, 147, 0.45)", "line": {"color": SURFACE, "width": 1}},
        text=[d.strftime("%a %b %-d") for d in gd.HIST_DATES],
        hovertemplate="%{text}<br>High %{x:.0f}°F · peak %{y:,.0f} MW<extra></extra>",
    ))
    fig.add_trace(go.Scatter(x=xs, y=np.polyval(coef, xs), mode="lines", name="Trend", hoverinfo="skip",
                             line={"color": MUTED, "width": 1.5}))
    fig.add_trace(go.Scatter(
        x=t_fc, y=p50, mode="markers", name="Forecast days",
        marker={"size": 9, "color": FORECAST, "line": {"color": SURFACE, "width": 2}},
        error_x={"type": "data", "symmetric": False, "array": f["tmax_q"][2] - t_fc,
                 "arrayminus": t_fc - f["tmax_q"][0], "color": BAND.replace("0.20", "0.55"), "thickness": 1.2,
                 "width": 0},
        error_y={"type": "data", "symmetric": False, "array": p90 - p50, "arrayminus": p50 - p10,
                 "color": BAND.replace("0.20", "0.55"), "thickness": 1.2, "width": 0},
        customdata=list(range(gd.FC_DAYS)), text=[day_label(d) for d in range(gd.FC_DAYS)],
        hovertemplate="%{text}<br>High %{x:.0f}°F · peak %{y:,.0f} MW<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[t_fc[sel]], y=[p50[sel]], mode="markers+text", showlegend=False, hoverinfo="skip",
        marker={"size": 14, "color": FORECAST, "line": {"color": "#f5b301", "width": 3}},
        text=[gd.FC_DATES[sel].strftime("%b %-d")], textposition="middle left",
        textfont={"size": 11, "color": INK},
    ))
    fig.add_hline(y=gd.SEASON_RECORD, line={"color": INK_2, "width": 1, "dash": "dot"})
    base_layout(fig, 340, hovermode="closest", clickmode="event")
    fig.update_xaxes(title="Daily high temperature, °F", ticksuffix="°", title_font={"color": MUTED, "size": 11})
    fig.update_yaxes(title="Daily peak, MW", tickformat=",")
    return fig


def hourly_hint(f, sel, view):
    name, _, _ = gd.level(f["risk"][sel])
    if view == "supply":
        return f"{day_label(sel, long=True)} · available supply by resource. Solar fades after 6 pm, batteries run 5–9 pm."
    return (f"{day_label(sel, long=True)} · {name} · {f['risk'][sel]:.0%} of weather scenarios cross "
            "the reserve line")


# ---------- components ----------

def card(title, body, hint=None, right=None, hint_id=None, **kwargs):
    hint_el = dmc.Text(hint, className="card-hint", **({"id": hint_id} if hint_id else {}))
    head = dmc.Group([dmc.Stack([dmc.Text(title, className="card-title"), hint_el], gap=2), right],
                     justify="space-between", align="flex-start", className="card-head")
    return dmc.Paper([head, body], className="card", **kwargs)


def kpi(label, value, sub, icon, tone=None):
    return dmc.Paper([
        dmc.Group([DashIconify(icon=icon, width=16, className="kpi-icon"), dmc.Text(label, className="kpi-label")],
                  gap=6),
        dmc.Text(value, className=f"kpi-value {tone or ''}"),
        dmc.Text(sub, className="kpi-sub"),
    ], className="kpi")


def level_badge(risk):
    name, color, icon = gd.level(risk)
    return html.Span([DashIconify(icon=icon, width=14), name], className=f"level level-{color}")


def risk_table(f, sel):
    head = html.Thead(html.Tr([html.Th(c) for c in [
        "Day", "High °F", "Peak forecast", "Peak hour", "Headroom at tightest hour", "Shortfall chance", "Alert"]]))
    rows = []
    for d in range(gd.FC_DAYS):
        t10, t50, t90 = f["tmax_q"][:, d]
        p10, p50, p90 = f["peak_q"][:, d]
        m = f["margin"][d]
        dr = f["dr_days"][d]
        rows.append(html.Tr([
            html.Td([html.Span(day_label(d), className="day"),
                     dr and html.Span([DashIconify(icon="tabler:plug-connected-x", width=12), "DR called"],
                                      className="dr-tag")]),
            html.Td([html.Span(f"{t50:.0f}°", className="num strong"),
                     html.Span(f" {t10:.0f}–{t90:.0f}", className="num range")]),
            html.Td([html.Span(f"{p50:,.0f}", className="num strong"),
                     html.Span(f" {fmt_gw(p10)}–{fmt_gw(p90)} GW", className="num range")]),
            html.Td(fmt_hour(f["peak_hour"][d]), className="num"),
            html.Td([html.Span(fmt_mw(m), className=f"num {'neg' if m < 0 else ''}"),
                     html.Span(f" at {fmt_hour(f['tight_hour'][d])}", className="range")]),
            html.Td(html.Div([html.Div(html.Div(className="risk-fill", style={"width": f"{f['risk'][d] * 100:.0f}%"}),
                                       className="risk-track"),
                              html.Span(f"{f['risk'][d]:.0%}", className="num")], className="risk-cell")),
            html.Td(level_badge(f["risk"][d])),
        ], id={"type": "day-row", "index": d}, n_clicks=0, className="row-selected" if d == sel else None))
    return html.Div(html.Table([head, html.Tbody(rows)], className="risk-table"), className="table-wrap")


# ---------- layout ----------

def unit_checkbox(u):
    note = " · forced outage since Jul 11" if u.id in gd.DEFAULT_OUTAGES else ""
    return dmc.Checkbox(value=u.id, color="yellow", size="xs", label=html.Span([
        html.Span(u.name), html.Span(f"{u.mw:,.0f} MW{note}", className="unit-mw")], className="unit-label"))


sidebar = dmc.Stack([
    dmc.Group([
        html.Div(DashIconify(icon="tabler:bolt", width=22), className="brand-mark"),
        dmc.Stack([dmc.Text("Lakeshore Power Pool", className="brand-name"),
                   dmc.Text("Grid operations · forecasting", className="brand-sub")], gap=0),
    ], gap=10, wrap="nowrap"),

    dmc.Text("Scenario", className="side-section"),
    dmc.Stack([
        dmc.Group([dmc.Text("Heat wave adjustment", className="side-label"),
                   dmc.Text("±0°F", id="temp-label", className="side-value")], justify="space-between"),
        dmc.Slider(id="temp", min=-4, max=4, step=1, value=0, color="yellow", size="sm", label=None,
                   marks=[{"value": v, "label": f"{v:+d}°" if v else "0"} for v in (-4, -2, 0, 2, 4)],
                   className="side-slider"),
        dmc.Text("Shifts every member of the weather ensemble hotter or cooler.", className="side-help"),
    ], gap=6),

    dmc.Stack([
        dmc.Group([dmc.Text("Demand response", className="side-label"),
                   dmc.Text("Off", id="dr-label", className="side-value")], justify="space-between"),
        dmc.Slider(id="dr", min=0, max=1000, step=100, value=0, color="yellow", size="sm", label=None,
                   marks=[{"value": v, "label": f"{v:,}" if v else "Off"} for v in (0, 500, 1000)],
                   className="side-slider"),
        dmc.Text("MW of load cut 3–10 pm on days at Watch or above.", className="side-help"),
    ], gap=6),

    dmc.Stack([
        dmc.Text("Units offline", className="side-label"),
        dmc.CheckboxGroup(dmc.Stack([unit_checkbox(u) for u in gd.UNITS], gap=7), id="outages",
                          value=gd.DEFAULT_OUTAGES),
        dmc.Text("Reserve covers the largest unit still online plus 3% of load.", className="side-help"),
    ], gap=8),

    dmc.Button("Reset scenario", id="reset", variant="subtle", color="gray", size="xs",
               leftSection=DashIconify(icon="tabler:refresh", width=14), className="reset"),

    html.Div([
        dmc.Text("How this works", className="side-label"),
        dmc.Text(f"{gd.ENSEMBLE} weather scenarios, each run through a load model fit on hourly history. "
                 "Ranges are the 10th to 90th percentile. All data is synthetic.", className="side-help"),
    ], className="side-foot"),
], gap=22, className="sidebar-inner")

header = dmc.Group([
    dmc.Group([
        dmc.Burger(id="burger", size="sm", hiddenFrom="sm", opened=False),
        dmc.Stack([
            html.H1("Peak Demand Outlook", className="title"),
            dmc.Text(f"Hourly system load, {day_label(0)} to {day_label(gd.FC_DAYS - 1)}", className="subtitle"),
        ], gap=2),
    ], gap=12, wrap="nowrap"),
    dmc.Group([
        dmc.Badge(f"Actuals through {gd.AS_OF.strftime('%b %-d, 11 pm')}", variant="outline", color="gray",
                  radius="sm", className="badge"),
        dmc.Badge(f"{gd.ENSEMBLE}-member ensemble", variant="outline", color="gray", radius="sm", className="badge"),
    ], gap=8),
], justify="space-between", align="flex-end", className="header")

main = dmc.Stack([
    header,
    html.Div(id="kpis", className="kpi-row"),
    card("Daily peak outlook", dcc.Graph(id="outlook", config={"displayModeBar": False}),
         hint="Median forecast with the 80% range. Bars below show headroom, colored by alert level, between load and supply "
              "less reserve at each day's tightest hour. Click a day for the hourly view."),
    dmc.Grid([
        dmc.GridCol(card(
            "Hourly load", dcc.Graph(id="hourly", config={"displayModeBar": False}), hint_id="hourly-hint",
            right=dmc.SegmentedControl(id="view", value="load", size="xs", data=[
                {"value": "load", "label": "Load vs limit"}, {"value": "supply", "label": "Supply stack"}]),
        ), span={"base": 12, "lg": 7}),
        dmc.GridCol(card(
            "Weather sensitivity", dcc.Graph(id="sensitivity", config={"displayModeBar": False}),
            hint="Each degree on a hot day adds about 300 MW. Whiskers show the forecast's range.",
        ), span={"base": 12, "lg": 5}),
    ], gutter="md"),
    card("Peak risk calendar", html.Div(id="table"),
         hint="Shortfall chance: share of weather scenarios where load eats into operating reserve at any hour."),
], gap="md", className="main")

app.layout = dmc.MantineProvider(
    dmc.AppShell([
        dmc.AppShellNavbar(sidebar, className="sidebar"),
        dmc.AppShellMain(main),
        dcc.Store(id="day", data=default_day(scenario(0, gd.DEFAULT_OUTAGES, 0))),
    ], navbar={"width": 300, "breakpoint": "sm", "collapsed": {"mobile": True}}, id="shell", padding=0),
    theme=THEME,
)


# ---------- callbacks ----------

@app.callback(Output("shell", "navbar"), Input("burger", "opened"), State("shell", "navbar"))
def toggle_navbar(opened, navbar):
    navbar["collapsed"] = {"mobile": not opened}
    return navbar


@app.callback(Output("temp", "value"), Output("dr", "value"), Output("outages", "value"),
              Input("reset", "n_clicks"), prevent_initial_call=True)
def reset(_):
    return 0, 0, gd.DEFAULT_OUTAGES


@app.callback(Output("temp-label", "children"), Output("dr-label", "children"),
              Input("temp", "value"), Input("dr", "value"))
def labels(temp, dr):
    return (f"{temp:+d}°F" if temp else "±0°F"), (f"{dr:,} MW" if dr else "Off")


@app.callback(
    Output("day", "data"),
    Input("outlook", "clickData"), Input("sensitivity", "clickData"),
    Input({"type": "day-row", "index": ALL}, "n_clicks"),
    State("day", "data"), prevent_initial_call=True,
)
def pick_day(outlook_click, sens_click, _rows, current):
    trig = ctx.triggered_id
    if isinstance(trig, dict):
        if not ctx.triggered[0]["value"]:
            return dash.no_update  # rows re-rendered, not clicked
        return trig["index"]
    click = outlook_click if trig == "outlook" else sens_click
    if not click:
        return dash.no_update
    pt = click["points"][0]
    if trig == "sensitivity":
        return pt["customdata"] if isinstance(pt.get("customdata"), int) else dash.no_update
    date = str(pt["x"])[:10]
    days = [d.isoformat() for d in gd.FC_DATES]
    return days.index(date) if date in days else current


@app.callback(
    Output("kpis", "children"), Output("outlook", "figure"), Output("hourly", "figure"),
    Output("sensitivity", "figure"), Output("table", "children"), Output("hourly-hint", "children"),
    Input("temp", "value"), Input("outages", "value"), Input("dr", "value"),
    Input("day", "data"), Input("view", "value"),
)
def render(temp, outages, dr, sel, view):
    f = scenario(temp, outages, dr)
    p10, p50, p90 = f["peak_q"]
    top = int(np.argmax(p50))
    tight = int(np.argmin(f["margin"]))
    m = f["margin"][tight]
    names = [gd.level(r)[0] for r in f["risk"]]
    n_em, n_warn = names.count("Emergency"), names.count("Warning")
    alert_sub = " · ".join(s for s in [n_em and f"{n_em} Emergency", n_warn and f"{n_warn} Warning",
                                       names.count("Watch") and f"{names.count('Watch')} Watch"] if s)
    dr_days = int(f["dr_days"].sum())
    kpis = [
        kpi("Forecast peak", fmt_mw(p50[top]),
            f"{day_label(top)} around {fmt_hour(f['peak_hour'][top])} · range {fmt_gw(p10[top])}–{fmt_gw(p90[top])} GW",
            "tabler:chart-arrows-vertical"),
        kpi("Tightest hour", f"{fmt_mw(abs(m))} {'short' if m < 0 else 'spare'}",
            f"{day_label(tight)} at {fmt_hour(f['tight_hour'][tight])}, against supply less reserve",
            "tabler:gauge", "neg" if m < 0 else "pos"),
        kpi("Days on alert", f"{n_em + n_warn} of {gd.FC_DAYS}",
            (alert_sub or "No Watch days") + (f" · DR called on {dr_days}" if dr_days else ""),
            "tabler:alert-triangle", "neg" if n_em else None),
        kpi("Chance of a new all-time peak", f"{f['new_record']:.0%}",
            f"Record {gd.SEASON_RECORD:,} MW, set {gd.RECORD_DATE}", "tabler:trophy"),
    ]
    return (kpis, outlook_figure(f, sel), hourly_figure(f, sel, view), sensitivity_figure(f, sel),
            risk_table(f, sel), hourly_hint(f, sel, view))


if __name__ == "__main__":
    app.run(debug=True)
