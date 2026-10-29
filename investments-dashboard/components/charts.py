import dash_mantine_components as dmc
from dash import dcc
import plotly.graph_objects as go
import plotly.express as px

CHART_COLORS = {
    'primary': '#228be6',
    'secondary': '#40c057', 
    'tertiary': '#fab005',
    'danger': '#fa5252',
    'gray': '#868e96',
}

CHART_LAYOUT = {
    'paper_bgcolor': 'rgba(0,0,0,0)',
    'plot_bgcolor': 'rgba(0,0,0,0)',
    'font': {'family': 'Inter, sans-serif'},
    'margin': {'l': 40, 'r': 20, 't': 40, 'b': 40},
    'hovermode': 'x unified',
    'hoverlabel': {
        'bgcolor': 'white',
        'bordercolor': '#dee2e6',
        'font': {'family': 'Inter, sans-serif', 'size': 13, 'color': '#333'},
    },
}

def create_performance_line_chart(df, title="Performance Over Time"):
    """Create multi-series line chart for fund performance"""
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Calibre Index Fund'],
        name='Calibre Index Fund',
        line={'color': CHART_COLORS['primary'], 'width': 2},
        hovertemplate='%{y:.2f}<extra></extra>'
    ))
    
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['MSCI EAFE Index Fund (ETF)'],
        name='MSCI EAFE Index',
        line={'color': CHART_COLORS['secondary'], 'width': 2},
        hovertemplate='%{y:.2f}<extra></extra>'
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': title, 'x': 0, 'font': {'size': 16, 'weight': 600}},
        legend={'orientation': 'h', 'y': -0.15},
        xaxis={
            'showgrid': True,
            'gridcolor': 'rgba(0,0,0,0.05)',
            'rangeselector': {
                'buttons': [
                    {'count': 1, 'label': '1M', 'step': 'month'},
                    {'count': 6, 'label': '6M', 'step': 'month'},
                    {'count': 1, 'label': 'YTD', 'step': 'year', 'stepmode': 'todate'},
                    {'count': 1, 'label': '1Y', 'step': 'year'},
                    {'count': 3, 'label': '3Y', 'step': 'year'},
                    {'count': 5, 'label': '5Y', 'step': 'year'},
                    {'step': 'all', 'label': 'All'}
                ],
                'bgcolor': 'rgba(0,0,0,0.02)',
                'activecolor': CHART_COLORS['primary'],
            },
            'rangeslider': {'visible': False},
        },
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'tickprefix': '$'},
    )
    fig.update_layout(margin={'l': 40, 'r': 20, 't': 100, 'b': 40})

    return fig

def create_sparkline(prices, symbol=""):
    """Minimal area sparkline for live price history"""
    color = CHART_COLORS['secondary'] if len(prices) > 1 and prices[-1] >= prices[0] else CHART_COLORS['danger']
    hex_to_rgba = lambda c, a: f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},{a})"

    fig = go.Figure(go.Scatter(
        y=prices,
        mode='lines',
        fill='tozeroy',
        line={'color': color, 'width': 2.5},
        fillcolor=hex_to_rgba(color, 0.15),
        hovertemplate='$%{y:.2f}<extra></extra>',
    ))

    if len(prices) > 1:
        ymin, ymax = min(prices), max(prices)
        padding = max((ymax - ymin) * 0.3, 0.10)
        yrange = [ymin - padding, ymax + padding]
    else:
        yrange = None

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Inter, sans-serif'},
        margin={'l': 0, 'r': 0, 't': 20, 'b': 0},
        xaxis={'visible': False},
        yaxis={'visible': False, 'range': yrange},
        showlegend=False,
        title={'text': symbol, 'x': 0, 'font': {'size': 13, 'weight': 600}},
        hovermode='x unified',
    )
    return fig

def create_sector_donut_chart(sector_data, title="Sector Allocation"):
    """Create donut chart for sector allocation"""
    
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
        title={'text': title, 'x': 0, 'font': {'size': 16, 'weight': 600}},
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

def create_hypothetical_growth_chart(initial=10000):
    """Create hypothetical growth of $10k chart"""
    
    years = ['2008', '2010', '2012', '2014', '2016', '2018']
    fund_values = [10000, 11500, 14000, 18500, 22000, 27500]
    benchmark_values = [10000, 10800, 13200, 17000, 20500, 25000]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=years,
        y=fund_values,
        name='Calibre Index Fund',
        fill='tozeroy',
        line={'color': CHART_COLORS['primary'], 'width': 2},
        fillcolor='rgba(34, 139, 230, 0.1)',
        hovertemplate='$%{y:,.2f}<extra></extra>',
    ))
    
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

def create_fee_comparison_chart(fund_fee=329, avg_fee=2242):
    """Create fee comparison bar chart"""
    
    savings = avg_fee - fund_fee
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=['Category Average', 'This Fund'],
        y=[avg_fee, fund_fee],
        marker_color=[CHART_COLORS['gray'], CHART_COLORS['primary']],
        text=[f'${avg_fee:,}', f'${fund_fee:,}'],
        textposition='outside',
    ))
    
    fig.add_annotation(
        x=1, y=fund_fee + 300,
        text=f'Save ${savings:,}',
        showarrow=True,
        arrowhead=2,
        arrowcolor=CHART_COLORS['secondary'],
        font={'color': CHART_COLORS['secondary'], 'weight': 600},
    )
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Fees on $10,000 Over 10 Years', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'tickprefix': '$'},
        showlegend=False,
    )
    
    return fig

def create_dividend_timeline(dividend_data):
    """Create dividend history chart"""
    
    df = dividend_data.copy()
    df['Amount'] = df['Amount'].str.replace('$', '').astype(float)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['Payable_Date'],
        y=df['Amount'],
        marker_color=CHART_COLORS['primary'],
        name='Dividend',
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Dividend History', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'tickprefix': '$'},
        xaxis={'title': 'Payment Date'},
    )
    
    return fig
