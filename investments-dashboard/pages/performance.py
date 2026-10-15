import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify
import plotly.graph_objects as go

from components.charts import create_performance_line_chart, CHART_COLORS, CHART_LAYOUT
from utils.data_loader import (
    get_time_series_data, get_returns_data, 
    df_current_prices, df_avg_returns, df_after_tax, df_recent_returns
)

ts_data = get_time_series_data()
returns_data = get_returns_data()

def create_returns_table(df):
    """Create properly formatted returns table from raw CSV data"""
    data = df.values.tolist()
    
    if len(data) < 2:
        return dmc.Text("No data available", c="dimmed")
    
    headers = [str(h).replace("'-", "").strip() or "Fund" for h in data[0]]
    rows_data = data[1:]
    
    header = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh(col, style={'fontWeight': 600, 'fontSize': '13px'}) for col in headers
        ])
    )
    
    rows = []
    for row in rows_data:
        cells = []
        for i, val in enumerate(row):
            val_str = str(val).replace("'-", "—").strip()
            style = {'fontSize': '13px'}
            
            if '%' in val_str and val_str not in ['—', '']:
                try:
                    num = float(val_str.replace('%', ''))
                    style['color'] = '#40c057' if num > 0 else '#fa5252' if num < 0 else None
                    style['fontWeight'] = 500
                except:
                    pass
            
            if i == 0:
                style['fontWeight'] = 500
            
            cells.append(dmc.TableTd(val_str if val_str else "—", style=style))
        rows.append(dmc.TableTr(cells))
    
    body = dmc.TableTbody(rows)
    
    return dmc.ScrollArea(
        dmc.Table(
            [header, body],
            striped=True,
            highlightOnHover=True,
            withTableBorder=True,
            withColumnBorders=False,
            verticalSpacing="xs",
        ),
        type="auto"
    )

def create_drawdown_chart(df):
    """Calculate and plot drawdown"""
    prices = df['Calibre Index Fund'].values
    peak = prices[0]
    drawdowns = []
    
    for price in prices:
        if price > peak:
            peak = price
        drawdown = (price - peak) / peak * 100
        drawdowns.append(drawdown)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=drawdowns,
        fill='tozeroy',
        line={'color': CHART_COLORS['danger'], 'width': 1},
        fillcolor='rgba(250, 82, 82, 0.2)',
        name='Drawdown',
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Drawdown Analysis', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'ticksuffix': '%'},
        showlegend=False,
    )
    return fig

initial_total_return = ((ts_data['Calibre Index Fund'].iloc[-1] - ts_data['Calibre Index Fund'].iloc[0]) / ts_data['Calibre Index Fund'].iloc[0] * 100)

layout = dmc.Stack([
    # Page Header
    dmc.Stack([
        dmc.Group([
            dmc.Stack([
                dmc.Title("Price Performance", order=2),
                dmc.Text("Historical prices, returns analysis, and benchmark comparison", c="dimmed"),
            ], gap=4),
        ], justify="space-between"),
        
        # Filter Row
        dmc.Paper(
            dmc.Group([
                dmc.Group([
                    dmc.Text("Period", size="xs", fw=500, c="dimmed"),
                    dmc.SegmentedControl(
                        id="performance-period",
                        data=["1M", "3M", "6M", "1Y", "3Y", "5Y", "All"],
                        value="All",
                        size="xs",
                    ),
                ], gap=6),
                dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
                dmc.Group([
                    dmc.Text("Benchmarks", size="xs", fw=500, c="dimmed"),
                    dmc.MultiSelect(
                        id="benchmark-selector",
                        data=[
                            {"value": "calibre", "label": "Calibre Index Fund"},
                            {"value": "msci", "label": "MSCI EAFE Index"},
                            {"value": "sp500", "label": "S&P 500"},
                        ],
                        value=["calibre", "msci", "sp500"],
                        w=220,
                        clearable=True,
                        size="xs",
                    ),
                ], gap=6),
                dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
                dmc.Group([
                    dmc.Text("Display", size="xs", fw=500, c="dimmed"),
                    dmc.Switch(
                        id="normalize-toggle",
                        label="Normalize",
                        checked=True,
                        size="xs",
                    ),
                    dmc.Switch(
                        id="log-scale-toggle",
                        label="Log Scale",
                        checked=False,
                        size="xs",
                    ),
                ], gap=8),
                dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
                dmc.Group([
                    dmc.Text("Overlay", size="xs", fw=500, c="dimmed"),
                    dmc.Select(
                        id="ma-selector",
                        data=[
                            {"value": "none", "label": "No MA"},
                            {"value": "20", "label": "20-day"},
                            {"value": "50", "label": "50-day"},
                            {"value": "200", "label": "200-day"},
                        ],
                        value="none",
                        w=100,
                        size="xs",
                    ),
                ], gap=6),
            ], gap="md", align="center"),
            p="sm",
            radius="md",
            withBorder=True,
        ),
    ], gap="sm", mb="md"),
    
    # 1. Stats Cards Row (TOP)
    dmc.SimpleGrid([
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Period High", size="sm", c="dimmed"),
                dmc.Text(
                    f"${ts_data['Calibre Index Fund'].max():.2f}", 
                    size="xl", fw=700, c="green",
                    id="period-high-value"
                ),
                dmc.Text(
                    ts_data.loc[ts_data['Calibre Index Fund'].idxmax(), 'Date'].strftime('%Y-%m-%d'), 
                    size="xs", c="dimmed",
                    id="period-high-date"
                ),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Period Low", size="sm", c="dimmed"),
                dmc.Text(
                    f"${ts_data['Calibre Index Fund'].min():.2f}", 
                    size="xl", fw=700, c="red",
                    id="period-low-value"
                ),
                dmc.Text(
                    ts_data.loc[ts_data['Calibre Index Fund'].idxmin(), 'Date'].strftime('%Y-%m-%d'), 
                    size="xs", c="dimmed",
                    id="period-low-date"
                ),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Current Price", size="sm", c="dimmed"),
                dmc.Text(
                    f"${ts_data['Calibre Index Fund'].iloc[-1]:.2f}", 
                    size="xl", fw=700,
                    id="current-price-value"
                ),
                dmc.Text("Latest available", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Total Return", size="sm", c="dimmed"),
                dmc.Text(
                    f"{initial_total_return:.1f}%", 
                    size="xl", fw=700, 
                    c="green" if initial_total_return > 0 else "red",
                    id="total-return-value"
                ),
                dmc.Text("For selected period", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
    ], cols={"base": 2, "md": 4}, spacing="md"),
    
    # 2. Performance Metrics Row (SECOND)
    dmc.SimpleGrid([
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Volatility (Ann.)", size="sm", c="dimmed"),
                dmc.Text("0.0%", size="xl", fw=700, id="perf-volatility"),
                dmc.Text("Std deviation of returns", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Max Drawdown", size="sm", c="dimmed"),
                dmc.Text("0.0%", size="xl", fw=700, c="red", id="perf-max-drawdown"),
                dmc.Text("Worst peak-to-trough", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Sharpe Ratio", size="sm", c="dimmed"),
                dmc.Text("0.00", size="xl", fw=700, id="perf-sharpe"),
                dmc.Text("Risk-adjusted return", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Best / Worst Day", size="sm", c="dimmed"),
                dmc.Group([
                    dmc.Text("+0.0%", size="lg", fw=700, c="green", id="perf-best-day"),
                    dmc.Text("/", size="lg", c="dimmed"),
                    dmc.Text("-0.0%", size="lg", fw=700, c="red", id="perf-worst-day"),
                ], gap=4),
                dmc.Text("Single-day extremes", size="xs", c="dimmed"),
            ], gap=4),
            p="md",
            radius="md",
            withBorder=True,
        ),
    ], cols={"base": 2, "md": 4}, spacing="md"),
    
    # 3. Returns Tables and Analysis Charts Row (THIRD)
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Tabs([
                        dmc.TabsList([
                            dmc.TabsTab("Average Returns", value="avg"),
                            dmc.TabsTab("After Tax", value="tax"),
                            dmc.TabsTab("Recent Returns", value="recent"),
                        ]),
                        dmc.TabsPanel(create_returns_table(df_avg_returns), value="avg", pt="md"),
                        dmc.TabsPanel(create_returns_table(df_after_tax), value="tax", pt="md"),
                        dmc.TabsPanel(create_returns_table(df_recent_returns), value="recent", pt="md"),
                    ], value="avg"),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
        
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Tabs([
                        dmc.TabsList([
                            dmc.TabsTab("Drawdown", value="drawdown"),
                            dmc.TabsTab("Rolling Returns", value="rolling"),
                        ]),
                        dmc.TabsPanel(
                            dcc.Graph(
                                id="drawdown-chart",
                                figure=create_drawdown_chart(ts_data),
                                config={"displayModeBar": False},
                                style={"height": "300px"}
                            ),
                            value="drawdown", pt="md"
                        ),
                        dmc.TabsPanel(
                            dcc.Graph(
                                id="rolling-returns-chart",
                                figure=go.Figure(),
                                config={"displayModeBar": False},
                                style={"height": "300px"}
                            ),
                            value="rolling", pt="md"
                        ),
                    ], value="drawdown", id="analysis-tabs"),
                ], gap="sm"),
                p="md",
                radius="md",
                withBorder=True,
            )
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    
    # 4. Main Performance Chart (BOTTOM)
    dmc.Paper(
        dmc.Stack([
            dcc.Graph(
                id="performance-chart",
                figure=create_performance_line_chart(ts_data),
                config={"displayModeBar": False},
                style={"height": "400px"}
            ),
        ]),
        p="md",
        radius="md",
        withBorder=True,
    ),
    
], gap="md")
