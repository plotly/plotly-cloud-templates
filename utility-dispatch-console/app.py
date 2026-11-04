"""
Outage & Work Order Dispatch Console

A dispatcher's view of one shift at a made-up electric utility. Trouble calls
come in as outages while planned work orders wait in the same queue. Pick a job
to see who is affected and which crews could get there soonest, dispatch one,
and watch the crew drive out, switch customers back on and close the job. The
clock runs on its own; turn the storm on to see the queue fill faster than the
crews can clear it, or let auto-assign take the emergencies.

The territory, crews and calls are synthetic, see dispatch.py.
"""

import copy

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

import dispatch as dp

# Chart colors, kept in sync with assets/style.css
SURFACE = "#ffffff"
INK = "#14202b"
INK_2 = "#4a5866"
MUTED = "#7d8894"
GRID = "#e8ecf0"
LINE_OK = "#9aa6b2"
LINE_OUT = "#d0312d"
PRIORITY_COLOR = {1: "#d0312d", 2: "#ef7a12", 3: "#d9a400", 4: "#4f7cac"}
PRIORITY_SHORT = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}
CREW_COLOR = {"Available": "#178a52", "En route": "#2f6fde", "On site": "#7048e8"}
STATUS_BADGE = {
    "Unassigned": "red", "Dispatched": "blue", "On site": "violet", "Restored": "green", "Complete": "green",
}
SPEEDS = {"1": 1, "5": 5, "15": 15}  # sim minutes per tick (one tick a second)

FONT = "'Barlow', system-ui, sans-serif"
FONT_NUM = "'Barlow Condensed', 'Barlow', sans-serif"
THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": FONT_NUM},
    "primaryColor": "orange",
    "defaultRadius": "sm",
}

app = dash.Dash(
    __name__,
    title="Outage Dispatch Console",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap"
    ],
)
server = app.server

INITIAL = dp.initial_state()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mins(m):
    m = int(round(m))
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60:02d}"


def open_jobs(state):
    return [j for j in state["jobs"] if j["status"] not in ("Restored", "Complete")]


def sorted_queue(state, view):
    t = state["t"]
    jobs = open_jobs(state)
    if view == "outages":
        jobs = [j for j in jobs if j["kind"] == "outage"]
    elif view == "orders":
        jobs = [j for j in jobs if j["kind"] == "order"]
    # unassigned work floats to the top inside each priority
    return sorted(jobs, key=lambda j: (j["status"] != "Unassigned",) + dp.queue_order(j, t))


def effective_selection(state, selected):
    ids = {j["id"] for j in state["jobs"]}
    if selected in ids:
        return selected
    q = sorted_queue(state, "all")
    return q[0]["id"] if q else None


def priority_badge(p):
    return dmc.Badge(dp.PRIORITIES[p], color=PRIORITY_COLOR[p], variant="filled", size="sm", radius="xs",
                     className="prio-badge")


def status_badge(s):
    return dmc.Badge(s, color=STATUS_BADGE.get(s, "gray"), variant="light", size="sm", radius="xs")


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

def kpi(label, value, sub=None, tone=None):
    return html.Div(
        [html.Div(label, className="kpi-label"),
         html.Div(value, className="kpi-value"),
         html.Div(sub, className="kpi-sub") if sub else None],
        className=f"kpi {tone or ''}",
    )


def kpis(state):
    t = state["t"]
    out = dp.customers_out(state)
    hist = state["history"]
    ago = next((h[1] for h in reversed(hist) if h[0] <= t - 30), hist[0][1])
    delta = out - ago
    outages = [j for j in open_jobs(state) if j["kind"] == "outage"]
    p1 = sum(j["priority"] == 1 for j in outages)
    unassigned = [j for j in open_jobs(state) if j["status"] == "Unassigned"]
    ua_out = sum(j["kind"] == "outage" for j in unassigned)
    avail = sum(c["status"] == "Available" for c in state["crews"])
    responded = [j["arrive"] - j["created"] for j in state["jobs"]
                 if j["kind"] == "outage" and j["arrive"] is not None and j["arrive"] <= t and j["created"] >= 0]
    crit = sorted({c for j in outages for c in j["critical"]})
    saidi = state["cmi"] / dp.TOTAL_CUSTOMERS
    return [
        kpi("Customers out", f"{out:,}",
            f"{delta:+,} in 30 min · {out / dp.TOTAL_CUSTOMERS:.1%} of {dp.TOTAL_CUSTOMERS:,}",
            "bad" if delta > 0 else "good" if delta < 0 else None),
        kpi("Active outages", f"{len(outages)}", f"{p1} emergency (P1)", "bad" if p1 else None),
        kpi("Waiting for a crew", f"{len(unassigned)}", f"{ua_out} outages · {len(unassigned) - ua_out} work orders",
            "warn" if ua_out else None),
        kpi("Crews available", f"{avail} of {len(state['crews'])}",
            f"{sum(c['status'] == 'En route' for c in state['crews'])} en route · "
            f"{sum(c['status'] == 'On site' for c in state['crews'])} on site"),
        kpi("Avg response", mins(np.mean(responded)) if responded else "–", "Call to crew on site, today"),
        kpi("Critical facilities out", f"{len(crit)}", ", ".join(crit) if crit else "None", "bad" if crit else None),
        kpi("SAIDI today", f"{saidi:.2f} min", f"{state['cmi'] / 1e3:,.0f}k customer-minutes"),
    ]


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

def _lines(segments):
    lat, lon = [], []
    for seg in segments:
        lat += [p[0] for p in seg] + [None]
        lon += [p[1] for p in seg] + [None]
    return lat, lon


def map_figure(state, selected):
    jobs = open_jobs(state)
    dead = {}  # feeder -> first de-energized point on the main line
    for j in jobs:
        if j["kind"] == "outage" and j["main_line"] and j["out"] > 0:
            dead[j["feeder"]] = min(dead.get(j["feeder"], 99), j["idx"])
    live_segs, dead_segs = [], []
    for name, f in dp.FEEDERS.items():
        k = dead.get(name)
        if k is None:
            live_segs.append(f["pts"])
        else:
            if k > 0:
                live_segs.append(f["pts"][:k + 1])
            dead_segs.append(f["pts"][k:])

    fig = go.Figure()
    lat, lon = _lines(live_segs)
    fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="lines", line={"color": LINE_OK, "width": 2},
                                name="Energized feeder", hoverinfo="skip"))
    lat, lon = _lines(dead_segs)
    fig.add_trace(go.Scattermap(lat=lat or [None], lon=lon or [None], mode="lines",
                                line={"color": LINE_OUT, "width": 3.5}, name="De-energized", hoverinfo="skip"))

    # routes of crews on the road
    by_id = {j["id"]: j for j in state["jobs"]}
    routes = [[(c["lat"], c["lon"]), (by_id[c["job"]]["lat"], by_id[c["job"]]["lon"])]
              for c in state["crews"] if c["status"] == "En route"]
    lat, lon = _lines(routes)
    fig.add_trace(go.Scattermap(lat=lat or [None], lon=lon or [None], mode="lines",
                                line={"color": CREW_COLOR["En route"], "width": 2}, opacity=0.7,
                                name="Crew route", hoverinfo="skip"))

    fig.add_trace(go.Scattermap(
        lat=[p[0] for p in dp.SUBSTATIONS.values()], lon=[p[1] for p in dp.SUBSTATIONS.values()],
        mode="markers+text", text=list(dp.SUBSTATIONS), textposition="bottom right",
        textfont={"size": 10, "color": INK_2}, marker={"size": 11, "color": INK},
        name="Substation", hovertemplate="<b>%{text}</b> substation<extra></extra>",
    ))
    out_crit = {c for j in jobs for c in j["critical"]}
    fig.add_trace(go.Scattermap(
        lat=[c["pt"][0] for c in dp.CRITICAL], lon=[c["pt"][1] for c in dp.CRITICAL], mode="markers",
        marker={"size": 10, "color": ["#d0312d" if c["name"] in out_crit else "#0f8b8d" for c in dp.CRITICAL]},
        name="Critical facility", customdata=[[c["name"], c["kind"], "Out" if c["name"] in out_crit else "On"]
                                              for c in dp.CRITICAL],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} · power %{customdata[2]}<extra></extra>",
    ))

    sel = by_id.get(selected)
    if sel:
        fig.add_trace(go.Scattermap(lat=[sel["lat"]], lon=[sel["lon"]], mode="markers",
                                    marker={"size": 34, "color": "#ffcf33", "opacity": 0.55},
                                    hoverinfo="skip", showlegend=False))

    for p in (4, 3, 2, 1):
        group = [j for j in jobs if j["priority"] == p]
        if not group:
            continue
        size = [9 if j["kind"] == "order" else 10 + 3.2 * np.sqrt(j["out"]) ** 0.75 for j in group]
        fig.add_trace(go.Scattermap(
            lat=[j["lat"] for j in group], lon=[j["lon"] for j in group], mode="markers",
            marker={"size": size, "color": PRIORITY_COLOR[p],
                    "opacity": [0.95 if j["status"] == "Unassigned" else 0.5 for j in group]},
            name=dp.PRIORITIES[p],
            customdata=[["job", j["id"], j["type"], j["status"], j["out"], j["address"]] for j in group],
            hovertemplate="<b>%{customdata[1]}</b> · %{customdata[2]}<br>%{customdata[5]}"
                          "<br>%{customdata[4]:,} customers out · %{customdata[3]}<extra></extra>",
        ))

    for status, color in CREW_COLOR.items():
        group = [c for c in state["crews"] if c["status"] == status]
        if not group:
            continue
        fig.add_trace(go.Scattermap(
            lat=[c["lat"] for c in group], lon=[c["lon"] for c in group], mode="markers+text",
            text=[c["id"] for c in group], textposition="top center",
            textfont={"size": 10, "color": color},
            marker={"size": 12, "color": color},
            name=f"Crew {status.lower()}",
            customdata=[["crew", c["id"], c["lead"], c["skill"], c["job"] or "no job"] for c in group],
            hovertemplate="<b>%{customdata[1]}</b> · %{customdata[2]}<br>%{customdata[3]} · %{customdata[4]}"
                          "<extra></extra>",
        ))

    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        map={"style": "carto-positron", "center": {"lat": dp.CENTER[0], "lon": dp.CENTER[1]}, "zoom": 10.6},
        legend={"x": 0.01, "y": 0.99, "bgcolor": "rgba(255,255,255,0.88)", "font": {"size": 11, "color": INK_2},
                "bordercolor": GRID, "borderwidth": 1},
        uirevision="map", font={"family": FONT}, paper_bgcolor=SURFACE,
    )
    return fig


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

def job_card(j, t, selected):
    if j["kind"] == "outage":
        line3 = [html.B(f"{j['out']:,}"), f" out · {mins(t - j['created'])} ago"]
    else:
        late = j["due"] - t
        line3 = [f"Due {dp.clock(j['due'])}", html.Span(" · overdue" if late < 0 else
                                                         f" · {mins(late)} left", className="late" if late < 90 else "")]
    crew = None
    if j["crew"]:
        eta = f"ETA {dp.clock(j['arrive'])}" if j["status"] == "Dispatched" else \
            f"ETR {dp.clock(j['arrive'] + j['duration'])}"
        crew = html.Div([DashIconify(icon="tabler:truck", width=13), f" {j['crew']} · {eta}"], className="jc-crew")
    flags = []
    if j["hazard"]:
        flags.append(DashIconify(icon="tabler:bolt", width=14, className="flag-hazard"))
    if j["critical"]:
        flags.append(DashIconify(icon="tabler:building-hospital", width=14, className="flag-crit"))
    return html.Div(
        [
            html.Div(className="jc-bar", style={"background": PRIORITY_COLOR[j["priority"]]}),
            html.Div(
                [
                    html.Div([html.Span(PRIORITY_SHORT[j["priority"]], className="jc-prio",
                                        style={"color": PRIORITY_COLOR[j["priority"]]}),
                              html.Span(j["id"], className="jc-id"), *flags,
                              html.Span(j["status"], className=f"jc-status s-{j['status'].replace(' ', '-').lower()}")],
                             className="jc-top"),
                    html.Div(j["type"], className="jc-type"),
                    html.Div(f"{j['address']} · {j['feeder']}", className="jc-addr"),
                    html.Div(line3, className="jc-meta"),
                    crew,
                ],
                className="jc-body",
            ),
        ],
        id={"type": "job", "id": j["id"]},
        className="job-card" + (" selected" if j["id"] == selected else ""),
        n_clicks=0,
    )


def queue(state, view, selected):
    q = sorted_queue(state, view)
    if not q:
        return dmc.Text("Nothing in the queue.", className="empty")
    return [job_card(j, state["t"], selected) for j in q]


# ---------------------------------------------------------------------------
# Selected job
# ---------------------------------------------------------------------------

def stat(label, value):
    return html.Div([html.Div(label, className="st-label"), html.Div(value, className="st-value")], className="st")


def detail(state, jid):
    if jid is None:
        return dmc.Text("All clear. No open jobs.", className="empty")
    t = state["t"]
    j = next(x for x in state["jobs"] if x["id"] == jid)
    head = html.Div(
        [
            html.Div([html.Span(j["id"], className="dt-id"), priority_badge(j["priority"]), status_badge(j["status"])],
                     className="dt-head"),
            html.Div(j["type"], className="dt-type"),
            html.Div(f"{j['address']} · feeder {j['feeder']}" + (f" · device {j['device']}" if j["device"] else ""),
                     className="dt-addr"),
        ]
    )
    if j["kind"] == "outage":
        stats = [stat("Customers out", f"{j['out']:,}" + (f" of {j['customers']:,}" if j["out"] != j["customers"] else "")),
                 stat("Reported", f"{dp.clock(j['created'])} · {mins(t - j['created'])} ago"),
                 stat("Cause", j["cause"]), stat("Est. repair", mins(j["duration"]))]
    else:
        stats = [stat("Due by", dp.clock(j["due"])), stat("Est. work", mins(j["duration"])),
                 stat("Open for", f"{(t - j['created']) / 1440:.1f} days"), stat("Crew type", j["skills"][0])]
    alerts = []
    if j["hazard"]:
        alerts.append(dmc.Alert("Wire down / public hazard. Line crew must make safe before restoration.",
                                color="red", variant="light", icon=DashIconify(icon="tabler:bolt"), className="dt-alert"))
    if j["critical"]:
        alerts.append(dmc.Alert("Critical customers off: " + ", ".join(j["critical"]), color="orange", variant="light",
                                icon=DashIconify(icon="tabler:building-hospital"), className="dt-alert"))
    if j["note"] and not j["hazard"]:
        alerts.append(dmc.Text(j["note"], className="dt-note"))

    body = [head, html.Div(stats, className="dt-stats"), *alerts]

    if j["status"] in ("Dispatched", "On site"):
        crew = next(c for c in state["crews"] if c["id"] == j["crew"])
        etr = j["arrive"] + j["duration"]
        if j["status"] == "Dispatched":
            pct = (t - j["dispatched"]) / max(j["arrive"] - j["dispatched"], 1) * 100
            line = f"Driving · arrives {dp.clock(j['arrive'])} ({mins(j['arrive'] - t)})"
        else:
            pct = (t - j["arrive"]) / j["duration"] * 100
            line = f"On site since {dp.clock(j['arrive'])} · done about {dp.clock(etr)}"
        body.append(html.Div(
            [
                html.Div([DashIconify(icon="tabler:truck", width=18),
                          html.B(f"{crew['id']} · {crew['lead']}"), html.Span(f"{crew['skill']}, {crew['size']} people")],
                         className="as-head"),
                html.Div(line, className="as-line"),
                dmc.Progress(value=min(max(pct, 2), 100), color="blue" if j["status"] == "Dispatched" else "violet",
                             size="sm", mt=6),
                html.Div(f"Estimated restoration {dp.clock(etr)}" + (" · overtime" if etr > dp.SHIFT_END else ""),
                         className="as-etr"),
                dmc.Button("Recall crew", id={"type": "recall", "job": j["id"]}, variant="subtle", color="gray",
                           size="xs", leftSection=DashIconify(icon="tabler:arrow-back-up"), mt=6, n_clicks=0)
                if j["status"] == "Dispatched" else None,
            ],
            className="assigned",
        ))
    elif j["status"] == "Unassigned":
        recs = dp.recommend(state, jid)
        rows = []
        for i, r in enumerate(recs):
            tags = [html.Span(r["fit"], className="tag" + (" tag-good" if r["fit"] == "Preferred" else ""))]
            if r["overtime"]:
                tags.append(html.Span("Overtime", className="tag tag-warn"))
            rows.append(html.Div(
                [
                    html.Div([html.Span(className="dot", style={"background": CREW_COLOR[r["status"]]}),
                              html.B(r["crew"]), html.Span(f" {r['lead']}", className="rc-lead")], className="rc-name"),
                    html.Div([f"{r['skill']} · {r['size']}p · ", *tags], className="rc-skill"),
                    html.Div([html.Span(mins(r["eta"]), className="rc-eta"),
                              html.Span(f"{r['km']:.1f} km" if r["available"] else "after current job",
                                        className="rc-km")], className="rc-when"),
                    dmc.Button("Dispatch", id={"type": "dispatch", "job": jid, "crew": r["crew"]}, size="xs",
                               disabled=not r["available"], variant="filled" if i == 0 and r["available"] else "light",
                               n_clicks=0),
                ],
                className="rc-row",
            ))
        body.append(html.Div(
            [html.Div([html.Span("Crews that can take it"), html.Span("ETA to site", className="rc-h-eta")],
                      className="rc-header"),
             *(rows or [dmc.Text("No crew on shift has the skills for this job.", className="empty")])],
            className="recs",
        ))
    else:
        body.append(dmc.Text(f"{j['status']} at {dp.clock(j['done'])} by {j['crew']}.", className="dt-note"))
    return body


# ---------------------------------------------------------------------------
# Crew board and trend
# ---------------------------------------------------------------------------

def hour_axis(t0, t1):
    ticks = list(range(int(t0 // 60) * 60, int(t1) + 60, 60))
    return {"tickvals": ticks, "ticktext": [dp.clock(v) for v in ticks], "range": [t0, t1]}


def crew_board(state):
    t = state["t"]
    crews = state["crews"]
    t0 = max(0, t - 180)
    t1 = min(t0 + 540, dp.DAY_END)
    names = [f"{c['id']} {c['lead']}" for c in crews][::-1]
    label = {c["id"]: f"{c['id']} {c['lead']}" for c in crews}
    fig = go.Figure()
    for p in (1, 2, 3, 4):
        travel = {"y": [], "x": [], "base": [], "cd": []}
        work = {"y": [], "x": [], "base": [], "cd": [], "pattern": []}
        for c in crews:
            for e in c["log"]:
                if e["priority"] != p:
                    continue
                end = e["end"] if e["end"] is not None else max(e["eta_end"], t)
                travel["y"].append(label[c["id"]])
                travel["base"].append(e["start"])
                travel["x"].append(e["arrive"] - e["start"])
                travel["cd"].append([e["job"], "Driving", dp.clock(e["start"]), dp.clock(e["arrive"])])
                # work done so far is solid, the estimate still to go is striped
                split = end if e["end"] is not None else min(max(t, e["arrive"]), end)
                for a, b, pat, what in ((e["arrive"], split, "", "Working"), (split, end, "/", "Still to go (estimate)")):
                    if b - a <= 0:
                        continue
                    work["y"].append(label[c["id"]])
                    work["base"].append(a)
                    work["x"].append(b - a)
                    work["cd"].append([e["job"], what, dp.clock(a), dp.clock(b)])
                    work["pattern"].append(pat)
        if travel["y"]:
            fig.add_trace(go.Bar(y=travel["y"], x=travel["x"], base=travel["base"], orientation="h",
                                 marker={"color": PRIORITY_COLOR[p], "opacity": 0.3}, width=0.55, showlegend=False,
                                 customdata=travel["cd"], hovertemplate=HOVER))
            fig.add_trace(go.Bar(y=work["y"], x=work["x"], base=work["base"], orientation="h", name=dp.PRIORITIES[p],
                                 marker={"color": PRIORITY_COLOR[p], "pattern": {"shape": work["pattern"],
                                                                                   "fgcolor": "white", "size": 6}},
                                 width=0.55, customdata=work["cd"], hovertemplate=HOVER))
    fig.add_vline(x=t, line={"color": INK, "width": 1.5})
    fig.add_annotation(x=t, y=1.0, yref="paper", text="Now", showarrow=False, yanchor="bottom",
                       font={"size": 11, "color": INK})
    if t1 > dp.SHIFT_END:
        fig.add_vrect(x0=dp.SHIFT_END, x1=t1, fillcolor="#f4e9dc", opacity=0.6, line_width=0, layer="below")
        fig.add_annotation(x=dp.SHIFT_END, y=1.0, yref="paper", text="Overtime", showarrow=False, xanchor="left",
                           yanchor="bottom", font={"size": 11, "color": MUTED})
    fig.update_layout(
        barmode="overlay", margin={"l": 8, "r": 12, "t": 22, "b": 28},
        xaxis={**hour_axis(t0, t1), "gridcolor": GRID, "tickfont": {"color": MUTED, "size": 11}, "zeroline": False},
        yaxis={"categoryorder": "array", "categoryarray": names, "range": [-0.6, len(names) - 0.4],
               "tickfont": {"color": INK_2, "size": 11}, "automargin": True},
        legend={"orientation": "h", "y": -0.1, "yanchor": "top", "x": 0, "font": {"size": 11, "color": INK_2}},
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font={"family": FONT}, bargap=0.3,
        hoverlabel={"font": {"family": FONT}},
    )
    return fig


HOVER = "<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]}–%{customdata[3]}<extra></extra>"


def trend(state):
    h = np.array(state["history"], dtype=float)
    fig = go.Figure(go.Scatter(
        x=h[:, 0], y=h[:, 1], mode="lines", line={"color": LINE_OUT, "width": 2, "shape": "hv"},
        fill="tozeroy", fillcolor="rgba(208,49,45,0.12)",
        customdata=[dp.clock(v) for v in h[:, 0]],
        hovertemplate="%{customdata} · %{y:,} customers out<extra></extra>",
    ))
    t = state["t"]
    fig.update_layout(
        margin={"l": 8, "r": 12, "t": 6, "b": 26}, showlegend=False,
        xaxis={**hour_axis(0, max(t, 240)), "gridcolor": GRID, "tickfont": {"color": MUTED, "size": 11},
               "ticklabelstandoff": 6},
        yaxis={"gridcolor": GRID, "tickfont": {"color": MUTED, "size": 11}, "rangemode": "tozero",
               "tickformat": ",", "automargin": True},
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font={"family": FONT},
    )
    return fig


def event_log(state):
    return [html.Div([html.Span(dp.clock(t), className="ev-t"), html.Span(msg)], className="ev")
            for t, msg in state["events"][:18]]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def panel(title, children, extra=None, cls=""):
    return html.Section(
        [html.Div([html.H3(title, className="panel-title"), extra], className="panel-head"), children],
        className=f"panel {cls}",
    )


header = html.Header(
    [
        html.Div(
            [
                html.Div(DashIconify(icon="tabler:bolt", width=22), className="brand-mark"),
                html.Div([html.Div(dp.UTILITY, className="brand-name"),
                          html.Div("Outage & work order dispatch", className="brand-sub")]),
            ],
            className="brand",
        ),
        html.Div(
            [
                html.Div([html.Div(id="clock", className="clock"), html.Div("Wed 4 Nov 2026", className="clock-date")]),
                html.Div(id="storm-flag"),
            ],
            className="clock-wrap",
        ),
        html.Div(
            [
                dmc.ActionIcon(DashIconify(icon="tabler:player-pause-filled", width=18), id="play", size="lg",
                               variant="filled", color="dark", n_clicks=0),
                dmc.SegmentedControl(id="speed", value="5", size="xs",
                                     data=[{"label": "1 min/s", "value": "1"}, {"label": "5 min/s", "value": "5"},
                                           {"label": "15 min/s", "value": "15"}]),
                dmc.Button("Storm", id="storm", variant="light", color="gray", size="sm", n_clicks=0,
                           leftSection=DashIconify(icon="tabler:cloud-storm", width=16)),
                dmc.Button("Auto-assign", id="auto", size="sm", n_clicks=0,
                           leftSection=DashIconify(icon="tabler:route", width=16)),
                dmc.Tooltip(dmc.ActionIcon(DashIconify(icon="tabler:refresh", width=18), id="reset", size="lg",
                                           variant="subtle", color="gray", n_clicks=0),
                            label="Start the shift over"),
            ],
            className="controls",
        ),
    ],
    className="header",
)

app.layout = dmc.MantineProvider(
    [
        dcc.Store(id="state", data=INITIAL),
        dcc.Store(id="selected", data=None),
        dcc.Interval(id="tick", interval=1000),
        header,
        html.Main(
            [
                html.Div(id="kpis", className="kpis"),
                html.Div(
                    [
                        panel("Dispatch queue", html.Div(id="queue", className="queue"),
                              dmc.SegmentedControl(id="view", value="all", size="xs",
                                                   data=[{"label": "All", "value": "all"},
                                                         {"label": "Outages", "value": "outages"},
                                                         {"label": "Orders", "value": "orders"}]),
                              cls="queue-panel"),
                        panel("Service territory",
                              dcc.Graph(id="map", config={"displayModeBar": False, "scrollZoom": True},
                                        className="map"),
                              html.Span("Click an outage or work order", className="hint"), cls="map-panel"),
                        panel("Job", html.Div(id="detail", className="detail"), cls="detail-panel"),
                    ],
                    className="console",
                ),
                html.Div(
                    [
                        panel("Crew board", dcc.Graph(id="board", config={"displayModeBar": False}, className="board"),
                              html.Span("Faded = driving · solid = working · striped = still to go", className="hint"),
                              cls="board-panel"),
                        html.Div(
                            [
                                panel("Customers out",
                                      dcc.Graph(id="trend", config={"displayModeBar": False}, className="trend")),
                                panel("Activity", html.Div(id="events", className="events")),
                            ],
                            className="side-stack",
                        ),
                    ],
                    className="lower",
                ),
                html.Div(
                    "Cedar Valley Power, its network, crews and every call on this screen are made up. ETAs assume "
                    f"{dp.SPEED_KMH} km/h over road distance ({dp.ROAD_FACTOR}× straight line). Large main-line "
                    "outages get about half their customers switched back on when the crew arrives and isolates the fault.",
                    className="foot",
                ),
            ],
            className="main",
        ),
    ],
    theme=THEME,
    forceColorScheme="light",
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    Output("state", "data"),
    Input("tick", "n_intervals"),
    Input({"type": "dispatch", "job": ALL, "crew": ALL}, "n_clicks"),
    Input({"type": "recall", "job": ALL}, "n_clicks"),
    Input("auto", "n_clicks"),
    Input("storm", "n_clicks"),
    Input("reset", "n_clicks"),
    State("state", "data"),
    State("speed", "value"),
    prevent_initial_call=True,
)
def step(_, __, ___, ____, _____, ______, state, speed):
    trig = ctx.triggered_id
    if trig is None:
        return dash.no_update
    if trig == "reset":
        return copy.deepcopy(INITIAL)
    if trig == "tick":
        return dp.tick(state, SPEEDS[speed])
    if not ctx.triggered[0]["value"]:
        return dash.no_update  # a button that was just rendered
    if trig == "auto":
        return dp.auto_assign(state)
    if trig == "storm":
        state.update(storm=not state["storm"], storm_until=None)
        state["events"].insert(0, [state["t"], "Storm mode on" if state["storm"] else "Storm mode off"])
        return state
    if trig["type"] == "dispatch":
        return dp.dispatch(state, trig["job"], trig["crew"])
    if trig["type"] == "recall":
        return dp.recall(state, trig["job"])
    return dash.no_update


@app.callback(
    Output("tick", "disabled"),
    Output("play", "children"),
    Input("play", "n_clicks"),
)
def play_pause(n):
    paused = bool(n % 2)
    icon = "tabler:player-play-filled" if paused else "tabler:player-pause-filled"
    return paused, DashIconify(icon=icon, width=18)


@app.callback(
    Output("selected", "data"),
    Input("map", "clickData"),
    Input({"type": "job", "id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select(click, _):
    trig = ctx.triggered_id
    if trig == "map" and click:
        cd = click["points"][0].get("customdata")
        return cd[1] if cd and cd[0] == "job" else dash.no_update
    if isinstance(trig, dict) and ctx.triggered[0]["value"]:
        return trig["id"]
    return dash.no_update


@app.callback(
    Output("clock", "children"),
    Output("storm-flag", "children"),
    Output("storm", "variant"),
    Output("storm", "color"),
    Output("kpis", "children"),
    Output("map", "figure"),
    Output("queue", "children"),
    Output("detail", "children"),
    Output("board", "figure"),
    Output("trend", "figure"),
    Output("events", "children"),
    Input("state", "data"),
    Input("selected", "data"),
    Input("view", "value"),
)
def render(state, selected, view):
    sel = effective_selection(state, selected)
    storm = dmc.Badge("Thunderstorm warning", color="red", variant="filled", radius="xs",
                      leftSection=DashIconify(icon="tabler:cloud-storm", width=14)) if state["storm"] else None
    if state["t"] >= dp.DAY_END:
        storm = dmc.Badge("End of day", color="gray", radius="xs")
    return (
        dp.clock(state["t"]), storm,
        "filled" if state["storm"] else "light", "red" if state["storm"] else "gray",
        kpis(state), map_figure(state, sel), queue(state, view, sel), detail(state, sel),
        crew_board(state), trend(state), event_log(state),
    )


if __name__ == "__main__":
    app.run(debug=True, port=8052)
