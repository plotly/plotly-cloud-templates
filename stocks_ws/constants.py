import logging
import os
import ssl

import certifi
from dotenv import load_dotenv

load_dotenv()

FINNHUB_TOKEN = os.getenv("API_KEY")
if not FINNHUB_TOKEN:
    logging.getLogger(__name__).warning(
        "API_KEY is not set: live Finnhub data is unavailable. Set it in .env "
        "locally, or as an app environment variable on Dash Enterprise."
    )
FINNHUB_URL = f"wss://ws.finnhub.io?token={FINNHUB_TOKEN}"
FINNHUB_API_BASE = "https://finnhub.io/api/v1"
FINNHUB_EXCHANGE = "US"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
MARKET_TIMEZONE = "America/New_York"

# Watchlist slots and the tickers offered in each dropdown.
DEFAULT_SYMBOLS = ["BAC", "JPM", "AAPL", "MSFT", "NVDA"]
SYMBOL_OPTIONS = [
    {"label": "BAC · Bank of America", "value": "BAC"},
    {"label": "JPM · JPMorgan Chase", "value": "JPM"},
    {"label": "WFC · Wells Fargo", "value": "WFC"},
    {"label": "C · Citigroup", "value": "C"},
    {"label": "GS · Goldman Sachs", "value": "GS"},
    {"label": "MS · Morgan Stanley", "value": "MS"},
    {"label": "SCHW · Charles Schwab", "value": "SCHW"},
    {"label": "AAPL · Apple", "value": "AAPL"},
    {"label": "MSFT · Microsoft", "value": "MSFT"},
    {"label": "NVDA · NVIDIA", "value": "NVDA"},
    {"label": "AMZN · Amazon", "value": "AMZN"},
    {"label": "GOOGL · Alphabet", "value": "GOOGL"},
    {"label": "META · Meta Platforms", "value": "META"},
    {"label": "TSLA · Tesla", "value": "TSLA"},
    {"label": "XOM · Exxon Mobil", "value": "XOM"},
    {"label": "SPY · S&P 500 ETF", "value": "SPY"},
    {"label": "QQQ · Nasdaq-100 ETF", "value": "QQQ"},
]

MAX_TRADES = 120  # rows kept in the recent trades grid
CHART_POINTS = 390  # one regular session of 1-minute bars
FLUSH_SECONDS = 1.0  # how often buffered live trades are pushed to the browser
STALE_CHECK_SECONDS = 2.0  # how often a stream checks if the watchlist changed
CALLBACK_THREADS = 64  # concurrent viewers the server can stream to
MARKET_CHECK_SECONDS = 60.0  # how often a stream re-checks if the market is open
RECENT_TRADE_KEYS = 5000  # trades remembered for de-duplicating the feed
