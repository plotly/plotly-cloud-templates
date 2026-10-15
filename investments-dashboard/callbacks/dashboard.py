import asyncio
import random
from datetime import datetime

from dash import callback, ctx, Input, Output, State, dcc, set_props, html
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from utils.data_loader import get_fund_metrics, get_returns_data, get_time_series_data, df_fund_facts, calculate_risk_metrics
from components.charts import create_hypothetical_growth_chart, create_sparkline, CHART_COLORS, CHART_LAYOUT
import plotly.graph_objects as go

def get_metrics_for_fund(fund_id, period="1Y"):
    """Get metrics for a specific fund and period"""
    ts = get_time_series_data()
    returns = get_returns_data()
    facts = dict(zip(df_fund_facts['label'], df_fund_facts['value']))
    
    if fund_id == "calibre":
        col = 'Calibre Index Fund'
        fund_name = "Calibre Index Fund"
    else:
        col = '"S&amp;P 500 Index, y"'
        fund_name = "500 Index Fund"
    
    latest_price = ts[col].iloc[-1]
    
    period_map = {
        "1Y": 252,
        "3Y": 252 * 3,
        "5Y": 252 * 5,
        "10Y": 252 * 10,
        "All": len(ts)
    }
    
    lookback = min(period_map.get(period, 252), len(ts) - 1)
    start_price = ts[col].iloc[-lookback] if lookback < len(ts) else ts[col].iloc[0]
    period_return = ((latest_price - start_price) / start_price) * 100
    
    fund_returns = returns[returns['Entity'].str.contains('500 Index Fund', na=False)].iloc[0]
    
    return {
        'nav': latest_price,
        'period_return': period_return,
        'period': period,
        '1y_return': fund_returns['1Y'],
        '3y_return': fund_returns['3Y'],
        '5y_return': fund_returns['5Y'],
        '10y_return': fund_returns['10Y'],
        'fund_name': fund_name,
        'expense_ratio': facts.get('Expense ratio as of 04/27/2017', '0.14%'),
        'category': facts.get('Category', 'Large Blend'),
        'asset_class': facts.get('Asset Class', 'Domestic Stock'),
        'min_investment': facts.get('Minimum investment', '$3,000'),
    }

def create_dynamic_growth_chart(fund_id, initial=10000, show_benchmark=True):
    """Create growth chart for selected fund"""
    ts = get_time_series_data()
    
    col = 'Calibre Index Fund' if fund_id == "calibre" else '"S&amp;P 500 Index, y"'
    fund_name = "Calibre Index Fund" if fund_id == "calibre" else "500 Index Fund"
    benchmark_col = '"S&amp;P 500 Index, y"'
    
    yearly_data = ts.set_index('Date').resample('YE').last().reset_index()
    yearly_data = yearly_data.tail(10)
    
    first_price = yearly_data[col].iloc[0]
    fund_values = [initial * (p / first_price) for p in yearly_data[col]]
    years = yearly_data['Date'].dt.year.astype(str).tolist()
    
    first_bench = yearly_data[benchmark_col].iloc[0]
    benchmark_values = [initial * (p / first_bench) for p in yearly_data[benchmark_col]]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=years,
        y=fund_values,
        name=fund_name,
        fill='tozeroy',
        line={'color': CHART_COLORS['primary'], 'width': 2},
        fillcolor='rgba(34, 139, 230, 0.1)',
        hovertemplate='$%{y:,.2f}<extra></extra>',
    ))
    
    if show_benchmark:
        fig.add_trace(go.Scatter(
            x=years,
            y=benchmark_values,
            name='S&P 500 Index',
            line={'color': CHART_COLORS['gray'], 'width': 2, 'dash': 'dash'},
            hovertemplate='$%{y:,.2f}<extra></extra>',
        ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': f'Hypothetical Growth of ${initial:,}', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        legend={'orientation': 'h', 'y': -0.15},
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'tickprefix': '$', 'tickformat': ','},
        xaxis={'showgrid': False},
    )
    
    return fig

@callback(
    [Output("kpi-nav-value", "children"),
     Output("kpi-nav-trend", "children"),
     Output("kpi-nav-trend", "c"),
     Output("kpi-period-value", "children"),
     Output("kpi-period-title", "children"),
     Output("kpi-period-subtitle", "children"),
     Output("kpi-expense-value", "children"),
     Output("kpi-category-value", "children"),
     Output("kpi-category-subtitle", "children"),
     Output("growth-chart", "figure"),
     Output("quick-1y", "children"),
     Output("quick-3y", "children"),
     Output("quick-5y", "children"),
     Output("quick-min", "children"),
     Output("risk-volatility-bar", "value"),
     Output("risk-volatility-value", "children"),
     Output("risk-beta-bar", "value"),
     Output("risk-beta-value", "children"),
     Output("risk-sharpe-bar", "value"),
     Output("risk-sharpe-value", "children"),
     Output("risk-alpha-bar", "value"),
     Output("risk-alpha-value", "children")],
    [Input("dashboard-fund-select", "value"),
     Input("dashboard-period", "value"),
     Input("benchmark-toggle", "checked"),
     Input("investment-amount", "value")]
)
def update_dashboard(fund, period, show_benchmark, investment):
    metrics = get_metrics_for_fund(fund, period)
    risk = calculate_risk_metrics(fund, period)
    
    investment = investment or 10000
    
    nav_value = f"${metrics['nav']:.2f}"
    trend_icon = "↑" if metrics['period_return'] > 0 else "↓"
    trend_value = f"{trend_icon} {abs(metrics['period_return']):.1f}% {period}"
    trend_color = "teal" if metrics['period_return'] > 0 else "red"
    
    period_labels = {"1Y": "1 Year", "3Y": "3 Year", "5Y": "5 Year", "10Y": "10 Year", "All": "All Time"}
    period_title = f"{period_labels.get(period, period)} Return"
    
    period_return_map = {"1Y": metrics['1y_return'], "3Y": metrics['3y_return'], 
                         "5Y": metrics['5y_return'], "10Y": metrics['10y_return'], "All": metrics['period_return']}
    period_value = f"{period_return_map.get(period, metrics['1y_return']):.2f}%"
    
    growth_chart = create_dynamic_growth_chart(fund, investment, show_benchmark)
    
    return (
        nav_value,
        trend_value,
        trend_color,
        period_value,
        period_title,
        "vs S&P 500",
        metrics['expense_ratio'],
        metrics['category'],
        metrics['asset_class'],
        growth_chart,
        f"{metrics['1y_return']:.2f}%",
        f"{metrics['3y_return']:.2f}%",
        f"{metrics['5y_return']:.2f}%",
        metrics['min_investment'].replace('"', ''),
        risk['volatility_pct'],
        risk['volatility_level'],
        risk['beta_pct'],
        f"{risk['beta']:.2f}",
        risk['sharpe_pct'],
        f"{risk['sharpe']:.2f}",
        risk['alpha_pct'],
        f"{risk['alpha']:.2f}%",
    )

@callback(
    Output("live-streaming", "data"),
    Input("live-toggle", "checked"),
)
def toggle_streaming(checked):
    return checked


@callback(persistent=True)
async def stream_market_prices():
    ws = ctx.websocket
    prices = {"AAPL": 189.50, "GOOGL": 176.30, "MSFT": 420.15, "AMZN": 185.60, "TSLA": 178.90}
    base_prices = dict(prices)
    history = {s: [p] for s, p in prices.items()}

    while not ws.is_shutdown:
        streaming = await ws.get_prop("live-streaming", "data")
        if streaming:
            for sym in prices:
                change_pct = round(random.gauss(0, 0.3), 2)
                prices[sym] = round(prices[sym] * (1 + change_pct / 100), 2)
                history[sym].append(prices[sym])
                if len(history[sym]) > 30:
                    history[sym] = history[sym][-30:]

                dollar_change = round(prices[sym] - base_prices[sym], 2)
                total_pct = round((prices[sym] - base_prices[sym]) / base_prices[sym] * 100, 2)
                sign = "+" if dollar_change >= 0 else ""
                color = "#40c057" if dollar_change >= 0 else "#fa5252"

                set_props(f"live-price-{sym}", {"children": f"${prices[sym]:.2f}"})
                set_props(f"live-change-{sym}", {
                    "children": f"{sign}{dollar_change:.2f} ({sign}{total_pct:.2f}%)",
                    "style": {"color": color},
                })

            selected = await ws.get_prop("sparkline-symbol", "value")
            if selected and selected in history:
                fig = create_sparkline(history[selected], selected)
                set_props("sparkline-chart", {"figure": fig})

            await asyncio.sleep(1)
        else:
            await asyncio.sleep(0.5)


