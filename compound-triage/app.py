"""
Compound Triage

Which molecules in a kinase hit-to-lead program actually work? Set the bar for
each assay in the target product profile and see which compounds clear every
one, where the rest drop out, which chemical series are worth more chemistry,
and, for any compound, its structure, its margin against each criterion and its
dose-response curve.

The assay data is synthetic, see compounds.py.
"""

from collections import Counter
from datetime import date

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

import compounds as cp

# Chart colors, kept in sync with assets/style.css
SURFACE = "#ffffff"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#7f7e78"
GRID = "#ebebe6"
AXIS = "#cfcec7"
SERIES_COLOR = dict(zip(cp.SERIES_NAMES, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))
# Verdict is a status: it always ships with a label in the legend, hover and badges
VERDICT = {
    "Meets every criterion": "#0ca30c",
    "Misses one": "#fab219",
    "Misses two or more": "#b9b8b1",
    "Not fully profiled": "#e4e3de",
}
VERDICT_ICON = {
    "Meets every criterion": "tabler:circle-check-filled",
    "Misses one": "tabler:alert-triangle-filled",
    "Misses two or more": "tabler:circle-x-filled",
    "Not fully profiled": "tabler:hourglass",
}
PASS, FAIL = "#0ca30c", "#d03b3b"
SEQ = ["#f1f6fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]

FONT = "Manrope, system-ui, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, monospace"
THEME = {"fontFamily": FONT, "headings": {"fontFamily": FONT}, "primaryColor": "teal", "defaultRadius": "md"}
DEFAULT_IDX = 2  # every gate's options list has the project default in the middle

app = dash.Dash(
    __name__,
    title="Compound Triage",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800"
        "&family=JetBrains+Mono:wght@400;500&display=swap"
    ],
)
server = app.server


# ---------- Evaluation ----------

def criteria_from(idx):
    return {k: g["options"][i] for (k, g), i in zip(cp.GATES.items(), idx)}


def verdict(ev):
    fails = sum(v is False for v in ev.values())
    if fails == 0 and all(v is True for v in ev.values()):
        return "Meets every criterion"
    if fails == 1 and all(v is not None for v in ev.values()):
        return "Misses one"
    if fails >= 2:
        return "Misses two or more"
    return "Misses one" if fails == 1 else "Not fully profiled"


def scored(series, criteria):
    rows = []
    for c in cp.COMPOUNDS:
        if c.series not in series:
            continue
        ev = cp.evaluate(c, criteria)
        margins = [cp.margin(c, k, criteria[k]) for k in cp.GATES]
        score = sum(min(m, 1.0) for m in margins if m is not None)  # cap so one huge margin can't carry a compound
        rows.append({"c": c, "ev": ev, "verdict": verdict(ev), "passed": sum(v is True for v in ev.values()),
                     "failed": [k for k, v in ev.items() if v is False], "score": score})
    return rows


def rank(rows):
    return sorted(rows, key=lambda r: (r["passed"], -len(r["failed"]), r["score"]), reverse=True)


def fmt_value(key, v):
    if v is None:
        return "Not tested"
    unit = cp.GATES[key]["unit"]
    if key in ("potency", "cell"):
        return f"{v:.1f} {unit} · {fmt_nm(10 ** (9 - v))}"
    if key == "selectivity":
        return f"{v:,.0f}×"
    return f"{v:,.1f} {unit}" if v < 10 else f"{v:,.0f} {unit}"


def fmt_short(key, v):
    if v is None:
        return ""
    if key in ("potency", "cell"):
        return f"{v:.1f}"
    if key == "selectivity":
        return f"{v:,.0f}×"
    return f"{v:,.1f}" if v < 10 else f"{v:,.0f}"


def fmt_nm(nm):
    return f"{nm:,.0f} nM" if nm < 1000 else f"{nm / 1000:,.1f} µM"


def fmt_threshold(key, t):
    g = cp.GATES[key]
    sign = "≥" if g["dir"] == ">=" else "≤"
    if key in ("potency", "cell"):
        return f"{sign} {t:.1f} ({fmt_nm(10 ** (9 - t))})"
    if key == "selectivity":
        return f"{sign} {t:,.0f}×"
    return f"{sign} {t:g} {g['unit']}"


# ---------- Charts ----------

def style_axes(fig):
    for axis in (fig.update_xaxes, fig.update_yaxes):
        axis(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
             title_font={"color": MUTED, "size": 12})
    fig.update_layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font={"family": FONT, "color": INK_2},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12, "family": FONT}},
    )
    return fig


def funnel_chart(rows, criteria):
    """Survivors after each gate, in the order the cascade runs them."""
    alive = list(rows)
    labels, kept, failed, untested = ["Made"], [len(alive)], [0], [0]
    for k, g in cp.GATES.items():
        f = sum(r["ev"][k] is False for r in alive)
        u = sum(r["ev"][k] is None for r in alive)
        alive = [r for r in alive if r["ev"][k] is True]
        labels.append(f"{g['short']} {fmt_threshold(k, criteria[k])}")
        kept.append(len(alive))
        failed.append(f)
        untested.append(u)
    y = labels[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=y, x=kept[::-1], orientation="h", marker={"color": "#256abf", "cornerradius": 4}, name="Still in",
        text=[f"{k}" for k in kept[::-1]], textposition="outside", cliponaxis=False,
        textfont={"color": INK, "size": 12},
        customdata=np.column_stack([failed[::-1], untested[::-1]]),
        hovertemplate="<b>%{y}</b><br>%{x} compounds still in<br>%{customdata[0]} failed here"
                      "<br>%{customdata[1]} never tested<extra></extra>",
    ))
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, max(kept) * 1.12])
    fig.update_yaxes(tickfont={"color": INK_2, "size": 12}, ticksuffix="  ", linecolor="rgba(0,0,0,0)")
    fig.update_layout(margin={"l": 8, "r": 8, "t": 4, "b": 4}, bargap=0.32, showlegend=False)
    return style_axes(fig)


def lle_chart(rows, selected):
    """Potency against lipophilicity, the classic med-chem plot. Diagonals are lipophilic ligand efficiency."""
    fig = go.Figure()
    xs = [r["c"].clogp for r in rows] or [0, 5]
    x0, x1 = min(xs) - 0.4, max(xs) + 0.4
    for lle in (3, 4, 5, 6):
        fig.add_trace(go.Scatter(x=[x0, x1], y=[x0 + lle, x1 + lle], mode="lines", hoverinfo="skip",
                                 line={"color": AXIS, "width": 1, "dash": "dot"}, showlegend=False))
        if x1 + lle <= 9.6:
            fig.add_annotation(x=x1, y=x1 + lle, text=f"LLE {lle}", showarrow=False, xanchor="right",
                               yanchor="bottom", font={"color": MUTED, "size": 10})
    for name in reversed(VERDICT):
        group = [r for r in rows if r["verdict"] == name]
        if not group:
            continue
        hollow = name == "Not fully profiled"
        fig.add_trace(go.Scatter(
            x=[r["c"].clogp for r in group], y=[r["c"].values["potency"] for r in group], mode="markers",
            name=f"{name} ({len(group)})",
            marker={"size": 11 if name == "Meets every criterion" else 9,
                    "color": SURFACE if hollow else VERDICT[name],
                    "line": {"color": "#b9b8b1" if hollow else SURFACE, "width": 1.5 if hollow else 1}},
            customdata=[[r["c"].id, r["c"].series, r["c"].lle, r["passed"],
                         ", ".join(cp.GATES[k]["short"] for k in r["failed"]) or "none"] for r in group],
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>pIC50 %{y:.2f} · cLogP %{x:.2f}"
                          " · LLE %{customdata[2]:.1f}<br>%{customdata[3]} of 7 criteria met"
                          "<br>Misses: %{customdata[4]}<extra></extra>",
        ))
    sel = next((r for r in rows if r["c"].id == selected), None)
    if sel:
        fig.add_trace(go.Scatter(
            x=[sel["c"].clogp], y=[sel["c"].values["potency"]], mode="markers", hoverinfo="skip", showlegend=False,
            marker={"size": 20, "color": "rgba(0,0,0,0)", "line": {"color": INK, "width": 2}},
        ))
    fig.update_xaxes(title="cLogP (lipophilicity)", range=[x0, x1])
    fig.update_yaxes(title="Biochemical pIC50", range=[4.5, 9.8])
    fig.update_layout(
        margin={"l": 56, "r": 12, "t": 8, "b": 44}, uirevision="lle", clickmode="event",
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2, "size": 11},
                "traceorder": "reversed"},
    )
    return style_axes(fig)


def series_heatmap(rows):
    """Share of tested compounds in each series that clear each bar."""
    series = [s for s in cp.SERIES_NAMES if any(r["c"].series == s for r in rows)]
    cols = ["Potency", "Cell", "Select.", "Solub.", "CLint", "Perm.", "hERG", "All 7"]
    z, text, hover = [], [], []
    for s in series:
        group = [r for r in rows if r["c"].series == s]
        zr, tr, hr = [], [], []
        for k in cp.GATES:
            tested = [r for r in group if r["ev"][k] is not None]
            ok = sum(r["ev"][k] for r in tested)
            rate = ok / len(tested) if tested else np.nan
            zr.append(rate)
            tr.append("–" if not tested else f"{rate:.0%}")
            hr.append(f"{ok} of {len(tested)} tested pass" if tested else "None tested")
        allp = sum(r["verdict"] == "Meets every criterion" for r in group)
        zr.append(allp / len(group))
        tr.append(f"{allp}")
        hr.append(f"{allp} of {len(group)} made meet every criterion")
        z.append(zr)
        text.append(tr)
        hover.append(hr)
    z = np.array(z, dtype=float)
    fig = go.Figure(go.Heatmap(
        z=z, x=cols, y=series, customdata=hover,
        colorscale=[[i / (len(SEQ) - 1), c] for i, c in enumerate(SEQ)], zmin=0, zmax=1, xgap=2, ygap=2,
        showscale=False, hovertemplate="<b>%{y}</b> · %{x}<br>%{customdata}<extra></extra>",
    ))
    for i, s in enumerate(series):
        for j, col in enumerate(cols):
            dark = not np.isnan(z[i, j]) and z[i, j] >= 0.62  # dark cells need white labels
            fig.add_annotation(x=col, y=s, text=text[i][j], showarrow=False,
                               font={"color": "#ffffff" if dark else INK, "size": 12, "family": FONT})
    fig.add_vline(x=len(cols) - 1.5, line={"color": SURFACE, "width": 6})
    fig.update_xaxes(side="top", showgrid=False, tickangle=0, tickfont={"color": INK_2, "size": 11})
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont={"color": INK_2, "size": 12}, ticksuffix="  ")
    fig.update_layout(margin={"l": 8, "r": 8, "t": 28, "b": 4})
    return style_axes(fig)


def monthly_chart(rows):
    """Compounds made each month, by verdict: is the chemistry getting better?"""
    months = sorted({(r["c"].made.year, r["c"].made.month) for r in rows})
    x = [date(y, m, 1) for y, m in months]
    fig = go.Figure()
    for name, color in VERDICT.items():
        counts = Counter((r["c"].made.year, r["c"].made.month) for r in rows if r["verdict"] == name)
        if not counts:
            continue
        hollow = name == "Not fully profiled"
        fig.add_trace(go.Bar(
            x=x, y=[counts.get(m, 0) for m in months], name=name,
            marker={"color": color, "line": {"color": SURFACE, "width": 1}, "cornerradius": 0},
            hovertemplate="%{y} compounds<extra>" + name + "</extra>",
            marker_pattern={"shape": "/", "fgcolor": "#b9b8b1", "size": 6} if hollow else None,
        ))
    fig.update_xaxes(dtick="M2", tickformat="%b %y", showgrid=False)
    fig.update_yaxes(title="Compounds made")
    fig.update_layout(
        barmode="stack", bargap=0.25, margin={"l": 56, "r": 12, "t": 44, "b": 32}, hovermode="x unified",
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2, "size": 11},
                "traceorder": "normal"},
    )
    return style_axes(fig)


def margin_chart(c, criteria):
    """How far each measurement sits past its bar, in log units (×10 per unit)."""
    keys = list(cp.GATES)[::-1]
    m = [cp.margin(c, k, criteria[k]) for k in keys]
    labels = [cp.GATES[k]["short"] for k in keys]
    fig = go.Figure()
    tested = [i for i, v in enumerate(m) if v is not None]
    fig.add_trace(go.Bar(
        y=[labels[i] for i in tested], x=[m[i] for i in tested], orientation="h",
        marker={"color": [PASS if m[i] >= 0 else FAIL for i in tested], "cornerradius": 4},
        customdata=[[fmt_value(keys[i], c.values[keys[i]]), fmt_threshold(keys[i], criteria[keys[i]]),
                     "Passes" if m[i] >= 0 else "Fails"] for i in tested],
        hovertemplate="<b>%{y}</b>: %{customdata[2]}<br>Measured %{customdata[0]}<br>Bar %{customdata[1]}"
                      "<extra></extra>",
    ))
    vals = [v for v in m if v is not None] or [0]
    for i, v in enumerate(m):
        val = fmt_short(keys[i], c.values[keys[i]])
        if v is None:
            fig.add_annotation(x=0, y=labels[i], text="Not tested", showarrow=False, xanchor="left", xshift=6,
                               font={"color": MUTED, "size": 11})
        else:
            fig.add_annotation(x=v, y=labels[i], text=("✓ " if v >= 0 else "✗ ") + val, showarrow=False,
                               xanchor="left" if v >= 0 else "right", xshift=6 if v >= 0 else -6,
                               font={"color": INK_2, "size": 11})
    fig.add_vline(x=0, line={"color": INK_2, "width": 1.5})
    fig.add_annotation(x=0, y=1, yref="paper", text="The bar", showarrow=False, yanchor="bottom",
                       font={"color": MUTED, "size": 10})
    fig.update_xaxes(range=[min(vals) - 1.1 if min(vals) < 0 else -0.6, max(max(vals), 0) + 1.1],
                     showticklabels=False, showgrid=False)
    fig.update_yaxes(categoryorder="array", categoryarray=labels, tickfont={"color": INK_2, "size": 12},
                     ticksuffix="  ", showgrid=False)
    fig.update_layout(margin={"l": 8, "r": 8, "t": 18, "b": 4}, showlegend=False, bargap=0.38)
    return style_axes(fig)


def dose_chart(c):
    d = c.curve
    conc = d["conc"]
    ic50 = 10 ** (9 - c.values["potency"])
    fig = go.Figure()
    xs = np.repeat(conc[None, :], 3, axis=0).ravel()
    fig.add_trace(go.Scatter(
        x=xs, y=d["reps"].ravel(), mode="markers", name="Replicates",
        marker={"size": 8, "color": "#9ec5f4", "line": {"color": "#256abf", "width": 1}},
        hovertemplate="%{x:,.1f} nM: %{y:.0f}% activity<extra></extra>",
    ))
    fine = np.logspace(np.log10(conc.min() / 2), np.log10(conc.max() * 2), 160)
    fig.add_trace(go.Scatter(
        x=fine, y=cp.hill(fine, ic50, d["slope"]), mode="lines", name="Fit", line={"color": INK, "width": 2},
        hovertemplate="%{x:,.1f} nM: %{y:.0f}%<extra>Fit</extra>",
    ))
    fig.add_shape(type="line", x0=ic50, x1=ic50, y0=-5, y1=50, line={"color": INK_2, "width": 1, "dash": "dot"})
    fig.add_annotation(x=np.log10(ic50), y=50, text=f"IC50 {fmt_nm(ic50)}", showarrow=False, xanchor="left",
                       xshift=6, yanchor="bottom", font={"color": INK, "size": 11})
    fig.update_xaxes(type="log", title="Concentration (nM)", tickvals=[0.1, 1, 10, 100, 1000, 10000],
                     ticktext=["0.1", "1", "10", "100", "1k", "10k"])
    fig.update_yaxes(title="Kinase activity remaining (%)", range=[-8, 115], tickvals=[0, 25, 50, 75, 100])
    fig.update_layout(margin={"l": 56, "r": 12, "t": 8, "b": 44}, showlegend=False)
    return style_axes(fig)


# ---------- Components ----------

def graph(graph_id, cls="graph"):
    return html.Div(
        dcc.Graph(id=graph_id, config={"displayModeBar": False, "responsive": True}, style={"height": "100%"}),
        className=cls,
    )


def card(title, *children, hint=None, **kwargs):
    return dmc.Paper(
        [dmc.Group([dmc.Text(title, className="card-title"), hint and dmc.Text(hint, className="card-hint")],
                   justify="space-between", mb="xs", wrap="nowrap", align="baseline"),
         *children],
        className="card", **kwargs,
    )


def verdict_badge(name, size="sm"):
    return dmc.Badge(
        name, size=size, radius="xl", variant="light",
        color={"Meets every criterion": "green", "Misses one": "yellow"}.get(name, "gray"),
        leftSection=DashIconify(icon=VERDICT_ICON[name], width=12), className="verdict",
    )


def series_tag(s):
    return html.Span([html.Span(className="dot", style={"background": SERIES_COLOR[s]}), s], className="series-tag")


def kpi(label, value, sub, icon):
    return html.Div(
        [
            dmc.Group([DashIconify(icon=icon, width=16, className="kpi-icon"), dmc.Text(label, className="kpi-label")],
                      gap=6, wrap="nowrap"),
            dmc.Text(value, className="kpi-value"),
            dmc.Text(sub, className="kpi-sub"),
        ],
        className="kpi",
    )


def kpis(rows):
    n = len(rows)
    winners = [r for r in rows if r["verdict"] == "Meets every criterion"]
    near = [r for r in rows if len(r["failed"]) == 1]
    blockers = Counter(r["failed"][0] for r in near)
    top = blockers.most_common(1)
    actives = [r for r in rows if r["ev"]["potency"]]
    best = max(actives, key=lambda r: r["c"].lle, default=None)
    profiled = sum(all(v is not None for v in r["ev"].values()) for r in rows)
    return [
        kpi("Compounds made", f"{n}", f"{profiled} fully profiled", "tabler:flask"),
        kpi("Meet every criterion", f"{len(winners)}", f"{len(winners) / n:.1%} of compounds made" if n else "–",
            "tabler:circle-check"),
        kpi("Miss by one criterion", f"{len(near)}",
            f"Most often blocked by {cp.GATES[top[0][0]]['short']} ({top[0][1]})" if top else "None", "tabler:target-arrow"),
        kpi("Best LLE among potent", f"{best['c'].lle:.1f}" if best else "–",
            f"{best['c'].id} · pIC50 {best['c'].values['potency']:.1f}" if best else "", "tabler:scale"),
    ]


def shelf(rows, selected):
    top = rank(rows)[:7]
    if not top:
        return dmc.Text("No compounds in the selected series.", className="empty")
    items = []
    for r in top:
        c = r["c"]
        items.append(html.Div(
            [
                dmc.Group([dmc.Text(c.id, className="mono cid"), dmc.Text(f"{r['passed']}/7", className="score")],
                          justify="space-between", wrap="nowrap"),
                html.Img(src=cp.structure_svg(c.smiles, 220, 150), className="thumb", alt=f"Structure of {c.id}"),
                series_tag(c.series),
                dmc.Text(
                    "Clears every bar" if not r["failed"] else
                    "Misses " + ", ".join(cp.GATES[k]["short"] for k in r["failed"]),
                    className="shelf-note " + ("ok" if not r["failed"] else ""),
                ),
            ],
            id={"type": "shelf", "id": c.id}, n_clicks=0,
            className="shelf-item" + (" selected" if c.id == selected else ""),
        ))
    return items


def property_list(c):
    def item(label, value, warn=False):
        return html.Div([dmc.Text(label, className="prop-label"),
                         dmc.Text(value, className="prop-value" + (" warn" if warn else ""))], className="prop")

    return [
        item("MW", f"{c.mw:.0f}", c.mw > 500),
        item("cLogP", f"{c.clogp:.2f}", c.clogp > 5),
        item("TPSA", f"{c.tpsa:.0f} Å²", c.tpsa > 140),
        item("HBD / HBA", f"{c.hbd} / {c.hba}", c.hbd > 5 or c.hba > 10),
        item("Rot. bonds", f"{c.rotb}"),
        item("QED", f"{c.qed:.2f}"),
        item("LLE", f"{c.lle:.1f}"),
        item("Basic amine", "Yes" if c.basic else "No"),
    ]


# ---------- Layout ----------

def gate_control(key, g):
    marks = [{"value": i, "label": f"{o:g}"} for i, o in enumerate(g["options"])]
    return html.Div(
        [
            dmc.Group([dmc.Text(g["label"], className="gate-label"),
                       dmc.Text(id={"type": "gate-value", "key": key}, className="gate-value")],
                      justify="space-between", wrap="nowrap"),
            dmc.Slider(id={"type": "gate", "key": key}, min=0, max=len(g["options"]) - 1, step=1,
                       value=DEFAULT_IDX, marks=marks, restrictToMarks=True, label=None, size="sm",
                       color="teal", className="gate-slider"),
            dmc.Text(id={"type": "gate-count", "key": key}, className="gate-count"),
        ],
        className="gate",
    )


navbar = dmc.AppShellNavbar(
    dmc.ScrollArea(
        dmc.Stack(
            [
                dmc.Stack([
                    dmc.Text("Chemical series", className="side-title"),
                    dmc.CheckboxGroup(
                        id="series", value=cp.SERIES_NAMES,
                        children=dmc.Stack([
                            dmc.Checkbox(value=s, size="xs", color="dark", label=dmc.Group(
                                [html.Span(className="dot", style={"background": SERIES_COLOR[s]}), s,
                                 dmc.Text(f"{sum(c.series == s for c in cp.COMPOUNDS)}", className="side-count")],
                                gap=6, wrap="nowrap"))
                            for s in cp.SERIES_NAMES], gap=6),
                    ),
                ], gap=8),
                dmc.Divider(color="#ecece7"),
                dmc.Group([
                    dmc.Stack([dmc.Text("Target product profile", className="side-title"),
                               dmc.Text("Drag right to raise the bar", className="side-hint")], gap=0),
                    dmc.Button("Reset", id="reset", variant="subtle", color="gray", size="compact-xs",
                               leftSection=DashIconify(icon="tabler:restore", width=14)),
                ], justify="space-between", align="flex-start"),
                *[gate_control(k, g) for k, g in cp.GATES.items()],
            ],
            gap="md", p="md",
        ),
        type="auto", h="100%",
    ),
    className="navbar",
)

header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Burger(id="burger", size="sm", hiddenFrom="sm", opened=False),
                    html.Div(DashIconify(icon="tabler:hexagons", width=20), className="brand-mark"),
                    dmc.Stack([dmc.Text("Compound Triage", className="brand-name"),
                               dmc.Text(f"{cp.TARGET} kinase · hit-to-lead", className="brand-sub")], gap=0),
                ],
                gap="sm", wrap="nowrap",
            ),
            dmc.Text(f"{len(cp.COMPOUNDS)} compounds · assays to {cp.AS_OF:%-d %b %Y}", className="asof",
                     visibleFrom="sm"),
        ],
        justify="space-between", h="100%", px="lg", wrap="nowrap",
    ),
    className="header",
)

detail = dmc.Paper(
    [
        dmc.Group(
            [
                dmc.Group([dmc.Title(id="cmp-title", order=2, className="cmp-title"), html.Div(id="cmp-badges")],
                          gap="sm", align="center"),
                dmc.Text(id="cmp-meta", className="cmp-meta"),
            ],
            justify="space-between", align="center", mb="md",
        ),
        dmc.Grid(
            [
                dmc.GridCol([
                    html.Div(html.Img(id="cmp-structure", className="structure", alt="Compound structure"),
                             className="structure-wrap"),
                    dmc.Text(id="cmp-smiles", className="smiles mono"),
                    html.Div(id="cmp-props", className="props"),
                ], span={"base": 12, "md": 6, "xl": 4}),
                dmc.GridCol([dmc.Text("Against each criterion", className="card-title"),
                             dmc.Text("Distance past the bar, log scale", className="card-hint"),
                             graph("margin-chart", "graph mid")], span={"base": 12, "md": 6, "xl": 4}),
                dmc.GridCol([dmc.Text("Biochemical dose-response", className="card-title"),
                             dmc.Text("10-point curve, three replicates", className="card-hint"),
                             graph("dose-chart", "graph mid")], span={"base": 12, "xl": 4}),
            ],
            gutter="lg",
        ),
    ],
    className="card detail",
)

main = dmc.AppShellMain(
    html.Div(
        [
            dcc.Store(id="selected"),
            html.Div(id="kpis", className="kpis"),
            dmc.Grid(
                [
                    dmc.GridCol(card("Where compounds drop out", graph("funnel", "graph"),
                                     hint="Gates in cascade order"), span={"base": 12, "lg": 5}),
                    dmc.GridCol(card("Potency vs lipophilicity", graph("lle", "graph"),
                                     hint="Click a compound"), span={"base": 12, "lg": 7}),
                    dmc.GridCol(card("Closest to a candidate", html.Div(id="shelf", className="shelf"),
                                     hint="Ranked by criteria met, then margin"), span=12),
                    dmc.GridCol(card("Which series clear each bar", graph("heatmap", "graph short"),
                                     hint="Share of tested compounds that pass"), span={"base": 12, "lg": 7}),
                    dmc.GridCol(card("Is the chemistry getting better?", graph("monthly", "graph short"),
                                     hint="Compounds made per month"), span={"base": 12, "lg": 5}),
                ],
                gutter="md",
            ),
            detail,
            dmc.Text(
                f"{cp.TARGET} and every compound, series and measurement here are made up. Structures are valid "
                "molecules built from four kinase-like scaffolds; MW, cLogP, TPSA and QED are computed with RDKit. "
                "Compounds go through the cascade as they would in a real project: only those with pIC50 ≥ 6 "
                "were run in cells, and only those with cell pEC50 ≥ 5.8 were profiled for ADME and hERG.",
                className="foot",
            ),
        ],
        className="main",
    ),
)

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [header, navbar, main],
        id="shell", header={"height": 60}, padding=0,
        navbar={"width": 300, "breakpoint": "sm", "collapsed": {"mobile": True}},
    ),
    theme=THEME, forceColorScheme="light",
)


# ---------- Callbacks ----------

@app.callback(Output("shell", "navbar"), Input("burger", "opened"), State("shell", "navbar"))
def toggle_nav(opened, navbar):
    navbar["collapsed"] = {"mobile": not opened}
    return navbar


@app.callback(Output({"type": "gate", "key": ALL}, "value"), Input("reset", "n_clicks"), prevent_initial_call=True)
def reset(_):
    return [DEFAULT_IDX] * len(cp.GATES)


@app.callback(
    Output("kpis", "children"),
    Output("funnel", "figure"),
    Output("heatmap", "figure"),
    Output("monthly", "figure"),
    Output({"type": "gate-value", "key": ALL}, "children"),
    Output({"type": "gate-count", "key": ALL}, "children"),
    Input("series", "value"),
    Input({"type": "gate", "key": ALL}, "value"),
)
def update_overview(series, idx):
    criteria = criteria_from(idx)
    rows = scored(series or [], criteria)
    values = [fmt_threshold(k, criteria[k]) for k in cp.GATES]
    counts = []
    for k in cp.GATES:
        tested = [r for r in rows if r["ev"][k] is not None]
        counts.append(f"{sum(r['ev'][k] for r in tested)} of {len(tested)} tested pass")
    return kpis(rows), funnel_chart(rows, criteria), series_heatmap(rows), monthly_chart(rows), values, counts


@app.callback(
    Output("selected", "data"),
    Input("lle", "clickData"),
    Input({"type": "shelf", "id": ALL}, "n_clicks"),
    Input("series", "value"),
    Input({"type": "gate", "key": ALL}, "value"),
    State("selected", "data"),
)
def select(click, _, series, idx, current):
    trigger = ctx.triggered_id
    if trigger == "lle" and click:
        cd = click["points"][0].get("customdata")
        return cd[0] if cd else dash.no_update
    if isinstance(trigger, dict) and trigger.get("type") == "shelf":
        return trigger["id"] if ctx.triggered[0]["value"] else dash.no_update
    # Keep the current compound while it is still shown, otherwise jump to the best one
    if current in cp.BY_ID and cp.BY_ID[current].series in (series or []):
        return dash.no_update
    top = rank(scored(series or [], criteria_from(idx)))
    return top[0]["c"].id if top else None


@app.callback(
    Output("lle", "figure"),
    Output("shelf", "children"),
    Output("cmp-title", "children"),
    Output("cmp-badges", "children"),
    Output("cmp-meta", "children"),
    Output("cmp-structure", "src"),
    Output("cmp-smiles", "children"),
    Output("cmp-props", "children"),
    Output("margin-chart", "figure"),
    Output("dose-chart", "figure"),
    Input("selected", "data"),
    Input("series", "value"),
    Input({"type": "gate", "key": ALL}, "value"),
)
def update_compound(selected, series, idx):
    criteria = criteria_from(idx)
    rows = scored(series or [], criteria)
    lle, items = lle_chart(rows, selected), shelf(rows, selected)
    c = cp.BY_ID.get(selected)
    if c is None:
        empty = style_axes(go.Figure())
        return lle, items, "No compound selected", None, "", None, "", [], empty, empty
    ev = cp.evaluate(c, criteria)
    badges = dmc.Group([verdict_badge(verdict(ev)), series_tag(c.series)], gap=8)
    meta = f"Made {c.made:%-d %b %Y} · R1 {c.r1.replace('%10', '1')} · R2 {c.r2.replace('%11', '1')}"
    return (lle, items, c.id, badges, meta, cp.structure_svg(c.smiles, 420, 280), c.smiles, property_list(c),
            margin_chart(c, criteria), dose_chart(c))


if __name__ == "__main__":
    app.run(debug=True, port=8061)
