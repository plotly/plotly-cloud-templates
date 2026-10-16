import dash_mantine_components as dmc
from dash import (
    ALL,
    Dash,
    Input,
    Output,
    Patch,
    State,
    callback,
    ctx,
    dcc,
    html,
    no_update,
)
from dash_iconify import DashIconify

import spc

app = Dash(
    __name__,
    title="Manufacturing SPC Dashboard",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
)
server = app.server

THEME = {
    "fontFamily": spc.FONT,
    "headings": {"fontFamily": spc.FONT},
    "primaryColor": "blue",
    "defaultRadius": "md",
}

ABOUT = """
This dashboard monitors process quality along a manufacturing line using
[Shewhart control charts](https://en.wikipedia.org/wiki/Shewhart_individuals_control_chart)
on mock measurement data.

**Start** replays one batch per second to simulate live measurements. A measurement
outside the control limits (mean ± 3σ by default) is flagged **out of control (OOC)**.
A parameter's status turns to *Warn* above 5% OOC and *Fail* above 7%.

Click a row in **Process control metrics** to show that parameter on the live chart,
and open **Specifications** to override the control and specification limits.
"""


def icon(name, size=16):
    return DashIconify(icon=f"tabler:{name}", width=size)


def stat_card(label, children):
    return dmc.Paper(
        [dmc.Text(label, size="xs", c="dimmed", fw=500), children],
        className="stat-card",
        withBorder=True,
    )


def metric_row(param):
    return html.Div(
        id={"type": "metric-row", "index": param},
        className="metric-row",
        children=[
            html.Button(
                param,
                id={"type": "metric-button", "index": param},
                className="metric-name",
                title=f"Show {param} on the live chart",
            ),
            dcc.Graph(
                id={"type": "spark", "index": param},
                figure=spc.sparkline(param, spc.START_BATCH),
                config={"staticPlot": True},
                className="sparkline",
            ),
            dmc.Text(id={"type": "ooc-pct", "index": param}, size="sm", ta="right"),
            dmc.Progress(id={"type": "ooc-bar", "index": param}, value=0, size="sm"),
            dmc.Badge(
                id={"type": "status", "index": param},
                variant="dot",
                size="sm",
                className="status-badge",
            ),
        ],
    )


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Title("Manufacturing SPC Dashboard", order=4, className="app-title"),
                    dmc.Text(
                        "Process control and exception reporting",
                        size="xs",
                        c="dimmed",
                        visibleFrom="sm",
                    ),
                ],
                gap=0,
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "About",
                        id="about-open",
                        variant="subtle",
                        color="gray",
                        size="sm",
                        leftSection=icon("info-circle"),
                    ),
                    html.A(
                        html.Img(src=app.get_asset_url("dash-logo.png"), height=32, alt="Plotly"),
                        href="https://dash.plotly.com/",
                        className="dash-logo",
                    ),
                ],
                gap="sm",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        h="100%",
        px="lg",
        wrap="nowrap",
    )
)

stats = html.Div(
    className="stat-row",
    children=[
        stat_card("Operator ID", dmc.Text("1704", className="hero-number mono")),
        stat_card(
            "Batch progress",
            dmc.Group(
                [
                    dmc.RingProgress(
                        id="progress-ring", sections=[], size=52, thickness=6, roundCaps=True
                    ),
                    dmc.Text(id="progress-text", className="hero-number"),
                ],
                gap="xs",
                wrap="nowrap",
            ),
        ),
        stat_card(
            "Parameters failing",
            dmc.Group(
                [
                    dmc.Text(id="fail-count", className="hero-number"),
                    dmc.Text(f"of {len(spc.PARAMS)}", size="sm", c="dimmed"),
                ],
                gap=6,
                align="baseline",
            ),
        ),
        dmc.Paper(
            dmc.Stack(
                [
                    dmc.Button(
                        "Start",
                        id="run-button",
                        leftSection=icon("player-play"),
                        fullWidth=True,
                    ),
                    dmc.Button(
                        "Specifications",
                        id="specs-open",
                        variant="default",
                        leftSection=icon("adjustments-horizontal"),
                        fullWidth=True,
                    ),
                ],
                gap=8,
            ),
            className="stat-card controls",
            withBorder=True,
        ),
    ],
)

metrics_card = dmc.Paper(
    [
        html.Div(
            [
                dmc.Text("Process control metrics", fw=600, size="sm"),
                dmc.Text("Click a row to chart it", size="xs", c="dimmed"),
            ],
            className="card-head",
        ),
        html.Div(
            [html.Span(h) for h in ["Parameter", "Trend", "OOC", f"0–{spc.OOC_BAR_MAX}%", "Status"]],
            className="metric-row metric-header",
        ),
        html.Div([metric_row(p) for p in spc.PARAMS], className="metric-rows"),
    ],
    className="card",
    withBorder=True,
)

chart_card = dmc.Paper(
    [
        html.Div(
            [
                dmc.Text(id="chart-title", fw=600, size="sm"),
                dmc.Text("Individuals chart with distribution", size="xs", c="dimmed"),
            ],
            className="card-head",
        ),
        dcc.Graph(
            id="control-chart",
            className="control-chart",
            config={"displaylogo": False, "responsive": True},
        ),
    ],
    className="card",
    withBorder=True,
)

specs_drawer = dmc.Drawer(
    id="specs-drawer",
    title=dmc.Text("Specification settings", fw=600),
    position="right",
    size="md",
    children=dmc.Stack(
        [
            dmc.Text(
                "Use historical limits as a benchmark, or set new values. "
                "Out-of-control points are recalculated against the control limits.",
                size="sm",
                c="dimmed",
            ),
            dmc.Select(
                id="spec-param",
                label="Parameter",
                data=spc.PARAMS,
                value=spc.PARAMS[0],
                allowDeselect=False,
            ),
            dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh("Limit"),
                                dmc.TableTh("Historical", ta="right"),
                                dmc.TableTh("Current"),
                            ]
                        )
                    ),
                    dmc.TableTbody(
                        [
                            dmc.TableTr(
                                [
                                    dmc.TableTd(label),
                                    dmc.TableTd(id=f"hist-{key}", ta="right", className="mono"),
                                    dmc.TableTd(
                                        dmc.NumberInput(id=f"input-{key}", size="xs", w=120)
                                    ),
                                ]
                            )
                            for key, label in spc.LIMITS.items()
                        ]
                    ),
                ],
                verticalSpacing="xs",
            ),
            dmc.Text(id="spec-feedback", size="sm"),
            dmc.Group(
                [
                    dmc.Button("Apply", id="spec-apply", leftSection=icon("check")),
                    dmc.Button(
                        "Reset to historical",
                        id="spec-reset",
                        variant="default",
                        leftSection=icon("restore"),
                    ),
                ],
                gap="sm",
            ),
        ],
        gap="md",
    ),
)

about_modal = dmc.Modal(
    id="about-modal",
    title=dmc.Text("About this dashboard", fw=600),
    size="lg",
    children=dcc.Markdown(ABOUT, className="about-text", link_target="_blank"),
)

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [
            header,
            dmc.AppShellMain(
                html.Div(
                    [stats, html.Div([metrics_card, chart_card], className="main-grid")],
                    className="page",
                )
            ),
            specs_drawer,
            about_modal,
            dcc.Interval(
                id="tick", interval=1000, n_intervals=spc.START_BATCH, disabled=True
            ),
            dcc.Store(
                id="specs",
                data={p: {k: s[k] for k in spc.LIMITS} for p, s in spc.HISTORICAL.items()},
            ),
            dcc.Store(id="selected-param", data=spc.PARAMS[0]),
        ],
        header={"height": 60},
    ),
    theme=THEME,
    forceColorScheme="light",
)


@callback(
    Output("tick", "disabled"),
    Output("tick", "n_intervals"),
    Output("run-button", "children"),
    Output("run-button", "leftSection"),
    Input("run-button", "n_clicks"),
    Input("tick", "n_intervals"),
    State("tick", "disabled"),
)
def run_control(_, batch, paused):
    finished = batch >= spc.MAX_BATCH
    if ctx.triggered_id == "run-button":
        if finished:  # restart the replay from the beginning
            return False, spc.START_BATCH, "Pause", icon("player-pause")
        paused = not paused
    elif finished:  # stop once the last batch has been shown
        return True, no_update, "Restart", icon("refresh")
    if paused:
        return True, no_update, "Start" if batch == spc.START_BATCH else "Resume", icon(
            "player-play"
        )
    return False, no_update, "Pause", icon("player-pause")


@callback(
    Output("progress-ring", "sections"),
    Output("progress-text", "children"),
    Output("fail-count", "children"),
    Output("fail-count", "c"),
    Output({"type": "ooc-pct", "index": ALL}, "children"),
    Output({"type": "ooc-bar", "index": ALL}, "value"),
    Output({"type": "ooc-bar", "index": ALL}, "color"),
    Output({"type": "status", "index": ALL}, "children"),
    Output({"type": "status", "index": ALL}, "color"),
    Output({"type": "spark", "index": ALL}, "figure"),
    Input("tick", "n_intervals"),
    Input("specs", "data"),
)
def update_metrics(batch, specs):
    n = spc.visible(batch)
    pcts = [spc.ooc_percent(p, n, specs[p]) for p in spc.PARAMS]
    statuses = [spc.status(pct) for pct in pcts]
    failing = sum(label == "Fail" for label, _ in statuses)

    sparks = []
    for p in spc.PARAMS:
        patch = Patch()
        patch["data"][0]["x"] = spc.BATCHES[:n]
        patch["data"][0]["y"] = spc.VALUES[p][:n]
        sparks.append(patch)

    return (
        [{"value": 100 * n / spc.MAX_BATCH, "color": "blue"}],
        f"{n} / {spc.MAX_BATCH}",
        str(failing),
        "red" if failing else None,
        [f"{pct:.1f}%" for pct in pcts],
        [min(pct, spc.OOC_BAR_MAX) / spc.OOC_BAR_MAX * 100 for pct in pcts],
        [color for _, color in statuses],
        [label for label, _ in statuses],
        [color for _, color in statuses],
        sparks,
    )


@callback(
    Output("selected-param", "data"),
    Input({"type": "metric-button", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_param(clicks):
    if not any(clicks):
        return no_update
    return ctx.triggered_id["index"]


@callback(
    Output({"type": "metric-row", "index": ALL}, "className"),
    Input("selected-param", "data"),
)
def highlight_row(selected):
    return ["metric-row selected" if p == selected else "metric-row" for p in spc.PARAMS]


@callback(
    Output("control-chart", "figure"),
    Output("chart-title", "children"),
    Input("tick", "n_intervals"),
    Input("specs", "data"),
    Input("selected-param", "data"),
)
def update_chart(batch, specs, param):
    fig = spc.control_chart(param, spc.visible(batch), specs[param])
    return fig, f"Live SPC chart · {param}"


@callback(
    Output("specs-drawer", "opened"),
    Input("specs-open", "n_clicks"),
    prevent_initial_call=True,
)
def open_specs(_):
    return True


@callback(
    Output("about-modal", "opened"),
    Input("about-open", "n_clicks"),
    prevent_initial_call=True,
)
def open_about(_):
    return True


@callback(
    [Output(f"hist-{k}", "children") for k in spc.LIMITS],
    [Output(f"input-{k}", "value") for k in spc.LIMITS],
    [Output(f"input-{k}", "step") for k in spc.LIMITS],
    Output("spec-feedback", "children", allow_duplicate=True),
    Input("spec-param", "value"),
    Input("specs-open", "n_clicks"),
    State("specs", "data"),
    prevent_initial_call="initial_duplicate",
)
def load_specs(param, _, specs):
    hist = spc.HISTORICAL[param]
    return (
        *[f"{hist[k]:g}" for k in spc.LIMITS],
        *[specs[param][k] for k in spc.LIMITS],
        *[hist["step"]] * len(spc.LIMITS),
        "",
    )


@callback(
    Output("specs", "data"),
    Output("spec-feedback", "children"),
    Output("spec-feedback", "c"),
    [Output(f"input-{k}", "value", allow_duplicate=True) for k in spc.LIMITS],
    Input("spec-apply", "n_clicks"),
    Input("spec-reset", "n_clicks"),
    State("spec-param", "value"),
    State("specs", "data"),
    [State(f"input-{k}", "value") for k in spc.LIMITS],
    prevent_initial_call=True,
)
def save_specs(_, __, param, specs, usl, lsl, ucl, lcl):
    unchanged = [no_update] * len(spc.LIMITS)
    if ctx.triggered_id == "spec-reset":
        hist = spc.HISTORICAL[param]
        specs[param] = {k: hist[k] for k in spc.LIMITS}
        message = f"{param} reset to historical limits."
        return specs, message, "dimmed", *[hist[k] for k in spc.LIMITS]

    values = {"usl": usl, "lsl": lsl, "ucl": ucl, "lcl": lcl}
    if any(not isinstance(v, (int, float)) for v in values.values()):
        return no_update, "Enter a number for every limit.", "red", *unchanged
    if lsl >= usl or lcl >= ucl:
        return no_update, "Each lower limit must be below its upper limit.", "red", *unchanged

    specs[param] = values
    return specs, f"{param} limits updated.", "teal", *unchanged


if __name__ == "__main__":
    app.run(debug=True)
