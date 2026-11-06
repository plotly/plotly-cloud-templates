"""
Screening Plate QC

Quality control review for a high-throughput screening campaign: 72 assay plates
of 384 wells read over six runs. Every plate that breaks a QC rule lands in a
review queue; open one to see its plate map and why it was flagged, then accept
it, send it for a re-run or reject it.

The screening data is synthetic, see screening.py.
"""

import time

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash._hooks import HooksManager
from dash_iconify import DashIconify

import screening as sc

# Chart colors, kept in sync with assets/style.css
SURFACE = "#ffffff"
INK = "#0b0b0b"
MUTED = "#808782"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "critical": "#d03b3b"}
PLATE_STATUS = {
    "Pass": ("good", "tabler:circle-check"),
    "Review": ("warning", "tabler:alert-triangle"),
    "Fail": ("critical", "tabler:circle-x"),
}
DECISIONS = {
    "Pending": ("gray", "tabler:clock"),
    "Accepted": ("teal", "tabler:check"),
    "Re-run": ("orange", "tabler:refresh"),
    "Rejected": ("red", "tabler:ban"),
}
SEQ_BLUE = [[0, "#f0f5fc"], [0.25, "#b7d3f6"], [0.5, "#6da7ec"], [0.75, "#2a78d6"], [1, "#104281"]]

FONT = "'Public Sans', system-ui, sans-serif"
THEME = {"fontFamily": FONT, "headings": {"fontFamily": FONT}, "primaryColor": "teal", "defaultRadius": "md"}

# Skip installed Dash plugins (such as the Plotly Studio Embedded chat) so the
# app renders on its own. Dash loads them once per process, on first app init
HooksManager._registered = True

app = dash.Dash(
    __name__,
    title="Screening Plate QC",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
    ],
)
server = app.server

RERUN_SECONDS = 15  # how long the lab takes to re-run a plate, shortened for the demo


def decision_of(pid, decisions):
    return decisions.get(pid, {}).get("decision", "Pending")


def is_reread(pid, decisions):
    return bool(decisions.get(pid, {}).get("reread"))


def current(pid, decisions):
    """The latest reading of a plate: the re-read once it is back from the lab, else the first read."""
    return sc.REREADS[pid] if is_reread(pid, decisions) else sc.BY_ID[pid]


def in_lab(decisions):
    """Plates sent for a re-run that haven't come back yet, with the time they're due."""
    return {pid: d["back_at"] for pid, d in decisions.items() if d.get("decision") == "Re-run" and d.get("back_at")}


def to_review(decisions):
    """Flagged plates nobody has decided on yet: re-reads just back from the lab, then failures, then worst Z′."""
    pending = [current(p.plate_id, decisions) for p in sc.PLATES
               if p.status != "Pass" and decision_of(p.plate_id, decisions) == "Pending"]
    return sorted(pending, key=lambda p: (not p.rerun, p.status != "Fail", p.stats["z"]))


DEFAULT_PLATE = to_review(sc.INITIAL_DECISIONS)[0].plate_id


# ---------------------------------------------------------------- plate map

def plate_map(p):
    role = np.full((sc.N_ROWS, sc.N_COLS), "Compound", dtype=object)
    role[:, sc.HIGH_COLS] = "DMSO control"
    role[:, sc.LOW_COLS] = "Reference inhibitor"
    cd = np.dstack([
        [[sc.well_name(r, c) for c in range(sc.N_COLS)] for r in range(sc.N_ROWS)],
        np.where(p.compounds == "", role, p.compounds),
    ])
    fig = go.Figure(go.Heatmap(
        z=p.pct, x=list(range(1, sc.N_COLS + 1)), y=sc.ROWS, colorscale=SEQ_BLUE, zmin=-20, zmax=100,
        xgap=2, ygap=2, customdata=cd,
        colorbar={"title": {"text": "% inhibition", "side": "right", "font": {"size": 11, "color": MUTED}},
                  "thickness": 10, "tickfont": {"size": 10, "color": MUTED}, "outlinewidth": 0},
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{z:.0f}% inhibition<extra></extra>",
    ))
    if p.hits:
        fig.add_trace(go.Scatter(
            x=[int(h["well"][1:]) for h in p.hits], y=[h["well"][0] for h in p.hits], mode="markers",
            marker={"symbol": "square-open", "size": 17, "color": INK, "line": {"width": 2}},
            hoverinfo="skip", showlegend=False,
        ))
    fig.update_yaxes(range=[sc.N_ROWS - 0.5, -0.5], showgrid=False, tickfont={"family": "JetBrains Mono"})
    fig.update_xaxes(range=[0.5, sc.N_COLS + 0.5], showgrid=False, tickvals=[1, 2, 6, 10, 14, 18, 22, 23, 24])
    for axis in (fig.update_xaxes, fig.update_yaxes):
        axis(zeroline=False, linecolor="rgba(0,0,0,0)", tickfont_color=MUTED, tickfont_size=11)
    fig.update_layout(
        margin={"l": 24, "r": 8, "t": 4, "b": 24}, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": FONT, "color": MUTED}, uirevision=p.plate_id,
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": "#cfd3d1", "font": {"color": INK, "size": 12}},
    )
    return fig


# ---------------------------------------------------------------- components

def status_badge(status, size="sm"):
    level, icon = PLATE_STATUS[status]
    return dmc.Badge(f"QC: {status}", color=STATUS[level], variant="light", size=size, radius="sm",
                     leftSection=DashIconify(icon=icon, width=12), className="badge")


def decision_badge(decision, size="sm"):
    color, icon = DECISIONS[decision]
    label = "Awaiting review" if decision == "Pending" else decision
    return dmc.Badge(label, color=color, variant="dot" if decision == "Pending" else "filled", size=size,
                     radius="sm", leftSection=None if decision == "Pending" else DashIconify(icon=icon, width=12),
                     className="badge")


TILE_CLASS = {"Accepted": "accepted", "Re-run": "rerun", "Rejected": "rejected", "Pending": "pending"}


def ribbon(selected, decisions):
    """Every plate as a small tile in run order, colored by where it stands in review."""
    blocks = []
    for r in range(1, sc.N_RUNS + 1):
        cells = []
        for p in (p for p in sc.PLATES if p.run == r):
            decision = decision_of(p.plate_id, decisions)
            cur = current(p.plate_id, decisions)
            cls = f"tile {TILE_CLASS[decision]}"
            if p.plate_id in in_lab(decisions):
                cls += " running"
            if p.plate_id == selected:
                cls += " selected"
            cells.append(html.Button(
                id={"type": "tile", "plate": p.plate_id}, n_clicks=0, className=cls,
                title=f"{p.plate_id}{' (re-read)' if cur.rerun else ''} · {cur.status} · Z′ {cur.stats['z']:.2f} · "
                      f"{'In the lab' if 'running' in cls else decision}",
            ))
        blocks.append(html.Div([html.Div(f"Run {r}", className="ribbon-run"),
                                html.Div(cells, className="ribbon-cells")]))
    return blocks


def legend_item(cls, label):
    return html.Span([html.Span(className=f"tile static {cls}"), label], className="ribbon-key")


def review_queue(selected, decisions):
    items = []
    for p in to_review(decisions):
        if p.rerun:
            first = sc.BY_ID[p.plate_id]
            note = (f"Re-read {'passed QC' if not p.flags else ', '.join(f[1] for f in p.flags)} · first read: "
                    + ", ".join(f[1] for f in first.flags))
        else:
            note = ", ".join(f[1] for f in p.flags)
        items.append(html.Div(
            [
                dmc.Group([
                    dmc.Group([dmc.Text(p.plate_id, className="q-name"), reread_badge("xs") if p.rerun else None], gap=6,
                              wrap="nowrap"),
                    status_badge(p.status, "xs"),
                ], justify="space-between", wrap="nowrap"),
                dmc.Text(note, className="q-flags"),
            ],
            id={"type": "queue", "plate": p.plate_id}, n_clicks=0,
            className="q-item" + (" selected" if p.plate_id == selected else "") + (" reread" if p.rerun else ""),
        ))
    if not items:
        return html.Div([DashIconify(icon="tabler:circle-check", width=28, className="done-icon"),
                         dmc.Text("All caught up", fw=600),
                         dmc.Text("Plates sent for a re-run come back here." if in_lab(decisions)
                                  else "Every flagged plate has a decision.", className="hint")],
                        className="queue-empty")
    return items


def lab_list(decisions, now):
    rows = []
    for pid, back_at in sorted(in_lab(decisions).items(), key=lambda kv: kv[1]):
        left = max(0, back_at - now)
        rows.append(html.Div([
            dmc.Group([dmc.Text(pid, className="q-name"), dmc.Text(f"back in {left:.0f}s", className="hint")],
                      justify="space-between"),
            dmc.Progress(value=100 * (1 - left / RERUN_SECONDS), size="sm", color="blue", animated=True,
                         striped=True, mt=4),
        ], className="lab-item"))
    return rows


def reread_badge(size="sm"):
    return dmc.Badge("Re-read", color="blue", variant="outline", size=size, radius="sm",
                     leftSection=DashIconify(icon="tabler:refresh", width=12), className="badge")


def plate_stats(p):
    s = p.stats

    def item(label, value, bad=False):
        return html.Div([dmc.Text(label, className="stat-label"),
                         dmc.Text(value, className="stat-value" + (" bad" if bad else ""))], className="stat")

    return [
        item("Z′-factor", f"{s['z']:.2f}", s["z"] < sc.Z_REVIEW),
        item("DMSO CV", f"{s['hi_cv']:.1%}", s["hi_cv"] > sc.CV_REVIEW),
        item("Hits", f"{s['n_hits']}", s["hit_rate"] > sc.HIT_RATE_REVIEW),
    ]


def flag_list(p):
    if p.rerun and not p.flags:
        first = sc.BY_ID[p.plate_id]
        return dmc.Alert(
            f"The first read was flagged for: {', '.join(f[1] for f in first.flags)}. The re-read passes every "
            f"QC rule, with Z′ {first.stats['z']:.2f} → {p.stats['z']:.2f} and hits {first.stats['n_hits']} → "
            f"{p.stats['n_hits']}.",
            title="Re-read is clean", color="teal", variant="light",
            icon=DashIconify(icon="tabler:circle-check", width=18), className="flag-alert")
    if not p.flags:
        return dmc.Alert("Every QC rule passed. Accepted automatically.", color="teal", variant="light",
                         icon=DashIconify(icon="tabler:circle-check", width=18), className="flag-alert")
    return dmc.Stack([
        dmc.Alert(detail, title=label, color="red" if sev == "fail" else "yellow", variant="light",
                  icon=DashIconify(icon="tabler:circle-x" if sev == "fail" else "tabler:alert-triangle", width=18),
                  className="flag-alert")
        for sev, label, detail in p.flags
    ], gap=8)


# ---------------------------------------------------------------- layout

header = html.Header(
    html.Div(
        [
            html.Div(
                [
                    html.Div(["Halden Bio", html.Span("/", className="sep"), sc.CAMPAIGN,
                              html.Span("/", className="sep"), f"{sc.ASSAY}, 384-well"], className="crumbs"),
                    html.H1("Plate QC review", className="title"),
                    dmc.Text(id="summary", className="summary"),
                ],
                className="head-left",
            ),
            html.Div(
                [
                    html.Div(
                        [legend_item("accepted", "Accepted"), legend_item("pending", "Awaiting review"),
                         legend_item("rerun", "Re-run"), legend_item("rejected", "Rejected")],
                        className="ribbon-keys",
                    ),
                    html.Div(id="ribbon", className="ribbon"),
                ],
                className="head-right",
            ),
        ],
        className="header-inner",
    ),
    className="header",
)

plate_panel = dmc.Paper(
    [
        dmc.Group(
            [
                dmc.Stack([
                    dmc.Group([dmc.Title(id="plate-title", order=2, className="plate-title"),
                               html.Div(id="plate-badges")], gap="sm", align="center"),
                    dmc.Text(id="plate-meta", className="plate-meta"),
                ], gap=2),
                dmc.Group([
                    dmc.Button("Accept", id={"type": "decide", "value": "Accepted"}, size="xs", color="teal",
                               leftSection=DashIconify(icon="tabler:check", width=14)),
                    dmc.Button("Re-run", id={"type": "decide", "value": "Re-run"}, size="xs", color="orange",
                               variant="light", leftSection=DashIconify(icon="tabler:refresh", width=14)),
                    dmc.Button("Reject", id={"type": "decide", "value": "Rejected"}, size="xs", color="red",
                               variant="light", leftSection=DashIconify(icon="tabler:ban", width=14)),
                    html.Div(dmc.Button("Back to queue", id={"type": "decide", "value": "Pending"}, size="xs",
                                        color="gray", variant="subtle"), id="reset-wrap"),
                ], gap=6),
            ],
            justify="space-between", align="flex-start", mb="md",
        ),
        dmc.Grid(
            [
                dmc.GridCol([
                    html.Div(
                        dcc.Graph(id="plate-map", config={"displayModeBar": False, "responsive": True},
                                  style={"height": "100%"}),
                        className="graph plate",
                    ),
                    dmc.Text("Outlined wells are hits (≥ 50% inhibition). Columns 1–2 hold DMSO, 23–24 the "
                             "reference inhibitor.", className="hint"),
                ], span={"base": 12, "lg": 8}),
                dmc.GridCol([
                    html.Div(id="plate-stats", className="stats"),
                    dmc.Text("QC findings", className="section-title"),
                    html.Div(id="flags"),
                ], span={"base": 12, "lg": 4}),
            ],
            gutter="lg",
        ),
    ],
    className="card",
)

app.layout = dmc.MantineProvider(
    [
        dcc.Store(id="selected", data=DEFAULT_PLATE),
        dcc.Store(id="last", data=None),
        dcc.Interval(id="tick", interval=1000, disabled=True),
        dcc.Store(id="decisions", data=sc.INITIAL_DECISIONS),  # in memory: a refresh starts the review over
        header,
        html.Main(
            [
                html.Div(
                    [
                        html.Aside(
                            dmc.Paper([
                                dmc.Group([dmc.Text("To review", className="section-title"),
                                           dmc.Badge(id="queue-count", color="dark", size="sm", radius="xl")],
                                          gap=8, align="flex-start"),
                                html.Div(id="queue", className="queue"),
                                html.Div([dmc.Text("In the lab", className="section-title"),
                                          html.Div(id="lab-list")], id="lab", className="lab",
                                         style={"display": "none"}),
                                dmc.Group(
                                    [html.Div(id="last-text"),
                                     dmc.Button("Undo", id="undo", size="compact-xs", variant="subtle", color="gray",
                                                leftSection=DashIconify(icon="tabler:arrow-back-up", width=14))],
                                    id="last-action", className="last-action", justify="space-between",
                                    style={"display": "none"},
                                ),
                            ], className="card"),
                            className="side",
                        ),
                        plate_panel,
                    ],
                    className="body",
                ),
                dmc.Text(f"Plates, compounds and readings are synthetic. A re-run takes {RERUN_SECONDS} seconds in this demo. "
                         "Decisions aren't saved; refreshing starts the review over.",
                         className="foot"),
            ],
            className="main",
        ),
    ],
    theme=THEME,
    forceColorScheme="light",
)


# ---------------------------------------------------------------- callbacks

@app.callback(
    Output("selected", "data"),
    Input({"type": "queue", "plate": ALL}, "n_clicks"),
    Input({"type": "tile", "plate": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_plate(*_):
    if isinstance(ctx.triggered_id, dict) and ctx.triggered[0]["value"]:
        return ctx.triggered_id["plate"]
    return dash.no_update


@app.callback(
    Output("decisions", "data"),
    Output("selected", "data", allow_duplicate=True),
    Output("last", "data"),
    Input({"type": "decide", "value": ALL}, "n_clicks"),
    State("selected", "data"),
    State("decisions", "data"),
    prevent_initial_call=True,
)
def decide(_, plate, decisions):
    """Record the decision, then move straight on to the next plate still to review."""
    if not ctx.triggered[0]["value"]:
        return dash.no_update, dash.no_update, dash.no_update
    value = ctx.triggered_id["value"]
    decisions = dict(decisions or {})
    queue_before = [p.plate_id for p in to_review(decisions)]
    last = {"plate": plate, "prev": decisions.get(plate), "decision": value}
    reread = is_reread(plate, decisions)
    if value == "Pending":
        decisions[plate] = {"decision": "Pending", "reread": reread}
        return decisions, plate, None
    decisions[plate] = {"decision": value, "by": "You", "reread": reread}
    if value == "Re-run":
        decisions[plate]["back_at"] = time.time() + RERUN_SECONDS
    remaining = [p.plate_id for p in to_review(decisions)]
    if not remaining:
        return decisions, plate, last
    # Next in line after the plate just decided, wrapping to the top
    after = queue_before[queue_before.index(plate) + 1:] if plate in queue_before else []
    nxt = next((pid for pid in after if pid in remaining), remaining[0])
    return decisions, nxt, last


@app.callback(
    Output("decisions", "data", allow_duplicate=True),
    Output("selected", "data", allow_duplicate=True),
    Output("last", "data", allow_duplicate=True),
    Input("undo", "n_clicks"),
    State("last", "data"),
    State("decisions", "data"),
    prevent_initial_call=True,
)
def undo(n, last, decisions):
    if not n or not last:
        return dash.no_update, dash.no_update, dash.no_update
    decisions = dict(decisions or {})
    if last["prev"] is None:
        decisions.pop(last["plate"], None)
    else:
        decisions[last["plate"]] = last["prev"]
    return decisions, last["plate"], None


@app.callback(
    Output("last-text", "children"),
    Output("last-action", "style"),
    Input("last", "data"),
)
def show_last(last):
    if not last:
        return None, {"display": "none"}
    color, icon = DECISIONS[last["decision"]]
    text = dmc.Group([DashIconify(icon=icon, width=14),
                      dmc.Text(f"{last['plate']} {last['decision'].lower()}", size="xs")], gap=4, c=color)
    return text, {}


@app.callback(
    Output("decisions", "data", allow_duplicate=True),
    Input("tick", "n_intervals"),
    State("decisions", "data"),
    prevent_initial_call=True,
)
def back_from_lab(_, decisions):
    """Plates whose re-run is done come back to the queue as a fresh, fault-free read."""
    now = time.time()
    due = [pid for pid, back_at in in_lab(decisions or {}).items() if back_at <= now]
    if not due:
        return dash.no_update
    decisions = dict(decisions)
    for pid in due:
        decisions[pid] = {"decision": "Pending", "reread": True}
    return decisions


@app.callback(
    Output("lab-list", "children"),
    Output("lab", "style"),
    Output("tick", "disabled"),
    Input("tick", "n_intervals"),
    Input("decisions", "data"),
)
def update_lab(_, decisions):
    rows = lab_list(decisions or {}, time.time())
    return rows, {} if rows else {"display": "none"}, not rows


@app.callback(
    Output("summary", "children"),
    Output("ribbon", "children"),
    Output("queue", "children"),
    Output("queue-count", "children"),
    Input("selected", "data"),
    Input("decisions", "data"),
)
def update_overview(selected, decisions):
    decisions = decisions or {}
    pending = len(to_review(decisions))
    passed = sum(p.status == "Pass" for p in sc.PLATES)
    lab = len(in_lab(decisions))
    summary = (f"{len(sc.PLATES)} plates · {passed} passed QC · {pending} awaiting review"
               + (f" · {lab} in the lab" if lab else "") + f" · last read {sc.AS_OF:%-d %b, %H:%M}")
    return summary, ribbon(selected, decisions), review_queue(selected, decisions), len(to_review(decisions))


@app.callback(
    Output("plate-title", "children"),
    Output("plate-badges", "children"),
    Output("plate-meta", "children"),
    Output("plate-stats", "children"),
    Output("flags", "children"),
    Output("plate-map", "figure"),
    Output("reset-wrap", "style"),
    Input("selected", "data"),
    Input("decisions", "data"),
)
def update_plate(pid, decisions):
    decisions = decisions or {}
    p = current(pid, decisions)
    d = decisions.get(pid, {})
    decision = d.get("decision", "Pending")
    badges = dmc.Group([reread_badge() if p.rerun else None, status_badge(p.status), decision_badge(decision)], gap=6)
    meta = (f"Run {p.run} · Re-read on {p.dispenser}" if p.rerun
            else f"Run {p.run} · Read {p.read_at:%-d %b %H:%M} · {p.dispenser}") + f" · Lot {p.lot}"
    if pid in in_lab(decisions):
        meta += " · In the lab for a re-run"
    elif decision != "Pending":
        meta += f" · {decision} by {d.get('by', '')}"
    flagged = sc.BY_ID[pid].status != "Pass"
    show_reset = {} if flagged and decision != "Pending" and pid not in in_lab(decisions) else {"display": "none"}
    return p.plate_id, badges, meta, plate_stats(p), flag_list(p), plate_map(p), show_reset


if __name__ == "__main__":
    app.run(debug=True)
