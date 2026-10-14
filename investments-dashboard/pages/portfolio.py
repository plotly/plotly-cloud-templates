import dash_mantine_components as dmc
from dash_iconify import DashIconify
from dash import dcc, html
import plotly.graph_objects as go
import plotly.express as px

from components.charts import create_sector_donut_chart, CHART_COLORS, CHART_LAYOUT
from components.tables import create_data_table
from utils.data_loader import get_sector_allocation, df_equity_char, df_equity_diver

sector_data = get_sector_allocation()

def create_style_box():
    """Create 3x3 investment style box"""
    fig = go.Figure()
    
    labels = [
        ['Large Value', 'Large Blend', 'Large Growth'],
        ['Mid Value', 'Mid Blend', 'Mid Growth'],
        ['Small Value', 'Small Blend', 'Small Growth']
    ]
    
    for i in range(3):
        for j in range(3):
            color = '#228be6' if (i == 0 and j == 1) else '#f1f3f5'
            opacity = 1 if (i == 0 and j == 1) else 0.5
            
            fig.add_shape(
                type="rect",
                x0=j, x1=j+1, y0=2-i, y1=3-i,
                fillcolor=color,
                opacity=opacity,
                line={'color': '#dee2e6', 'width': 1},
            )
            
            fig.add_annotation(
                x=j+0.5, y=2.5-i,
                text=labels[i][j],
                showarrow=False,
                font={'size': 10, 'color': '#fff' if (i == 0 and j == 1) else '#495057'},
            )
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Investment Style', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        xaxis={'visible': False, 'range': [-0.1, 3.1]},
        yaxis={'visible': False, 'range': [-0.1, 3.1]},
        height=300,
    )
    
    return fig

def create_sector_comparison_bar():
    """Create horizontal bar chart comparing fund vs benchmark sectors"""
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=sector_data['Sector'],
        x=sector_data['Fund'],
        name='Fund',
        orientation='h',
        marker_color=CHART_COLORS['primary'],
    ))
    
    fig.add_trace(go.Bar(
        y=sector_data['Sector'],
        x=sector_data['Benchmark'],
        name='Benchmark',
        orientation='h',
        marker_color=CHART_COLORS['gray'],
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Sector Allocation vs Benchmark', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        barmode='group',
        bargap=0.3,
        legend={'orientation': 'h', 'y': -0.15},
        xaxis={'title': 'Allocation %', 'ticksuffix': '%'},
        yaxis={'title': ''},
        height=450,
    )
    
    return fig

def create_risk_return_scatter():
    """Create risk/return scatter plot"""
    funds = ['500 Index Fund', 'MSCI EAFE', 'Growth Fund', 'Value Fund', 'Bond Fund']
    returns = [16.94, 14.2, 19.5, 12.3, 5.2]
    risk = [15.2, 18.5, 22.1, 14.8, 6.3]
    sizes = [100, 80, 60, 70, 50]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=risk,
        y=returns,
        mode='markers+text',
        marker={'size': sizes, 'color': px.colors.qualitative.Set2[:5], 'opacity': 0.7},
        text=funds,
        textposition='top center',
        hovertemplate='<b>%{text}</b><br>Risk: %{x:.1f}%<br>Return: %{y:.1f}%<extra></extra>'
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Risk vs Return', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        xaxis={'title': 'Risk (Std Dev %)', 'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)'},
        yaxis={'title': 'Return %', 'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)'},
        height=350,
    )
    
    return fig

def create_donut_with_click():
    """Create donut chart configured for click events"""
    colors = px.colors.qualitative.Set3[:len(sector_data)]
    
    fig = go.Figure(go.Pie(
        labels=sector_data['Sector'],
        values=sector_data['Fund'],
        hole=0.6,
        marker={'colors': colors},
        textinfo='percent',
        textposition='outside',
        hovertemplate='%{label}<br>%{value:.1f}%<extra></extra>'
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Sector Allocation (Click to highlight)', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        showlegend=True,
        legend={'orientation': 'v', 'x': 1.05, 'y': 0.5},
        annotations=[{
            'text': 'Sectors',
            'x': 0.5, 'y': 0.5,
            'font': {'size': 14, 'weight': 600},
            'showarrow': False
        }]
    )
    
    return fig

# Allocation View Content
allocation_view = html.Div([
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dcc.Graph(
                        id="sector-donut",
                        figure=create_donut_with_click(),
                        config={"displayModeBar": False},
                        style={"height": "400px"}
                    ),
                    dmc.Text("Click on a sector to see details", size="sm", c="dimmed", ta="center", id="sector-detail-text"),
                ]),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
        
        dmc.GridCol([
            dmc.Stack([
                dmc.Paper(
                    dcc.Graph(
                        figure=create_style_box(),
                        config={"displayModeBar": False},
                    ),
                    p="md",
                    radius="md",
                    withBorder=True,
                ),
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("Portfolio Style Summary", fw=600),
                        dmc.Group([
                            dmc.Badge("Large Cap", color="blue", size="lg"),
                            dmc.Badge("Blend", color="gray", size="lg"),
                            dmc.Badge("Domestic", color="green", size="lg"),
                        ]),
                        dmc.Text(
                            "This fund tracks the S&P 500 Index, providing broad exposure to large-cap U.S. equities across value, blend, and growth styles.",
                            size="sm", c="dimmed", mt="xs"
                        ),
                    ], gap="sm"),
                    p="md",
                    radius="md",
                    withBorder=True,
                ),
            ], gap="md"),
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    
    dmc.Paper(
        dcc.Graph(
            id="sector-bar-chart",
            figure=create_sector_comparison_bar(),
            config={"displayModeBar": False},
        ),
        p="md",
        radius="md",
        withBorder=True,
        mt="md",
    ),
], id="allocation-view")

# Characteristics View Content
characteristics_view = html.Div([
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Equity Characteristics", fw=600, size="lg"),
                    create_data_table(df_equity_char),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Sector Diversification", fw=600, size="lg"),
                    create_data_table(df_equity_diver),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    
    dmc.Paper(
        dmc.Stack([
            dmc.Text("Key Metrics Comparison", fw=600, size="lg"),
            dmc.SimpleGrid([
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("P/E Ratio", size="sm", c="dimmed"),
                        dmc.Text("21.4", size="xl", fw=700),
                        dmc.Text("vs 22.1 benchmark", size="xs", c="dimmed"),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("P/B Ratio", size="sm", c="dimmed"),
                        dmc.Text("3.2", size="xl", fw=700),
                        dmc.Text("vs 3.4 benchmark", size="xs", c="dimmed"),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("Dividend Yield", size="sm", c="dimmed"),
                        dmc.Text("1.8%", size="xl", fw=700),
                        dmc.Text("vs 1.7% benchmark", size="xs", c="dimmed"),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("Earnings Growth", size="sm", c="dimmed"),
                        dmc.Text("12.5%", size="xl", fw=700),
                        dmc.Text("5-year average", size="xs", c="dimmed"),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
            ], cols={"base": 2, "md": 4}, spacing="md"),
        ], gap="sm"),
        p="md",
        radius="md",
        withBorder=True,
        mt="md",
    ),
], id="characteristics-view", style={"display": "none"})

# Risk Analysis View Content
risk_view = html.Div([
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(
                    figure=create_risk_return_scatter(),
                    config={"displayModeBar": False},
                    style={"height": "400px"}
                ),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Risk Metrics", fw=600, size="lg"),
                    dmc.Stack([
                        dmc.Group([
                            dmc.Text("Standard Deviation", size="sm", w=150),
                            dmc.Progress(value=65, color="blue", size="lg", style={"flex": 1}),
                            dmc.Text("15.2%", size="sm", fw=500, w=60),
                        ], gap="sm"),
                        dmc.Group([
                            dmc.Text("Beta", size="sm", w=150),
                            dmc.Progress(value=100, color="green", size="lg", style={"flex": 1}),
                            dmc.Text("1.00", size="sm", fw=500, w=60),
                        ], gap="sm"),
                        dmc.Group([
                            dmc.Text("Sharpe Ratio", size="sm", w=150),
                            dmc.Progress(value=70, color="teal", size="lg", style={"flex": 1}),
                            dmc.Text("0.85", size="sm", fw=500, w=60),
                        ], gap="sm"),
                        dmc.Group([
                            dmc.Text("Sortino Ratio", size="sm", w=150),
                            dmc.Progress(value=75, color="cyan", size="lg", style={"flex": 1}),
                            dmc.Text("1.12", size="sm", fw=500, w=60),
                        ], gap="sm"),
                        dmc.Group([
                            dmc.Text("Max Drawdown", size="sm", w=150),
                            dmc.Progress(value=35, color="red", size="lg", style={"flex": 1}),
                            dmc.Text("-33.8%", size="sm", fw=500, w=60),
                        ], gap="sm"),
                        dmc.Group([
                            dmc.Text("Tracking Error", size="sm", w=150),
                            dmc.Progress(value=10, color="gray", size="lg", style={"flex": 1}),
                            dmc.Text("0.04%", size="sm", fw=500, w=60),
                        ], gap="sm"),
                    ], gap="md", mt="md"),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
                h="100%",
            )
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    
    dmc.Paper(
        dmc.Stack([
            dmc.Text("Risk Analysis Summary", fw=600, size="lg"),
            dmc.Alert(
                "This fund closely tracks its benchmark (S&P 500) with minimal tracking error. The risk profile is consistent with broad market exposure.",
                title="Low Tracking Error",
                color="blue",
            ),
            dmc.SimpleGrid([
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("Upside Capture", size="sm", c="dimmed"),
                        dmc.Text("99.8%", size="xl", fw=700, c="green"),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("Downside Capture", size="sm", c="dimmed"),
                        dmc.Text("100.2%", size="xl", fw=700, c="red"),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("Information Ratio", size="sm", c="dimmed"),
                        dmc.Text("-0.12", size="xl", fw=700),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
                dmc.Paper(
                    dmc.Stack([
                        dmc.Text("R-Squared", size="sm", c="dimmed"),
                        dmc.Text("99.9%", size="xl", fw=700, c="green"),
                    ], gap=4),
                    p="md", radius="sm", withBorder=True,
                ),
            ], cols={"base": 2, "md": 4}, spacing="md"),
        ], gap="md"),
        p="md",
        radius="md",
        withBorder=True,
        mt="md",
    ),
], id="risk-view", style={"display": "none"})

layout = dmc.Stack([
    # Page Header
    dmc.Group([
        dmc.Stack([
            dmc.Title("Portfolio Analysis", order=2),
            dmc.Text("Asset allocation, sector breakdown, and portfolio characteristics", c="dimmed"),
        ], gap=4),
        dmc.Group([
            dmc.SegmentedControl(
                id="portfolio-view",
                data=[
                    {"value": "allocation", "label": "Allocation"},
                    {"value": "characteristics", "label": "Characteristics"},
                    {"value": "risk", "label": "Risk Analysis"},
                ],
                value="allocation",
            ),
        ], gap="sm"),
    ], justify="space-between", mb="lg"),
    
    # View Containers
    allocation_view,
    characteristics_view,
    risk_view,
    
], gap="md")
