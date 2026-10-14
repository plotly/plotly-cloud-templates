import os

import dash_ag_grid as dag
import pandas as pd
import dash_design_kit as ddk
from dash import Dash, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from dash_ai_analyst import AiAnalyst, DashEnterpriseConnector, register_data

from data import (
    FIRST_YEAR,
    DataUnavailable,
    LABELS,
    LAST_FULL_YEAR,
    PORTFOLIO,
    TICKERS,
    asset_stats,
    cache,
    calendar_returns,
    growth_of_10k,
    label_for,
    monthly_returns,
    window,
    year_labels,
)
from figures import asset_color, build_growth, build_quilt, empty_figure
from theme import NEGATIVE, PORTFOLIO_LINE


from dotenv import load_dotenv

load_dotenv()


app = Dash(__name__, title="Asset Class Quilt")
server = app.server
# AI Analyst keys per-viewer data and secrets off the Flask session, so every
# gunicorn worker must sign cookies with the same stable key.
server.secret_key = os.environ.get("SECRET_KEY")
cache.init_app(server)

ALL_ASSETS = TICKERS + [PORTFOLIO]
DEFAULT_EQUITY_PCT = 60


# Auto-discovered by Plotly Cloud's AI Analyst (Plotly Studio Embedded).
# A function rather than a module-level DataFrame, so nothing downloads at
# startup; the prices underneath are cached server-side for 12 hours.
def get_data() -> pd.DataFrame:
    """Calendar-year total returns for every asset class, one row per asset-year.

    Columns: Year, Period (e.g. "2026 YTD"), Ticker, Asset, Return (decimal,
    0.05 = 5%), Rank (1 = best that year), Assets ranked, Is YTD. The
    balanced portfolio (ticker "BAL") is 60% SPY / 40% AGG, rebalanced monthly.
    """
    monthly = monthly_returns(ALL_ASSETS, DEFAULT_EQUITY_PCT)
    monthly = window(monthly, FIRST_YEAR, LAST_FULL_YEAR, include_ytd=True)
    annual = calendar_returns(monthly)
    ranks = annual.rank(axis=1, ascending=False)
    periods = dict(zip(annual.index, year_labels(annual.index)))

    tidy = annual.stack().rename("Return").reset_index()
    tidy.columns = ["Year", "Ticker", "Return"]
    tidy["Rank"] = [ranks.at[y, t] for y, t in zip(tidy["Year"], tidy["Ticker"])]
    tidy["Rank"] = tidy["Rank"].astype(int)
    tidy["Assets ranked"] = tidy["Year"].map(annual.notna().sum(axis=1))
    tidy["Period"] = tidy["Year"].map(periods)
    tidy["Is YTD"] = tidy["Period"].str.endswith("YTD")
    tidy["Asset"] = [label_for(t, DEFAULT_EQUITY_PCT) for t in tidy["Ticker"]]
    tidy_final=tidy[
        [
            "Year",
            "Period",
            "Ticker",
            "Asset",
            "Return",
            "Rank",
            "Assets ranked",
            "Is YTD",
        ]
    ].sort_values(["Year", "Rank"], ignore_index=True)

    register_data(tidy_final, "data", "Asset class returns ranked by year")

    return tidy_final


GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
PERCENT = {"function": "params.value == null ? '' : d3.format('+.1%')(params.value)"}
PLAIN_PERCENT = {
    "function": "params.value == null ? '' : d3.format('.1%')(params.value)"
}
NEGATIVE_STYLE = {
    "styleConditions": [
        {"condition": "params.value < 0", "style": {"color": NEGATIVE}},
    ]
}


def asset_option(asset: str) -> dict:
    """Checklist option with a color swatch matching the quilt."""
    is_portfolio = asset == PORTFOLIO
    swatch_style = {
        # Swatch color is per-asset data, so it is set here, not in style.css
        "backgroundColor": asset_color(asset),
        "borderColor": PORTFOLIO_LINE if is_portfolio else asset_color(asset),
    }
    return {
        "label": html.Span(
            [
                html.Span(className="swatch", style=swatch_style),
                "Balanced" if is_portfolio else asset,
            ],
            className="asset-chip",
            title="Stock/bond blend of SPY and AGG" if is_portfolio else LABELS[asset],
        ),
        "value": asset,
    }


def filter_control(label: str, component, class_name: str = "") -> html.Div:
    return html.Div(
        [html.Div(label, className="filter-label"), component],
        className=f"filter {class_name}".strip(),
    )


controls = html.Div(
    [
        filter_control(
            "Asset classes",
            dcc.Checklist(
                id="asset-checklist",
                options=[asset_option(a) for a in ALL_ASSETS],
                value=ALL_ASSETS,
                inline=True,
                className="asset-checklist",
            ),
            "filter-assets",
        ),
        filter_control(
            "Years",
            dcc.RangeSlider(
                id="year-slider",
                min=FIRST_YEAR,
                max=LAST_FULL_YEAR,
                step=1,
                value=[LAST_FULL_YEAR - 14, LAST_FULL_YEAR],
                marks={
                    y: str(y)
                    for y in range(FIRST_YEAR, LAST_FULL_YEAR + 1)
                    if y % 5 == 0 or y == LAST_FULL_YEAR
                },
                allowCross=False,
                tooltip={"placement": "bottom"},
            ),
            "filter-years",
        ),
        filter_control(
            "Year to date",
            dcc.Checklist(
                id="ytd-toggle",
                options=[{"label": " Include", "value": "ytd"}],
                value=["ytd"],
                className="ytd-toggle",
            ),
        ),
        filter_control(
            "Balanced mix · % stocks",
            dcc.Slider(
                id="equity-slider",
                min=0,
                max=100,
                step=10,
                value=DEFAULT_EQUITY_PCT,
                marks={0: "0", 50: "50", 100: "100"},
                tooltip={"placement": "bottom"},
            ),
            "filter-mix",
        ),
        filter_control(
            "Highlight",
            dcc.Dropdown(
                id="highlight-select",
                options=[
                    {
                        "label": "Balanced portfolio" if a == PORTFOLIO else LABELS[a],
                        "value": a,
                    }
                    for a in ALL_ASSETS
                ],
                placeholder="Click a cell…",
                clearable=True,
            ),
            "filter-highlight",
        ),
    ],
    className="control-bar",
)

stats_grid = dag.AgGrid(
    id="stats-grid",
    className="stats-grid",
    columnDefs=[
        {"field": "Asset", "pinned": "left", "minWidth": 120},
        {
            "field": "Return",
            "headerTooltip": "Annualized (geometric) return over full calendar years",
            "valueFormatter": PERCENT,
            "cellStyle": NEGATIVE_STYLE,
        },
        {
            "field": "Volatility",
            "headerName": "Vol",
            "headerTooltip": "Annualized volatility of monthly returns",
            "valueFormatter": PLAIN_PERCENT,
        },
        {
            "field": "Max drawdown",
            "headerName": "Max DD",
            "headerTooltip": "Largest peak-to-trough decline (monthly)",
            "valueFormatter": PERCENT,
            "cellStyle": NEGATIVE_STYLE,
        },
        {
            "field": "#1 finishes",
            "headerName": "#1",
            "headerTooltip": "Years ranked first",
        },
        {
            "field": "Last place",
            "headerName": "Last",
            "headerTooltip": "Years ranked last",
        },
        {
            "field": "Avg rank",
            "headerTooltip": "Average yearly rank (1 = best)",
            "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
        },
    ],
    rowData=[],
    getRowId="params.data.asset",
    columnSize="responsiveSizeToFit",
    defaultColDef={"filter": True, "sortable": True, "minWidth": 78},
    dashGridOptions={
        "theme": "themeBalham",
        "animateRows": True,
        "pagination": True,
        "paginationPageSize": 10,
        "paginationAutoPageSize": True,
        "paginationPageSizeSelector": False,
        "rowSelection": {"mode": "singleRow", "checkboxes": False},
        "tooltipShowDelay": 300,
    },
)

app.layout = ddk.App(
    className="app-shell",
    children=[
        ddk.Header(
            className="app-header",
            children=[
                AiAnalyst(
                    inline=False,
                    skip_global_data=True,
                    login_provider="dash_enterprise",
                    connector=DashEnterpriseConnector(
                        username=os.environ.get("DE_USERNAME"),
                        password=os.environ.get("DE_PASSWORD"),
                        de_url=os.environ.get("DE_URL"),
                    ),
                #     system_prompt_appendix
                ),
                html.Div(
                    [
                        html.Div(
                            [html.Span() for _ in range(4)], className="brand-mark"
                        ),
                        html.Div("MARKET QUILT", className="brand-name"),
                        html.Div(className="brand-divider"),
                        html.Div("Asset Class Quilt", className="brand-product"),
                    ],
                    className="brand",
                ),
                html.Div(
                    "Calendar-year total returns · ETF proxies · Source: Yahoo Finance",
                    className="data-source-note",
                ),
            ],
        ),
        controls,
        html.Div(
            [
                ddk.Card(
                    className="fill-card quilt-card",
                    children=[
                        ddk.CardHeader(
                            title="Periodic table of returns · ranked best to worst each year"
                        ),
                        dcc.Loading(
                            ddk.Graph(
                                id="quilt-chart",
                                config=GRAPH_CONFIG,
                                className="fill-graph",
                            ),
                            parent_className="fill-loading",
                            color=PORTFOLIO_LINE,
                        ),
                    ],
                ),
                html.Div(
                    [
                        ddk.Card(
                            className="fill-card",
                            children=[
                                ddk.CardHeader(
                                    title="Risk & return · full calendar years",
                                    id="stats-title",
                                ),
                                stats_grid,
                            ],
                        ),
                        ddk.Card(
                            className="fill-card",
                            children=[
                                ddk.CardHeader(title="Growth of $10,000"),
                                ddk.Graph(
                                    id="growth-chart",
                                    config=GRAPH_CONFIG,
                                    className="fill-graph",
                                ),
                            ],
                        ),
                    ],
                    className="side-column",
                ),
            ],
            className="dashboard",
        ),
    ],
)


DATA_ERROR = "Market data couldn't be loaded from Yahoo Finance. Try again in a minute."


def selected_window(assets, years, ytd, equity_pct):
    monthly = monthly_returns(assets or [], equity_pct)
    return window(monthly, years[0], years[1], bool(ytd))


@callback(
    Output("quilt-chart", "figure"),
    Input("asset-checklist", "value"),
    Input("year-slider", "value"),
    Input("ytd-toggle", "value"),
    Input("equity-slider", "value"),
    Input("highlight-select", "value"),
)
def update_quilt(assets, years, ytd, equity_pct, highlight):
    try:
        monthly = selected_window(assets, years, ytd, equity_pct)
    except DataUnavailable:
        return empty_figure(DATA_ERROR)
    return build_quilt(calendar_returns(monthly), equity_pct, highlight)


@callback(
    Output("stats-grid", "rowData"),
    Input("asset-checklist", "value"),
    Input("year-slider", "value"),
    Input("equity-slider", "value"),
)
def update_stats(assets, years, equity_pct):
    # Stats use full calendar years only, so the YTD toggle doesn't apply.
    try:
        monthly = selected_window(assets, years, False, equity_pct)
    except DataUnavailable:
        return []
    return asset_stats(monthly, calendar_returns(monthly), equity_pct)


@callback(
    Output("stats-title", "title"),
    Input("year-slider", "value"),
)
def update_stats_title(years):
    return f"Risk & return · {years[0]}–{years[1]}"


@callback(
    Output("growth-chart", "figure"),
    Input("asset-checklist", "value"),
    Input("year-slider", "value"),
    Input("ytd-toggle", "value"),
    Input("equity-slider", "value"),
    Input("highlight-select", "value"),
)
def update_growth(assets, years, ytd, equity_pct, highlight):
    try:
        monthly = selected_window(assets, years, ytd, equity_pct)
    except DataUnavailable:
        return empty_figure(DATA_ERROR)
    if monthly.empty or monthly.shape[1] == 0:
        return build_growth(monthly, equity_pct, highlight)
    return build_growth(growth_of_10k(monthly), equity_pct, highlight)


@callback(
    Output("highlight-select", "value"),
    Input("quilt-chart", "clickData"),
    Input("stats-grid", "cellClicked"),
    State("highlight-select", "value"),
    prevent_initial_call=True,
)
def set_highlight(click_data, cell_clicked, current):
    """Clicking a quilt cell or a stats row highlights that asset.

    Clicking the already-highlighted asset again clears the highlight.
    """
    if ctx.triggered_id == "quilt-chart":
        if not click_data:
            raise PreventUpdate
        asset = click_data["points"][0].get("customdata")
    else:
        if not cell_clicked or cell_clicked.get("rowIndex") is None:
            raise PreventUpdate
        asset = cell_clicked.get("rowId")
    if not asset:
        return no_update
    return None if asset == current else asset


if __name__ == "__main__":
    app.run(debug=True)
