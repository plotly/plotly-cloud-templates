from dash import callback, Input, Output, State, dcc, html
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from utils.data_loader import get_dividend_history
from components.charts import CHART_COLORS, CHART_LAYOUT

def calculate_fees(investment, years, fund_expense=0.0014, avg_expense=0.0099, annual_return=0.07):
    """Calculate fee impact over time"""
    fund_values = []
    avg_values = []
    
    fund_value = investment
    avg_value = investment
    
    for _ in range(years):
        fund_value *= (1 + annual_return - fund_expense)
        avg_value *= (1 + annual_return - avg_expense)
        fund_values.append(fund_value)
        avg_values.append(avg_value)
    
    fund_fees = investment * (1 + annual_return) ** years - fund_values[-1]
    avg_fees = investment * (1 + annual_return) ** years - avg_values[-1]
    savings = avg_fees - fund_fees
    
    return {
        'fund_values': fund_values,
        'avg_values': avg_values,
        'fund_final': fund_values[-1],
        'avg_final': avg_values[-1],
        'fund_fees': fund_fees,
        'avg_fees': avg_fees,
        'savings': savings
    }

def create_dynamic_fee_comparison(investment, years):
    """Create fee comparison chart with custom investment amount"""
    results = calculate_fees(investment, years)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=['Category Average', 'This Fund'],
        y=[results['avg_fees'], results['fund_fees']],
        marker_color=[CHART_COLORS['gray'], CHART_COLORS['primary']],
        text=[f"${results['avg_fees']:,.0f}", f"${results['fund_fees']:,.0f}"],
        textposition='outside',
    ))
    
    fig.add_annotation(
        x=1, y=results['fund_fees'] + results['savings'] * 0.15,
        text=f"Save ${results['savings']:,.0f}",
        showarrow=True,
        arrowhead=2,
        arrowcolor=CHART_COLORS['secondary'],
        font={'color': CHART_COLORS['secondary'], 'weight': 600},
    )
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': f'Fees on ${investment:,} Over {years} Years', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'tickprefix': '$', 'tickformat': ','},
        showlegend=False,
    )
    
    return fig

def create_dynamic_cost_impact(investment, years):
    """Create cost impact chart with custom parameters"""
    all_years = list(range(1, years + 1))
    results = calculate_fees(investment, years)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=all_years,
        y=results['avg_values'],
        name='Category Avg (0.99%)',
        line={'color': CHART_COLORS['gray'], 'width': 2},
    ))
    
    fig.add_trace(go.Scatter(
        x=all_years,
        y=results['fund_values'],
        name='This Fund (0.14%)',
        line={'color': CHART_COLORS['primary'], 'width': 2},
        fill='tonexty',
        fillcolor='rgba(34, 139, 230, 0.1)',
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': f'Long-Term Cost Impact (7% annual return)', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        xaxis={'title': 'Years'},
        yaxis={'title': 'Portfolio Value', 'tickprefix': '$', 'tickformat': ','},
        legend={'orientation': 'h', 'y': -0.15},
    )
    
    return fig

@callback(
    [Output("fee-comparison-chart", "figure"),
     Output("cost-impact-chart", "figure"),
     Output("savings-amount", "children"),
     Output("final-value-fund", "children"),
     Output("final-value-avg", "children")],
    [Input("investment-amount", "value"),
     Input("time-horizon", "value")]
)
def update_fee_calculations(amount, years):
    if amount is None or amount <= 0:
        amount = 10000
    if years is None or years <= 0:
        years = 10
    
    results = calculate_fees(amount, years)
    
    fee_chart = create_dynamic_fee_comparison(amount, years)
    cost_chart = create_dynamic_cost_impact(amount, years)
    
    return (
        fee_chart,
        cost_chart,
        f"${results['savings']:,.0f}",
        f"${results['fund_final']:,.0f}",
        f"${results['avg_final']:,.0f}"
    )

