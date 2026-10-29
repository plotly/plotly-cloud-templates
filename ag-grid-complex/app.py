"""
Rebalance Desk

A portfolio rebalancing workflow built around Dash AG Grid. Screen the book for
accounts that have drifted outside their model's tolerance band, drill into
holdings and tax lots, size the trades on an editable ticket, run pre-trade
compliance, then release the orders and watch them fill.

Every screen is an AG Grid; the controls around it drive the grid API
(selection, filter models, quick filter, transactions, undo/redo, column state,
CSV export). The book is synthetic, see desk.py.
"""

import dash
import dash_ag_grid as dag
from dash import Input, Output, Patch, State, clientside_callback, ctx, dcc, html
from dash._hooks import HooksManager

import desk

# Skip installed Dash plugins (such as the Plotly Studio Embedded chat) so the
# desk renders on its own. Dash loads them once per process, on first app init
HooksManager._registered = True

app = dash.Dash(
    __name__,
    title="Rebalance Desk",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap"
    ],
)
server = app.server

THEME = {"function": "deskTheme(themeQuartz, agGrid)"}
STEPS = [
    ("Screen", "Find accounts outside their tolerance band and pick the ones to rebalance"),
    ("Propose", "Size the trades that take each account back to its model"),
    ("Check", "Pre-trade compliance on every order before it reaches the market"),
    ("Release", "Route the cleared orders and follow the fills"),
]
NEXT_LABEL = ["Propose trades", "Run checks", "Release orders", "New session"]
FILL_TICK_MS = 900
MAX_TICKS = 40


def fmt_money(x):
    a = abs(x)
    if a >= 1e6:
        return f"${x / 1e6:,.2f}M"
    if a >= 1e3:
        return f"${x / 1e3:,.0f}k"
    return f"${x:,.0f}"


def fn(expr):
    return {"function": expr}


# Column helpers -----------------------------------------------------------

def money_col(field, header, compact=False, **kw):
    return {"field": field, "headerName": header, "type": "rightAligned", "filter": "agNumberColumnFilter",
            "valueFormatter": fn(f"{'compact' if compact else 'money'}(params.value)"), **kw}


def pct_col(field, header, digits=1, **kw):
    return {"field": field, "headerName": header, "type": "rightAligned", "filter": "agNumberColumnFilter",
            "valueFormatter": fn(f"pct(params.value, {digits})"), **kw}


def gain_col(field, header, **kw):
    return money_col(field, header, cellClassRules={"pos": "params.value > 0", "neg": "params.value < 0"}, **kw)


SELECTION = {
    "mode": "multiRow",
    "checkboxes": True,
    "headerCheckbox": True,
    "selectAll": "filtered",
    "enableClickSelection": False,
}

BASE_OPTIONS = {
    "theme": THEME,
    "animateRows": True,
    "tooltipShowDelay": 250,
    "tooltipInteraction": True,
    "suppressCellFocus": False,
    "suppressDragLeaveHidesColumns": True,
    "selectionColumnDef": {"pinned": "left", "width": 48, "suppressHeaderMenuButton": True},
}

DEFAULT_COL = {"sortable": True, "resizable": True, "filter": True, "cellDataType": False, "minWidth": 90}


# Step 1 · Screen -----------------------------------------------------------

ACCOUNT_COLUMNS = [
    {"field": "household", "headerName": "Household", "cellRenderer": "Drill", "pinned": "left",
     "minWidth": 270, "filter": "agTextColumnFilter", "lockPinned": True,
     "tooltipValueGetter": fn("'Open ' + params.data.household + ' holdings'")},
    {"headerName": "Drift vs model", "children": [
        {"field": "max_drift", "headerName": "Largest drift", "cellRenderer": "DriftBar", "minWidth": 190,
         "filter": "agNumberColumnFilter", "sort": "desc",
         "cellRendererParams": {"scale": 0.08},
         "headerTooltip": "Widest single-position gap to target. The shaded band is the model's tolerance"},
        pct_col("abs_drift", "Total drift", 1, minWidth=110,
                headerTooltip="Half the sum of absolute drifts: the share of the account that is in the wrong place"),
        pct_col("band", "Band", 1, minWidth=75, hide=True),
        {"field": "status", "headerName": "Status", "cellRenderer": "Pill", "minWidth": 130,
         "filter": "agTextColumnFilter"},
    ]},
    {"headerName": "Mandate", "children": [
        {"field": "model", "headerName": "Model", "cellRenderer": "ModelTag", "minWidth": 150},
        {"field": "advisor", "headerName": "Advisor", "minWidth": 120},
        {"field": "registration", "headerName": "Registration", "minWidth": 120, "hide": True},
    ]},
    {"headerName": "Value", "children": [
        money_col("value", "AUM", compact=True, minWidth=100),
        {"field": "history", "headerName": "30 days", "cellRenderer": "Sparkline", "sortable": False,
         "filter": False, "minWidth": 120, "maxWidth": 130, "columnGroupShow": "open"},
        {"field": "return_30d", "headerName": "30d return", "type": "rightAligned", "filter": "agNumberColumnFilter",
         "valueFormatter": fn("signedPct(params.value)"), "minWidth": 105,
         "cellClassRules": {"pos": "params.value > 0", "neg": "params.value < 0"}},
        pct_col("cash_weight", "Cash", minWidth=80, columnGroupShow="open"),
    ], "openByDefault": True},
    gain_col("unrealized", "Unrealized", minWidth=110),
    {"field": "positions", "headerName": "Positions", "type": "rightAligned", "filter": "agNumberColumnFilter",
     "minWidth": 95},
    {"field": "last_rebalanced", "headerName": "Last rebalanced", "minWidth": 135,
     "valueFormatter": fn("dateFmt(params.value)"),
     "filter": "agDateColumnFilter",
     "filterParams": {"comparator": fn("isoDateComparator(filterLocalDateAtMidnight, cellValue)")},
     "cellClassRules": {"stale": "params.data.days_since > 270"}},
]
TOGGLEABLE = [("model", "Model"), ("advisor", "Advisor"), ("registration", "Registration"),
              ("history", "30-day sparkline"), ("cash_weight", "Cash"), ("band", "Band"),
              ("unrealized", "Unrealized"), ("positions", "Positions"), ("last_rebalanced", "Last rebalanced")]
VISIBLE_BY_DEFAULT = [c for c, _ in TOGGLEABLE if c not in ("registration", "band")]

accounts_grid = dag.AgGrid(
    id="accounts-grid",
    rowData=desk.ACCOUNTS,
    columnDefs=ACCOUNT_COLUMNS,
    defaultColDef={**DEFAULT_COL, "floatingFilter": True},
    getRowId="params.data.id",
    dashGridOptions={
        **BASE_OPTIONS,
        "rowSelection": SELECTION,
        "rowClassRules": {"row-out": "params.data.status === 'Out of band'"},
        "quickFilterText": "",
        "pagination": False,
    },
    csvExportParams={"fileName": "rebalance-desk-accounts.csv",
                     "columnKeys": ["household", "model", "advisor", "registration", "value", "return_30d",
                                    "cash_weight", "max_drift", "abs_drift", "status", "unrealized",
                                    "last_rebalanced"]},
    persistence=True,
    persisted_props=["columnState"],
    columnSize="responsiveSizeToFit",
    className="grid",
    style={"height": "100%"},
)

HOLDING_COLUMNS = [
    {"field": "ticker", "headerName": "Security", "cellRenderer": "Security", "cellRendererParams": {"drill": True},
     "pinned": "left", "minWidth": 210, "filter": "agTextColumnFilter",
     "tooltipValueGetter": fn("params.node.rowPinned ? '' : 'Open tax lots for ' + params.value")},
    {"field": "asset_class", "headerName": "Asset class", "cellRenderer": "AssetClass", "minWidth": 135},
    {"field": "sector", "headerName": "Sector", "minWidth": 130},
    {"field": "qty", "headerName": "Shares", "type": "rightAligned", "filter": "agNumberColumnFilter",
     "valueFormatter": fn("params.value == null ? '' : params.value.toLocaleString()")},
    {"field": "price", "headerName": "Price", "type": "rightAligned", "valueFormatter": fn("price(params.value)"),
     "filter": "agNumberColumnFilter"},
    {"field": "change", "headerName": "Day", "type": "rightAligned", "valueFormatter": fn("signedPct(params.value)"),
     "cellClassRules": {"pos": "params.value > 0", "neg": "params.value < 0"}, "minWidth": 80},
    money_col("market_value", "Market value", minWidth=120),
    {"field": "weight", "headerName": "Weight vs target", "cellRenderer": "WeightBar", "minWidth": 170,
     "cellRendererParams": {"max": 0.3}, "filter": "agNumberColumnFilter",
     "headerTooltip": "Bar is the current weight, the tick is the model target"},
    pct_col("target", "Target", 2, minWidth=85),
    {"field": "drift", "headerName": "Drift", "cellRenderer": "DriftBar", "minWidth": 180, "sort": "desc",
     "comparator": fn("absComparator(valueA, valueB)"), "filter": "agNumberColumnFilter"},
    gain_col("gain", "Unrealized", minWidth=110),
    {"field": "lots", "headerName": "Lots", "type": "rightAligned", "minWidth": 70},
]

holdings_grid = dag.AgGrid(
    id="holdings-grid",
    rowData=[],
    columnDefs=HOLDING_COLUMNS,
    defaultColDef=DEFAULT_COL,
    getRowId="params.data.id",
    dashGridOptions={
        **BASE_OPTIONS,
        "quickFilterText": "",
        "pinnedBottomRowData": [],
        "rowClassRules": {"row-legacy": "params.data.target === 0 && !params.node.rowPinned"},
    },
    columnSize="responsiveSizeToFit",
    className="grid",
    style={"height": "100%"},
)

LOT_COLUMNS = [
    {"field": "lot", "headerName": "Lot", "pinned": "left", "minWidth": 80, "maxWidth": 90},
    {"field": "acquired", "headerName": "Acquired", "minWidth": 130, "valueFormatter": fn("dateFmt(params.value)"),
     "filter": "agDateColumnFilter",
     "filterParams": {"comparator": fn("isoDateComparator(filterLocalDateAtMidnight, cellValue)")}},
    {"field": "days_held", "headerName": "Days held", "type": "rightAligned", "filter": "agNumberColumnFilter"},
    {"field": "term", "headerName": "Term", "cellRenderer": "Pill", "minWidth": 100,
     "cellRendererParams": {"labels": {"Short": "Short-term", "Long": "Long-term"}}},
    {"field": "qty", "headerName": "Shares", "type": "rightAligned", "filter": "agNumberColumnFilter",
     "valueFormatter": fn("params.value == null ? '' : params.value.toLocaleString()")},
    {"field": "cost", "headerName": "Cost / share", "type": "rightAligned", "valueFormatter": fn("price(params.value)")},
    money_col("cost_basis", "Cost basis"),
    money_col("market_value", "Market value"),
    gain_col("gain", "Gain"),
    {"field": "gain_pct", "headerName": "Gain %", "type": "rightAligned", "valueFormatter": fn("signedPct(params.value)"),
     "cellClassRules": {"pos": "params.value > 0", "neg": "params.value < 0"}},
    money_col("tax_if_sold", "Tax if sold", headerTooltip="Federal tax a full sale of the lot would realize today",
              cellClassRules={"warn-text": "params.value > 0"}),
]

lots_grid = dag.AgGrid(
    id="lots-grid",
    rowData=[],
    columnDefs=LOT_COLUMNS,
    defaultColDef={**DEFAULT_COL, "flex": 1},
    getRowId="params.data.id",
    dashGridOptions={**BASE_OPTIONS, "quickFilterText": "", "pinnedBottomRowData": []},
    columnSize="responsiveSizeToFit",
    className="grid",
    style={"height": "100%"},
)


# Step 2 · Propose ----------------------------------------------------------

EDITABLE = {"editable": True, "cellClass": "editable"}

PROPOSAL_COLUMNS = [
    {"field": "ticker", "headerName": "Security", "cellRenderer": "Security", "pinned": "left", "rowDrag": True,
     "minWidth": 210, "filter": "agTextColumnFilter", "tooltipValueGetter": fn("tradeTooltip(params)")},
    {"field": "household", "headerName": "Account", "minWidth": 170, "filter": "agTextColumnFilter",
     "tooltipField": "account_id"},
    {"field": "side", "headerName": "Side", "cellRenderer": "Side", "minWidth": 80, "maxWidth": 90},
    {"headerName": "Order ticket · click to edit", "headerClass": "hdr-edit", "children": [
        {"field": "qty", "headerName": "Shares", "type": "rightAligned", **EDITABLE, "minWidth": 100,
         "cellEditor": "agNumberCellEditor", "cellEditorParams": {"min": 1, "precision": 0, "showStepperButtons": True},
         "valueFormatter": fn("params.value == null ? '' : params.value.toLocaleString()"),
         "valueParser": fn("Number(params.newValue)"),
         "cellClassRules": {"edited": "params.data && params.data.qty !== params.data.orig_qty",
                            "oversell": "params.data && params.data.side === 'Sell' && params.data.qty > params.data.held_qty"}},
        {"field": "order_type", "headerName": "Type", **EDITABLE, "minWidth": 95,
         "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["Market", "Limit", "VWAP"]},
         "cellClassRules": {"edited": "params.data && params.data.order_type !== params.data.orig_type"}},
        {"field": "limit", "headerName": "Limit", "type": "rightAligned", "cellClass": "editable", "minWidth": 95,
         "editable": fn("params.data.order_type === 'Limit'"),
         "cellEditor": "agNumberCellEditor", "cellEditorParams": {"min": 0, "precision": 2},
         "valueParser": fn("params.newValue === '' || params.newValue == null ? null : Number(params.newValue)"),
         "valueFormatter": fn("params.node.rowPinned ? '' : params.data.order_type === 'Limit' ? price(params.value) : '—'"),
         "cellClassRules": {"needs-limit": "params.data && params.data.order_type === 'Limit' && !params.data.limit",
                            "locked": "params.data && params.data.order_type !== 'Limit'"}},
        {"field": "tif", "headerName": "TIF", **EDITABLE, "minWidth": 75,
         "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["Day", "GTC", "IOC"]}},
    ]},
    {"field": "price", "headerName": "Price", "type": "rightAligned", "valueFormatter": fn("price(params.value)")},
    {"colId": "notional", "headerName": "Notional", "type": "rightAligned", "minWidth": 115,
     "valueGetter": fn("params.node.rowPinned ? params.data.notional : signedNotional(params.data)"),
     "valueFormatter": fn("money(params.value)"),
     "cellClassRules": {"buy-text": "params.value > 0", "sell-text": "params.value < 0"}},
    {"headerName": "Allocation", "children": [
        pct_col("weight", "Now", 2, minWidth=80),
        pct_col("target", "Target", 2, minWidth=80),
        {"colId": "post_weight", "headerName": "After", "type": "rightAligned", "minWidth": 85,
         "valueGetter": fn("params.node.rowPinned ? null : postWeight(params.data)"),
         "valueFormatter": fn("pct(params.value, 2)")},
        {"colId": "residual", "headerName": "Residual drift", "cellRenderer": "DriftBar", "minWidth": 170,
         "valueGetter": fn("params.node.rowPinned ? null : residualDrift(params.data)"),
         "cellRendererParams": {"scale": 0.02}},
    ]},
    {"colId": "est_tax", "headerName": "Est. tax", "type": "rightAligned", "minWidth": 100,
     "valueGetter": fn("params.node.rowPinned ? params.data.est_tax : estTax(params.data)"),
     "valueFormatter": fn("params.value ? money(params.value) : '—'"),
     "cellClassRules": {"warn-text": "params.value > 0"},
     "headerTooltip": "Federal tax realized by the sale, pro rata across lots. Zero in tax-deferred accounts"},
    {"field": "registration", "headerName": "Acct type", "minWidth": 110, "hide": True},
]

proposal_grid = dag.AgGrid(
    id="proposal-grid",
    rowData=[],
    columnDefs=PROPOSAL_COLUMNS,
    defaultColDef=DEFAULT_COL,
    getRowId="params.data.id",
    dashGridOptions={
        **BASE_OPTIONS,
        "rowSelection": SELECTION,
        "undoRedoCellEditing": True,
        "undoRedoCellEditingLimit": 50,
        "singleClickEdit": True,
        "stopEditingWhenCellsLoseFocus": True,
        "rowDragManaged": True,
        "rowDragMultiRow": True,
        "quickFilterText": "",
        "pinnedBottomRowData": [],
        "rowClassRules": {"row-legacy": "params.data && params.data.legacy"},
    },
    csvExportParams={"fileName": "rebalance-desk-proposal.csv", "onlySelected": True,
                     "columnKeys": ["household", "ticker", "side", "qty", "order_type", "limit", "tif", "price",
                                    "notional", "weight", "target", "post_weight", "est_tax"]},
    columnSize="responsiveSizeToFit",
    className="grid",
    style={"height": "100%"},
)


# Step 3 · Check ------------------------------------------------------------

def check_col(key, header, tip):
    return {"field": f"chk_{key}", "headerName": header, "cellRenderer": "Check", "minWidth": 82, "maxWidth": 100,
            "headerTooltip": tip, "cellClass": "center", "filter": "agTextColumnFilter"}


CHECK_COLUMNS = [
    {"field": "household", "headerName": "Account", "spanRows": True, "pinned": "left", "minWidth": 200,
     "cellClass": "span-cell", "sortable": False},
    {"field": "ticker", "headerName": "Security", "cellRenderer": "Security", "minWidth": 190},
    {"field": "side", "headerName": "Side", "cellRenderer": "Side", "minWidth": 80, "maxWidth": 90},
    {"field": "qty", "headerName": "Shares", "type": "rightAligned",
     "valueFormatter": fn("params.value.toLocaleString()")},
    money_col("notional", "Notional", minWidth=110),
    {"headerName": "Pre-trade rules", "children": [
        check_col("restricted", "Restricted", "Advisor restricted list (insider and employer stock)"),
        check_col("wash_sale", "Wash sale", "Buying back a security sold at a loss within 30 days"),
        check_col("concentration", "Conc.", "Single-name weight after the trade must stay under 10%"),
        check_col("tax", "Tax", "Short-term gains above $1,500 in a taxable account"),
        check_col("liquidity", "Liquidity", "Order above 5% of average daily volume"),
        check_col("ticket", "Ticket", "Minimum ticket size and complete limit instructions"),
    ]},
    {"field": "result", "headerName": "Result", "cellRenderer": "Pill", "minWidth": 105, "pinned": "right",
     "cellRendererParams": {"labels": {"pass": "Cleared", "warn": "Review", "fail": "Blocked"}}},
    {"field": "reasons", "headerName": "Detail", "minWidth": 320, "flex": 1, "wrapText": True, "autoHeight": True,
     "cellClass": "reason", "tooltipField": "reasons"},
]

checks_grid = dag.AgGrid(
    id="checks-grid",
    rowData=[],
    columnDefs=CHECK_COLUMNS,
    defaultColDef=DEFAULT_COL,
    getRowId="params.data.id",
    dashGridOptions={
        **BASE_OPTIONS,
        "enableCellSpan": True,
        "rowSelection": {**SELECTION, "isRowSelectable": fn("params.data && params.data.result !== 'fail'"),
                         "hideDisabledCheckboxes": False},
        "rowClassRules": {"row-fail": "params.data.result === 'fail'", "row-warn": "params.data.result === 'warn'"},
    },
    columnSize="responsiveSizeToFit",
    className="grid",
    style={"height": "100%"},
)


# Step 4 · Release ----------------------------------------------------------

BLOTTER_COLUMNS = [
    {"field": "order_no", "headerName": "Order", "pinned": "left", "minWidth": 110, "cellClass": "mono"},
    {"field": "ticker", "headerName": "Security", "cellRenderer": "Security", "minWidth": 190},
    {"field": "household", "headerName": "Account", "minWidth": 190},
    {"field": "side", "headerName": "Side", "cellRenderer": "Side", "minWidth": 80, "maxWidth": 90},
    {"field": "order_type", "headerName": "Type", "minWidth": 85},
    {"field": "filled", "headerName": "Filled", "cellRenderer": "FillBar", "minWidth": 200,
     "enableCellChangeFlash": True},
    {"field": "avg_px", "headerName": "Avg price", "type": "rightAligned", "valueFormatter": fn("params.value == null ? '—' : price(params.value)"),
     "enableCellChangeFlash": True},
    {"field": "last_px", "headerName": "Last", "type": "rightAligned", "valueFormatter": fn("params.value == null ? '—' : price(params.value)"),
     "enableCellChangeFlash": True},
    {"colId": "slippage", "headerName": "Slippage", "type": "rightAligned", "minWidth": 95,
     "valueGetter": fn("params.data.avg_px ? (params.data.avg_px / params.data.price - 1) * 1e4 "
                       "* (params.data.side === 'Buy' ? 1 : -1) : null"),
     "valueFormatter": fn("params.value == null ? '—' : params.value.toFixed(1) + ' bp'"),
     "cellClassRules": {"neg": "params.value > 0", "pos": "params.value < 0"},
     "headerTooltip": "Fill price versus arrival price. Positive costs the client"},
    {"colId": "done_notional", "headerName": "Executed", "type": "rightAligned", "minWidth": 115,
     "valueGetter": fn("params.data.avg_px ? params.data.filled * params.data.avg_px : 0"),
     "valueFormatter": fn("money(params.value)")},
    {"field": "status", "headerName": "Status", "cellRenderer": "Pill", "minWidth": 110, "pinned": "right",
     "filter": "agTextColumnFilter"},
]

blotter_grid = dag.AgGrid(
    id="blotter-grid",
    rowData=[],
    columnDefs=BLOTTER_COLUMNS,
    defaultColDef=DEFAULT_COL,
    getRowId="params.data.id",
    dashGridOptions={**BASE_OPTIONS, "cellFlashDuration": 600, "cellFadeDuration": 900,
                     "rowClassRules": {"row-done": "params.data.status === 'Filled'"}},
    csvExportParams={"fileName": "rebalance-desk-executions.csv"},
    columnSize="responsiveSizeToFit",
    className="grid",
    style={"height": "100%"},
)


# Layout ----------------------------------------------------------------------

def kpi(label, id_, sub_id=None):
    return html.Div([html.Span(label, className="kpi-label"), html.B("—", id=id_),
                     html.Small("", id=sub_id) if sub_id else None], className="kpi")


def features(*names):
    return html.Div([html.Span("grid api", className="feat-label")] + [html.Code(n) for n in names],
                    className="features")


def tool(label, id_, kind="", **kw):
    return html.Button(label, id=id_, className=f"tool {kind}".strip(), n_clicks=0, **kw)


def segmented(id_, options, value):
    return dcc.RadioItems(id=id_, options=options, value=value, className="seg", inline=True,
                          inputClassName="seg-input", labelClassName="seg-label")


brand_mark = html.Div([html.Span(className=f"bar b{i}") for i in range(4)], className="mark")

topbar = html.Header([
    html.Div([brand_mark, html.Div([html.B("Rebalance Desk"),
                                    html.Span("Q4 rebalance window · Private Wealth · Book A")])],
             className="brand"),
    html.Div([
        html.Span([html.I(className="live"), "Market open"], className="mkt"),
        html.Span(f"{desk.TODAY:%a %d %b %Y}", className="mono dim"),
        html.Span("Dash AG Grid 35 · Community", className="badge"),
    ], className="top-right"),
], className="topbar")

stepper = html.Nav([
    html.Button([html.Span(f"0{i + 1}", className="step-no"), html.Span(name, className="step-name")],
                id=f"step-btn-{i}", className="step", n_clicks=0)
    for i, (name, _) in enumerate(STEPS)
], className="stepper")


def step_head(i, kpis):
    return html.Div([
        html.Div([html.Span(f"Step 0{i + 1}", className="eyebrow"), html.H1(STEPS[i][0]),
                  html.P(STEPS[i][1])], className="head-text"),
        html.Div(kpis, className="kpis"),
    ], className="step-head")


screen = html.Section([
    step_head(0, [kpi("Accounts selected", "k-sel", "k-sel-sub"), kpi("AUM in scope", "k-aum"),
                  kpi("Out of band", "k-oob", "k-oob-sub")]),
    html.Div([
        html.Div([
            html.Button("← Back", id="drill-up", className="tool up", n_clicks=0, style={"display": "none"}),
            html.Button("Book", id="crumb-book", className="crumb", n_clicks=0),
            html.Span("/", className="crumb-sep", id="sep-1"),
            html.Button("", id="crumb-account", className="crumb", n_clicks=0),
            html.Span("/", className="crumb-sep", id="sep-2"),
            html.Span("", id="crumb-position", className="crumb current"),
        ], className="crumbs"),
        html.Div([
            dcc.Input(id="quick", type="search", placeholder="Quick filter…  ticker, household, advisor",
                      debounce=False, className="search"),
            html.Div(segmented("status-filter", ["All", "Out of band", "Watch", "In band"], "All"),
                     id="status-wrap"),
            html.Div([
                tool("Select out-of-band", "select-oob", "accent"),
                html.Details([
                    html.Summary("Columns", className="tool"),
                    dcc.Checklist(id="col-toggle", options=[{"label": l, "value": v} for v, l in TOGGLEABLE],
                                  value=VISIBLE_BY_DEFAULT, className="col-menu"),
                ], id="col-menu", className="dropdown"),
                tool("Reset layout", "reset-cols"),
                tool("Export CSV", "export-accounts"),
            ], id="account-tools", className="tools"),
            html.Div([tool("", "toggle-include", "accent")], id="holding-tools", className="tools"),
        ], className="toolbar-right"),
    ], className="toolbar"),
    html.Div(id="account-card", className="account-card"),
    html.Div([
        html.Div(accounts_grid, id="lvl-accounts", className="lvl"),
        html.Div(holdings_grid, id="lvl-holdings", className="lvl"),
        html.Div(lots_grid, id="lvl-lots", className="lvl"),
    ], className="grid-frame"),
    features("rowSelection · selectAll:'filtered'", "cellRendererData", "filterModel", "floatingFilter",
             "quickFilterText", "setNodesSelected()", "setColumnsVisible()", "resetColumnState",
             "persistence · columnState", "pinnedBottomRowData", "comparator", "agDateColumnFilter",
             "exportDataAsCsv"),
], id="panel-0", className="panel")

propose = html.Section([
    step_head(1, [kpi("Trades selected", "p-count", "p-count-sub"), kpi("Buys", "p-buys"), kpi("Sells", "p-sells"),
                  kpi("Net cash", "p-net"), kpi("Est. tax", "p-tax")]),
    html.Div([
        html.Div([
            tool("↶ Undo", "undo"), tool("↷ Redo", "redo"),
            html.Span(className="divider"),
            tool("Select out-of-band", "p-select-oob"),
            tool("Select all", "p-select-all"),
            tool("Clear", "p-clear"),
        ], className="tools"),
        html.Div([
            html.Span("Selected rows →", className="dim small"),
            segmented("bulk-type", ["Market", "Limit", "VWAP"], "VWAP"),
            tool("Apply order type", "bulk-apply", "accent"),
            tool("Export selected", "export-proposal"),
        ], className="tools"),
    ], className="toolbar"),
    html.Div(html.Div(proposal_grid, className="lvl show"), className="grid-frame"),
    features("editable", "agNumberCellEditor", "agSelectCellEditor", "editable(fn)", "valueGetter", "valueParser",
             "cellValueChanged", "undoRedoCellEditing", "undoCellEditing()", "rowDragManaged · rowDragMultiRow",
             "rowTransaction.update", "selectedRows(fn)", "cellClassRules", "tooltipValueGetter",
             "csvExportParams.onlySelected"),
], id="panel-1", className="panel")

check = html.Section([
    step_head(2, [kpi("Cleared", "c-pass"), kpi("Needs review", "c-warn"), kpi("Blocked", "c-fail"),
                  kpi("Releasing", "c-sel", "c-sel-sub")]),
    html.Div([
        segmented("result-filter", [{"label": "All orders", "value": "all"}, {"label": "Needs review", "value": "warn"},
                                    {"label": "Blocked", "value": "fail"}], "all"),
        html.Div([tool("Acknowledge all reviews", "ack-warn", "accent")], className="tools"),
    ], className="toolbar"),
    html.Div(html.Div(checks_grid, className="lvl show"), className="grid-frame"),
    features("isRowSelectable", "enableCellSpan · spanRows", "wrapText · autoHeight", "rowClassRules",
             "pinned: 'right'", "columnGroups", "headerTooltip", "filterModel", "forEachNode()"),
], id="panel-2", className="panel")

release = html.Section([
    step_head(3, [kpi("Orders", "r-orders"), kpi("Filled", "r-filled", "r-filled-sub"), kpi("Executed", "r-exec"),
                  kpi("Avg slippage", "r-slip")]),
    html.Div([
        html.Div(id="r-banner", className="banner"),
        html.Div([tool("Export executions", "export-blotter")], className="tools"),
    ], className="toolbar"),
    html.Div(html.Div(blotter_grid, className="lvl show"), className="grid-frame"),
    features("rowTransaction · update", "getRowId", "enableCellChangeFlash", "cellFlashDuration", "animateRows",
             "valueGetter", "custom cellRenderer", "exportDataAsCsv"),
], id="panel-3", className="panel")

footer = html.Footer([
    html.Div(id="foot-summary", className="foot-summary"),
    html.Div([
        html.Button("← Back", id="back", className="btn ghost", n_clicks=0),
        html.Button("Propose trades →", id="next", className="btn primary", n_clicks=0),
    ], className="foot-actions"),
], className="footer")

app.layout = html.Div([
    dcc.Store(id="step", data=0),
    dcc.Store(id="reached", data=0),
    dcc.Store(id="drill", data={"level": "accounts"}),
    dcc.Store(id="trades", data={}),
    dcc.Store(id="orders", data=[]),
    dcc.Interval(id="ticker", interval=FILL_TICK_MS, disabled=True, n_intervals=0),
    topbar,
    stepper,
    html.Main([screen, propose, check, release], className="main"),
    footer,
], className="app")


# Navigation ------------------------------------------------------------------

@app.callback(
    Output("step", "data"),
    Output("reached", "data"),
    Output("trades", "data"),
    Output("proposal-grid", "rowData"),
    Output("proposal-grid", "selectedRows"),
    Output("checks-grid", "rowData"),
    Output("checks-grid", "selectedRows"),
    Output("orders", "data"),
    Output("blotter-grid", "rowData"),
    Output("ticker", "n_intervals"),
    Output("ticker", "disabled"),
    Output("accounts-grid", "deselectAll"),
    Output("drill", "data", allow_duplicate=True),
    Input("next", "n_clicks"),
    Input("back", "n_clicks"),
    *[Input(f"step-btn-{i}", "n_clicks") for i in range(len(STEPS))],
    State("step", "data"),
    State("reached", "data"),
    State("accounts-grid", "selectedRows"),
    State("proposal-grid", "selectedRows"),
    State("proposal-grid", "virtualRowData"),
    State("trades", "data"),
    State("checks-grid", "selectedRows"),
    State("checks-grid", "rowData"),
    prevent_initial_call=True,
)
def navigate(_n, _b, *args):
    *_, step, reached, accounts, proposal_sel, proposal_order, trades, check_sel, check_rows = args
    nu = dash.no_update
    out = {k: nu for k in ("trades", "prop_rows", "prop_sel", "chk_rows", "chk_sel", "orders", "blotter",
                           "tick", "paused", "deselect", "drill")}
    trigger = ctx.triggered_id

    if trigger == "back":
        target = max(step - 1, 0)
    elif trigger and trigger.startswith("step-btn-"):
        target = int(trigger.rsplit("-", 1)[1])
        if target > reached or target == step:
            raise dash.exceptions.PreventUpdate
    elif step == 0:
        if not accounts:
            raise dash.exceptions.PreventUpdate
        proposed = desk.propose_trades([a["id"] for a in accounts])
        for t in proposed:
            t["orig_qty"], t["orig_type"] = t["qty"], t["order_type"]
        out.update(trades={t["id"]: t for t in proposed}, prop_rows=proposed,
                   prop_sel=proposed, chk_rows=[], blotter=[], orders=[])
        target, reached = 1, 1
    elif step == 1:
        if not proposal_sel:
            raise dash.exceptions.PreventUpdate
        chosen = {r["id"] for r in proposal_sel}
        # Keep the priority the desk dragged rows into
        order = [r["id"] for r in (proposal_order or [])] or list(trades)
        results = desk.check_trades([trades[i] for i in order if i in chosen])
        out.update(chk_rows=results, chk_sel=[r for r in results if r["result"] == "pass"], blotter=[], orders=[])
        target, reached = 2, 2
    elif step == 2:
        if not check_sel:
            raise dash.exceptions.PreventUpdate
        chosen = {r["id"] for r in check_sel}
        orders = []
        for n, t in enumerate(trades[r["id"]] for r in check_rows if r["id"] in chosen):
            orders.append({k: t[k] for k in ("id", "household", "ticker", "name", "side", "qty", "price",
                                             "order_type", "limit")} | {"order_no": f"ORD-{58210 + n}"})
        out.update(orders=orders, blotter=[o | desk.fill_state(o, 0) for o in orders], tick=0, paused=False)
        target, reached = 3, 3
    else:
        # New session: clear everything and go back to the book
        out.update(trades={}, prop_rows=[], chk_rows=[], orders=[], blotter=[], paused=True, deselect=True,
                   drill={"level": "accounts"})
        target, reached = 0, 0

    return (target, max(reached, target), out["trades"], out["prop_rows"], out["prop_sel"], out["chk_rows"],
            out["chk_sel"], out["orders"], out["blotter"], out["tick"], out["paused"], out["deselect"], out["drill"])


@app.callback(
    *[Output(f"panel-{i}", "className") for i in range(len(STEPS))],
    *[Output(f"step-btn-{i}", "className") for i in range(len(STEPS))],
    Output("next", "children"),
    Output("back", "disabled"),
    Input("step", "data"),
    Input("reached", "data"),
)
def show_step(step, reached):
    panels = ["panel show" if i == step else "panel" for i in range(len(STEPS))]
    steps = ["step " + ("active" if i == step else "done" if i < reached or (i <= reached and i < step) else
                        "open" if i <= reached else "locked") for i in range(len(STEPS))]
    label = NEXT_LABEL[step] + ("" if step == 3 else " →")
    return *panels, *steps, label, step == 0


@app.callback(
    Output("foot-summary", "children"),
    Output("next", "disabled"),
    Input("step", "data"),
    Input("accounts-grid", "selectedRows"),
    Input("proposal-grid", "selectedRows"),
    Input("checks-grid", "selectedRows"),
    Input("blotter-grid", "rowData"),
    Input("ticker", "disabled"),
)
def footer_summary(step, accounts, proposal, checks, _blotter, paused):
    if step == 0:
        n = len(accounts or [])
        aum = sum(a["value"] for a in accounts or [])
        text = [html.B(f"{n} account{'s' * (n != 1)}"), f" selected · {fmt_money(aum)} in scope"] if n else \
            ["Tick the accounts to rebalance, or click ", html.B("→"), " on a household to inspect its holdings"]
        return text, n == 0
    if step == 1:
        n = len(proposal or [])
        return ([html.B(f"{n} trade{'s' * (n != 1)}"), " will go to compliance"] if n
                else ["Select at least one trade"]), n == 0
    if step == 2:
        n = len(checks or [])
        return ([html.B(f"{n} order{'s' * (n != 1)}"), " cleared for release. Blocked orders cannot be selected"]
                if n else ["Select the orders to release"]), n == 0
    return ["Orders are working" if not paused else "Session complete. Start a new one to rebalance again"], False


# Step 1 · Screen ---------------------------------------------------------------

@app.callback(
    Output("drill", "data"),
    Input("accounts-grid", "cellRendererData"),
    Input("holdings-grid", "cellClicked"),
    Input("crumb-book", "n_clicks"),
    Input("crumb-account", "n_clicks"),
    Input("drill-up", "n_clicks"),
    State("drill", "data"),
    prevent_initial_call=True,
)
def drill(renderer, clicked, _book, _acct, _up, current):
    trigger = ctx.triggered_id
    if trigger == "accounts-grid" and renderer and renderer.get("value", {}).get("action") == "drill":
        return {"level": "holdings", "account": renderer["value"]["id"]}
    if trigger == "holdings-grid" and clicked and clicked.get("colId") == "ticker" and clicked.get("rowId"):
        return {**current, "level": "lots", "position": clicked["rowId"]}
    if trigger == "crumb-book":
        return {"level": "accounts"}
    if trigger == "crumb-account" and current.get("account"):
        return {"level": "holdings", "account": current["account"]}
    if trigger == "drill-up":
        # One level up: lots -> holdings -> book
        if current["level"] == "lots":
            return {"level": "holdings", "account": current["account"]}
        return {"level": "accounts"}
    raise dash.exceptions.PreventUpdate


@app.callback(
    Output("lvl-accounts", "className"),
    Output("lvl-holdings", "className"),
    Output("lvl-lots", "className"),
    Output("crumb-account", "children"),
    Output("crumb-account", "style"),
    Output("sep-1", "style"),
    Output("crumb-position", "children"),
    Output("crumb-position", "style"),
    Output("sep-2", "style"),
    Output("crumb-book", "className"),
    Output("crumb-account", "className"),
    Output("drill-up", "children"),
    Output("drill-up", "style"),
    Output("status-wrap", "style"),
    Output("account-tools", "style"),
    Output("holding-tools", "style"),
    Output("holdings-grid", "rowData"),
    Output("holdings-grid", "dashGridOptions"),
    Output("lots-grid", "rowData"),
    Output("lots-grid", "dashGridOptions"),
    Output("account-card", "children"),
    Output("account-card", "className"),
    Input("drill", "data"),
)
def render_drill(state):
    level = state["level"]
    hide, show = {"display": "none"}, {}
    nu = dash.no_update
    holdings_rows, holdings_opts, lot_rows, lot_opts, card = nu, nu, nu, nu, None
    acct = desk.ACCOUNT_MAP.get(state.get("account"))
    pos = desk.POSITION_MAP.get(state.get("position"))

    if acct and level in ("holdings", "lots"):
        rows = [p | {"band": acct["band"]} for p in desk.holdings(acct["id"])]
        holdings_rows = rows
        holdings_opts = Patch()
        holdings_opts["pinnedBottomRowData"] = [{
            "id": "total", "ticker": "Total invested", "market_value": sum(p["market_value"] for p in rows),
            "weight": sum(p["weight"] for p in rows), "target": sum(p["target"] for p in rows),
            "gain": sum(p["gain"] for p in rows), "lots": sum(p["lots"] for p in rows),
        }]
        card = account_card(acct, pos)
    if pos and level == "lots":
        taxable = acct["registration"] == "Taxable"
        lots = [l | {"tax_if_sold": round(max(l["gain"], 0) * (desk.ST_RATE if l["term"] == "Short" else desk.LT_RATE), 2)
                     if taxable else 0.0} for l in desk.lots(pos["id"])]
        lot_rows = lots
        lot_opts = Patch()
        lot_opts["pinnedBottomRowData"] = [{
            "id": "total", "lot": "Total", "qty": sum(l["qty"] for l in lots), "cost_basis": sum(l["cost_basis"] for l in lots),
            "market_value": sum(l["market_value"] for l in lots), "gain": sum(l["gain"] for l in lots),
            "tax_if_sold": sum(l["tax_if_sold"] for l in lots),
        }]

    is_acc, is_hold, is_lots = level == "accounts", level == "holdings", level == "lots"
    return (
        "lvl show" if is_acc else "lvl", "lvl show" if is_hold else "lvl", "lvl show" if is_lots else "lvl",
        acct["household"] if acct else "", show if not is_acc else hide, show if not is_acc else hide,
        pos["ticker"] + " tax lots" if pos and is_lots else "", show if is_lots else hide, show if is_lots else hide,
        "crumb current" if is_acc else "crumb", "crumb current" if is_hold else "crumb",
        "← Holdings" if is_lots else "← All accounts", hide if is_acc else show,
        show if is_acc else hide, show if is_acc else hide, hide if is_acc else show,
        holdings_rows, holdings_opts, lot_rows, lot_opts, card, "account-card" + ("" if is_acc else " show"),
    )


def account_card(acct, pos):
    def stat(label, value, cls=""):
        return html.Div([html.Span(label), html.B(value, className=cls)], className="stat")

    stats = [
        stat("Model", acct["model"]), stat("Advisor", acct["advisor"]), stat("Registration", acct["registration"]),
        stat("AUM", fmt_money(acct["value"])), stat("Cash", f"{acct['cash_weight']:.1%}"),
        stat("Largest drift", f"{acct['max_drift']:+.2%}", "bad" if acct["status"] == "Out of band" else ""),
        stat("Band", f"±{acct['band']:.1%}"),
    ]
    if pos:
        stats = [stat("Security", f"{pos['ticker']} · {pos['name']}"), stat("Shares", f"{pos['qty']:,}"),
                 stat("Avg cost", f"${pos['avg_cost']:,.2f}"), stat("Price", f"${pos['price']:,.2f}"),
                 stat("Short-term gain", fmt_money(pos["st_gain"]), "pos" if pos["st_gain"] > 0 else "neg"),
                 stat("Long-term gain", fmt_money(pos["lt_gain"]), "pos" if pos["lt_gain"] > 0 else "neg"),
                 stat("Drift", f"{pos['drift']:+.2%}")]
    return [html.Div(className=f"card-strip {acct['status'].split()[0].lower()}"), *stats]


@app.callback(
    Output("toggle-include", "children"),
    Output("toggle-include", "className"),
    Input("accounts-grid", "selectedRows"),
    Input("drill", "data"),
)
def include_label(selected, state):
    included = state.get("account") in {a["id"] for a in selected or []}
    return ("✓ In this rebalance" if included else "+ Add account to rebalance",
            "tool " + ("on" if included else "accent"))


# Select or deselect the drilled account in the (hidden) accounts grid
clientside_callback(
    """(n, state) => {
        if (!n || !state.account) return dash_clientside.no_update;
        const node = dash_ag_grid.getApi('accounts-grid').getRowNode(state.account);
        if (node) node.setSelected(!node.isSelected());
        return dash_clientside.no_update;
    }""",
    Output("toggle-include", "title"),
    Input("toggle-include", "n_clicks"),
    State("drill", "data"),
    prevent_initial_call=True,
)

# Select exactly the out-of-band accounts that pass the current filters
clientside_callback(
    """(n) => {
        const api = dash_ag_grid.getApi('accounts-grid');
        const nodes = [];
        api.forEachNodeAfterFilter((node) => { if (node.data.status === 'Out of band') nodes.push(node); });
        api.deselectAll();
        api.setNodesSelected({nodes: nodes, newValue: true});
        return dash_clientside.no_update;
    }""",
    Output("select-oob", "title"),
    Input("select-oob", "n_clicks"),
    prevent_initial_call=True,
)

# Show and hide columns through the column API
clientside_callback(
    """(visible, all) => {
        const api = dash_ag_grid.getApi('accounts-grid');
        if (!api) return dash_clientside.no_update;
        const ids = all.map((o) => o.value);
        api.setColumnsVisible(ids.filter((c) => !visible.includes(c)), false);
        api.setColumnsVisible(visible, true);
        return dash_clientside.no_update;
    }""",
    Output("col-menu", "title"),
    Input("col-toggle", "value"),
    State("col-toggle", "options"),
    prevent_initial_call=True,
)


@app.callback(
    Output("accounts-grid", "resetColumnState"),
    Output("col-toggle", "value"),
    Input("reset-cols", "n_clicks"),
    prevent_initial_call=True,
)
def reset_columns(_):
    return True, VISIBLE_BY_DEFAULT


@app.callback(
    Output("accounts-grid", "filterModel"),
    Input("status-filter", "value"),
    State("accounts-grid", "filterModel"),
)
def status_filter(status, model):
    model = {k: v for k, v in (model or {}).items() if k != "status"}
    if status != "All":
        model["status"] = {"filterType": "text", "type": "equals", "filter": status}
    return model


@app.callback(
    Output("accounts-grid", "dashGridOptions"),
    Output("holdings-grid", "dashGridOptions", allow_duplicate=True),
    Output("lots-grid", "dashGridOptions", allow_duplicate=True),
    Output("proposal-grid", "dashGridOptions"),
    Input("quick", "value"),
    prevent_initial_call=True,
)
def quick_filter(text):
    patches = []
    for _ in range(4):
        p = Patch()
        p["quickFilterText"] = text or ""
        patches.append(p)
    return patches


@app.callback(
    Output("accounts-grid", "exportDataAsCsv"),
    Input("export-accounts", "n_clicks"),
    prevent_initial_call=True,
)
def export_accounts(_):
    return True


@app.callback(
    Output("k-sel", "children"),
    Output("k-sel-sub", "children"),
    Output("k-aum", "children"),
    Output("k-oob", "children"),
    Output("k-oob-sub", "children"),
    Input("accounts-grid", "selectedRows"),
    Input("accounts-grid", "virtualRowData"),
)
def screen_kpis(selected, visible):
    selected = selected or []
    visible = visible if visible is not None else desk.ACCOUNTS
    oob = [a for a in visible if a["status"] == "Out of band"]
    oob_sel = sum(a["status"] == "Out of band" for a in selected)
    return (f"{len(selected)}", f"of {len(visible)} shown", fmt_money(sum(a["value"] for a in selected)),
            f"{len(oob)}", f"{oob_sel} selected")


# Step 2 · Propose --------------------------------------------------------------

@app.callback(
    Output("trades", "data", allow_duplicate=True),
    Output("proposal-grid", "rowTransaction"),
    Input("proposal-grid", "cellValueChanged"),
    Input("bulk-apply", "n_clicks"),
    State("bulk-type", "value"),
    State("proposal-grid", "selectedRows"),
    State("trades", "data"),
    prevent_initial_call=True,
)
def edit_trades(changes, _bulk, bulk_type, selected, trades):
    if ctx.triggered_id == "proposal-grid":
        # Edits already live in the grid; mirror them so totals and checks see them
        for c in changes or []:
            trades[c["rowId"]] = c["data"]
        return trades, dash.no_update
    if not selected:
        raise dash.exceptions.PreventUpdate
    updated = []
    for r in selected:
        t = trades[r["id"]]
        t["order_type"] = bulk_type
        if bulk_type == "Limit" and not t.get("limit"):
            # Seed a marketable limit 25 bp through the price
            t["limit"] = round(t["price"] * (1.0025 if t["side"] == "Buy" else 0.9975), 2)
        updated.append(t)
    return trades, {"update": updated}


@app.callback(
    Output("proposal-grid", "dashGridOptions", allow_duplicate=True),
    Output("p-count", "children"),
    Output("p-count-sub", "children"),
    Output("p-buys", "children"),
    Output("p-sells", "children"),
    Output("p-net", "children"),
    Output("p-tax", "children"),
    Input("trades", "data"),
    Input("proposal-grid", "selectedRows"),
    prevent_initial_call=True,
)
def proposal_totals(trades, selected):
    chosen = [trades[r["id"]] for r in selected or [] if r["id"] in trades]

    def notional(t):
        px = t["limit"] if t["order_type"] == "Limit" and t.get("limit") else t["price"]
        return t["qty"] * px

    buys = sum(notional(t) for t in chosen if t["side"] == "Buy")
    sells = sum(notional(t) for t in chosen if t["side"] == "Sell")
    tax = sum(t["qty"] * t["tax_per_share"] for t in chosen if t["side"] == "Sell")
    opts = Patch()
    opts["pinnedBottomRowData"] = [{"id": "total", "ticker": f"{len(chosen)} selected", "household": "", "notional": sells - buys,
                                    "est_tax": tax}]
    edited = sum(t["qty"] != t["orig_qty"] or t["order_type"] != t["orig_type"] for t in trades.values())
    return (opts, f"{len(chosen)}", f"of {len(trades)} · {edited} edited", fmt_money(buys), fmt_money(sells),
            ("+" if sells >= buys else "−") + fmt_money(abs(sells - buys)), fmt_money(tax))


for button, js in [
    ("undo", "api.undoCellEditing()"),
    ("redo", "api.redoCellEditing()"),
    ("p-select-all", "api.selectAll('filtered')"),
    ("p-clear", "api.deselectAll()"),
    ("p-select-oob", "api.deselectAll(); const nodes = []; "
                     "api.forEachNodeAfterFilter((n) => { if (n.data.out_of_band) nodes.push(n); }); "
                     "api.setNodesSelected({nodes: nodes, newValue: true})"),
]:
    clientside_callback(
        f"""(n) => {{
            const api = dash_ag_grid.getApi('proposal-grid');
            {js};
            return dash_clientside.no_update;
        }}""",
        Output(button, "title"),
        Input(button, "n_clicks"),
        prevent_initial_call=True,
    )


@app.callback(
    Output("proposal-grid", "exportDataAsCsv"),
    Input("export-proposal", "n_clicks"),
    prevent_initial_call=True,
)
def export_proposal(_):
    return True


# Step 3 · Check ------------------------------------------------------------------

@app.callback(
    Output("c-pass", "children"),
    Output("c-warn", "children"),
    Output("c-fail", "children"),
    Output("c-sel", "children"),
    Output("c-sel-sub", "children"),
    Input("checks-grid", "rowData"),
    Input("checks-grid", "selectedRows"),
)
def check_kpis(rows, selected):
    rows, selected = rows or [], selected or []
    count = lambda r: sum(x["result"] == r for x in rows)
    notional = sum(x["notional"] for x in selected)
    return count("pass"), count("warn"), count("fail"), len(selected), fmt_money(notional)


@app.callback(
    Output("checks-grid", "filterModel"),
    Input("result-filter", "value"),
)
def result_filter(value):
    return {} if value == "all" else {"result": {"filterType": "text", "type": "equals", "filter": value}}


clientside_callback(
    """(n) => {
        const api = dash_ag_grid.getApi('checks-grid');
        const nodes = [];
        api.forEachNode((node) => { if (node.data.result === 'warn') nodes.push(node); });
        api.setNodesSelected({nodes: nodes, newValue: true});
        return dash_clientside.no_update;
    }""",
    Output("ack-warn", "title"),
    Input("ack-warn", "n_clicks"),
    prevent_initial_call=True,
)


# Step 4 · Release ----------------------------------------------------------------

@app.callback(
    Output("blotter-grid", "rowTransaction"),
    Output("ticker", "disabled", allow_duplicate=True),
    Input("ticker", "n_intervals"),
    State("orders", "data"),
    prevent_initial_call=True,
)
def fills(tick, orders):
    if not orders:
        raise dash.exceptions.PreventUpdate
    states = [o | desk.fill_state(o, tick) for o in orders]
    done = all(s["status"] == "Filled" for s in states) or tick >= MAX_TICKS
    return {"update": states}, done


@app.callback(
    Output("r-orders", "children"),
    Output("r-filled", "children"),
    Output("r-filled-sub", "children"),
    Output("r-exec", "children"),
    Output("r-slip", "children"),
    Output("r-banner", "children"),
    Input("ticker", "n_intervals"),
    Input("ticker", "disabled"),
    State("orders", "data"),
)
def release_kpis(tick, paused, orders):
    if not orders:
        return "—", "—", "", "—", "—", ""
    states = [o | desk.fill_state(o, tick or 0) for o in orders]
    shares = sum(s["qty"] for s in states)
    filled = sum(s["filled"] for s in states)
    executed = sum(s["filled"] * s["avg_px"] for s in states if s["avg_px"])
    slip_num = sum(s["filled"] * s["avg_px"] * (s["avg_px"] / s["price"] - 1) * (1 if s["side"] == "Buy" else -1)
                   for s in states if s["avg_px"])
    slip = slip_num / executed * 1e4 if executed else 0
    complete = sum(s["status"] == "Filled" for s in states)
    resting = len(states) - complete
    if paused:
        banner = [html.I(className="dot ok"), html.B("Session closed. "),
                  f"{complete} orders filled" + (f", {resting} limit orders resting for the rest of the day" if resting else "")]
    else:
        banner = [html.I(className="live"), html.B("Routing. "), f"Fills stream in every {FILL_TICK_MS} ms "
                  "as row transactions; changed cells flash"]
    return (len(states), f"{int(filled / shares * 1000) / 10:.1f}%", f"{complete} of {len(states)} complete", fmt_money(executed),
            f"{slip:+.1f} bp", banner)


@app.callback(
    Output("blotter-grid", "exportDataAsCsv"),
    Input("export-blotter", "n_clicks"),
    prevent_initial_call=True,
)
def export_blotter(_):
    return True


if __name__ == "__main__":
    import os

    app.run(debug=True, port=int(os.environ.get("PORT", 8050)))
