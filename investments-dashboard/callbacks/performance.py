from dash import callback, Input, Output, State, dcc, html
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

from utils.data_loader import get_time_series_data
from components.charts import CHART_COLORS, CHART_LAYOUT

BENCHMARK_COLUMNS = {
    "calibre": ("Calibre Index Fund", CHART_COLORS['primary']),
    "msci": ("MSCI EAFE Index Fund (ETF)", CHART_COLORS['secondary']),
    "sp500": ('"S&amp;P 500 Index, y"', CHART_COLORS['tertiary']),
}

BENCHMARK_LABELS = {
    "calibre": "Calibre Index Fund",
    "msci": "MSCI EAFE Index",
    "sp500": "S&P 500",
}

def calculate_date_range_from_period(period, df):
    """Calculate date range based on period selector"""
    if period == "All" or not period:
        return None
    
    end_date = df['Date'].max()
    
    period_map = {
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
        "3Y": timedelta(days=365 * 3),
        "5Y": timedelta(days=365 * 5),
    }
    
    delta = period_map.get(period, timedelta(days=365))
    start_date = end_date - delta
    
    return [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]

def filter_data_by_date(df, date_range):
    """Filter dataframe by date range"""
    if date_range and len(date_range) == 2 and date_range[0] and date_range[1]:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        return df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
    return df

def normalize_series(df, columns):
    """Normalize series to start at 100"""
    normalized_df = df.copy()
    for col in columns:
        if col in normalized_df.columns:
            first_val = normalized_df[col].iloc[0]
            if first_val != 0:
                normalized_df[col] = (normalized_df[col] / first_val) * 100
    return normalized_df

def calculate_moving_average(df, col_name, window):
    """Calculate moving average"""
    if col_name in df.columns and window > 0:
        return df[col_name].rolling(window=window).mean()
    return None

def calculate_performance_metrics(df, col_name):
    """Calculate volatility, max drawdown, Sharpe, best/worst day"""
    if col_name not in df.columns or len(df) < 2:
        return {
            'volatility': 0, 'max_drawdown': 0, 'sharpe': 0,
            'best_day': 0, 'worst_day': 0
        }
    
    returns = df[col_name].pct_change().dropna()
    
    if len(returns) == 0:
        return {
            'volatility': 0, 'max_drawdown': 0, 'sharpe': 0,
            'best_day': 0, 'worst_day': 0
        }
    
    volatility = returns.std() * (252 ** 0.5) * 100
    
    prices = df[col_name].values
    peak = prices[0]
    max_dd = 0
    for price in prices:
        if price > peak:
            peak = price
        dd = (price - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd
    
    risk_free = 0.02
    excess = returns.mean() * 252 - risk_free
    std_ann = returns.std() * (252 ** 0.5)
    sharpe = excess / std_ann if std_ann > 0 else 0
    
    best_day = returns.max() * 100
    worst_day = returns.min() * 100
    
    return {
        'volatility': volatility,
        'max_drawdown': max_dd,
        'sharpe': sharpe,
        'best_day': best_day,
        'worst_day': worst_day
    }

def create_dynamic_performance_chart(df, benchmarks, normalize=False, ma_period=None, log_scale=False, title="Performance Over Time"):
    """Create performance chart with selected benchmarks, normalization, MA, and log scale"""
    fig = go.Figure()
    
    columns_to_plot = []
    for benchmark in benchmarks:
        if benchmark in BENCHMARK_COLUMNS:
            col_name, _ = BENCHMARK_COLUMNS[benchmark]
            if col_name in df.columns:
                columns_to_plot.append(col_name)
    
    plot_df = df.copy()
    if normalize and columns_to_plot:
        plot_df = normalize_series(plot_df, columns_to_plot)
    
    for benchmark in benchmarks:
        if benchmark in BENCHMARK_COLUMNS:
            col_name, color = BENCHMARK_COLUMNS[benchmark]
            if col_name in plot_df.columns:
                fig.add_trace(go.Scatter(
                    x=plot_df['Date'],
                    y=plot_df[col_name],
                    name=BENCHMARK_LABELS.get(benchmark, benchmark),
                    line={'color': color, 'width': 2},
                    hovertemplate='%{y:.2f}<extra></extra>'
                ))
                
                if ma_period and ma_period != "none":
                    window = int(ma_period)
                    ma = calculate_moving_average(plot_df, col_name, window)
                    if ma is not None:
                        fig.add_trace(go.Scatter(
                            x=plot_df['Date'],
                            y=ma,
                            name=f"{BENCHMARK_LABELS.get(benchmark, benchmark)} {window}MA",
                            line={'color': color, 'width': 1, 'dash': 'dot'},
                            hovertemplate='%{y:.2f}<extra></extra>'
                        ))
    
    y_prefix = '' if normalize else '$'
    y_type = 'log' if log_scale else 'linear'
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': title, 'x': 0, 'font': {'size': 16, 'weight': 600}},
        legend={'orientation': 'h', 'y': -0.15},
        xaxis={
            'showgrid': True,
            'gridcolor': 'rgba(0,0,0,0.05)',
        },
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'tickprefix': y_prefix, 'type': y_type},
    )
    
    return fig

def create_dynamic_drawdown_chart(df, benchmarks, show_all=False):
    """Calculate and plot drawdown for selected benchmarks"""
    fig = go.Figure()
    
    colors = [CHART_COLORS['danger'], CHART_COLORS['secondary'], CHART_COLORS['tertiary']]
    fill_colors = ['rgba(250, 82, 82, 0.2)', 'rgba(64, 192, 87, 0.15)', 'rgba(250, 176, 5, 0.15)']
    
    benchmarks_to_show = benchmarks if show_all else [benchmarks[0]] if benchmarks else ["calibre"]
    
    for idx, benchmark in enumerate(benchmarks_to_show):
        col_name = BENCHMARK_COLUMNS.get(benchmark, BENCHMARK_COLUMNS["calibre"])[0]
        
        if col_name not in df.columns:
            continue
        
        prices = df[col_name].values
        peak = prices[0]
        drawdowns = []
        
        for price in prices:
            if price > peak:
                peak = price
            drawdown = (price - peak) / peak * 100
            drawdowns.append(drawdown)
        
        color = colors[idx % len(colors)]
        fill = fill_colors[idx % len(fill_colors)] if idx == 0 else 'rgba(0,0,0,0)'
        
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=drawdowns,
            fill='tozeroy' if idx == 0 else 'none',
            line={'color': color, 'width': 2 if idx == 0 else 1},
            fillcolor=fill,
            name=BENCHMARK_LABELS.get(benchmark, benchmark),
        ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Drawdown Analysis', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'ticksuffix': '%'},
        showlegend=len(benchmarks_to_show) > 1,
        legend={'orientation': 'h', 'y': -0.15},
    )
    return fig

def create_rolling_returns_chart(df, benchmarks, show_all=False, window=252):
    """Create rolling returns chart for selected benchmarks"""
    fig = go.Figure()
    
    if len(df) < window + 1:
        fig.update_layout(
            **CHART_LAYOUT,
            title={'text': f'Rolling 1-Year Returns', 'x': 0, 'font': {'size': 16, 'weight': 600}},
            annotations=[{'text': 'Insufficient data for rolling calculation', 'showarrow': False, 'x': 0.5, 'y': 0.5, 'xref': 'paper', 'yref': 'paper'}]
        )
        return fig
    
    benchmarks_to_show = benchmarks if show_all else [benchmarks[0]] if benchmarks else ["calibre"]
    
    for idx, benchmark in enumerate(benchmarks_to_show):
        col_name, color = BENCHMARK_COLUMNS.get(benchmark, BENCHMARK_COLUMNS["calibre"])
        
        if col_name not in df.columns:
            continue
        
        rolling_returns = (df[col_name] / df[col_name].shift(window) - 1) * 100
        
        fill = 'tozeroy' if idx == 0 else 'none'
        fill_color = 'rgba(34, 139, 230, 0.15)' if idx == 0 else 'rgba(0,0,0,0)'
        
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=rolling_returns,
            fill=fill,
            line={'color': color, 'width': 2 if idx == 0 else 1},
            fillcolor=fill_color,
            name=BENCHMARK_LABELS.get(benchmark, benchmark),
        ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': f'Rolling 1-Year Returns', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        yaxis={'showgrid': True, 'gridcolor': 'rgba(0,0,0,0.05)', 'ticksuffix': '%'},
        showlegend=len(benchmarks_to_show) > 1,
        legend={'orientation': 'h', 'y': -0.15},
    )
    return fig

def calculate_stats(df, col_name="Calibre Index Fund"):
    """Calculate stats for the filtered data"""
    if col_name not in df.columns:
        col_name = "Calibre Index Fund"
    
    high_val = df[col_name].max()
    high_date = df.loc[df[col_name].idxmax(), 'Date']
    
    low_val = df[col_name].min()
    low_date = df.loc[df[col_name].idxmin(), 'Date']
    
    current_val = df[col_name].iloc[-1]
    
    total_return = ((df[col_name].iloc[-1] - df[col_name].iloc[0]) / df[col_name].iloc[0]) * 100
    
    return {
        'high': high_val,
        'high_date': high_date,
        'low': low_val,
        'low_date': low_date,
        'current': current_val,
        'total_return': total_return
    }

@callback(
    [Output("performance-chart", "figure"),
     Output("drawdown-chart", "figure"),
     Output("rolling-returns-chart", "figure"),
     Output("period-high-value", "children"),
     Output("period-high-date", "children"),
     Output("period-low-value", "children"),
     Output("period-low-date", "children"),
     Output("current-price-value", "children"),
     Output("total-return-value", "children"),
     Output("total-return-value", "c"),
     Output("perf-volatility", "children"),
     Output("perf-max-drawdown", "children"),
     Output("perf-sharpe", "children"),
     Output("perf-best-day", "children"),
     Output("perf-worst-day", "children")],
    [Input("benchmark-selector", "value"),
     Input("performance-period", "value"),
     Input("normalize-toggle", "checked"),
     Input("ma-selector", "value"),
     Input("log-scale-toggle", "checked")]
)
def update_performance(benchmarks, period, normalize, ma_period, log_scale):
    df = get_time_series_data()
    
    date_range = calculate_date_range_from_period(period, df)
    filtered_df = filter_data_by_date(df, date_range)
    
    if not benchmarks:
        benchmarks = ["calibre"]
    
    primary_benchmark = benchmarks[0] if benchmarks else "calibre"
    col_name = BENCHMARK_COLUMNS.get(primary_benchmark, BENCHMARK_COLUMNS["calibre"])[0]
    
    perf_chart = create_dynamic_performance_chart(filtered_df, benchmarks, normalize, ma_period, log_scale)
    drawdown_chart = create_dynamic_drawdown_chart(filtered_df, benchmarks, show_all=normalize)
    rolling_chart = create_rolling_returns_chart(filtered_df, benchmarks, show_all=normalize)
    
    stats = calculate_stats(filtered_df, col_name)
    metrics = calculate_performance_metrics(filtered_df, col_name)
    
    high_date_str = stats['high_date'].strftime('%Y-%m-%d') if hasattr(stats['high_date'], 'strftime') else str(stats['high_date'])
    low_date_str = stats['low_date'].strftime('%Y-%m-%d') if hasattr(stats['low_date'], 'strftime') else str(stats['low_date'])
    
    return (
        perf_chart,
        drawdown_chart,
        rolling_chart,
        f"${stats['high']:.2f}",
        high_date_str,
        f"${stats['low']:.2f}",
        low_date_str,
        f"${stats['current']:.2f}",
        f"{stats['total_return']:.1f}%",
        "green" if stats['total_return'] > 0 else "red",
        f"{metrics['volatility']:.1f}%",
        f"{metrics['max_drawdown']:.1f}%",
        f"{metrics['sharpe']:.2f}",
        f"+{metrics['best_day']:.1f}%",
        f"{metrics['worst_day']:.1f}%",
    )

