"""
Compound Triage

Which molecules in a kinase hit-to-lead program actually work? Set the bar for
each assay in the target product profile and see which compounds clear every
one, what their structures look like, and what is holding the rest back.

The assay data is synthetic, see compounds.py.
"""

import dash
import dash_mantine_components as dmc
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
# Verdict is a status: it always ships with a label in the legend, hover and badges
VERDICT = {
    "Meets every criterion": ("#0ca30c", "green", "tabler:circle-check-filled"),
    "Misses one": ("#fab219", "yellow", "tabler:alert-triangle-filled"),
    "Misses two or more": ("#c4c3bc", "gray", "tabler:circle-x-filled"),
}

FONT = "Manrope, system-ui, sans-serif"
THEME = {"fontFamily": FONT, "headings": {"fontFamily": FONT}, "primaryColor": "teal", "defaultRadius": "md"}
DEFAULT_IDX = 2  # every gate's options list has the project default in the middle
N_CARDS = 9


def load_dash_plugins(skip=("dash_ai_analyst",)):
    """Load installed Dash plugins ourselves, leaving out the embedded AI chat.

    Dash otherwise loads every installed `dash_hooks` plugin into every app, and
    there is no setting to opt out of one. Must run before dash.Dash() is created.
    """
    from importlib import metadata

    from dash._hooks import HooksManager

    if HooksManager._registered:
        return
    for dist in metadata.distributions():
        for entry in dist.entry_points:
            if entry.group == "dash_hooks" and entry.name not in skip:
                entry.load()
    HooksManager._registered = True


load_dash_plugins()

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


def scored(criteria):
    rows = []
    for c in cp.COMPOUNDS:
        ev = cp.evaluate(c, criteria)
        failed = [k for k, v in ev.items() if v is False]
        if not failed and all(v is True for v in ev.values()):
            verdict = "Meets every criterion"
        elif len(failed) == 1:
            verdict = "Misses one"
        else:
            verdict = "Misses two or more"
        rows.append({"c": c, "ev": ev, "failed": failed, "verdict": verdict,
                     "passed": sum(v is True for v in ev.values())})
    # Most criteria met first; ties go to the more potent compound
    rows.sort(key=lambda r: (r["passed"], -len(r["failed"]), r["c"].values["potency"]), reverse=True)
    return rows


def fmt_nm(nm):
    return f"{nm:,.0f} nM" if nm < 1000 else f"{nm / 1000:,.1f} µM"


def fmt_value(key, v):
    if v is None:
        return "Not tested"
    if key in ("potency", "cell"):
        return fmt_nm(10 ** (9 - v))
    if key == "selectivity":
        return f"{v:,.0f}×"
    unit = cp.GATES[key]["unit"]
    return f"{v:,.1f} {unit}" if v < 10 else f"{v:,.0f} {unit}"


def fmt_threshold(key, t):
    sign = "≥" if cp.GATES[key]["dir"] == ">=" else "≤"
    if key in ("potency", "cell"):
        # pIC50 7.5 is 32 nM: potency bars read as "at most this concentration"
        return f"≤ {fmt_nm(10 ** (9 - t))}"
    if key == "selectivity":
        return f"{sign} {t:,.0f}×"
    return f"{sign} {t:g} {cp.GATES[key]['unit']}"


# ---------- Pieces ----------

def verdict_badge(name):
    _, color, icon = VERDICT[name]
    return dmc.Badge(name, size="md", radius="xl", variant="light", color=color,
                     leftSection=DashIconify(icon=icon, width=13), className="verdict")


def candidate_cards(rows, selected):
    cards = []
    for r in rows[:N_CARDS]:
        c = r["c"]
        note = "Clears every bar" if not r["failed"] else "Misses " + ", ".join(
            cp.GATES[k]["short"] for k in r["failed"])
        cards.append(html.Div(
            [
                html.Div([html.Span(c.id, className="cid"), html.Span(f"{r['passed']}/7", className="score")],
                         className="card-row"),
                html.Img(src=c.structure, className="thumb", alt=f"Structure of {c.id}"),
                html.Div(note, className="note" + (" ok" if not r["failed"] else "")),
            ],
            id={"type": "cand", "id": c.id}, n_clicks=0,
            className="cand" + (" selected" if c.id == selected else ""),
        ))
    return cards


def checklist(r, criteria):
    c = r["c"]
    items = []
    for k, g in cp.GATES.items():
        ok = r["ev"][k]
        icon, cls = {True: ("tabler:circle-check-filled", "pass"), False: ("tabler:circle-x-filled", "fail"),
                     None: ("tabler:circle-dashed", "untested")}[ok]
        items.append(html.Div(
            [
                DashIconify(icon=icon, width=18, className="check-icon " + cls),
                html.Span(g["label"], className="check-label"),
                html.Span(fmt_value(k, c.values[k]), className="check-value " + cls),
                html.Span(fmt_threshold(k, criteria[k]), className="check-bar"),
            ],
            className="check",
        ))
    return items


def scatter(rows, selected):
    """Potency against lipophilicity, the classic med-chem plot."""
    fig = go.Figure()
    for name in reversed(VERDICT):
        group = [r for r in rows if r["verdict"] == name]
        if not group:
            continue
        color = VERDICT[name][0]
        fig.add_trace(go.Scatter(
            x=[r["c"].clogp for r in group], y=[r["c"].values["potency"] for r in group], mode="markers",
            name=f"{name} ({len(group)})",
            marker={"size": 12 if name == "Meets every criterion" else 9, "color": color,
                    "line": {"color": SURFACE, "width": 1}},
            customdata=[[r["c"].id, r["passed"]] for r in group],
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} of 7 criteria met"
                          "<br>pIC50 %{y:.1f} · cLogP %{x:.1f}<extra></extra>",
        ))
    sel = next((r for r in rows if r["c"].id == selected), None)
    if sel:
        fig.add_trace(go.Scatter(
            x=[sel["c"].clogp], y=[sel["c"].values["potency"]], mode="markers", hoverinfo="skip", showlegend=False,
            marker={"size": 20, "color": "rgba(0,0,0,0)", "line": {"color": INK, "width": 2}},
        ))
    for axis in (fig.update_xaxes, fig.update_yaxes):
        axis(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
             title_font={"color": MUTED, "size": 12})
    fig.update_xaxes(title="cLogP (greasier →)")
    fig.update_yaxes(title="Potency, pIC50 (stronger ↑)")
    fig.update_layout(
        margin={"l": 56, "r": 12, "t": 8, "b": 44}, uirevision="scatter", paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE, font={"family": FONT, "color": INK_2},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12, "family": FONT}},
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2, "size": 12},
                "traceorder": "reversed"},
    )
    return fig


# ---------- Layout ----------

def gate_control(key, g):
    return html.Div(
        [
            dmc.Group([dmc.Text(g["label"], className="gate-label"),
                       dmc.Text(id={"type": "gate-value", "key": key}, className="gate-value")],
                      justify="space-between", wrap="nowrap"),
            dmc.Slider(id={"type": "gate", "key": key}, min=0, max=len(g["options"]) - 1, step=1,
                       value=DEFAULT_IDX, restrictToMarks=True, label=None, size="sm", color="teal",
                       marks=[{"value": i} for i in range(len(g["options"]))], className="gate-slider"),
        ],
        className="gate",
    )


navbar = dmc.AppShellNavbar(
    dmc.ScrollArea(
        dmc.Stack(
            [
                dmc.Group([
                    dmc.Stack([dmc.Text("What counts as working", className="side-title"),
                               dmc.Text("Slide right to raise the bar", className="side-hint")], gap=0),
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
            dmc.Burger(id="burger", size="sm", hiddenFrom="sm", opened=False),
            html.Div(DashIconify(icon="tabler:hexagons", width=20), className="brand-mark"),
            dmc.Stack([dmc.Text("Compound Triage", className="brand-name"),
                       dmc.Text(f"{cp.TARGET} kinase · hit-to-lead", className="brand-sub")], gap=0),
        ],
        gap="sm", h="100%", px="lg", wrap="nowrap",
    ),
    className="header",
)

main = dmc.AppShellMain(
    html.Div(
        [
            dcc.Store(id="selected"),
            html.Div([html.H1(id="headline", className="headline"), html.P(id="subline", className="subline")]),
            dmc.Grid(
                [
                    dmc.GridCol(dmc.Paper(
                        [dmc.Text("Closest to a candidate", className="card-title"),
                         html.Div(id="cands", className="cands")],
                        className="card",
                    ), span={"base": 12, "lg": 7}),
                    dmc.GridCol(dmc.Paper(
                        [
                            dmc.Group([dmc.Text(id="cmp-id", className="cmp-id"), html.Div(id="cmp-badge")],
                                      justify="space-between", wrap="nowrap"),
                            html.Img(id="cmp-structure", className="structure", alt="Compound structure"),
                            html.Div(id="cmp-checks", className="checks"),
                        ],
                        className="card",
                    ), span={"base": 12, "lg": 5}),
                    dmc.GridCol(dmc.Paper(
                        [dmc.Group([dmc.Text(f"All {len(cp.COMPOUNDS)} compounds", className="card-title"),
                                    dmc.Text("Click a dot to open it", className="card-hint")],
                                   justify="space-between"),
                         html.Div(dcc.Graph(id="scatter", config={"displayModeBar": False, "responsive": True},
                                            style={"height": "100%"}), className="graph")],
                        className="card",
                    ), span=12),
                ],
                gutter="md",
            ),
            dmc.Text(
                f"{cp.TARGET} and every compound and measurement here are made up. The structures are valid "
                "molecules, drawn and profiled with RDKit when the data was built.",
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
        navbar={"width": 280, "breakpoint": "sm", "collapsed": {"mobile": True}},
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
    Output("selected", "data"),
    Input("scatter", "clickData"),
    Input({"type": "cand", "id": ALL}, "n_clicks"),
    Input({"type": "gate", "key": ALL}, "value"),
    State("selected", "data"),
)
def select(click, _, idx, current):
    trigger = ctx.triggered_id
    if trigger == "scatter" and click:
        cd = click["points"][0].get("customdata")
        return cd[0] if cd else dash.no_update
    if isinstance(trigger, dict) and trigger.get("type") == "cand":
        return trigger["id"] if ctx.triggered[0]["value"] else dash.no_update
    if current in cp.BY_ID:
        return dash.no_update
    return scored(criteria_from(idx))[0]["c"].id


@app.callback(
    Output({"type": "gate-value", "key": ALL}, "children"),
    Output("headline", "children"),
    Output("subline", "children"),
    Output("cands", "children"),
    Output("scatter", "figure"),
    Output("cmp-id", "children"),
    Output("cmp-badge", "children"),
    Output("cmp-structure", "src"),
    Output("cmp-checks", "children"),
    Input({"type": "gate", "key": ALL}, "value"),
    Input("selected", "data"),
)
def update(idx, selected):
    criteria = criteria_from(idx)
    rows = scored(criteria)
    n_ok = sum(r["verdict"] == "Meets every criterion" for r in rows)
    n_one = sum(r["verdict"] == "Misses one" for r in rows)
    headline = (f"{n_ok} of {len(rows)} molecules clear every bar" if n_ok else
                f"None of the {len(rows)} molecules clear every bar")
    subline = f"{n_one} more miss by a single criterion."
    r = next((r for r in rows if r["c"].id == selected), rows[0])
    c = r["c"]
    return ([fmt_threshold(k, criteria[k]) for k in cp.GATES], headline, subline, candidate_cards(rows, c.id),
            scatter(rows, c.id), c.id, verdict_badge(r["verdict"]), c.structure,
            checklist(r, criteria))


if __name__ == "__main__":
    app.run(debug=True, port=8061)
