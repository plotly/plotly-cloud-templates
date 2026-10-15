import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify
import plotly.graph_objects as go

from components.charts import create_fee_comparison_chart, create_dividend_timeline, CHART_COLORS, CHART_LAYOUT
from components.tables import create_data_table, create_dividend_table
from utils.data_loader import (
    df_expenses, df_minimums, get_dividend_history,
    df_realized, df_unrealized
)

dividend_data = get_dividend_history()

def create_fee_waterfall():
    """Create fee breakdown waterfall chart"""
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Management Fee", "Admin Fee", "12b-1 Fee", "Other", "Total Expense"],
        y=[0.10, 0.02, 0.00, 0.02, 0],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": CHART_COLORS['secondary']}},
        increasing={"marker": {"color": CHART_COLORS['danger']}},
        totals={"marker": {"color": CHART_COLORS['primary']}},
        text=["+0.10%", "+0.02%", "+0.00%", "+0.02%", "0.14%"],
        textposition="outside",
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Expense Ratio Breakdown', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'title': 'Percentage', 'ticksuffix': '%'},
        showlegend=False,
    )
    
    return fig

def create_cost_impact_chart(initial=10000, years=30):
    """Show cost impact over time"""
    year_range = list(range(1, years + 1))
    
    fund_values = [initial * (1.07 - 0.0014) ** y for y in year_range]
    avg_values = [initial * (1.07 - 0.0099) ** y for y in year_range]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=year_range,
        y=avg_values,
        name='Category Avg (0.99%)',
        line={'color': CHART_COLORS['gray'], 'width': 2},
    ))
    
    fig.add_trace(go.Scatter(
        x=year_range,
        y=fund_values,
        name='This Fund (0.14%)',
        line={'color': CHART_COLORS['primary'], 'width': 2},
        fill='tonexty',
        fillcolor='rgba(34, 139, 230, 0.1)',
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Long-Term Cost Impact (7% annual return)', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        xaxis={'title': 'Years'},
        yaxis={'title': 'Portfolio Value', 'tickprefix': '$', 'tickformat': ','},
        legend={'orientation': 'h', 'y': -0.15},
    )
    
    return fig

def create_dividend_calendar():
    """Create dividend payment calendar visualization"""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    dividends = [0, 0, 0.96, 0, 0, 0.96, 0, 0, 1.13, 0, 0, 1.13]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=months,
        y=dividends,
        marker_color=[CHART_COLORS['primary'] if d > 0 else CHART_COLORS['gray'] for d in dividends],
        text=[f'${d:.2f}' if d > 0 else '' for d in dividends],
        textposition='outside',
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Dividend Payment Calendar', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'title': 'Dividend per Share', 'tickprefix': '$'},
        xaxis={'title': 'Month'},
    )
    
    return fig

layout = dmc.Stack([
    # Page Header
    dmc.Group([
        dmc.Stack([
            dmc.Title("Fees & Distributions", order=2),
            dmc.Text("Expense analysis, dividend history, and capital gains", c="dimmed"),
        ], gap=4),
        dmc.Group([
        ], gap="sm"),
    ], justify="space-between", mb="lg"),
    
    # Fee Calculator Section
    dmc.Paper(
        dmc.Stack([
            dmc.Text("Fee Impact Calculator", fw=600, size="lg"),
            dmc.Text("Adjust investment amount and time horizon to see the impact of fees", size="sm", c="dimmed"),
            dmc.Grid([
                dmc.GridCol([
                    dmc.Stack([
                        dmc.Text("Investment Amount", size="sm", fw=500),
                        dmc.NumberInput(
                            id="investment-amount",
                            value=10000,
                            min=1000,
                            max=1000000,
                            step=1000,
                            prefix="$",
                            thousandSeparator=",",
                            w="100%",
                        ),
                    ], gap="xs"),
                ], span={"base": 12, "sm": 6, "md": 3}),
                dmc.GridCol([
                    dmc.Stack([
                        dmc.Text("Time Horizon (Years)", size="sm", fw=500),
                        dmc.Slider(
                            id="time-horizon",
                            value=10,
                            min=1,
                            max=30,
                            step=1,
                            marks=[
                                {"value": 1, "label": "1"},
                                {"value": 10, "label": "10"},
                                {"value": 20, "label": "20"},
                                {"value": 30, "label": "30"},
                            ],
                            mt="md",
                        ),
                        dmc.Space(h=20),
                    ], gap="xs"),
                ], span={"base": 12, "sm": 6, "md": 5}),
                dmc.GridCol([
                    dmc.Paper(
                        dmc.Stack([
                            dmc.Stack([
                                dmc.Text("Your Savings", size="xs", c="dimmed", tt="uppercase", fw=500),
                                dmc.Text("$1,913", size="28px", fw=700, c="teal", id="savings-amount"),
                                dmc.Text("vs category average", size="xs", c="dimmed"),
                            ], gap=2, align="center"),
                            dmc.Divider(),
                            dmc.Group([
                                dmc.Stack([
                                    dmc.Text("This Fund", size="xs", c="dimmed"),
                                    dmc.Text("$19,672", size="lg", fw=600, c="teal", id="final-value-fund"),
                                ], gap=2, align="center"),
                                dmc.Divider(orientation="vertical", h=40),
                                dmc.Stack([
                                    dmc.Text("Category Avg", size="xs", c="dimmed"),
                                    dmc.Text("$17,759", size="lg", fw=600, c="gray", id="final-value-avg"),
                                ], gap=2, align="center"),
                            ], justify="center", gap="xl"),
                        ], gap="sm"),
                        p="md",
                        radius="md",
                        bg="var(--mantine-color-gray-0)",
                        style={"border": "1px dashed var(--mantine-color-gray-4)"},
                    ),
                ], span={"base": 12, "md": 4}),
            ], gutter="md", align="center"),
        ], gap="md"),
        p="md",
        radius="md",
        withBorder=True,
    ),
    
    # Fee Highlight Cards
    dmc.SimpleGrid([
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Expense Ratio", size="sm", c="dimmed"),
                dmc.Group([
                    dmc.Text("0.14%", size="xl", fw=700, c="green"),
                    dmc.Badge("85% below avg", color="green", size="sm"),
                ], gap="sm"),
                dmc.Text("Category average: 0.99%", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Distribution Yield", size="sm", c="dimmed"),
                dmc.Text("1.77%", size="xl", fw=700),
                dmc.Text("Annual yield based on distributions", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("SEC Yield", size="sm", c="dimmed"),
                dmc.Text("1.77%", size="xl", fw=700),
                dmc.Text("30-day SEC yield", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Annual Fee", size="sm", c="dimmed"),
                dmc.Text("$14", size="xl", fw=700, c="green"),
                dmc.Text("Per $10,000 invested", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
    ], cols={"base": 2, "md": 4}, spacing="md"),
    
    # Fee Charts Row
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(
                    id="fee-comparison-chart",
                    figure=create_fee_comparison_chart(),
                    config={"displayModeBar": False},
                    style={"height": "350px"}
                ),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
        
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(
                    figure=create_fee_waterfall(),
                    config={"displayModeBar": False},
                    style={"height": "350px"}
                ),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    
    # Long-term Cost Impact
    dmc.Paper(
        dcc.Graph(
            id="cost-impact-chart",
            figure=create_cost_impact_chart(),
            config={"displayModeBar": False},
            style={"height": "350px"}
        ),
        p="md",
        radius="md",
        withBorder=True,
    ),
    
    # Distributions Section
    dmc.Title("Distributions", order=3, mt="lg"),
    
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(
                    figure=create_dividend_calendar(),
                    config={"displayModeBar": False},
                    style={"height": "300px"}
                ),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Recent Distributions", fw=600, size="lg"),
                    create_data_table(dividend_data.head(5)),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    
    # Capital Gains Section
    dmc.Title("Capital Gains", order=3, mt="lg"),
    
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Realized Gains", fw=600, size="lg"),
                    create_data_table(df_realized),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Unrealized Appreciation", fw=600, size="lg"),
                    create_data_table(df_unrealized),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    
], gap="md")
