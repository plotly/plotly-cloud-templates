"""
Reorder Planner

Finds the SKUs that will run out before replenishment can arrive and builds a
purchase plan that spends a fixed budget where it protects the most margin.
Pick a SKU on the runway board or in the purchase orders to see its projected
stock with and without the recommended order.

The catalogue is synthetic, see inventory.py.
"""

import csv
import io
from datetime import timedelta

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

import inventory as inv

# Chart colors, kept in sync with assets/style.css
SURFACE = "#ffffff"
INK = "#101828"
INK_2 = "#475467"
MUTED = "#7d8796"
GRID = "#e9ecf1"
AXIS = "#cfd5dd"
PLAN = "#2a78d6"
NO_ACTION = "#a3a29a"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "critical": "#d03b3b"}
STATUS_LABEL = {"critical": "Runs out before an order lands", "warning": "Order this cycle", "good": "Covered"}
STATUS_SHORT = {"critical": "Out before arrival", "warning": "Order now", "good": "Covered"}
STATUS_ICON = {"good": "tabler:circle-check", "warning": "tabler:alert-triangle", "critical": "tabler:urgent"}

FONT = "'Instrument Sans', system-ui, sans-serif"
THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": "'Bricolage Grotesque', system-ui, sans-serif"},
    "primaryColor": "blue",
    "defaultRadius": "md",
}

app = dash.Dash(
    __name__,
    title="Reorder Planner",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700"
        "&family=Instrument+Sans:wght@400;500;600&family=Fragment+Mono&display=swap"
    ],
)
server = app.server

# Warm the simulation caches so the first request is fast on every worker
for _r in (7, 14, 28):
    inv.order_curves(_r)


def money(x, short=False):
    if short and abs(x) >= 1000:
        return f"${x / 1000:,.1f}k"
    return f"${x:,.0f}"


def scoped_ids(category, supplier):
    return frozenset(s.id for s in inv.SKUS if category in (None, "All", s.category)
                     and (supplier in (None, "All") or s.supplier == supplier))


def style_axes(fig):
    axis = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
                title_font={"color": MUTED, "size": 12})
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    fig.update_layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"color": INK, "size": 12, "family": FONT}},
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"size": 11, "color": INK_2}},
    )
    return fig


def status_badge(level, short=False):
    return dmc.Badge(
        STATUS_SHORT[level] if short else STATUS_LABEL[level],
        leftSection=DashIconify(icon=STATUS_ICON[level], width=14),
        variant="light", radius="sm", className=f"status status-{level}",
    )


# ---------------------------------------------------------------- figures


def runway_figure(skus, review, selected):
    """Days until stockout with no new order, against the supplier lead time."""
    order = sorted(skus, key=lambda s: inv.RUNWAY[s.id] - s.lead_mean)[::-1]  # most urgent on top
    names = [f"<b>{s.name}</b>" if s.id == selected else s.name for s in order]
    fig = go.Figure()
    for level in ["critical", "warning", "good"]:
        idx = [i for i, s in enumerate(order) if inv.status(s, review) == level]
        if not idx:
            continue
        fig.add_trace(go.Bar(
            y=[names[i] for i in idx], x=[min(inv.RUNWAY[order[i].id], inv.HORIZON) for i in idx],
            orientation="h", name=STATUS_SHORT[level],
            marker={"color": STATUS[level],
                    "opacity": [1 if order[i].id == selected or selected is None else 0.8 for i in idx]},
            customdata=[[order[i].id, order[i].supplier, order[i].lead_mean,
                         "120+" if inv.RUNWAY[order[i].id] >= inv.HORIZON else f"{inv.RUNWAY[order[i].id]:.0f}"]
                        for i in idx],
            hovertemplate="<b>%{y}</b><br>Runs out in %{customdata[3]} days<br>"
                          "Lead time %{customdata[2]:.0f} days · %{customdata[1]}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        y=names, x=[s.lead_mean for s in order], mode="markers", name="Order placed today lands",
        marker={"symbol": "line-ns", "size": 14, "line": {"width": 2.5, "color": INK}},
        customdata=[[s.id] for s in order],
        hovertemplate="An order placed today lands in ~%{x:.0f} days<extra></extra>",
    ))
    style_axes(fig)
    fig.update_layout(
        height=26 * len(order) + 40, margin={"l": 8, "r": 16, "t": 30, "b": 10},
        barmode="overlay", bargap=0.35, barcornerradius=4, clickmode="event", showlegend=False,
        xaxis={"range": [0, inv.HORIZON + 2], "side": "top", "ticksuffix": "d"},
        yaxis={"categoryorder": "array", "categoryarray": names, "range": [-0.6, len(names) - 0.4], "tickfont": {"color": INK_2, "size": 12},
               "gridcolor": "rgba(0,0,0,0)"},
    )
    return fig


def projection_figure(s, packs):
    """Projected on-hand stock with no action vs with the recommended order (10th-90th percentile bands)."""
    days = np.arange(inv.HORIZON)
    dates = [inv.AS_OF + timedelta(days=int(d)) for d in days]
    fig = go.Figure()
    scenarios = [("No new order", 0, NO_ACTION, "rgba(163,162,154,0.22)", "dash")]
    if packs:
        scenarios.append(("With recommended order", packs * s.case_pack, PLAN, "rgba(42,120,214,0.16)", "solid"))
    lead = None
    for name, qty, color, fill, dash_style in scenarios:
        stock, lost, lead = inv.simulate_stock(s, qty)
        p10, p50, p90 = np.percentile(stock, [10, 50, 90], axis=0)
        fig.add_trace(go.Scatter(x=dates, y=p90, mode="lines", line={"width": 0}, showlegend=False,
                                 hoverinfo="skip", legendgroup=name))
        fig.add_trace(go.Scatter(x=dates, y=p10, mode="lines", line={"width": 0}, fill="tonexty",
                                 fillcolor=fill, showlegend=False, hoverinfo="skip", legendgroup=name))
        p_out = (stock <= 0).mean(axis=0)
        fig.add_trace(go.Scatter(
            x=dates, y=p50, mode="lines", name=name, legendgroup=name,
            line={"color": color, "width": 2, "dash": dash_style},
            customdata=np.stack([p10, p90, p_out * 100], axis=1),
            hovertemplate=f"{name}: %{{y:,.0f}} units (80% range %{{customdata[0]:,.0f}}–%{{customdata[1]:,.0f}})"
                          f" · %{{customdata[2]:.0f}}% out<extra></extra>",
        ))
    land = inv.AS_OF + timedelta(days=int(np.median(lead)))
    if packs:
        fig.add_vline(x=land, line={"color": PLAN, "width": 1, "dash": "dot"})
        fig.add_annotation(x=land, y=1, yref="paper", text=f"Order lands ~{inv.day_label(np.median(lead))}",
                           showarrow=False, xanchor="left", xshift=6, yanchor="top",
                           font={"size": 11, "color": INK_2})
    for qty, eta in s.inbound:
        x = inv.AS_OF + timedelta(days=eta)
        fig.add_vline(x=x, line={"color": MUTED, "width": 1, "dash": "dot"})
        fig.add_annotation(x=x, y=1, yref="paper", text=f"Open PO +{qty}", showarrow=False, xanchor="left",
                           xshift=6, yanchor="top", yshift=-18, font={"size": 11, "color": MUTED})
    style_axes(fig)
    fig.update_layout(height=380, margin={"l": 8, "r": 12, "t": 36, "b": 30}, hovermode="x unified",
                      yaxis={"title": "Units on hand", "rangemode": "tozero"})
    fig.add_hline(y=0, line={"color": AXIS, "width": 1})
    return fig


def demand_figure(s):
    weeks_back = np.arange(-inv.HISTORY_WEEKS, 0)
    hist_x = [inv.AS_OF + timedelta(days=int(w * 7)) for w in weeks_back]
    lo, mid, hi = inv.forecast_weeks(s)
    fc_x = [inv.AS_OF + timedelta(days=int(w * 7)) for w in range(len(mid))]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=hist_x, y=s.history, name="Units sold per week", marker={"color": NO_ACTION},
                         hovertemplate="Week of %{x|%b %d}: %{y:,.0f} sold<extra></extra>"))
    fig.add_trace(go.Scatter(x=fc_x, y=hi, mode="lines", line={"width": 0}, showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fc_x, y=lo, mode="lines", line={"width": 0}, fill="tonexty",
                             fillcolor="rgba(42,120,214,0.16)", showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fc_x, y=mid, mode="lines+markers", name="Forecast (80% range shaded)",
                             line={"color": PLAN, "width": 2}, marker={"size": 8, "line": {"color": SURFACE, "width": 2}},
                             customdata=np.stack([lo, hi], axis=1),
                             hovertemplate="Week of %{x|%b %d}: %{y:,.0f} forecast "
                                           "(%{customdata[0]:,.0f}–%{customdata[1]:,.0f})<extra></extra>"))
    fig.add_vline(x=inv.AS_OF, line={"color": AXIS, "width": 1, "dash": "dot"})
    style_axes(fig)
    fig.update_layout(height=380, margin={"l": 8, "r": 12, "t": 36, "b": 30}, bargap=0.25, barcornerradius=4,
                      yaxis={"title": "Units per week", "rangemode": "tozero"})
    return fig


def frontier_figure(xs, ys, spend, budget):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", line={"color": PLAN, "width": 2, "shape": "hv"}, name="Expected lost revenue",
        fill="tozeroy", fillcolor="rgba(42,120,214,0.08)",
        hovertemplate="Spend %{x:$,.0f} → %{y:$,.0f} lost<extra></extra>",
    ))
    at = ys[np.searchsorted(xs, spend, side="right") - 1]
    fig.add_trace(go.Scatter(x=[spend], y=[at], mode="markers", showlegend=False,
                             marker={"size": 11, "color": PLAN, "line": {"color": SURFACE, "width": 2}},
                             hovertemplate="This plan: %{x:$,.0f} → %{y:$,.0f} lost<extra></extra>"))
    fig.add_annotation(x=spend, y=at, text=f"<b>This plan</b><br>{money(spend)} → {money(at)} lost",
                       showarrow=False, xanchor="left", yanchor="bottom", xshift=10, yshift=6,
                       align="left", font={"size": 11, "color": INK})
    fig.add_hline(y=ys[-1], line={"color": STATUS["critical"], "width": 1, "dash": "dot"})
    fig.add_annotation(x=xs[-1], y=ys[-1], text="Unavoidable: runs out before any order lands", showarrow=False,
                       xanchor="right", yanchor="top", yshift=-4, font={"size": 11, "color": INK_2})
    if budget < xs[-1]:
        fig.add_vline(x=budget, line={"color": MUTED, "width": 1, "dash": "dot"})
    style_axes(fig)
    fig.update_layout(height=380, margin={"l": 8, "r": 16, "t": 16, "b": 30}, showlegend=False,
                      xaxis={"title": "Purchase spend", "tickprefix": "$", "tickformat": "~s"},
                      yaxis={"title": "Expected lost revenue", "tickprefix": "$", "tickformat": "~s",
                             "rangemode": "tozero"})
    return fig


# ---------------------------------------------------------------- layout


def kpi(label, value_id, sub_id, icon):
    return dmc.Paper(
        [
            dmc.Group([DashIconify(icon=icon, width=16, className="kpi-icon"), dmc.Text(label, className="kpi-label")],
                      gap=6),
            html.Div(id=value_id, className="kpi-value"),
            html.Div(id=sub_id, className="kpi-sub"),
        ],
        className="card kpi",
    )


header = html.Header(
    [
        html.Div(
            [
                html.Div(DashIconify(icon="tabler:packages", width=22), className="brand-mark"),
                html.Div([
                    html.Div("Ridgeline Cycle Supply", className="eyebrow"),
                    html.H1("Reorder Planner", className="title"),
                ]),
            ],
            className="brand",
        ),
        html.Div(
            [
                html.Span("Stock position as of"),
                html.Strong(f"{inv.AS_OF:%a %b} {inv.AS_OF.day}, {inv.AS_OF.year}"),
                html.Span("·"),
                html.Span(f"{len(inv.SKUS)} SKUs · {len(inv.SUPPLIERS)} suppliers"),
            ],
            className="asof",
        ),
    ],
    className="topbar",
)

controls = dmc.Paper(
    dmc.SimpleGrid(
        [
            dmc.Select(id="category", label="Category", data=["All", *inv.CATEGORIES], value="All",
                       allowDeselect=False, className="ctl"),
            dmc.Select(id="supplier", label="Supplier", data=["All", *inv.SUPPLIERS], value="All",
                       allowDeselect=False, className="ctl"),
            html.Div([
                dmc.Group([dmc.Text("Purchase budget", className="ctl-label"),
                           dmc.Text(id="budget-readout", className="ctl-readout")], justify="space-between"),
                dmc.Slider(id="budget", min=0, max=60000, step=1000, value=20000, label=None, size="sm",
                           marks=[{"value": v, "label": f"${v // 1000}k"} for v in (0, 20000, 40000, 60000)]),
            ], className="ctl"),
            html.Div([
                dmc.Text("Review cycle", className="ctl-label"),
                dmc.SegmentedControl(id="review", value="14", fullWidth=True, size="sm",
                                     data=[{"label": "Weekly", "value": "7"}, {"label": "Biweekly", "value": "14"},
                                           {"label": "Monthly", "value": "28"}]),
            ], className="ctl"),
            html.Div([
                dmc.Group([
                    dmc.Text("Cost of a lost sale", className="ctl-label"),
                    dmc.Tooltip(DashIconify(icon="tabler:info-circle", width=14, className="muted"),
                                label="Multiple of the item's margin. Above 1× accounts for customers who "
                                      "don't come back after a stockout.", multiline=True, w=240),
                ], gap=4),
                dmc.SegmentedControl(id="penalty", value="1.5", fullWidth=True, size="sm",
                                     data=[{"label": f"{v}× margin", "value": v} for v in ("1", "1.5", "2")]),
            ], className="ctl"),
        ],
        cols={"base": 1, "sm": 2, "lg": 5},
        spacing="lg",
    ),
    className="card controls",
)

kpis = dmc.SimpleGrid(
    [
        kpi("At risk of stockout", "kpi-risk", "kpi-risk-sub", "tabler:alert-triangle"),
        kpi("Recommended spend", "kpi-spend", "kpi-spend-sub", "tabler:receipt"),
        kpi("Expected lost revenue", "kpi-lost", "kpi-lost-sub", "tabler:trending-down"),
        kpi("Fill rate this cycle", "kpi-fill", "kpi-fill-sub", "tabler:gauge"),
    ],
    cols={"base": 1, "xs": 2, "lg": 4},
    spacing="md",
)

runway_card = dmc.Paper(
    [
        html.Div([
            html.H2("Runway board", className="card-title"),
            dmc.Text("Most urgent first. The bar is how long stock lasts with no new order; the tick is when an "
                     "order placed today would arrive. Click a row for detail.", className="card-sub"),
        ]),
        html.Div(
            [html.Span([html.I(className=f"swatch sw-{lv}"), STATUS_SHORT[lv]], className="lg-item")
             for lv in ("critical", "warning", "good")]
            + [html.Span([html.I(className="swatch sw-tick"), "Order placed today lands"], className="lg-item"),
               html.Span("Days until stockout, no new order", className="lg-axis")],
            className="legend-row",
        ),
        html.Div(dcc.Graph(id="runway", config={"displayModeBar": False}), className="runway-scroll"),
    ],
    className="card",
)

detail_card = dmc.Paper(
    [
        html.Div(id="detail-head"),
        html.Div(id="detail-facts", className="facts"),
        dmc.Tabs(
            [
                dmc.TabsList([dmc.TabsTab("Stock projection", value="stock"),
                              dmc.TabsTab("Demand", value="demand")]),
                dmc.TabsPanel(dcc.Graph(id="projection", config={"displayModeBar": False}), value="stock"),
                dmc.TabsPanel(dcc.Graph(id="demand", config={"displayModeBar": False}), value="demand"),
            ],
            value="stock", variant="pills", radius="xl", className="detail-tabs",
        ),
        html.Div(id="detail-note", className="card-sub note"),
    ],
    className="card",
)

frontier_card = dmc.Paper(
    [
        html.H2("What the budget buys", className="card-title"),
        dmc.Text("Expected lost revenue over the cycle as spend goes up, spending first on the case packs that "
                 "protect the most margin per dollar. The curve flattens where extra stock mostly sits on the "
                 "shelf.", className="card-sub"),
        dcc.Graph(id="frontier", config={"displayModeBar": False}),
    ],
    className="card",
)

po_card = dmc.Paper(
    [
        dmc.Group([
            html.Div([
                html.H2("Purchase orders", className="card-title"),
                dmc.Text("Grouped by supplier. Stockout chance is for the stretch between the order landing and "
                         "the next cycle's order landing, without → with the order.",
                         className="card-sub"),
            ]),
            dmc.Button("Download CSV", id="download-btn", variant="light", size="xs",
                       leftSection=DashIconify(icon="tabler:download", width=14)),
        ], justify="space-between", align="flex-start", wrap="nowrap"),
        html.Div(id="po-table", className="po-scroll"),
        dcc.Download(id="download"),
    ],
    className="card",
)

app.layout = dmc.MantineProvider(
    html.Div(
        [
            header,
            html.Main(
                [
                    controls,
                    kpis,
                    dmc.Grid([dmc.GridCol(runway_card, span={"base": 12, "lg": 5}),
                              dmc.GridCol(detail_card, span={"base": 12, "lg": 7})], gutter="md"),
                    dmc.Grid([dmc.GridCol(frontier_card, span={"base": 12, "lg": 5}),
                              dmc.GridCol(po_card, span={"base": 12, "lg": 7})], gutter="md"),
                    html.Footer("Synthetic data. Demand, lead times and stock positions are simulated, "
                                "800 paths per SKU.", className="footer"),
                ],
                className="main",
            ),
            dcc.Store(id="selected", data=None),
        ],
    ),
    theme=THEME,
    forceColorScheme="light",
)


# ---------------------------------------------------------------- callbacks


def compute(categories, supplier, budget, review, penalty):
    ids = scoped_ids(categories, supplier)
    review, penalty = int(review), float(penalty)
    packs, spend = inv.plan(budget, review, penalty, 0.25, ids)
    return ids, review, penalty, packs, spend


@app.callback(
    Output("budget-readout", "children"),
    Output("kpi-risk", "children"), Output("kpi-risk-sub", "children"),
    Output("kpi-spend", "children"), Output("kpi-spend-sub", "children"),
    Output("kpi-lost", "children"), Output("kpi-lost-sub", "children"),
    Output("kpi-fill", "children"), Output("kpi-fill-sub", "children"),
    Output("frontier", "figure"),
    Output("po-table", "children"),
    Input("category", "value"), Input("supplier", "value"), Input("budget", "value"),
    Input("review", "value"), Input("penalty", "value"), Input("selected", "data"),
)
def update_plan(categories, supplier, budget, review, penalty, selected):
    ids, review, penalty, packs, spend = compute(categories, supplier, budget, review, penalty)
    skus = [s for s in inv.SKUS if s.id in ids]
    if not skus:
        empty = dmc.Text("No SKUs match these filters.", className="card-sub")
        blank = style_axes(go.Figure()).update_layout(height=300)
        return money(budget), "—", "", "—", "", "—", "", "—", "", blank, empty

    curves = inv.order_curves(review)
    levels = [inv.status(s, review) for s in skus]
    n_crit, n_warn = levels.count("critical"), levels.count("warning")
    ordered = [s for s in skus if packs[s.id]]
    suppliers = sorted({s.supplier for s in ordered})

    lost_before = sum(curves[s.id]["lost"][0] * s.price for s in skus)
    lost_after = sum(curves[s.id]["lost"][packs[s.id]] * s.price for s in skus)
    demand_rev = sum(curves[s.id]["window_demand"] * s.price for s in skus)
    fill_before, fill_after = 1 - lost_before / demand_rev, 1 - lost_after / demand_rev
    xs, ys = inv.frontier(review, penalty, 0.25, ids)
    uncovered = [s for s, lv in zip(skus, levels) if lv != "good" and not packs[s.id]]

    risk_sub = [html.Span(f"{n_crit} out before arrival", className="t-critical"), " · ",
                f"{n_warn} need an order this cycle"]
    spend_sub = (f"{len(ordered)} SKUs on {len(suppliers)} POs · {money(budget - spend)} unspent"
                 if spend < xs[-1] - 1 else f"{len(ordered)} SKUs · more spend wouldn't pay back")
    if uncovered:
        spend_sub = [spend_sub, html.Br(), html.Span(f"{len(uncovered)} at-risk SKUs left unordered",
                                                    className="t-critical")]
    lost_sub = [f"vs {money(lost_before, True)} with no orders · ",
                html.Span(f"{money(ys[-1], True)} unavoidable", className="muted")]
    fill_sub = f"vs {fill_before:.1%} with no orders · revenue-weighted"

    # Purchase order table
    rows = []
    for sup in suppliers:
        lines = sorted([s for s in ordered if s.supplier == sup], key=lambda s: -packs[s.id] * s.case_pack * s.unit_cost)
        sub_total = sum(packs[s.id] * s.case_pack * s.unit_cost for s in lines)
        meta = inv.SUPPLIERS[sup]
        rows.append(html.Tr([
            html.Td([html.Strong(sup), html.Span(f"  {meta.origin} · ~{meta.lead_mean:.0f} day lead",
                                                 className="muted")], colSpan=4),
            html.Td(money(sub_total), className="num right strong"),
        ], className="po-group"))
        for s in lines:
            c = curves[s.id]
            n = packs[s.id]
            rows.append(html.Tr([
                html.Td([html.Div(s.name, className="strong"), html.Div(s.id, className="mono muted")]),
                html.Td(status_badge(inv.status(s, review), short=True)),
                html.Td([html.Span(f"{n * s.case_pack:,}", className="num strong"),
                         html.Span(f" ({n}×{s.case_pack})", className="num muted")], className="right"),
                html.Td([html.Span(f"{c['p_out_after'][0]:.0%}", className="num muted"),
                         DashIconify(icon="tabler:arrow-right", width=12, className="muted arrow"),
                         html.Span(f"{c['p_out_after'][n]:.0%}", className="num strong")], className="right nowrap"),
                html.Td(money(n * s.case_pack * s.unit_cost), className="num right"),
            ], id={"type": "po-row", "sku": s.id}, n_clicks=0,
                className="po-row selected" if s.id == selected else "po-row"))
    if rows:
        table = dmc.Table(
            [html.Thead(html.Tr([html.Th("Item"), html.Th("Status"), html.Th("Qty", className="right"),
                                 html.Th("Stockout after it lands", className="right"), html.Th("Cost", className="right")])),
             html.Tbody(rows)],
            highlightOnHover=True, verticalSpacing=6, className="po",
        )
    else:
        table = dmc.Text("Nothing to order at this budget.", className="card-sub")

    return (
        money(budget),
        f"{n_crit + n_warn} SKUs", risk_sub,
        money(spend), spend_sub,
        money(lost_after, True), lost_sub,
        f"{fill_after:.1%}", fill_sub,
        frontier_figure(xs, ys, spend, budget),
        table,
    )


@app.callback(
    Output("runway", "figure"),
    Input("category", "value"), Input("supplier", "value"), Input("review", "value"), Input("selected", "data"),
)
def update_runway(categories, supplier, review, selected):
    ids = scoped_ids(categories, supplier)
    skus = [s for s in inv.SKUS if s.id in ids]
    if not skus:
        return style_axes(go.Figure()).update_layout(height=260)
    return runway_figure(skus, int(review), selected)


@app.callback(
    Output("selected", "data"),
    Input("runway", "clickData"),
    Input({"type": "po-row", "sku": ALL}, "n_clicks"),
    Input("category", "value"), Input("supplier", "value"), Input("review", "value"),
    State("selected", "data"),
)
def select_sku(click, _rows, categories, supplier, review, current):
    trig = ctx.triggered_id
    if trig == "runway" and click:
        return click["points"][0]["customdata"][0]
    if isinstance(trig, dict) and ctx.triggered and ctx.triggered[0]["value"]:
        return trig["sku"]
    ids = scoped_ids(categories, supplier)
    if current in ids:
        return current
    # Default to the most urgent SKU in scope
    skus = [s for s in inv.SKUS if s.id in ids]
    return min(skus, key=lambda s: inv.RUNWAY[s.id] - s.lead_mean).id if skus else None


@app.callback(
    Output("detail-head", "children"), Output("detail-facts", "children"),
    Output("projection", "figure"), Output("demand", "figure"), Output("detail-note", "children"),
    Input("selected", "data"),
    Input("category", "value"), Input("supplier", "value"), Input("budget", "value"),
    Input("review", "value"), Input("penalty", "value"),
)
def update_detail(sid, categories, supplier, budget, review, penalty):
    if sid is None:
        blank = style_axes(go.Figure()).update_layout(height=330)
        return dmc.Text("Pick a SKU", className="card-title"), None, blank, blank, None
    s = inv.BY_ID[sid]
    ids, review, penalty, packs, spend = compute(categories, supplier, budget, review, penalty)
    n = packs.get(sid, 0)
    c = inv.order_curves(review)[sid]
    level = inv.status(s, review)
    run = inv.RUNWAY[sid]

    head = dmc.Group([
        html.Div([
            html.Div(f"{s.id} · {s.category}", className="eyebrow dark"),
            html.H2(s.name, className="detail-title"),
        ]),
        status_badge(level),
    ], justify="space-between", align="flex-start")

    def fact(label, value, sub=None):
        return html.Div([html.Div(label, className="fact-label"), html.Div(value, className="fact-value"),
                         html.Div(sub, className="fact-sub") if sub else None], className="fact")

    inbound = sum(q for q, _ in s.inbound)
    facts = [
        fact("On hand", f"{s.on_hand:,}", f"{money(s.on_hand * s.unit_cost)} at cost"),
        fact("Open POs", f"{inbound:,}" if inbound else "None",
             ", ".join(f"lands {inv.day_label(e)}" for _, e in s.inbound) or None),
        fact("Forecast", f"{s.rate(np.arange(30)).mean():.1f}/day", "next 30 days"),
        fact("Lead time", f"~{s.lead_mean:.0f} days", s.supplier),
        fact("Runs out", "Not in 120 days" if run >= inv.HORIZON else inv.day_label(run),
             None if run >= inv.HORIZON else f"in ~{run:.0f} days, median"),
        fact("Recommended", f"{n * s.case_pack:,} units" if n else "No order",
             f"{n} case{'s' if n != 1 else ''} · {money(n * s.case_pack * s.unit_cost)}" if n else None),
    ]

    if n:
        note = (f"Once it lands, the order cuts the chance of running out before the next cycle's order arrives "
                f"from {c['p_out_after'][0]:.0%} to {c['p_out_after'][n]:.0%}.")
        if c["lost_before"][0] >= 1:
            note += (f" About {c['lost_before'][0]:,.0f} units of demand fall before it can arrive; no order "
                     f"placed today can save those.")
    elif level == "good":
        note = "Covered past the next review, so nothing to order this cycle."
    else:
        note = (f"At risk ({c['p_out_after'][0]:.0%} stockout chance after an order would land) but not funded: at this budget other SKUs protect "
                f"more margin per dollar. Raise the budget or narrow the filters to fund it.")
    return head, facts, projection_figure(s, n), demand_figure(s), note


@app.callback(
    Output("download", "data"),
    Input("download-btn", "n_clicks"),
    State("category", "value"), State("supplier", "value"), State("budget", "value"),
    State("review", "value"), State("penalty", "value"),
    prevent_initial_call=True,
)
def download(_n, categories, supplier, budget, review, penalty):
    ids, review, penalty, packs, spend = compute(categories, supplier, budget, review, penalty)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["supplier", "sku", "item", "case_pack", "cases", "units", "unit_cost", "line_cost"])
    for s in sorted(inv.SKUS, key=lambda s: (s.supplier, s.id)):
        n = packs.get(s.id, 0)
        if n:
            w.writerow([s.supplier, s.id, s.name, s.case_pack, n, n * s.case_pack, s.unit_cost,
                        round(n * s.case_pack * s.unit_cost, 2)])
    return dict(content=buf.getvalue(), filename=f"reorder-plan-{inv.AS_OF.isoformat()}.csv")


if __name__ == "__main__":
    app.run(debug=True, port=8081)
