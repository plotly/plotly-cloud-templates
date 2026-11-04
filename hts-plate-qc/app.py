"""
Screening Plate QC

Quality control review for a high-throughput screening campaign: 72 assay plates
of 384 wells read over six runs. Tracks plate quality (Z′, signal window, control
CVs) across the campaign, flags plates that break the QC rules and says why, and
lets a reviewer open any plate, inspect its plate map, controls and hits, and
accept it, send it for a re-run or reject it.

The screening data is synthetic, see screening.py.
"""

import dash
import dash_ag_grid as dag
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash._hooks import HooksManager
from dash_iconify import DashIconify
from plotly.subplots import make_subplots

import screening as sc

# Chart colors, kept in sync with assets/style.css
SURFACE = "#ffffff"
INK = "#0b0b0b"
INK_2 = "#4f5551"
MUTED = "#808782"
GRID = "#eceeed"
AXIS = "#cfd3d1"
HIGH_COLOR = "#2a78d6"  # neutral control, categorical slot 1
LOW_COLOR = "#eb6834"  # reference inhibitor, categorical slot 2
CMPD_COLOR = "#a3a8a5"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
PLATE_STATUS = {
    "Pass": ("good", "tabler:circle-check", "circle"),
    "Review": ("warning", "tabler:alert-triangle", "diamond"),
    "Fail": ("critical", "tabler:circle-x", "x"),
}
DECISIONS = {
    "Pending": ("gray", "tabler:clock"),
    "Accepted": ("teal", "tabler:check"),
    "Re-run": ("orange", "tabler:refresh"),
    "Rejected": ("red", "tabler:ban"),
}
# Sequential blue for magnitude, blue–gray–red for the signed B-score
SEQ_BLUE = [[0, "#f0f5fc"], [0.25, "#b7d3f6"], [0.5, "#6da7ec"], [0.75, "#2a78d6"], [1, "#104281"]]
DIVERGING = [[0, "#104281"], [0.25, "#6da7ec"], [0.5, "#f0efec"], [0.75, "#ec8a83"], [1, "#a52a2a"]]

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

RUN_OPTIONS = [{"value": "All", "label": "All runs"}] + [
    {"value": str(r), "label": f"Run {r} · {d:%-d %b}"} for r, d in sc.RUN_DATES.items()
]
DEFAULT_PLATE = "ZK7-304"


def plates_in(run):
    return [p for p in sc.PLATES if run == "All" or p.run == int(run)]


def style_axes(fig):
    for axis in (fig.update_xaxes, fig.update_yaxes):
        axis(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
             title_font={"color": MUTED, "size": 12})
    fig.update_layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font={"family": FONT, "color": INK_2},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12, "family": FONT}},
    )
    return fig


# ---------------------------------------------------------------- campaign chart

METRICS = {
    "z": ("Z′-factor", "Z′"),
    "controls": ("Control signal", "Controls"),
    "hits": ("Hit rate", "Hit rate"),
}


def campaign_chart(run, metric, selected):
    plates = plates_in(run)
    x = [p.seq for p in plates]
    fig = go.Figure()

    if metric == "controls":
        for key, name, color in (("hi", "Neutral control (DMSO)", HIGH_COLOR), ("lo", "Reference inhibitor", LOW_COLOR)):
            mean = np.array([p.stats[f"{key}_mean"] for p in plates])
            sd = np.array([p.stats[f"{key}_sd"] for p in plates])
            fig.add_trace(go.Scatter(
                x=x, y=mean, mode="markers", name=name,
                marker={"color": color, "size": 8, "line": {"color": SURFACE, "width": 1.5}},
                error_y={"type": "data", "array": 3 * sd, "color": color, "thickness": 1.25, "width": 0},
                customdata=[[p.plate_id, s] for p, s in zip(plates, sd)],
                hovertemplate="<b>%{customdata[0]}</b><br>" + name + " %{y:,.0f} ± 3 × %{customdata[1]:,.0f}"
                              "<extra></extra>",
            ))
        top = max(p.stats["hi_mean"] + 3 * p.stats["hi_sd"] for p in plates)
        fig.update_yaxes(title="TR-FRET ratio × 10⁴", range=[0, top * 1.05])
    else:
        if metric == "z":
            y = [p.stats["z"] for p in plates]
            fmt, title = ".2f", "Z′-factor"
            fig.add_hrect(y0=-2, y1=sc.Z_FAIL, fillcolor="rgba(208,59,59,0.06)", line_width=0, layer="below")
            fig.add_hrect(y0=sc.Z_FAIL, y1=sc.Z_REVIEW, fillcolor="rgba(250,178,25,0.10)", line_width=0,
                          layer="below")
            for lim, label in ((sc.Z_REVIEW, "Review below 0.5"), (sc.Z_FAIL, "Fail below 0.4")):
                fig.add_hline(y=lim, line={"color": AXIS, "width": 1, "dash": "dot"})
                fig.add_annotation(x=1, xref="paper", y=lim, text=label, showarrow=False, xanchor="right",
                                   yanchor="bottom", font={"color": MUTED, "size": 10})
            lo = min(y)
            fig.update_yaxes(title=title, range=[max(lo, -0.2) - 0.05, 1])
        else:
            y = [100 * p.stats["hit_rate"] for p in plates]
            fmt, title = ".1f", "Hit rate, %"
            fig.add_hline(y=100 * sc.HIT_RATE_REVIEW, line={"color": AXIS, "width": 1, "dash": "dot"})
            fig.add_annotation(x=1, xref="paper", y=100 * sc.HIT_RATE_REVIEW, text="Review above 2%",
                               showarrow=False, xanchor="right", yanchor="bottom", font={"color": MUTED, "size": 10})
            fig.update_yaxes(title=title, rangemode="tozero")
        # Off-scale plates (a broken control column) sit on the floor of the axis with their real value in the hover
        floor = -0.2 if metric == "z" else None
        fig.add_trace(go.Scatter(
            x=x, y=[max(v, floor) if floor is not None else v for v in y], mode="lines",
            line={"color": AXIS, "width": 1}, hoverinfo="skip", showlegend=False,
        ))
        for status, (level, _, symbol) in PLATE_STATUS.items():
            group = [(p, v) for p, v in zip(plates, y) if p.status == status]
            if not group:
                continue
            fig.add_trace(go.Scatter(
                x=[p.seq for p, _ in group],
                y=[max(v, floor) if floor is not None else v for _, v in group],
                mode="markers", name=status,
                marker={"color": STATUS[level], "size": 10 if status != "Pass" else 8, "symbol": symbol,
                        "line": {"color": SURFACE, "width": 1.5}},
                customdata=[[p.plate_id, v, ", ".join(f[1] for f in p.flags) or "No flags"] for p, v in group],
                hovertemplate="<b>%{customdata[0]}</b> · " + status + "<br>" + title + " %{customdata[1]:" + fmt
                              + "}<br>%{customdata[2]}<extra></extra>",
            ))

    if selected in sc.BY_ID and sc.BY_ID[selected] in plates:
        fig.add_vline(x=sc.BY_ID[selected].seq, line={"color": "#0f766e", "width": 2}, opacity=0.35)

    runs = sorted({p.run for p in plates})
    for r in runs:
        first = r * sc.PLATES_PER_RUN - sc.PLATES_PER_RUN
        if r != runs[0]:
            fig.add_vline(x=first - 0.5, line={"color": GRID, "width": 1})
        fig.add_annotation(x=first + (sc.PLATES_PER_RUN - 1) / 2, y=1, yref="paper", yanchor="bottom",
                           text=f"Run {r}", showarrow=False, font={"color": MUTED, "size": 11})
    if sc.LOT_CHANGE_SEQ in x:
        fig.add_vline(x=sc.LOT_CHANGE_SEQ - 0.5, line={"color": INK_2, "width": 1, "dash": "dot"})
        fig.add_annotation(x=sc.LOT_CHANGE_SEQ - 0.5, y=1, yref="paper", yanchor="top", xanchor="left",
                           text="New reagent lot 24-131 →", showarrow=False, font={"color": INK_2, "size": 10},
                           xshift=4, yshift=-2, bgcolor=SURFACE)

    fig.update_xaxes(showticklabels=False, showgrid=False, range=[min(x) - 1, max(x) + 1])
    fig.update_layout(
        margin={"l": 60, "r": 12, "t": 22, "b": 8}, hovermode="closest", clickmode="event",
        legend={"orientation": "h", "x": 0, "y": -0.04, "yanchor": "top", "font": {"color": INK_2, "size": 11}},
        uirevision=f"{run}-{metric}",
    )
    return style_axes(fig)


# ---------------------------------------------------------------- plate map

VIEWS = {
    "pct": "% inhibition",
    "raw": "Raw signal",
    "bscore": "B-score",
}


def plate_map(p, view):
    if view == "raw":
        z = p.raw
        zmin, zmax = float(np.percentile(p.raw, 1)), float(np.percentile(p.raw, 99))
        scale, unit, fmt, cbar = SEQ_BLUE, "", ",.0f", "Ratio × 10⁴"
    elif view == "bscore":
        z = p.bscore
        zmin, zmax = -6, 6
        scale, unit, fmt, cbar = DIVERGING, "", "+.1f", "B-score"
    else:
        z = p.pct
        zmin, zmax = -20, 100
        scale, unit, fmt, cbar = SEQ_BLUE, "%", ".0f", "% inhib."

    s = p.stats
    fig = make_subplots(rows=2, cols=2, column_widths=[0.88, 0.12], row_heights=[0.12, 0.88],
                        horizontal_spacing=0.015, vertical_spacing=0.03, shared_xaxes=True, shared_yaxes=True)
    cols = list(range(1, sc.N_COLS + 1))
    role = np.full((sc.N_ROWS, sc.N_COLS), "Compound", dtype=object)
    role[:, sc.HIGH_COLS] = "Neutral control"
    role[:, sc.LOW_COLS] = "Reference inhibitor"
    cd = np.dstack([
        [[sc.well_name(r, c) for c in range(sc.N_COLS)] for r in range(sc.N_ROWS)],
        np.where(p.compounds == "", role, p.compounds),
        np.round(p.raw).astype(int).astype(str),
        np.char.mod("%.0f", p.pct),
    ])
    fig.add_trace(go.Heatmap(
        z=z, x=cols, y=sc.ROWS, colorscale=scale, zmin=zmin, zmax=zmax, xgap=2, ygap=2,
        customdata=cd,
        colorbar={"title": {"text": cbar, "side": "top", "font": {"size": 11, "color": MUTED}}, "thickness": 10,
                  "len": 0.84, "y": 0, "yanchor": "bottom", "x": 1.01, "tickfont": {"size": 10, "color": MUTED},
                  "outlinewidth": 0},
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>Raw %{customdata[2]}"
                      "<br>%{customdata[3]}% inhibition<extra></extra>",
    ), row=2, col=1)

    # Hits outlined
    if p.hits:
        hr = [h["well"][0] for h in p.hits]
        hc = [int(h["well"][1:]) for h in p.hits]
        fig.add_trace(go.Scatter(
            x=hc, y=hr, mode="markers", name="Hit",
            marker={"symbol": "square-open", "size": 17, "color": INK, "line": {"width": 2}},
            hoverinfo="skip", showlegend=False,
        ), row=2, col=1)

    # Column and row medians of compound % inhibition
    col_med = np.full(sc.N_COLS, np.nan)
    col_med[sc.CMPD_COLS] = s["col_med"]
    fig.add_trace(go.Bar(
        x=cols, y=col_med, marker={"color": [LOW_COLOR if abs(v) > sc.LINE_REVIEW else CMPD_COLOR for v in col_med]},
        hovertemplate="Column %{x}: median %{y:+.0f}%<extra></extra>", showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        y=sc.ROWS, x=s["row_med"], orientation="h",
        marker={"color": [LOW_COLOR if abs(v) > sc.LINE_REVIEW else CMPD_COLOR for v in s["row_med"]]},
        hovertemplate="Row %{y}: median %{x:+.0f}%<extra></extra>", showlegend=False,
    ), row=2, col=2)

    col_lim = max(15, float(np.nanmax(np.abs(col_med))) * 1.1)
    lim = max(15, float(np.max(np.abs(s["row_med"]))) * 1.1)
    fig.update_yaxes(range=[-col_lim, col_lim], row=1, col=1, showticklabels=False, showgrid=False,
                     zeroline=True, zerolinecolor=AXIS)
    fig.update_xaxes(range=[-lim, lim], row=2, col=2, showticklabels=False, showgrid=False,
                     zeroline=True, zerolinecolor=AXIS)
    fig.update_yaxes(range=[sc.N_ROWS - 0.5, -0.5], row=2, col=1, showgrid=False, tickfont={"family": "JetBrains Mono"})
    fig.update_xaxes(row=2, col=1, range=[0.5, sc.N_COLS + 0.5], showgrid=False, tickvals=[1, 2, 6, 10, 14, 18, 22, 23, 24], side="bottom")
    fig.update_xaxes(row=1, col=1, showgrid=False)
    fig.update_layout(
        margin={"l": 28, "r": 56, "t": 4, "b": 24}, bargap=0.25, uirevision=f"{p.plate_id}-{view}",
    )
    style_axes(fig)
    fig.update_xaxes(linecolor="rgba(0,0,0,0)")
    fig.update_yaxes(linecolor="rgba(0,0,0,0)")
    return fig


# ---------------------------------------------------------------- control separation

def controls_chart(p):
    rng = np.random.default_rng(p.seq)
    hi = p.raw[:, sc.HIGH_COLS].ravel()
    lo = p.raw[:, sc.LOW_COLS].ravel()
    cm = p.raw[:, sc.CMPD_COLS].ravel()
    s = p.stats
    fig = go.Figure()
    groups = [("Reference inhibitor", lo, LOW_COLOR, s["lo_mean"], s["lo_sd"]),
              ("Neutral control", hi, HIGH_COLOR, s["hi_mean"], s["hi_sd"])]
    for i, (name, vals, color, m, sd) in enumerate(groups):
        fig.add_shape(type="rect", x0=max(m - 3 * sd, 0), x1=m + 3 * sd, y0=i - 0.38, y1=i + 0.38, yref="y",
                      fillcolor=color, opacity=0.12, line_width=0, layer="below")
        fig.add_shape(type="line", x0=m, x1=m, y0=i - 0.38, y1=i + 0.38, line={"color": color, "width": 2})
        fig.add_trace(go.Scatter(
            x=vals, y=i + rng.uniform(-0.28, 0.28, len(vals)), mode="markers", name=name,
            marker={"color": color, "size": 7, "opacity": 0.85, "line": {"color": SURFACE, "width": 1}},
            hovertemplate="%{x:,.0f}<extra>" + name + "</extra>",
        ))
    fig.add_trace(go.Violin(
        x=cm, y0=2, orientation="h", name="Compounds", side="positive", width=1.6, points=False,
        line={"color": CMPD_COLOR, "width": 1}, fillcolor="rgba(163,168,165,0.35)", hoverinfo="skip",
        spanmode="hard", scalemode="width",
    ))
    gap_lo, gap_hi = s["lo_mean"] + 3 * s["lo_sd"], s["hi_mean"] - 3 * s["hi_sd"]
    if gap_hi > gap_lo:
        fig.add_annotation(x=(gap_lo + gap_hi) / 2, y=0.5, text=f"Z′ {s['z']:.2f}", showarrow=False,
                           font={"color": INK, "size": 13})
        fig.add_shape(type="line", x0=gap_lo, x1=gap_hi, y0=0.5 - 0.14, y1=0.5 - 0.14,
                      line={"color": INK_2, "width": 1})
    else:
        fig.add_annotation(x=(s["lo_mean"] + s["hi_mean"]) / 2, y=0.5, text=f"Z′ {s['z']:.2f} · bands overlap",
                           showarrow=False, bgcolor=SURFACE, yshift=4, font={"color": STATUS["critical"], "size": 13})
    fig.update_yaxes(tickvals=[0, 1, 2], ticktext=["Ref. inhibitor", "DMSO", "Compounds"], range=[-0.6, 3.1],
                     showgrid=False)
    fig.update_xaxes(title="TR-FRET ratio × 10⁴", rangemode="tozero")
    fig.update_layout(margin={"l": 92, "r": 12, "t": 4, "b": 40}, showlegend=False, hovermode="closest",
                      uirevision=p.plate_id)
    return style_axes(fig)


# ---------------------------------------------------------------- components

def graph(graph_id, cls="graph"):
    return html.Div(
        dcc.Graph(id=graph_id, config={"displayModeBar": False, "responsive": True}, style={"height": "100%"}),
        className=cls,
    )


def card(title, *children, extra=None, **kwargs):
    return dmc.Paper(
        [dmc.Group([dmc.Text(title, className="card-title"), extra], justify="space-between", mb="sm", wrap="nowrap"),
         *children],
        className="card", **kwargs,
    )


def status_badge(status, size="sm"):
    level, icon, _ = PLATE_STATUS[status]
    return dmc.Badge(status, color=STATUS[level], variant="light", size=size, radius="sm",
                     leftSection=DashIconify(icon=icon, width=12), className="badge")


def decision_badge(decision, size="sm"):
    color, icon = DECISIONS[decision]
    return dmc.Badge(decision, color=color, variant="dot" if decision == "Pending" else "filled", size=size,
                     radius="sm", leftSection=None if decision == "Pending" else DashIconify(icon=icon, width=12),
                     className="badge")


def kpi(label, value, sub=None, icon=None):
    return html.Div(
        [dmc.Group([icon and DashIconify(icon=icon, width=16, className="kpi-icon"),
                    dmc.Text(label, className="kpi-label")], gap=6, wrap="nowrap"),
         dmc.Text(value, className="kpi-value"),
         sub and dmc.Text(sub, className="kpi-sub")],
        className="kpi",
    )


def decision_of(pid, decisions):
    return decisions.get(pid, {}).get("decision", "Pending")


def kpis(run, decisions):
    plates = plates_in(run)
    n = len(plates)
    z = np.array([p.stats["z"] for p in plates])
    passed = sum(p.status == "Pass" for p in plates)
    pending = sum(decision_of(p.plate_id, decisions) == "Pending" for p in plates)
    accepted = [p for p in plates if decision_of(p.plate_id, decisions) == "Accepted"]
    hits = sum(p.stats["n_hits"] for p in accepted)
    cmpds = len(accepted) * len(sc.CMPD_COLS) * sc.N_ROWS
    rerun = sum(decision_of(p.plate_id, decisions) in ("Re-run", "Rejected") for p in plates)
    return [
        kpi("Plates read", f"{n}", f"{n * 320:,} compounds at {sc.COMPOUND_CONC}", "tabler:grid-dots"),
        kpi("Passed auto QC", f"{passed / n:.0%}", f"{passed} of {n} plates, no flags", "tabler:circle-check"),
        kpi("Median Z′", f"{np.median(z):.2f}", f"{(z >= sc.Z_REVIEW).mean():.0%} of plates at 0.5 or better",
            "tabler:arrows-horizontal"),
        kpi("Hit rate", f"{hits / cmpds:.2%}" if cmpds else "–",
            f"{hits} hits ≥ {sc.HIT_THRESHOLD}% on accepted plates", "tabler:target-arrow"),
        kpi("Awaiting review", f"{pending}", f"{rerun} plates sent back to the lab", "tabler:clipboard-list"),
    ]


def review_queue(run, selected, decisions):
    flagged = [p for p in plates_in(run) if p.status != "Pass"]
    if not flagged:
        return dmc.Text("No plate in this run broke a QC rule.", className="empty")
    order = {"Pending": 0, "Re-run": 1, "Rejected": 1, "Accepted": 2}
    flagged.sort(key=lambda p: (order[decision_of(p.plate_id, decisions)], p.status != "Fail", p.stats["z"]))
    items = []
    for p in flagged:
        d = decisions.get(p.plate_id, {})
        decision = d.get("decision", "Pending")
        items.append(html.Div(
            [
                dmc.Group([
                    dmc.Group([dmc.Text(p.plate_id, className="q-name"), status_badge(p.status, "xs")], gap=6,
                              wrap="nowrap"),
                    decision_badge(decision, "xs"),
                ], justify="space-between", wrap="nowrap"),
                dmc.Group([dmc.Badge(f[1], variant="outline", color="gray", size="xs", radius="sm",
                                     className="badge flag") for f in p.flags], gap=4, mt=6),
                dmc.Text(
                    f"Run {p.run} · {p.read_at:%-d %b %H:%M} · {p.dispenser}"
                    + (f" · {d['by']}" if decision != "Pending" else ""),
                    className="q-meta",
                ),
            ],
            id={"type": "queue", "plate": p.plate_id}, n_clicks=0,
            className="q-item" + (" selected" if p.plate_id == selected else "")
                      + (" done" if decision != "Pending" else ""),
        ))
    return items


def grid_rows(run, decisions):
    rows = []
    for p in plates_in(run):
        s = p.stats
        rows.append({
            "plate": p.plate_id, "run": p.run, "read_at": f"{p.read_at:%Y-%m-%d %H:%M}", "status": p.status,
            "decision": decision_of(p.plate_id, decisions), "z": round(s["z"], 3), "rz": round(s["robust_z"], 3),
            "sb": round(s["sb"], 2), "hi_cv": round(100 * s["hi_cv"], 1), "lo_cv": round(100 * s["lo_cv"], 1),
            "edge": round(100 * s["edge"], 1), "hits": s["n_hits"], "hit_rate": round(100 * s["hit_rate"], 2),
            "reader": p.reader, "dispenser": p.dispenser, "lot": p.lot,
            "flags": ", ".join(f[1] for f in p.flags),
        })
    return rows


def num(fmt, suffix=""):
    return {"function": f"params.value == null ? '–' : d3.format('{fmt}')(params.value) + '{suffix}'"}


COLUMNS = [
    {"field": "plate", "headerName": "Plate", "pinned": "left", "width": 110, "cellClass": "mono"},
    {"field": "status", "headerName": "Auto QC", "width": 115, "cellRenderer": "StatusCell"},
    {"field": "decision", "headerName": "Decision", "width": 120, "cellRenderer": "DecisionCell"},
    {"field": "z", "headerName": "Z′", "type": "numericColumn", "width": 85, "valueFormatter": num(".2f"),
     "cellClassRules": {"bad": f"params.value < {sc.Z_FAIL}", "warn": f"params.value >= {sc.Z_FAIL} && "
                                                                      f"params.value < {sc.Z_REVIEW}"}},
    {"field": "rz", "headerName": "Robust Z′", "type": "numericColumn", "width": 105, "valueFormatter": num(".2f")},
    {"field": "sb", "headerName": "S/B", "type": "numericColumn", "width": 80, "valueFormatter": num(".1f")},
    {"field": "hi_cv", "headerName": "DMSO CV", "type": "numericColumn", "width": 100, "valueFormatter": num(".1f", "%"),
     "cellClassRules": {"warn": f"params.value > {100 * sc.CV_REVIEW}"}},
    {"field": "lo_cv", "headerName": "Ref. CV", "type": "numericColumn", "width": 90, "valueFormatter": num(".1f", "%")},
    {"field": "edge", "headerName": "Edge", "type": "numericColumn", "width": 85, "valueFormatter": num("+.1f", "%"),
     "cellClassRules": {"warn": f"Math.abs(params.value) > {100 * sc.EDGE_REVIEW}"}},
    {"field": "hits", "headerName": "Hits", "type": "numericColumn", "width": 80},
    {"field": "hit_rate", "headerName": "Hit rate", "type": "numericColumn", "width": 95,
     "valueFormatter": num(".1f", "%"), "cellClassRules": {"warn": f"params.value > {100 * sc.HIT_RATE_REVIEW}"}},
    {"field": "flags", "headerName": "Flags", "width": 260, "tooltipField": "flags"},
    {"field": "read_at", "headerName": "Read at", "width": 145, "cellClass": "mono"},
    {"field": "reader", "headerName": "Reader", "width": 115},
    {"field": "dispenser", "headerName": "Dispenser", "width": 120},
    {"field": "lot", "headerName": "Reagent lot", "width": 115, "cellClass": "mono"},
]

HIT_COLUMNS = [
    {"field": "well", "headerName": "Well", "width": 75, "cellClass": "mono"},
    {"field": "compound", "headerName": "Compound", "width": 115, "cellClass": "mono"},
    {"field": "pct", "headerName": "% inhib.", "type": "numericColumn", "width": 95, "valueFormatter": num(".0f"),
     "sort": "desc"},
    {"field": "bscore", "headerName": "B-score", "type": "numericColumn", "width": 95, "valueFormatter": num("+.1f")},
    {"field": "note", "headerName": "Caution", "flex": 1, "minWidth": 120, "cellClass": "note"},
]


def plate_stats(p):
    s = p.stats

    def item(label, value, sub=None, bad=False):
        return html.Div([dmc.Text(label, className="stat-label"),
                         dmc.Text(value, className="stat-value" + (" bad" if bad else "")),
                         sub and dmc.Text(sub, className="stat-sub")], className="stat")

    return [
        item("Z′-factor", f"{s['z']:.2f}", f"Robust Z′ {s['robust_z']:.2f}", s["z"] < sc.Z_REVIEW),
        item("Signal window", f"{s['sb']:.1f}×", f"{s['hi_mean']:,.0f} vs {s['lo_mean']:,.0f}"),
        item("DMSO CV", f"{s['hi_cv']:.1%}", f"Reference {s['lo_cv']:.1%}", s["hi_cv"] > sc.CV_REVIEW),
        item("Edge vs interior", f"{s['edge']:+.1%}", "Outer compound wells, raw",
             abs(s["edge"]) > sc.EDGE_REVIEW),
        item("Hits", f"{s['n_hits']}", f"{s['hit_rate']:.1%} of 320 wells", s["hit_rate"] > sc.HIT_RATE_REVIEW),
    ]


def flag_list(p):
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

def ribbon(run, selected, decisions):
    """Every plate as a small tile in run order, colored by its auto QC result."""
    blocks = []
    for r in range(1, sc.N_RUNS + 1):
        cells = []
        for p in sc.PLATES:
            if p.run != r:
                continue
            decision = decision_of(p.plate_id, decisions)
            cls = f"tile {p.status.lower()}"
            if p.status != "Pass" and decision == "Pending":
                cls += " open"
            if p.plate_id == selected:
                cls += " selected"
            cells.append(html.Button(
                id={"type": "tile", "plate": p.plate_id}, n_clicks=0, className=cls,
                title=f"{p.plate_id} · {p.status} · Z′ {p.stats['z']:.2f} · {decision}",
            ))
        blocks.append(html.Div(
            [html.Div(f"Run {r}", className="ribbon-run"), html.Div(cells, className="ribbon-cells")],
            className="ribbon-block" + ("" if run in ("All", str(r)) else " dim"),
        ))
    return blocks


def legend_item(cls, label):
    return html.Span([html.Span(className=f"tile static {cls}"), label], className="ribbon-key")


header = html.Header(
    html.Div(
        [
            html.Div(
                [
                    html.Div(
                        ["Halden Bio", html.Span("/", className="sep"), sc.CAMPAIGN, html.Span("/", className="sep"),
                         f"{sc.ASSAY}, 384-well"],
                        className="crumbs",
                    ),
                    html.H1("Plate QC review", className="title"),
                    dmc.Group(
                        [
                            dmc.Select(id="run", data=RUN_OPTIONS, value="All", size="xs", w=170,
                                       allowDeselect=False, leftSection=DashIconify(icon="tabler:calendar", width=14),
                                       comboboxProps={"zIndex": 300}),
                            dmc.Text(f"Last plate read {sc.AS_OF:%-d %b %Y, %H:%M}", className="asof"),
                        ],
                        gap="md", mt=10,
                    ),
                ],
                className="head-left",
            ),
            html.Div(
                [
                    html.Div(
                        [html.Span("All 72 plates in run order", className="ribbon-title"),
                         html.Span([legend_item("pass", "Pass"), legend_item("review", "Review"),
                                    legend_item("fail", "Fail"), legend_item("review open", "Awaiting review")],
                                   className="ribbon-keys")],
                        className="ribbon-head",
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
                    dmc.Button("Reset", id={"type": "decide", "value": "Pending"}, size="xs", color="gray",
                               variant="subtle"),
                ], gap=6, className="decide"),
            ],
            justify="space-between", align="flex-start", mb="md",
        ),
        html.Div(id="plate-stats", className="stats"),
        dmc.Grid(
            [
                dmc.GridCol([
                    dmc.Group([
                        dmc.Text("Plate map", className="card-title"),
                        dmc.SegmentedControl(id="view", value="pct", size="xs",
                                             data=[{"value": k, "label": v} for k, v in VIEWS.items()]),
                    ], justify="space-between", mb=4),
                    graph("plate-map", "graph plate"),
                    dmc.Text("Bars show the median % inhibition of compound wells in each row and column. "
                             "Outlined wells are hits. Columns 1–2 hold DMSO, 23–24 the reference inhibitor.", className="card-hint"),
                ], span={"base": 12, "lg": 7}),
                dmc.GridCol([
                    dmc.Text("Why it was flagged", className="card-title", mb=8),
                    html.Div(id="flags"),
                    dmc.Text("Control separation", className="card-title", mt="md", mb=4),
                    graph("controls-chart", "graph controls"),
                    dmc.Text("Shaded bands are mean ± 3 SD. Z′ is the gap between them over the distance between "
                             "the means.", className="card-hint"),
                ], span={"base": 12, "lg": 5}),
                dmc.GridCol([
                    dmc.Group([dmc.Text("Hits on this plate", className="card-title"),
                               dmc.Text(id="hit-hint", className="card-hint")], justify="space-between", mb=6),
                    dag.AgGrid(
                        id="hit-grid", columnDefs=HIT_COLUMNS, rowData=[],
                        defaultColDef={"sortable": True, "resizable": True, "suppressMovable": True},
                        dashGridOptions={"theme": {"function": "qcTheme(themeQuartz)"}, "rowHeight": 32,
                                         "headerHeight": 34, "animateRows": False,
                                         "localeText": {"noRowsToShow": "No compound reached 50% inhibition"}},
                        style={"height": "230px"},
                    ),
                ], span=12),
            ],
            gutter="lg", mt="md",
        ),
    ],
    className="card plate-card",
)

app.layout = dmc.MantineProvider(
    [
        dcc.Store(id="selected", data=DEFAULT_PLATE),
        dcc.Store(id="decisions", data=sc.INITIAL_DECISIONS, storage_type="session"),
        header,
        html.Main(
            [
                html.Div(id="kpis", className="kpis"),
                html.Div(
                    [
                        html.Aside(card("Review queue", html.Div(id="queue", className="queue"),
                                        extra=dmc.Text("Open items first", className="card-hint")),
                                   className="side"),
                        html.Div(
                            [
                                card("Plate quality across the campaign", graph("campaign", "graph campaign"),
                                     extra=dmc.SegmentedControl(
                                         id="metric", value="z", size="xs",
                                         data=[{"value": k, "label": v[1]} for k, v in METRICS.items()])),
                                plate_panel,
                            ],
                            className="center",
                        ),
                    ],
                    className="body",
                ),
                card(
                    "All plates",
                    dag.AgGrid(
                        id="grid", columnDefs=COLUMNS, rowData=[],
                        defaultColDef={"sortable": True, "resizable": True, "suppressMovable": True,
                                       "filter": True},
                        dashGridOptions={"theme": {"function": "qcTheme(themeQuartz)"},
                                         "rowSelection": {"mode": "singleRow", "checkboxes": False,
                                                          "enableClickSelection": True},
                                         "getRowId": {"function": "params.data.plate"},
                                         "animateRows": False, "rowHeight": 34, "headerHeight": 36,
                                         "tooltipShowDelay": 300},
                        className="grid", style={"height": "100%"},
                    ),
                    extra=dmc.Text("Click a row to open the plate", className="card-hint"),
                ),
                dmc.Text(
                    "Compounds, plates and readings are synthetic. Percent inhibition is normalised to the median of "
                    "each plate's own controls; B-scores are median-polish residuals scaled by their MAD. "
                    f"QC rules: Z′ below {sc.Z_FAIL} fails, below {sc.Z_REVIEW} goes to review, as do a DMSO CV over "
                    f"{sc.CV_REVIEW:.0%}, outer wells more than {sc.EDGE_REVIEW:.0%} off the interior, a row or column "
                    f"median beyond ±{sc.LINE_REVIEW}%, and a hit rate over {sc.HIT_RATE_REVIEW:.0%}. Decisions are "
                    "kept for this browser session.",
                    className="foot",
                ),
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
    Input("campaign", "clickData"),
    Input("grid", "cellClicked"),
    Input({"type": "queue", "plate": ALL}, "n_clicks"),
    Input({"type": "tile", "plate": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_plate(click, cell, *_):
    trigger = ctx.triggered_id
    if trigger == "campaign" and click:
        cd = click["points"][0].get("customdata")
        return cd[0] if cd else dash.no_update
    if trigger == "grid" and cell:
        return cell["rowId"]
    if isinstance(trigger, dict) and ctx.triggered[0]["value"]:
        return trigger["plate"]
    return dash.no_update


@app.callback(
    Output("decisions", "data"),
    Input({"type": "decide", "value": ALL}, "n_clicks"),
    State("selected", "data"),
    State("decisions", "data"),
    prevent_initial_call=True,
)
def decide(_, plate, decisions):
    if not ctx.triggered[0]["value"]:
        return dash.no_update
    value = ctx.triggered_id["value"]
    decisions = dict(decisions or {})
    if value == "Pending":
        decisions.pop(plate, None)
    else:
        decisions[plate] = {"decision": value, "by": "You", "note": ""}
    return decisions


@app.callback(
    Output("kpis", "children"),
    Output("queue", "children"),
    Output("grid", "rowData"),
    Output("grid", "selectedRows"),
    Output("ribbon", "children"),
    Input("run", "value"),
    Input("selected", "data"),
    Input("decisions", "data"),
)
def update_overview(run, selected, decisions):
    decisions = decisions or {}
    return kpis(run, decisions), review_queue(run, selected, decisions), grid_rows(run, decisions), \
        {"ids": [selected]}, ribbon(run, selected, decisions)


@app.callback(
    Output("campaign", "figure"),
    Input("run", "value"),
    Input("metric", "value"),
    Input("selected", "data"),
)
def update_campaign(run, metric, selected):
    return campaign_chart(run, metric, selected)


@app.callback(
    Output("plate-title", "children"),
    Output("plate-badges", "children"),
    Output("plate-meta", "children"),
    Output("plate-stats", "children"),
    Output("flags", "children"),
    Output("controls-chart", "figure"),
    Output("hit-grid", "rowData"),
    Output("hit-hint", "children"),
    Input("selected", "data"),
    Input("decisions", "data"),
)
def update_plate(pid, decisions):
    p = sc.BY_ID[pid]
    d = (decisions or {}).get(pid, {})
    decision = d.get("decision", "Pending")
    badges = dmc.Group([status_badge(p.status), decision_badge(decision)], gap=6)
    meta = (f"Run {p.run}, plate {p.order_in_run} of {sc.PLATES_PER_RUN} · Read {p.read_at:%-d %b %Y %H:%M} on "
            f"{p.reader} · Reagents by {p.dispenser} · Lot {p.lot}")
    if decision != "Pending":
        meta += f" · {decision} by {d.get('by', '')}" + (f": {d['note']}" if d.get("note") else "")
    caution = sum(bool(h["note"]) for h in p.hits)
    hint = f"{len(p.hits)} at ≥ {sc.HIT_THRESHOLD}% inhibition" + (
        f", {caution} in a suspect row or edge well" if caution else "")
    return p.plate_id, badges, meta, plate_stats(p), flag_list(p), controls_chart(p), p.hits, hint


@app.callback(
    Output("plate-map", "figure"),
    Input("selected", "data"),
    Input("view", "value"),
)
def update_plate_map(pid, view):
    return plate_map(sc.BY_ID[pid], view)


if __name__ == "__main__":
    app.run(debug=True)
