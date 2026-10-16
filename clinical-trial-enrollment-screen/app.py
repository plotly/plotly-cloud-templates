"""
Clinical Trial Risk Screen

Screens a portfolio of clinical trials for two risks: missing the enrollment
target on time, and failing (early termination or a missed primary endpoint).
Pick a trial from the risk matrix or the watchlist to see its enrollment
forecast, what drives its failure risk, its screening funnel and site
performance, and to try out fixes such as adding sites or relaxing criteria.

The trials are synthetic, see trials.py.
"""

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

import trials as tr

# Chart colors, kept in sync with assets/style.css
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#7a7974"
GRID = "#ecebe7"
AXIS = "#d6d5d0"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
NEUTRAL = "#a3a29a"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
STATUS_ICON = {
    "good": "tabler:circle-check",
    "warning": "tabler:alert-triangle",
    "serious": "tabler:alert-octagon",
    "critical": "tabler:urgent",
}
VERDICT_LEVEL = {"On track": "good", "Watch": "warning", "Intervene": "critical"}
PHASE_COLOR = dict(zip(tr.PHASES, SERIES))

THEME = {
    "fontFamily": "'Public Sans', system-ui, sans-serif",
    "headings": {"fontFamily": "'Source Serif 4', Georgia, serif"},
    "primaryColor": "teal",
    "defaultRadius": "lg",
}

app = dash.Dash(
    __name__,
    title="Clinical Trial Risk Screen",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap"
    ],
)
server = app.server


def filtered(areas, phase):
    return [t for t in tr.TRIALS if t.area in (areas or []) and (phase == "All" or t.phase == phase)]


def risk_rank(t):
    s = tr.SCORES[t.id]
    return -max(1 - s["p_on_time"], s["p_fail"])


def month_label(d):
    return d.strftime("%b %Y")


def months_from_now(n):
    """Projected completion as a month label, or '5+ yrs' when it falls past the simulation."""
    if n is None:
        return "Enrolled"
    return "5+ yrs" if n > tr.HORIZON else month_label(tr.add_months(tr.AS_OF, n))


def style_axes(fig):
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
                     title_font={"color": MUTED, "size": 12})
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
                     title_font={"color": MUTED, "size": 12})
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": "Public Sans, system-ui, sans-serif", "color": INK_2},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12}},
    )
    return fig


def risk_matrix(trials, selected):
    fig = go.Figure()
    # Quadrants split at 50% on both risks
    for x0, x1, y0, y1, label, xa, ya in [
        (0, 0.5, 0, 0.5, "On track", "left", "bottom"),
        (0.5, 1, 0, 0.5, "Enrollment problem", "right", "bottom"),
        (0, 0.5, 0.5, 1, "Design problem", "left", "top"),
        (0.5, 1, 0.5, 1, "Intervene", "right", "top"),
    ]:
        if label == "Intervene":
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor="rgba(208,59,59,0.06)",
                          line={"width": 0}, layer="below")
        fig.add_annotation(x=x0 if xa == "left" else x1, y=y0 if ya == "bottom" else y1, text=label,
                           showarrow=False, xanchor=xa, yanchor=ya, xshift=8 if xa == "left" else -8,
                           yshift=8 if ya == "bottom" else -8, font={"color": MUTED, "size": 11})
    fig.add_hline(y=0.5, line={"color": AXIS, "width": 1, "dash": "dot"})
    fig.add_vline(x=0.5, line={"color": AXIS, "width": 1, "dash": "dot"})

    for phase in tr.PHASES:
        group = [t for t in trials if t.phase == phase]
        if not group:
            continue
        s = [tr.SCORES[t.id] for t in group]
        fig.add_trace(go.Scatter(
            x=[1 - x["p_on_time"] for x in s], y=[x["p_fail"] for x in s],
            mode="markers", name=phase,
            marker={"size": [10 + 14 * np.sqrt(t.target / 1100) for t in group], "color": PHASE_COLOR[phase],
                    "line": {"color": SURFACE, "width": 2}, "opacity": 0.9},
            customdata=[[t.id, t.indication, x["p_on_time"], t.enrolled, t.target] for t, x in zip(group, s)],
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                          "On-time enrollment %{customdata[2]:.0%} · %{customdata[3]}/%{customdata[4]} enrolled<br>"
                          "Failure risk %{y:.0%}<extra>" + phase + "</extra>",
        ))
    if selected in tr.BY_ID and tr.BY_ID[selected] in trials:
        s = tr.SCORES[selected]
        fig.add_trace(go.Scatter(
            x=[1 - s["p_on_time"]], y=[s["p_fail"]], mode="markers+text", text=[selected],
            textposition="top center", textfont={"color": INK, "size": 12}, hoverinfo="skip", showlegend=False,
            marker={"size": 30, "color": "rgba(0,0,0,0)", "line": {"color": INK, "width": 2}},
        ))
    fig.update_xaxes(range=[-0.04, 1.04], tickformat=".0%", title="Enrollment risk (chance of missing the target date)")
    fig.update_yaxes(range=[-0.02, 1.04], tickformat=".0%", title="Failure risk")
    fig.update_layout(
        margin={"l": 56, "r": 16, "t": 8, "b": 48}, clickmode="event", uirevision="matrix",
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2}},
    )
    return style_axes(fig)


def enrollment_chart(t, base, scenario):
    fig = go.Figure()
    actual_x = [t.start] + [tr.add_months(t.start, m + 1) for m in range(t.elapsed)]
    actual_y = np.concatenate([[0], t.monthly.cumsum()])
    plan_end = tr.add_months(t.start, t.plan_months)

    fig.add_trace(go.Scatter(
        x=[t.start, plan_end], y=[0, t.target], mode="lines", name="Plan",
        line={"color": MUTED, "width": 2, "dash": "dash"}, hovertemplate="%{y:,.0f} planned<extra>Plan</extra>",
    ))

    def band(s, color, name, fill):
        if s["paths"] is None:
            return
        n = min(tr.HORIZON, (s["hi"] or tr.HORIZON) + 2)
        lo, med, hi = t.enrolled + np.percentile(s["paths"][:, :n], [10, 50, 90], axis=0)
        x = [tr.AS_OF] + [tr.add_months(tr.AS_OF, k + 1) for k in range(n)]
        fig.add_trace(go.Scatter(
            x=x + x[::-1], y=np.concatenate([[t.enrolled], hi, lo[::-1], [t.enrolled]]),
            fill="toself", fillcolor=fill, line={"width": 0}, hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=x, y=np.concatenate([[t.enrolled], med]), mode="lines", name=name,
            line={"color": color, "width": 2, "dash": "dot"},
            customdata=np.column_stack([np.concatenate([[t.enrolled], lo]), np.concatenate([[t.enrolled], hi])]),
            hovertemplate="%{y:,.0f} (80%: %{customdata[0]:,.0f}–%{customdata[1]:,.0f})<extra>" + name + "</extra>",
        ))

    band(base, SERIES[0], "Forecast", "rgba(42,120,214,0.12)")
    if scenario is not None:
        band(scenario, SERIES[1], "Scenario", "rgba(235,104,52,0.08)")

    fig.add_trace(go.Scatter(
        x=actual_x, y=actual_y, mode="lines", name="Enrolled", line={"color": SERIES[0], "width": 2.5},
        hovertemplate="%{y:,.0f} enrolled<extra>Actual</extra>",
    ))
    fig.add_hline(y=t.target, line={"color": INK_2, "width": 1})
    fig.add_annotation(x=0, xref="paper", y=t.target, text=f"Target {t.target:,}", showarrow=False,
                       xanchor="left", yanchor="bottom", font={"color": INK_2, "size": 11})
    for when, label in [(tr.AS_OF, "Today"), (plan_end, "Planned end")]:
        fig.add_vline(x=when, line={"color": AXIS if label == "Today" else INK_2, "width": 1, "dash": "dot"})
        fig.add_annotation(x=when, y=1, yref="paper", text=label, showarrow=False, xanchor="left", xshift=4,
                           yanchor="top", font={"color": MUTED, "size": 11})
    fig.update_yaxes(rangemode="tozero", title="Patients randomized", range=[0, t.target * 1.12])
    fig.update_layout(
        margin={"l": 64, "r": 16, "t": 8, "b": 32}, hovermode="x unified", uirevision=t.id,
        legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.02, "yanchor": "bottom",
                "font": {"color": INK_2}},
    )
    return style_axes(fig)


def drivers_chart(t, s):
    """Waterfall from the phase/area baseline to the trial's failure risk, biggest movers first."""
    terms = sorted(s["terms"], key=lambda x: -abs(x[2]))
    logit, prev = s["base_logit"], s["baseline"]
    labels, deltas, details = [f"Baseline · {t.phase}, {t.area}"], [prev * 100], ["Typical for phase and area"]
    for name, detail, v in terms:
        logit += v
        p = tr.sigmoid(logit)
        labels.append(name)
        deltas.append((p - prev) * 100)
        details.append(detail)
        prev = p
    labels.append("Failure risk")
    deltas.append(prev * 100)
    details.append(tr.LEVEL_LABEL[s["fail_level"]] + " risk")
    measure = ["absolute"] + ["relative"] * len(terms) + ["total"]
    text = [f"{deltas[0]:.0f}%"] + [f"{d:+.1f}" for d in deltas[1:-1]] + [f"{deltas[-1]:.0f}%"]

    fig = go.Figure(go.Waterfall(
        orientation="h", y=labels, x=deltas, measure=measure, text=text, textposition="outside",
        textfont={"color": INK_2, "size": 11}, customdata=details, cliponaxis=False,
        increasing={"marker": {"color": SERIES[1]}}, decreasing={"marker": {"color": SERIES[0]}},
        totals={"marker": {"color": NEUTRAL}}, connector={"line": {"color": AXIS, "width": 1}},
        hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont={"color": INK_2, "size": 11})
    fig.update_xaxes(ticksuffix="%", range=[0, 105])
    fig.update_layout(margin={"l": 8, "r": 36, "t": 4, "b": 28}, showlegend=False, uirevision=t.id)
    return style_axes(fig)


def reasons_chart(t):
    items = sorted(t.fail_reasons.items(), key=lambda x: x[1])
    total = sum(v for _, v in items) or 1
    fig = go.Figure(go.Bar(
        y=[k for k, _ in items], x=[v for _, v in items], orientation="h", marker={"color": SERIES[0]},
        text=[f"{v / total:.0%}" for _, v in items], textposition="outside", textfont={"color": INK_2, "size": 11},
        cliponaxis=False, hovertemplate="%{y}: %{x:,} patients<extra></extra>",
    ))
    fig.update_traces(marker_cornerradius=4)
    fig.update_xaxes(visible=False, range=[0, max(v for _, v in items) * 1.25 or 1])
    fig.update_yaxes(tickfont={"color": INK_2, "size": 11})
    fig.update_layout(margin={"l": 8, "r": 8, "t": 4, "b": 4}, bargap=0.35, showlegend=False)
    return style_axes(fig)


def sites_chart(t):
    active = sorted([s for s in t.sites if s["activated"] is not None], key=lambda s: -s["enrolled"])
    fig = go.Figure(go.Bar(
        x=list(range(1, len(active) + 1)), y=[s["enrolled"] for s in active],
        marker={"color": SERIES[0]},
        customdata=[[s["name"], s["country"], s["screened"], month_label(tr.add_months(t.start, s["activated"]))]
                    for s in active],
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{y} enrolled of %{customdata[2]} screened"
                      "<br>Active since %{customdata[3]}<extra></extra>",
    ))
    if active:
        mean = t.enrolled / len(active)
        fig.add_hline(y=mean, line={"color": INK_2, "width": 1, "dash": "dot"})
        fig.add_annotation(x=1, xref="paper", y=mean, text=f"Mean {mean:.1f}", showarrow=False, xanchor="right",
                           yanchor="bottom", font={"color": INK_2, "size": 11})
    fig.update_traces(marker_cornerradius=3)
    fig.update_xaxes(title="Active sites, ranked", showticklabels=False, showgrid=False)
    fig.update_yaxes(title="Patients enrolled", rangemode="tozero")
    fig.update_layout(margin={"l": 56, "r": 8, "t": 4, "b": 32}, bargap=0.2, showlegend=False)
    return style_axes(fig)


def graph(graph_id, height_class="graph"):
    return html.Div(
        dcc.Graph(id=graph_id, config={"displayModeBar": False, "responsive": True}, style={"height": "100%"}),
        className=height_class,
    )


def card(title, *children, extra=None, **kwargs):
    return dmc.Paper(
        [dmc.Group([dmc.Text(title, className="card-title"), extra], justify="space-between", mb="sm", wrap="nowrap"),
         *children],
        className="card",
        **kwargs,
    )


def summary_item(label, value, sub, status=None):
    return html.Div(
        [
            dmc.Text(label, className="summary-label"),
            dmc.Group([dmc.Text(value, className="summary-value"),
                       status and DashIconify(icon=STATUS_ICON[status], width=18, color=STATUS[status])],
                      gap=6, wrap="nowrap"),
            dmc.Text(sub, className="summary-sub"),
        ],
        className="summary-item",
    )


def level_badge(level, label, size="sm"):
    return dmc.Badge(label, color=STATUS[level], variant="light", size=size, radius="xl",
                     leftSection=DashIconify(icon=STATUS_ICON[level], width=12), className="level-badge")


def stat(label, value, sub=None):
    return html.Div([dmc.Text(label, className="stat-label"), dmc.Text(value, className="stat-value"),
                     sub and dmc.Text(sub, className="stat-sub")], className="stat")


def watchlist(trials, selected):
    rows = []
    for t in trials:
        s = tr.SCORES[t.id]
        rows.append(html.Tr(
            [
                html.Td([dmc.Text(t.id, className="num row-id"), dmc.Text(t.indication, className="row-sub")]),
                html.Td(t.phase.replace("Phase ", "P"), className="num phase-col"),
                html.Td([dmc.Text(f"{t.enrolled:,} / {t.target:,}", className="num row-sub"),
                         dmc.Progress(value=min(100, 100 * t.enrolled / t.target), size="sm", color=SERIES[0],
                                      className="row-progress")]),
                html.Td(level_badge(s["enroll_level"], f"{s['p_on_time']:.0%}")),
                html.Td(level_badge(s["fail_level"], f"{s['p_fail']:.0%}")),
            ],
            id={"type": "row", "id": t.id},
            n_clicks=0,
            className="watch-row" + (" selected" if t.id == selected else ""),
        ))
    return dmc.Table(
        [html.Thead(html.Tr([html.Th(h, className="phase-col" if h == "Phase" else None)
                             for h in ["Trial", "Phase", "Enrolled", "On time", "Failure"]])),
         html.Tbody(rows or [html.Tr(html.Td("No trials match the filters.", colSpan=5, className="empty"))])],
        className="watch-table",
        stickyHeader=True,
    )


def area_count(area):
    return sum(t.area == area for t in tr.TRIALS)


brand = dmc.Group(
    [
        html.Div(DashIconify(icon="tabler:stethoscope", width=20), className="brand-mark"),
        dmc.Stack([dmc.Text("Trial Screen", className="brand-name"),
                   dmc.Text("Enrollment & failure risk", className="brand-sub")], gap=0),
    ],
    gap="sm", wrap="nowrap",
)

# Shown on phones only, where the sidebar collapses behind the burger
header = dmc.AppShellHeader(
    dmc.Group([brand, dmc.Burger(id="burger", size="sm", opened=False)], justify="space-between", h="100%", px="md"),
    className="mobile-header",
)

navbar = dmc.AppShellNavbar(
    [
        dmc.Box(brand, className="nav-brand", visibleFrom="md"),
        dmc.Text("Phase", className="nav-label"),
        dmc.ChipGroup(
            dmc.Group([dmc.Chip(p, value=p, size="sm", radius="xl") for p in ["All", *tr.PHASES]], gap=6),
            id="phase", value="All", multiple=False,
        ),
        dmc.Group([dmc.Text("Therapeutic area", className="nav-label"),
                   dmc.Button("Select all", id="areas-all", variant="subtle", size="compact-xs", radius="xl")],
                  justify="space-between", align="flex-end"),
        dmc.CheckboxGroup(
            dmc.Stack([
                dmc.Checkbox(
                    value=a, size="sm",
                    label=dmc.Group([dmc.Text(a, size="sm"), dmc.Text(str(area_count(a)), className="nav-count")],
                                    justify="space-between", wrap="nowrap", w=190),
                ) for a in tr.AREAS
            ], gap=10),
            id="areas", value=list(tr.AREAS),
        ),
        html.Div(className="nav-spacer"),
        dmc.Text(
            [f"Data as of {tr.AS_OF:%-d %B %Y}. ", html.Br(),
             "All trials, sponsors and sites are synthetic. Risk models are illustrative."],
            className="nav-foot",
        ),
    ],
    p="lg",
    className="navbar",
)

whatif = card(
    "What if…",
    dmc.Text("Try a fix and see how the forecast and failure risk move.", className="card-hint", mb=4),
    dmc.Stack(
        [
            dmc.Text("Add sites", className="slider-label"),
            dmc.Slider(id="add-sites", min=0, max=40, step=1, value=0, color="teal",
                       marks=[{"value": v, "label": str(v)} for v in (0, 20, 40)]),
            dmc.Text("Remove eligibility criteria", className="slider-label"),
            dmc.Slider(id="drop-criteria", min=0, max=10, step=1, value=0, color="teal",
                       marks=[{"value": v, "label": str(v)} for v in (0, 5, 10)]),
            dmc.Text("Extend enrollment window (months)", className="slider-label"),
            dmc.Slider(id="extend", min=0, max=12, step=1, value=0, color="teal",
                       marks=[{"value": v, "label": str(v)} for v in (0, 6, 12)]),
            html.Div(id="whatif-result", className="whatif-result"),
        ],
        gap=4,
    ),
    extra=dmc.Button("Reset", id="reset", variant="light", size="compact-xs", color="teal", radius="xl"),
)

app.layout = dmc.MantineProvider(
    [
        dmc.AppShell(
            [
                header,
                navbar,
                dmc.AppShellMain(
                    [
                        html.Div(
                            [
                                dmc.Text("Portfolio review", className="eyebrow"),
                                dmc.Title("Which trials need attention?", order=1, className="page-title"),
                                dmc.Text(id="portfolio-meta", className="meta"),
                            ],
                            className="page-head",
                        ),
                        dmc.Paper(id="kpis", className="summary-strip"),
                        dmc.Grid(
                            [
                                dmc.GridCol(card("Risk matrix", graph("matrix", "graph-tall"),
                                                 extra=dmc.Text("Click a trial · size = target enrollment",
                                                                className="card-hint")),
                                            span={"base": 12, "xl": 7}),
                                dmc.GridCol(card("Watchlist",
                                                 dmc.ScrollArea(html.Div(id="watchlist"), h=440, type="auto"),
                                                 extra=dmc.Text("Riskiest first", className="card-hint")),
                                            span={"base": 12, "xl": 5}),
                            ],
                            gutter="lg", mb="xl",
                        ),
                        dmc.Text("Trial report", className="eyebrow section-eyebrow"),
                        html.Div(id="trial-head", className="trial-head"),
                        dmc.Grid(
                            [
                                dmc.GridCol(card("Enrollment forecast", graph("enrollment", "graph-tall"),
                                                 extra=dmc.Text("Band = 80% of simulated outcomes",
                                                                className="card-hint")),
                                            span={"base": 12, "lg": 8}),
                                dmc.GridCol(whatif, span={"base": 12, "lg": 4}),
                                dmc.GridCol(card("Failure risk drivers", graph("drivers"),
                                                 extra=dmc.Text("Points vs typical trial", className="card-hint")),
                                            span={"base": 12, "md": 6, "xl": 4}),
                                dmc.GridCol(card("Screening", html.Div(id="funnel", className="funnel"),
                                                 dmc.Text("Screen-fail reasons", className="sub-title"),
                                                 graph("reasons", "graph-short")),
                                            span={"base": 12, "md": 6, "xl": 4}),
                                dmc.GridCol(card("Site performance", html.Div(id="site-summary", className="site-summary"),
                                                 graph("sites", "graph-short")),
                                            span={"base": 12, "xl": 4}),
                            ],
                            gutter="lg",
                        ),
                    ],
                    className="main",
                ),
            ],
            header={"height": {"base": 56, "md": 0}},
            navbar={"width": 280, "breakpoint": "md", "collapsed": {"mobile": True}},
            padding="xl",
            id="shell",
        ),
        dcc.Store(id="selected", data=min(tr.TRIALS, key=risk_rank).id),
    ],
    theme=THEME,
    forceColorScheme="light",
)


@app.callback(Output("shell", "navbar"), Input("burger", "opened"), State("shell", "navbar"))
def toggle_navbar(opened, navbar):
    return {**navbar, "collapsed": {"mobile": not opened}}


@app.callback(Output("areas", "value"), Input("areas-all", "n_clicks"), prevent_initial_call=True)
def all_areas(_):
    return list(tr.AREAS)


@app.callback(
    Output("portfolio-meta", "children"),
    Output("kpis", "children"),
    Output("matrix", "figure"),
    Output("watchlist", "children"),
    Input("areas", "value"),
    Input("phase", "value"),
    Input("selected", "data"),
)
def portfolio(areas, phase, selected):
    trials = sorted(filtered(areas, phase), key=risk_rank)
    scores = [tr.SCORES[t.id] for t in trials]
    enrolling = [t for t in trials if not t.complete]
    late = sum(s["p_on_time"] < 0.5 for s in scores)
    risky = sum(s["fail_level"] in ("serious", "critical") for s in scores)
    intervene = sum(s["verdict"] == "Intervene" for s in scores)
    enrolled = sum(t.enrolled for t in trials)
    target = sum(t.target for t in trials) or 1
    sfr = np.median([t.screen_fail for t in trials]) if trials else 0

    kpis = [
        summary_item("Trials", f"{len(trials)}", f"{len(enrolling)} enrolling · {len(trials) - len(enrolling)} full"),
        summary_item("Randomized", f"{enrolled:,}", f"{enrolled / target:.0%} of {target:,} target"),
        summary_item("Likely late", f"{late}", "Under 50% on-time chance", "serious" if late else None),
        summary_item("High failure risk", f"{risky}", "High or critical score", "serious" if risky else None),
        summary_item("Intervene", f"{intervene}", "High risk on either axis", "critical" if intervene else None),
        summary_item("Screen-fail rate", f"{sfr:.0%}", "Portfolio median"),
    ]
    meta = f"{len(trials)} trials · {len({t.sponsor for t in trials})} sponsors · " \
           f"{sum(len(t.sites) for t in trials):,} sites"
    return meta, kpis, risk_matrix(trials, selected), watchlist(trials, selected)


@app.callback(
    Output("selected", "data"),
    Input("matrix", "clickData"),
    Input({"type": "row", "id": ALL}, "n_clicks"),
    Input("areas", "value"),
    Input("phase", "value"),
    State("selected", "data"),
    prevent_initial_call=True,
)
def select(click, _, areas, phase, selected):
    trigger = ctx.triggered_id
    if trigger == "matrix":
        point = (click or {}).get("points", [{}])[0]
        return point.get("customdata", [selected])[0]
    if isinstance(trigger, dict):
        # Re-rendered rows arrive with n_clicks=0, which is not a click
        if not ctx.triggered[0]["value"]:
            return dash.no_update
        return trigger["id"]
    # Filters changed: keep the selection if it is still visible, otherwise take the riskiest match
    trials = filtered(areas, phase)
    if not trials or any(t.id == selected for t in trials):
        return dash.no_update
    return min(trials, key=risk_rank).id


@app.callback(
    Output("add-sites", "value"),
    Output("drop-criteria", "value"),
    Output("extend", "value"),
    Output("add-sites", "max"),
    Output("add-sites", "marks"),
    Output("drop-criteria", "max"),
    Input("selected", "data"),
    Input("reset", "n_clicks"),
)
def reset_whatif(selected, _):
    t = tr.BY_ID[selected]
    top = int(max(10, round(len(t.sites) / 10) * 10))
    drop = min(10, t.criteria - 8)
    return 0, 0, 0, top, [{"value": v, "label": str(v)} for v in (0, top // 2, top)], drop


@app.callback(
    Output("trial-head", "children"),
    Output("funnel", "children"),
    Output("reasons", "figure"),
    Output("site-summary", "children"),
    Output("sites", "figure"),
    Input("selected", "data"),
)
def trial_detail(selected):
    t = tr.BY_ID[selected]
    s = tr.SCORES[selected]
    flags = [x for x in [
        "Biomarker-selected" if t.biomarker else None,
        "First in class" if t.novel else None,
        f"{t.criteria} eligibility criteria",
        f"{t.competing} competing trials",
    ] if x]
    head = dmc.Paper(
        [
            dmc.Group(
                [
                    dmc.Stack([
                        dmc.Group([dmc.Text(t.id, className="trial-id"),
                                   level_badge(VERDICT_LEVEL[s["verdict"]], s["verdict"], size="lg")], gap="sm"),
                        dmc.Text(t.title, className="trial-title"),
                        dmc.Text(f"{t.sponsor} · {t.area} · started {month_label(t.start)} · "
                                 + " · ".join(flags), className="trial-meta"),
                    ], gap=2),
                ],
                justify="space-between",
            ),
            html.Div(
                [
                    stat("Enrolled", f"{t.enrolled:,} / {t.target:,}", f"{t.enrolled / t.target:.0%} of target"),
                    stat("Planned end", month_label(tr.add_months(t.start, t.plan_months)),
                         f"{t.plan_months} month window"),
                    stat("Projected end", months_from_now(s["median"]),
                         None if s["median"] is None else
                         f"80%: {months_from_now(s['lo'])} – {months_from_now(s['hi'])}"),
                    stat("On-time chance", f"{s['p_on_time']:.0%}", tr.LEVEL_LABEL[s["enroll_level"]] + " enrollment risk"),
                    stat("Failure risk", f"{s['p_fail']:.0%}", tr.LEVEL_LABEL[s["fail_level"]]
                         + f" · baseline {s['baseline']:.0%}"),
                    stat("Screen-fail rate", f"{t.screen_fail:.0%}", f"{t.screened:,} screened"),
                    stat("Dropout", f"{t.dropout:.0%}", f"{t.discontinued:,} discontinued"),
                ],
                className="stat-grid",
            ),
        ],
        className="card trial-card",
    )

    stages = [("Screened", t.screened), ("Randomized", t.enrolled), ("On study", t.enrolled - t.discontinued)]
    funnel = [
        html.Div([
            dmc.Group([dmc.Text(name, className="funnel-name"),
                       dmc.Text(f"{n:,}" + (f" · {n / t.screened:.0%}" if i else ""), className="num funnel-n")],
                      justify="space-between"),
            html.Div(html.Div(style={"width": f"{100 * n / max(1, t.screened):.1f}%"}, className="funnel-fill"),
                     className="funnel-track"),
        ], className="funnel-row")
        for i, (name, n) in enumerate(stages)
    ]

    active = [x for x in t.sites if x["activated"] is not None]
    zero = sum(x["enrolled"] == 0 for x in active)
    pending = len(t.sites) - len(active)
    summary = [
        stat("Active", f"{len(active)}", f"of {len(t.sites)} planned"),
        stat("Not yet open", f"{pending}", "Awaiting activation"),
        html.Div([dmc.Text("Zero enrolled", className="stat-label"),
                  dmc.Group([dmc.Text(f"{zero}", className="stat-value"),
                             zero and DashIconify(icon=STATUS_ICON["warning"], width=16, color=STATUS["warning"])],
                            gap=6),
                  dmc.Text("Active, no patients", className="stat-sub")], className="stat"),
    ]
    return head, funnel, reasons_chart(t), summary, sites_chart(t)


@app.callback(
    Output("enrollment", "figure"),
    Output("drivers", "figure"),
    Output("whatif-result", "children"),
    Input("selected", "data"),
    Input("add-sites", "value"),
    Input("drop-criteria", "value"),
    Input("extend", "value"),
)
def scenario(selected, add_sites, drop_criteria, extend):
    t = tr.BY_ID[selected]
    base = tr.SCORES[selected]
    changed = bool(add_sites or drop_criteria or extend)
    sc = tr.score(t, add_sites or 0, drop_criteria or 0, extend or 0) if changed else base

    def row(label, before, after, better):
        arrow = "tabler:arrow-right"
        cls = "delta-good" if better is True else "delta-bad" if better is False else ""
        return dmc.Group([
            dmc.Text(label, className="stat-label"),
            dmc.Group([dmc.Text(before, className="num muted"), DashIconify(icon=arrow, width=14, color=MUTED),
                       dmc.Text(after, className=f"num {cls}")], gap=6, wrap="nowrap"),
        ], justify="space-between", wrap="nowrap")

    if t.complete:
        result = dmc.Text("Enrollment is complete. Only the criteria change affects the failure score.",
                          className="card-hint")
        result = [result, row("Failure risk", f"{base['p_fail']:.0%}", f"{sc['p_fail']:.0%}",
                              sc["p_fail"] < base["p_fail"] - 0.005 if changed else None)]
    else:
        def cmp(a, b, lower_is_better):
            if not changed or abs(a - b) < 0.005:
                return None
            return (b < a) == lower_is_better

        result = [
            row("On-time chance", f"{base['p_on_time']:.0%}", f"{sc['p_on_time']:.0%}",
                cmp(base["p_on_time"], sc["p_on_time"], False)),
            row("Projected end", months_from_now(base["median"]), months_from_now(sc["median"]),
                cmp(base["median"], sc["median"], True)),
            row("Failure risk", f"{base['p_fail']:.0%}", f"{sc['p_fail']:.0%}", cmp(base["p_fail"], sc["p_fail"], True)),
            row("Verdict", base["verdict"], sc["verdict"], None),
        ]
    if drop_criteria:
        sfr = tr.screen_fail_base(t.criteria - drop_criteria, t.biomarker) / tr.screen_fail_base(t.criteria, t.biomarker)
        result.append(dmc.Text(f"Expected screen-fail rate {t.screen_fail:.0%} → {t.screen_fail * sfr:.0%}",
                               className="card-hint"))

    fig = enrollment_chart(t, base, sc if changed and not t.complete else None)
    if extend:
        new_end = tr.add_months(t.start, t.plan_months + extend)
        fig.add_vline(x=new_end, line={"color": SERIES[1], "width": 1, "dash": "dot"})
        fig.add_annotation(x=new_end, y=0.92, yref="paper", text="Extended end", showarrow=False, xanchor="left",
                           xshift=4, font={"color": MUTED, "size": 11})
    return fig, drivers_chart(t, sc), result


if __name__ == "__main__":
    app.run(debug=True)
