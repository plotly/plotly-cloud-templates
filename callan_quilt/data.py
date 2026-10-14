"""Market data and the calculations behind the quilt, stats and growth chart."""

import tempfile
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf
from flask_caching import Cache

TICKERS = ["SPY", "IWM", "EFA", "EEM", "AGG", "VNQ", "GLD"]
LABELS = {
    "SPY": "US Large Cap",
    "IWM": "US Small Cap",
    "EFA": "Intl Developed",
    "EEM": "Emerging Markets",
    "AGG": "US Bonds",
    "VNQ": "REITs",
    "GLD": "Gold",
}
PORTFOLIO = "BAL"  # balanced stock/bond blend, computed from SPY and AGG

FIRST_YEAR = 2005  # first full calendar year every ETF above has data for
LAST_FULL_YEAR = date.today().year - 1

cache = Cache(
    config={
        "CACHE_TYPE": "FileSystemCache",
        "CACHE_DIR": f"{tempfile.gettempdir()}/callan-quilt-cache",
        "CACHE_DEFAULT_TIMEOUT": 12 * 60 * 60,
    }
)


class DataUnavailable(Exception):
    """Raised when the price download fails, so the failure is never cached."""


@cache.memoize()
def load_monthly_prices() -> pd.DataFrame:
    """Month-end adjusted closes for every ticker; refreshed twice a day."""
    daily = yf.download(
        TICKERS,
        start=f"{FIRST_YEAR - 1}-12-01",
        auto_adjust=True,
        progress=False,
    )["Close"]
    # yfinance reports failed tickers as empty columns rather than raising;
    # raise here so memoize doesn't cache an empty result for 12 hours.
    missing = [t for t in TICKERS if t not in daily or daily[t].isna().all()]
    if daily.empty or missing:
        raise DataUnavailable(f"No price data from Yahoo Finance for {missing}")
    return daily.resample("ME").last()[TICKERS]


def portfolio_label(equity_pct: int) -> str:
    return f"Balanced {equity_pct}/{100 - equity_pct}"


def label_for(asset: str, equity_pct: int) -> str:
    return portfolio_label(equity_pct) if asset == PORTFOLIO else LABELS[asset]


def monthly_returns(assets: list[str], equity_pct: int) -> pd.DataFrame:
    """Monthly returns for the selected assets, plus the balanced blend.

    The blend is rebalanced monthly back to its stock/bond weights.
    """
    returns = load_monthly_prices().pct_change().iloc[1:]
    weight = equity_pct / 100
    returns[PORTFOLIO] = weight * returns["SPY"] + (1 - weight) * returns["AGG"]
    return returns[[a for a in assets if a in returns.columns]]


def window(
    returns: pd.DataFrame, start_year: int, end_year: int, include_ytd: bool
) -> pd.DataFrame:
    last_year = date.today().year if include_ytd else end_year
    years = returns.index.year
    return returns[(years >= start_year) & (years <= last_year)]


def calendar_returns(monthly: pd.DataFrame) -> pd.DataFrame:
    """Compound monthly returns into calendar-year returns (one row per year)."""
    annual = (1 + monthly).groupby(monthly.index.year).prod() - 1
    # prod() skips gaps, so an asset with no data in a year would read as
    # 0%; mask those years instead.
    counts = monthly.notna().groupby(monthly.index.year).sum()
    return annual.where(counts > 0)


def year_labels(years: pd.Index) -> list[str]:
    this_year = date.today().year
    return [f"{y} YTD" if y == this_year else str(y) for y in years]


def asset_stats(monthly: pd.DataFrame, annual: pd.DataFrame, equity_pct: int):
    """Summary statistics per asset over full calendar years in the window."""
    full_years = annual[annual.index < date.today().year]
    full_months = monthly[monthly.index.year < date.today().year]
    ranks = full_years.rank(axis=1, ascending=False)
    n_assets = full_years.notna().sum(axis=1)

    rows = []
    for asset in annual.columns:
        yearly = full_years[asset].dropna()
        months = full_months[asset].dropna()
        if yearly.empty:
            continue
        # Start the running peak at the initial $1 so a first-month loss counts.
        growth = pd.concat([pd.Series([1.0]), (1 + months).cumprod()])
        drawdown = growth / growth.cummax() - 1
        rows.append(
            {
                "asset": asset,
                "Asset": label_for(asset, equity_pct),
                "Ticker": asset if asset != PORTFOLIO else "—",
                "Return": float((1 + yearly).prod() ** (1 / len(yearly)) - 1),
                "Volatility": float(months.std() * np.sqrt(12)),
                "Max drawdown": float(drawdown.min()),
                "Best year": float(yearly.max()),
                "Worst year": float(yearly.min()),
                "#1 finishes": int((ranks[asset] == 1).sum()),
                "Last place": int((ranks[asset] == n_assets).sum()),
                "Avg rank": float(ranks[asset].mean()),
            }
        )
    return rows


def growth_of_10k(monthly: pd.DataFrame) -> pd.DataFrame:
    """Value of $10,000 invested at the start of the window, month by month."""
    growth = 10_000 * (1 + monthly.fillna(0)).cumprod()
    start = monthly.index[0] - pd.offsets.MonthEnd(1)
    return pd.concat(
        [pd.DataFrame(10_000.0, index=[start], columns=growth.columns), growth]
    )
