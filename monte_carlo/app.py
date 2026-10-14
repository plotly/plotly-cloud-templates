import json
import time
from dataclasses import fields
from urllib.parse import urlencode

import dash_ag_grid as dag
import dash_design_kit as ddk
from dash import Dash, Input, Output, State, callback, dcc, html, no_update
from flask import Response, abort, request
from flask_caching import Cache

import engine
from code_panel import code_panel
from figures import convergence_chart, distribution_chart, empty_figure, fan_chart
from report import build_report, report_title
from theme import BRAND_PRIMARY

app = Dash(
    __name__,
    title="Halcyon Capital | Monte Carlo Pricing Lab",
)
server = app.server

RECENT_REPORTS = 20  # the sidebar list scrolls

# Runs are deterministic for a given seed, so identical requests (a demo
# re-run, a second viewer) come straight from the cache.
cache = Cache(
    server,
    config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 60 * 60},
)

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
PATH_OPTIONS = [10_000, 50_000, 100_000, 250_000, 500_000]
STEP_OPTIONS = [12, 52, 252]
MAX_PATH_STEPS = 60_000_000  # keep a single run to a few seconds


@cache.memoize()
def cached_run(params: engine.Params, estimator: str) -> dict:
    return engine.run(params, estimator)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def field(label: str, component, field_id: str | None = None, hint: str = ""):
    children = [html.Label(label, className="form-label"), component]
    if hint:
        children.append(html.Div(hint, className="form-hint"))
    props = {"id": field_id} if field_id else {}
    return html.Div(children, className="form-field", **props)


def number(input_id: str, value, step, min_value=None, max_value=None):
    return dcc.Input(
        id=input_id,
        type="number",
        value=value,
        step=step,
        min=min_value,
        max=max_value,
        debounce=True,
        className="number-input",
    )


def section(title: str, *children):
    return html.Div(
        [html.Div(title, className="panel-section-title"), *children],
        className="panel-section",
    )


def select(select_id: str, options: dict | list, value):
    if isinstance(options, dict):
        options = [{"label": label, "value": key} for key, label in options.items()]
    return dcc.Dropdown(
        id=select_id, options=options, value=value, clearable=False, className="select"
    )


controls = html.Div(
    [
        html.Div(
            [
                section(
                    "Instrument",
                    field(
                        "Product",
                        select("product-select", engine.PRODUCTS, "euro_call"),
                    ),
                    html.Div(
                        [
                            field("Strike K", number("strike-input", 100, 1, 1)),
                            field(
                                "Maturity T (yrs)",
                                number("maturity-input", 1.0, 0.05, 0.05, 10),
                            ),
                        ],
                        className="form-pair",
                    ),
                    field(
                        "Barrier H",
                        number("barrier-input", 130, 1, 1),
                        field_id="barrier-field",
                        hint="Up-and-out: knocked out if S ≥ H on any monitoring date",
                    ),
                ),
                section(
                    "Market & model",
                    html.Div(
                        [
                            field("Spot S₀", number("spot-input", 100, 1, 1)),
                            field("Volatility σ %", number("vol-input", 20, 1, 1, 200)),
                        ],
                        className="form-pair",
                    ),
                    html.Div(
                        [
                            field("Rate r %", number("rate-input", 4, 0.25, -5, 25)),
                            field(
                                "Div. yield q %", number("div-input", 1, 0.25, 0, 25)
                            ),
                        ],
                        className="form-pair",
                    ),
                    field(
                        "Model",
                        dcc.RadioItems(
                            id="model-radio",
                            options=[
                                {"label": v, "value": k}
                                for k, v in engine.MODELS.items()
                            ],
                            value="gbm",
                            inline=True,
                            className="radio",
                        ),
                    ),
                    html.Div(
                        [
                            field(
                                "Jumps / yr λ",
                                number("jump-lambda-input", 0.5, 0.1, 0, 20),
                            ),
                            field(
                                "Jump mean %", number("jump-mean-input", -5, 1, -50, 50)
                            ),
                            field(
                                "Jump vol %", number("jump-vol-input", 10, 1, 0, 100)
                            ),
                        ],
                        id="jump-fields",
                        className="form-trio",
                    ),
                ),
                section(
                    "Simulation",
                    html.Div(
                        [
                            field(
                                "Paths",
                                select(
                                    "paths-select",
                                    [
                                        {"label": f"{n:,}", "value": n}
                                        for n in PATH_OPTIONS
                                    ],
                                    100_000,
                                ),
                            ),
                            field(
                                "Time steps",
                                select(
                                    "steps-select",
                                    [
                                        {"label": str(n), "value": n}
                                        for n in STEP_OPTIONS
                                    ],
                                    52,
                                ),
                            ),
                            field("Seed", number("seed-input", 2026, 1, 0)),
                        ],
                        className="form-trio sim-trio",
                    ),
                    field(
                        "Headline estimator",
                        select("estimator-select", engine.ESTIMATORS, "anti_cv"),
                    ),
                ),
            ],
            # Scrolls on its own when the barrier or jump fields appear, so
            # the action buttons below always stay in view.
            className="control-scroll",
        ),
        html.Div(
            [
                html.Button("Run simulation", id="run-button", className="run-button"),
                html.Div(id="run-message", className="run-message"),
                html.Button(
                    "Generate PDF report",
                    id="report-button",
                    className="report-button",
                ),
                html.Div(id="report-status", className="run-message"),
                dcc.Download(id="report-download"),
            ],
            className="control-actions",
        ),
        html.Div(
            [
                html.Div("Recent reports", className="panel-section-title"),
                html.Div(id="report-list", className="report-list"),
                # Reports are rebuilt on demand from their inputs (runs are
                # deterministic for a seed), so this browser only keeps specs.
                dcc.Store(id="report-history", storage_type="local"),
            ],
            className="report-box",
        ),
    ],
    className="control-panel",
)

comparison_grid = dag.AgGrid(
    id="comparison-grid",
    className="comparison-grid",
    columnDefs=[
        {"field": "Estimator", "minWidth": 130},
        {
            "field": "Price",
            "valueFormatter": {"function": "d3.format('.4f')(params.value)"},
        },
        {
            "field": "Std error",
            "valueFormatter": {"function": "d3.format('.5f')(params.value)"},
        },
        {
            "field": "Efficiency",
            "headerTooltip": "Variance reduction vs plain MC at the same path "
            "count: how many times more plain paths give the same precision",
            "valueFormatter": {
                "function": "params.value == null ? '—' : d3.format('.1f')(params.value) + '×'"
            },
        },
    ],
    rowData=[],
    getRowId="params.data.estimator",
    columnSize="responsiveSizeToFit",
    defaultColDef={"filter": True, "sortable": True},
    dashGridOptions={
        "theme": "themeBalham",
        "animateRows": True,
        "pagination": True,
        "paginationPageSize": 10,
        "paginationPageSizeSelector": False,
        "domLayout": "autoHeight",
        "tooltipShowDelay": 300,
    },
)


def chart_card(title: str, graph_id: str, extra=None):
    children = [
        ddk.CardHeader(title=title),
        ddk.Graph(id=graph_id, config=GRAPH_CONFIG, className="fill-graph"),
    ]
    if extra is not None:
        children.append(extra)
    return ddk.Card(className="fill-card", children=children)


def dashboard_layout():
    return [
        ddk.Header(
            className="app-header",
            children=[
                html.Div(
                    [
                        html.Div(
                            [html.Span() for _ in range(5)], className="brand-flag"
                        ),
                        html.Div("Halcyon Capital", className="brand-name"),
                        html.Div(className="brand-divider"),
                        html.Div("Monte Carlo Pricing Lab", className="brand-product"),
                    ],
                    className="brand",
                ),
                html.Div(
                    [
                        html.Div(
                            "Risk-neutral simulation · variance reduction · "
                            "closed-form validation",
                            className="data-source-note",
                        ),
                        code_panel(engine.__file__),
                    ],
                    className="header-meta",
                ),
            ],
        ),
        html.Div(
            [
                controls,
                dcc.Loading(
                    html.Div(
                        [
                            dcc.Store(id="result-store"),
                            html.Div(id="kpi-strip", className="kpi-strip"),
                            html.Div(
                                [
                                    chart_card(
                                        "Simulated paths · percentile fan",
                                        "fan-chart",
                                    ),
                                    chart_card(
                                        "Terminal distribution · by outcome",
                                        "distribution-chart",
                                    ),
                                ],
                                className="chart-row",
                            ),
                            html.Div(
                                [
                                    chart_card(
                                        "Convergence · running estimate with 95% band",
                                        "convergence-chart",
                                    ),
                                    ddk.Card(
                                        className="fill-card",
                                        children=[
                                            ddk.CardHeader(
                                                title="Variance reduction · same path count"
                                            ),
                                            comparison_grid,
                                            html.Div(
                                                id="comparison-note",
                                                className="card-note",
                                            ),
                                        ],
                                    ),
                                ],
                                className="chart-row",
                            ),
                        ],
                        className="results",
                    ),
                    parent_className="results-loading",
                    color=BRAND_PRIMARY,
                    delay_show=250,
                    overlay_style={"visibility": "visible", "opacity": 0.55},
                ),
            ],
            className="workspace",
        ),
    ]


app.layout = ddk.App(
    className="app-shell",
    children=[html.Div(dashboard_layout(), className="page-content")],
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    Output("barrier-field", "className"),
    Input("product-select", "value"),
)
def toggle_barrier(product):
    return "form-field" if product == "uo_call" else "form-field hidden"


@callback(
    Output("jump-fields", "className"),
    Input("model-radio", "value"),
)
def toggle_jumps(model):
    return "form-trio" if model == "merton" else "form-trio hidden"


def validation_error(p: engine.Params) -> str | None:
    # Dash sends None for a blank input or one the browser rejects (outside
    # min/max, or off the step grid, e.g. 102.5 in a step-1 field).
    values = {
        "Spot S₀": p.s0,
        "Strike K": p.k,
        "Maturity T": p.t,
        "Volatility σ": p.sigma,
        "Rate r": p.r,
        "Div. yield q": p.q,
        "Seed": p.seed,
    }
    missing = [name for name, v in values.items() if v is None]
    if missing:
        return f"Check {', '.join(missing)}: blank or not an allowed value."
    if p.s0 <= 0 or p.k <= 0 or p.t <= 0 or p.sigma <= 0:
        return "Spot, strike, maturity and volatility must be positive."
    if p.product == "uo_call" and not (p.barrier and p.barrier > max(p.s0, p.k)):
        return "Barrier must sit above both spot and strike."
    if p.n_paths * p.steps > MAX_PATH_STEPS:
        return (
            f"{p.n_paths:,} paths × {p.steps} steps is too large for one run; "
            "reduce paths or steps."
        )
    return None


@callback(
    Output("result-store", "data"),
    Output("run-message", "children"),
    Input("run-button", "n_clicks"),
    State("product-select", "value"),
    State("model-radio", "value"),
    State("spot-input", "value"),
    State("strike-input", "value"),
    State("maturity-input", "value"),
    State("rate-input", "value"),
    State("div-input", "value"),
    State("vol-input", "value"),
    State("barrier-input", "value"),
    State("jump-lambda-input", "value"),
    State("jump-mean-input", "value"),
    State("jump-vol-input", "value"),
    State("paths-select", "value"),
    State("steps-select", "value"),
    State("seed-input", "value"),
    State("estimator-select", "value"),
)
def run_simulation(
    _clicks, product, model, s0, k, t, r, q, vol, barrier,
    jump_lambda, jump_mean, jump_vol, n_paths, n_steps, seed, estimator,
):  # fmt: skip
    """Runs on page load and on every click of Run simulation."""
    pct = lambda v: None if v is None else v / 100  # noqa: E731
    params = engine.Params(
        product=product,
        model=model,
        s0=s0,
        k=k,
        t=t,
        r=pct(r),
        q=pct(q),
        sigma=pct(vol),
        barrier=barrier or 0.0,
        jump_lambda=jump_lambda or 0.0,
        jump_mean=pct(jump_mean) or 0.0,
        jump_vol=pct(jump_vol) or 0.0,
        n_paths=int(n_paths),
        n_steps=int(n_steps),
        seed=int(seed) if seed is not None else None,
    )
    error = validation_error(params)
    if error:
        return no_update, html.Span(error, className="run-error")

    result = cached_run(params, estimator)
    message = (
        f"{params.n_paths:,} paths × {params.steps} step"
        f"{'s' if params.steps > 1 else ''} per estimator · "
        f"{result['runtime_s'] * 1000:,.0f} ms"
    )
    return result, message


def tile(label: str, value: str, sub: str = "", class_name: str = ""):
    return html.Div(
        [
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value"),
            html.Div(sub, className="kpi-sub"),
        ],
        className=f"kpi {class_name}".strip(),
    )


@callback(
    Output("kpi-strip", "children"),
    Input("result-store", "data"),
)
def render_kpis(result):
    if not result:
        return []
    head = result["headline"]
    bench = result["benchmark"]
    estimator = engine.ESTIMATORS[result["estimator"]]

    if bench is None:
        bench_tile = tile("Benchmark", "—", result["benchmark_label"])
        error_tile = tile("Error vs benchmark", "—", "MC is the reference here")
    else:
        z = result["z_score"]
        approx = "BGK" in result["benchmark_label"]
        error_tile = tile(
            "Error vs benchmark",
            f"{head['price'] - bench:+.4f}",
            f"{z:+.1f} s.e." + (" · incl. BGK approx. error" if approx else ""),
            "kpi-warn" if abs(z) > 3 and not approx else "",
        )
        bench_tile = tile("Benchmark", f"{bench:.4f}", result["benchmark_label"])

    rate = result["path_steps_per_s"]
    pricing = [
        tile("MC price", f"{head['price']:.4f}", f"± {head['se']:.4f} s.e. · {estimator}", "kpi-primary"),
        tile("95% confidence", f"{head['ci_low']:.3f} – {head['ci_high']:.3f}", f"width {head['ci_high'] - head['ci_low']:.4f}"),
        bench_tile,
        error_tile,
        tile("Runtime", f"{result['runtime_s'] * 1000:,.0f} ms", f"{rate / 1e6:,.0f}M path-steps/s" if rate else ""),
    ]  # fmt: skip

    analytic = result["analytic_greeks"] or {}
    greeks = []
    for name, digits in [("Delta", 4), ("Gamma", 4), ("Vega", 4), ("Rho", 4)]:
        mc_value = result["greeks"][name]
        sub = (
            f"BS {analytic[name]:.{digits}f}" if name in analytic else "bump & revalue"
        )
        greeks.append(tile(name, f"{mc_value:.{digits}f}", sub, "kpi-greek"))

    return [
        html.Div(pricing, className="kpi-group"),
        html.Div(
            [
                html.Div("Greeks · common random numbers", className="kpi-group-label"),
                html.Div(greeks, className="kpi-group"),
            ],
            className="kpi-greeks",
        ),
    ]


@callback(Output("fan-chart", "figure"), Input("result-store", "data"))
def render_fan(result):
    return fan_chart(result) if result else empty_figure()


@callback(Output("distribution-chart", "figure"), Input("result-store", "data"))
def render_distribution(result):
    return distribution_chart(result) if result else empty_figure()


@callback(Output("convergence-chart", "figure"), Input("result-store", "data"))
def render_convergence(result):
    if not result:
        return empty_figure()
    return convergence_chart(result, engine.ESTIMATORS[result["estimator"]])


@callback(
    Output("comparison-grid", "rowData"),
    Output("comparison-note", "children"),
    Input("result-store", "data"),
)
def render_comparison(result):
    if not result:
        return [], ""
    best = max(result["comparison"], key=lambda row: row["Efficiency"] or 0)
    dist = result["distribution"]
    note = (
        f"{best['Estimator']} is {best['Efficiency']:.1f}× as efficient as plain MC. "
        f"{dist['share_pays']:.0%} of paths pay off"
        + (f", {dist['share_knocked']:.0%} knock out." if result["barrier"] else ".")
    )
    return result["comparison"], note


# ---------------------------------------------------------------------------
# PDF reports (ReportLab)
# ---------------------------------------------------------------------------

PARAM_FIELDS = {f.name for f in fields(engine.Params)}


def report_href(spec: dict) -> str:
    return app.get_relative_path("/report.pdf") + "?" + urlencode(
        {"spec": json.dumps(spec, separators=(",", ":"))}
    )


def report_filename(spec: dict) -> str:
    stamp = spec["generated_at"].replace("-", "").replace(":", "").replace(" ", "-")
    return f"monte-carlo-{spec['params']['product']}-{stamp}.pdf"


@server.route(f"{app.config.routes_pathname_prefix}report.pdf")
def report_pdf():
    """Rebuild a saved report from its inputs, for the Recent reports links."""
    try:
        spec = json.loads(request.args["spec"])
        if set(spec["params"]) != PARAM_FIELDS:
            raise ValueError("unexpected parameters")
        params = engine.Params(**spec["params"])
        estimator = spec["estimator"]
        generated_at = str(spec["generated_at"])
    except (KeyError, TypeError, ValueError):
        abort(400)
    if (
        params.product not in engine.PRODUCTS
        or params.model not in engine.MODELS
        or estimator not in engine.ESTIMATORS
        or validation_error(params)
    ):
        abort(400)
    pdf = build_report(cached_run(params, estimator), generated_at)
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{report_filename(spec)}"'
        },
    )


@callback(
    Output("report-list", "children"),
    Input("report-history", "data"),
)
def render_report_list(history):
    return [
        html.Div(
            [
                html.Div(
                    [
                        html.Div(entry["title"], className="report-name"),
                        html.Div(entry["generated_at"], className="report-time"),
                    ]
                ),
                html.Div(
                    html.A(
                        "PDF",
                        href=report_href(entry),
                        target="_blank",
                        className="report-link",
                    ),
                    className="report-actions",
                ),
            ],
            className="report-row",
        )
        for entry in history or []
    ]


@callback(
    Output("report-download", "data"),
    Output("report-history", "data"),
    Output("report-status", "children"),
    Input("report-button", "n_clicks"),
    State("result-store", "data"),
    State("report-history", "data"),
    prevent_initial_call=True,
)
def generate_report(_clicks, result, history):
    """Build the PDF for the current run and download it."""
    if not result:
        return no_update, no_update, "Run a simulation first."
    started = time.time()
    spec = {
        "title": report_title(result),
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "params": result["params"],
        "estimator": result["estimator"],
    }
    pdf = build_report(result, spec["generated_at"])
    status = html.Div(
        [
            html.Span(f"Report ready ({time.time() - started:.1f}s)"),
            html.A(
                "PDF", href=report_href(spec), target="_blank", className="report-link"
            ),
        ],
        className="report-ready",
    )
    history = [spec, *(history or [])][:RECENT_REPORTS]
    return dcc.send_bytes(pdf, report_filename(spec)), history, status


if __name__ == "__main__":
    app.run(debug=True)
