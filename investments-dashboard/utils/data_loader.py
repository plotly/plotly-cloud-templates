import pandas as pd
import pathlib

PATH = pathlib.Path(__file__).parent.parent
DATA_PATH = PATH.joinpath("data").resolve()

def load_csv(filename):
    return pd.read_csv(DATA_PATH.joinpath(filename))

# Fund data
df_fund_facts = load_csv("df_fund_facts.csv")
df_price_perf = load_csv("df_price_perf.csv")

# Price data
df_current_prices = load_csv("df_current_prices.csv")
df_hist_prices = load_csv("df_hist_prices.csv")
df_graph = load_csv("df_graph.csv")

# Returns data
df_avg_returns = load_csv("df_avg_returns.csv")
df_after_tax = load_csv("df_after_tax.csv")
df_recent_returns = load_csv("df_recent_returns.csv")

# Portfolio data
df_equity_char = load_csv("df_equity_char.csv")
df_equity_diver = load_csv("df_equity_diver.csv")

# Fees data
df_expenses = load_csv("df_expenses.csv")
df_minimums = load_csv("df_minimums.csv")

# Distribution data
df_dividend = load_csv("df_dividend.csv")
df_realized = load_csv("df_realized.csv")
df_unrealized = load_csv("df_unrealized.csv")

def get_time_series_data():
    """Process df_graph for time series charts"""
    df = df_graph.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    return df

def get_sector_allocation():
    """Process sector diversification data for charts"""
    df = df_equity_diver.copy()
    df.columns = ['Sector', 'Fund', 'Benchmark']
    df = df.iloc[1:]  # Skip header row
    df['Fund'] = df['Fund'].str.replace('%', '').astype(float)
    df['Benchmark'] = df['Benchmark'].apply(lambda x: 0 if x == '—' else float(str(x).replace('%', '')))
    return df

def get_returns_data():
    """Process average returns for comparison charts"""
    df = df_avg_returns.copy()
    df.columns = ['Entity', '1Y', '3Y', '5Y', '10Y', 'Since_Inception']
    df = df.iloc[1:]  # Skip header
    for col in ['1Y', '3Y', '5Y', '10Y']:
        df[col] = df[col].str.replace('%', '').astype(float)
    return df

def get_dividend_history():
    """Process dividend data"""
    df = df_dividend.copy()
    df.columns = ['Type', 'Amount', 'Record_Date', 'Reinvest_Date', 
                  'Payable_Date', 'Reinvest_Price', 'Dist_Yield', 'SEC_Yield']
    df = df.iloc[1:]  # Skip header
    return df

def get_fund_metrics():
    """Extract key fund metrics for KPI cards"""
    facts = dict(zip(df_fund_facts['label'], df_fund_facts['value']))
    
    ts = get_time_series_data()
    latest_price = ts['Calibre Index Fund'].iloc[-1]
    first_price = ts['Calibre Index Fund'].iloc[0]
    ytd_return = ((latest_price - first_price) / first_price) * 100
    
    returns = get_returns_data()
    fund_returns = returns[returns['Entity'].str.contains('500 Index Fund', na=False)].iloc[0]
    
    return {
        'nav': latest_price,
        'ytd_return': ytd_return,
        'expense_ratio': facts.get('Expense ratio as of 04/27/2017', '0.14%'),
        'category': facts.get('Category', 'Large Blend'),
        'asset_class': facts.get('Asset Class', 'Domestic Stock'),
        'min_investment': facts.get('Minimum investment', '$3,000'),
        '1y_return': fund_returns['1Y'],
        '3y_return': fund_returns['3Y'],
        '5y_return': fund_returns['5Y'],
    }

def calculate_risk_metrics(fund_id, period="1Y"):
    """Calculate risk metrics (volatility, beta, sharpe, alpha) for a fund and period"""
    ts = get_time_series_data()
    
    fund_col = 'Calibre Index Fund'
    benchmark_col = '"S&amp;P 500 Index, y"'
    
    period_days = {"1Y": 252, "3Y": 756, "5Y": 1260, "10Y": 2520, "All": len(ts)}
    lookback = min(period_days.get(period, 252), len(ts) - 1)
    
    data = ts[fund_col].iloc[-lookback:]
    benchmark = ts[benchmark_col].iloc[-lookback:]
    
    returns = data.pct_change().dropna()
    bench_returns = benchmark.pct_change().dropna()
    
    volatility = returns.std() * (252 ** 0.5) * 100
    
    covariance = returns.cov(bench_returns)
    bench_variance = bench_returns.var()
    beta = covariance / bench_variance if bench_variance > 0 else 1.0
    
    excess_return = returns.mean() * 252 - 0.02
    sharpe = excess_return / (returns.std() * (252 ** 0.5)) if returns.std() > 0 else 0
    
    alpha = (returns.mean() * 252) - (0.02 + beta * (bench_returns.mean() * 252 - 0.02))
    
    volatility_pct = min(max(volatility / 40 * 100, 10), 100)
    beta_pct = min(max(beta * 50, 10), 100)
    sharpe_pct = min(max((sharpe + 1) / 3 * 100, 10), 100)
    alpha_pct = min(max((alpha * 100 + 5) / 10 * 100, 10), 100)
    
    return {
        'volatility': volatility,
        'volatility_level': "Low" if volatility < 10 else "Medium" if volatility < 20 else "High",
        'volatility_pct': volatility_pct,
        'beta': beta,
        'beta_pct': beta_pct,
        'sharpe': sharpe,
        'sharpe_pct': sharpe_pct,
        'alpha': alpha * 100,
        'alpha_pct': alpha_pct,
    }
