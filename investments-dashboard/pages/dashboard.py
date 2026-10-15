import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

from components.charts import create_hypothetical_growth_chart, create_sparkline
from components.tables import create_fund_facts_table
from utils.data_loader import get_fund_metrics, df_fund_facts

metrics = get_fund_metrics()

SYMBOLS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
INITIAL_PRICES = {"AAPL": 189.50, "GOOGL": 176.30, "MSFT": 420.15, "AMZN": 185.60, "TSLA": 178.90}

def create_kpi_card(id_prefix, title, value, trend=None, trend_positive=True, subtitle=None, icon=None):
    """Create a KPI card with IDs for callback updates"""
    trend_color = "teal" if trend_positive else "red"
    
    return dmc.Paper(
        dmc.Stack([
            dmc.Group([
                dmc.Text(title, size="sm", c="dimmed", fw=500, id=f"{id_prefix}-title"),
                DashIconify(icon=icon, width=20, color="gray") if icon else None,
            ], justify="space-between"),
            dmc.Group([
                dmc.Text(value, size="xl", fw=700, id=f"{id_prefix}-value"),
                dmc.Text(
                    trend if trend else "", 
                    size="sm", 
                    c=trend_color, 
                    fw=500, 
                    id=f"{id_prefix}-trend",
                    style={"display": "block" if trend else "none"}
                ),
            ], justify="space-between", mt="xs"),
            dmc.Text(subtitle, size="xs", c="dimmed", mt=4, id=f"{id_prefix}-subtitle") if subtitle else None,
        ], gap="xs"),
        p="md",
        radius="md",
        withBorder=True,
        style={"minWidth": "200px"}
    )

def create_risk_row(id_prefix, label, value, progress_value, color):
    """Create a risk metric row with IDs for dynamic updates"""
    return dmc.Group([
        dmc.Text(label, size="sm", w=100),
        dmc.Progress(value=progress_value, color=color, size="lg", style={"flex": 1}, id=f"{id_prefix}-bar"),
        dmc.Text(value, size="sm", fw=500, w=60, id=f"{id_prefix}-value"),
    ], gap="sm")

layout = dmc.Stack([
    # Page Header
    dmc.Group([
        dmc.Stack([
            dmc.Title("Executive Dashboard", order=2),
            dmc.Text("Fund performance overview and key metrics", c="dimmed"),
        ], gap=4),
        dmc.Group([
            dmc.SegmentedControl(
                id="dashboard-period",
                data=[
                    {"value": "1Y", "label": "1Y"},
                    {"value": "3Y", "label": "3Y"},
                    {"value": "5Y", "label": "5Y"},
                    {"value": "10Y", "label": "10Y"},
                    {"value": "All", "label": "All"},
                ],
                value="1Y",
                size="sm",
            ),
            dmc.Select(
                id="dashboard-fund-select",
                data=[
                    {"value": "500", "label": "500 Index Fund Inv"},
                    {"value": "calibre", "label": "Calibre Index Fund"},
                ],
                value="500",
                w=200,
            ),
            dmc.Switch(
                id="benchmark-toggle",
                label="Benchmark",
                checked=True,
                size="sm",
            ),
            dmc.NumberInput(
                id="investment-amount",
                value=10000,
                min=1000,
                max=1000000,
                step=1000,
                prefix="$",
                thousandSeparator=",",
                w=130,
                size="sm",
            ),
        ], gap="sm"),
    ], justify="space-between", mb="lg"),
    
    # KPI Cards Row
    dmc.SimpleGrid([
        create_kpi_card(
            "kpi-nav",
            "Net Asset Value",
            f"${metrics['nav']:.2f}",
            trend=f"↑ {metrics['ytd_return']:.1f}% YTD",
            trend_positive=metrics['ytd_return'] > 0,
            icon="tabler:currency-dollar"
        ),
        create_kpi_card(
            "kpi-period",
            "1 Year Return",
            f"{metrics['1y_return']:.2f}%",
            subtitle="vs S&P 500",
            icon="tabler:chart-line"
        ),
        create_kpi_card(
            "kpi-expense",
            "Expense Ratio",
            metrics['expense_ratio'],
            trend="↓ 85% lower",
            trend_positive=True,
            subtitle="vs 0.99% category avg",
            icon="tabler:percentage"
        ),
        create_kpi_card(
            "kpi-category",
            "Category",
            metrics['category'],
            subtitle=metrics['asset_class'],
            icon="tabler:category"
        ),
    ], cols={"base": 1, "sm": 2, "lg": 4}, spacing="md"),
    
    # Main Charts Row
    dmc.Grid([
        dmc.GridCol([
            dcc.Store(id="live-streaming", data=True),
            dmc.Paper(
                dmc.Stack([
                    dmc.Group([
                        dmc.Group([
                            dmc.Text("Live Market Prices", fw=600, size="lg"),
                            html.Div(
                                style={
                                    "width": 8, "height": 8, "borderRadius": "50%",
                                    "backgroundColor": "#40c057",
                                    "animation": "pulse 1.5s ease-in-out infinite",
                                },
                                id="live-indicator",
                            ),
                            dmc.Badge("LIVE", color="green", size="sm", variant="light"),
                        ], gap="xs"),
                        dmc.Switch(
                            id="live-toggle",
                            label="Stream",
                            checked=True,
                            size="sm",
                        ),
                    ], justify="space-between"),
                    dmc.Divider(),
                    dmc.Stack([
                        dmc.Group([
                            dmc.Text(sym, size="sm", fw=600, w=60),
                            dmc.Text(
                                f"${INITIAL_PRICES[sym]:.2f}",
                                size="sm", fw=700, ff="monospace",
                                id=f"live-price-{sym}",
                            ),
                            dmc.Text(
                                "+0.00 (0.00%)",
                                size="xs", c="dimmed", ff="monospace",
                                id=f"live-change-{sym}",
                            ),
                        ], justify="space-between")
                        for sym in SYMBOLS
                    ], gap="xs"),
                    dmc.Divider(),
                    dmc.Select(
                        id="sparkline-symbol",
                        data=[{"value": s, "label": s} for s in SYMBOLS],
                        value="AAPL",
                        size="xs",
                        w=120,
                    ),
                    dcc.Graph(
                        id="sparkline-chart",
                        figure=create_sparkline([INITIAL_PRICES["AAPL"]], "AAPL"),
                        config={"displayModeBar": False},
                        style={"height": "120px"},
                    ),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 7}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dcc.Graph(
                        id="growth-chart",
                        figure=create_hypothetical_growth_chart(),
                        config={"displayModeBar": False},
                        style={"height": "350px"}
                    ),
                ]),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 5}),
    ], gutter="md"),
    
    # Fund Facts and Quick Stats Row
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Fund Facts", fw=600, size="lg"),
                    create_fund_facts_table(df_fund_facts),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 4}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Quick Comparison", fw=600, size="lg"),
                    dmc.SimpleGrid([
                        dmc.Paper(
                            dmc.Stack([
                                dmc.Text("1Y RETURN", size="xs", c="dimmed", fw=600),
                                dmc.Text(f"{metrics['1y_return']:.2f}%", size="lg", fw=600, id="quick-1y"),
                                dmc.Text("Fund", size="xs", c="dimmed"),
                            ], gap=4),
                            p="sm", radius="sm", withBorder=True,
                        ),
                        dmc.Paper(
                            dmc.Stack([
                                dmc.Text("3Y RETURN", size="xs", c="dimmed", fw=600),
                                dmc.Text(f"{metrics['3y_return']:.2f}%", size="lg", fw=600, id="quick-3y"),
                                dmc.Text("Fund", size="xs", c="dimmed"),
                            ], gap=4),
                            p="sm", radius="sm", withBorder=True,
                        ),
                        dmc.Paper(
                            dmc.Stack([
                                dmc.Text("5Y RETURN", size="xs", c="dimmed", fw=600),
                                dmc.Text(f"{metrics['5y_return']:.2f}%", size="lg", fw=600, id="quick-5y"),
                                dmc.Text("Fund", size="xs", c="dimmed"),
                            ], gap=4),
                            p="sm", radius="sm", withBorder=True,
                        ),
                        dmc.Paper(
                            dmc.Stack([
                                dmc.Text("MIN INVESTMENT", size="xs", c="dimmed", fw=600),
                                dmc.Text(metrics['min_investment'].replace('"', ''), size="lg", fw=600, id="quick-min"),
                            ], gap=4),
                            p="sm", radius="sm", withBorder=True,
                        ),
                    ], cols=2, spacing="sm"),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 4}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Risk Overview", fw=600, size="lg"),
                    dmc.Stack([
                        create_risk_row("risk-volatility", "Volatility", "Medium", 45, "blue"),
                        create_risk_row("risk-beta", "Beta", "1.00", 100, "green"),
                        create_risk_row("risk-sharpe", "Sharpe Ratio", "0.85", 70, "teal"),
                        create_risk_row("risk-alpha", "Alpha", "-0.02", 50, "yellow"),
                    ], gap="md", mt="sm"),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
                h="100%",
            )
        ], span={"base": 12, "md": 4}),
    ], gutter="md"),
    
], gap="md")
