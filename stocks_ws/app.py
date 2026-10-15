import asyncio
import itertools
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from functools import lru_cache
from zoneinfo import ZoneInfo

import dash_ag_grid as dag
import dash_design_kit as ddk
import plotly.graph_objects as go
import yfinance as yf
from dash import ALL, Dash, Input, Output, Patch, callback, ctx, dcc, html, set_props
from dash.exceptions import PreventUpdate
from dash.mcp import configure_mcp_server, mcp_enabled
from fastapi import Response
from dash_devtools_plus import configure_devtools_plus

from code_panel import code_panel
from constants import (
    CALLBACK_THREADS,
    CHART_POINTS,
    DEFAULT_SYMBOLS,
    FINNHUB_API_BASE,
    FINNHUB_EXCHANGE,
    FINNHUB_TOKEN,
    FLUSH_SECONDS,
    MARKET_TIMEZONE,
    MARKET_CHECK_SECONDS,
    MAX_TRADES,
    SSL_CONTEXT,
    STALE_CHECK_SECONDS,
    SYMBOL_OPTIONS,
)
from feed import feed
from theme import BRAND_VIOLET, GRID_LINE, NEGATIVE, NEUTRAL, POSITIVE, SLOT_COLORS

# Debug-only drawer in Dash Dev Tools; inactive unless app.run(debug=True).
# Must be configured before the Dash instance is created.
configure_devtools_plus(
    accent_color=BRAND_VIOLET,
    editor="vscode",
    project_root=Path(__file__).resolve().parent,
)

app = Dash(
    __name__,
    # Serve an MCP server so AI agents (Claude, Cursor, ChatGPT) can query
    # live market data through the tools defined below.
    enable_mcp=True,
    # Dash 4.4.1's FastAPI backend only sets up the request context for paths
    # under /_dash-, so the default /_mcp path fails with "No active request
    # in context". Serving MCP under /_dash- avoids that.
    mcp_path="_dash-mcp",
    backend="fastapi",
    websocket_callbacks=True,
    title="Ashgrove Capital | Markets Live",
)
server = app.server

# Each open page holds one callback thread for its stream. Python's default
# pool is min(32, CPUs + 4): only 5-6 threads on a small Dash Enterprise
# container, so a handful of viewers would freeze everyone after them.
app.backend.get_callback_executor(max_workers=CALLBACK_THREADS)


# Dash Enterprise's health probe sends HEAD requests to the app root, which
# the FastAPI backend otherwise answers with 405 Method Not Allowed.
@server.head(app.config.requests_pathname_prefix, include_in_schema=False)
def health_probe():
    return Response(status_code=200)


MARKET_TZ = ZoneInfo(MARKET_TIMEZONE)

CHART_MARGIN = {"l": 4, "r": 4, "t": 6, "b": 24}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def make_sparkline(
    color: str,
    times: list[str] | None = None,
    prices: list[float] | None = None,
    previous_close: float | None = None,
) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=times or [],
            y=prices or [],
            mode="lines",
            line={"width": 2, "color": color},
            hovertemplate="%{x|%H:%M} ET<br>$%{y:,.2f}<extra></extra>",
        )
    )
    if previous_close:
        fig.add_hline(
            y=previous_close,
            line={"color": NEUTRAL, "width": 1, "dash": "dot"},
        )
    fig.update_layout(
        autosize=True,
        margin=CHART_MARGIN,
        showlegend=False,
        xaxis={"showgrid": False, "tickformat": "%H:%M", "nticks": 4},
        yaxis={"side": "right", "tickprefix": "$", "gridcolor": GRID_LINE},
    )
    return fig


def make_performance_chart(slots: list[dict] | None = None) -> go.Figure:
    fig = go.Figure()
    for index, color in enumerate(SLOT_COLORS):
        slot = slots[index] if slots else None
        fig.add_trace(
            go.Scatter(
                x=slot["times"] if slot else [],
                y=percent_series(slot) if slot else [],
                mode="lines",
                name=slot["symbol"] if slot else "",
                line={"width": 2, "color": color},
                hovertemplate="%{fullData.name}: %{y:+.2%}<extra></extra>",
            )
        )
    fig.update_layout(
        autosize=True,
        margin={"l": 10, "r": 10, "t": 30, "b": 30},
        hovermode="x unified",
        # Explicit anchors: the DDK template defaults xanchor to "right",
        # which hangs the legend off the left edge and shoves the plot over.
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": 1,
            "yanchor": "bottom",
        },
        xaxis={"showgrid": False, "tickformat": "%H:%M"},
        yaxis={
            "side": "right",
            "tickformat": "+.1%",
            "gridcolor": GRID_LINE,
            "zeroline": True,
            "zerolinecolor": NEUTRAL,
        },
    )
    return fig


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def ticker_card(index: int, symbol: str) -> ddk.Card:
    color = SLOT_COLORS[index]
    return ddk.Card(
        className="ticker-card fill-card",
        # Per-slot accent color, so it is computed rather than in style.css
        style={"--slot-color": color},
        children=[
            dcc.Dropdown(
                id={"type": "stock-select", "index": index},
                options=SYMBOL_OPTIONS,
                value=symbol,
                clearable=False,
                className="ticker-select",
            ),
            html.Div(
                [
                    html.Div(
                        "—",
                        id={"type": "stock-price", "index": index},
                        className="ticker-price",
                    ),
                    html.Div(
                        "",
                        id={"type": "stock-change", "index": index},
                        className="ticker-change flat",
                    ),
                ],
                className="ticker-quote",
            ),
            ddk.Graph(
                id={"type": "stock-chart", "index": index},
                figure=make_sparkline(color),
                config=GRAPH_CONFIG,
                className="fill-graph",
            ),
        ],
    )


trades_grid = dag.AgGrid(
    id="trades-grid",
    className="trades-grid",
    columnDefs=[
        {"field": "Time"},
        {"field": "Symbol"},
        {
            "field": "Price",
            "valueFormatter": {"function": "d3.format('$,.2f')(params.value)"},
            "cellStyle": {
                "styleConditions": [
                    {
                        "condition": "params.data.priceChange == 'up'",
                        "style": {"color": POSITIVE},
                    },
                    {
                        "condition": "params.data.priceChange == 'down'",
                        "style": {"color": NEGATIVE},
                    },
                ],
                "defaultStyle": {"color": "inherit"},
            },
        },
        {
            "field": "Volume",
            "valueFormatter": {"function": "d3.format(',')(params.value)"},
        },
    ],
    rowData=[],
    getRowId="params.data.id",
    columnSize="responsiveSizeToFit",
    defaultColDef={"filter": True, "sortable": True},
    dashGridOptions={
        "theme": {
            "function": (
                "themeQuartz.withParams({"
                "foregroundColor: '#1E1B2E', headerBackgroundColor: '#F5F3FF',"
                "headerTextColor: '#5B21B6', accentColor: '#7C3AED',"
                "borderColor: '#ECEEF5', rowHoverColor: 'rgba(124, 58, 237, 0.06)',"
                "oddRowBackgroundColor: '#FAFAFE', wrapperBorderRadius: 10,"
                "fontFamily: 'Inter', fontSize: 12, spacing: 4,"
                "rowHeight: 26, headerHeight: 30, cellHorizontalPadding: 10})"
            )
        },
        "animateRows": True,
        "pagination": True,
        "paginationPageSize": 10,
        # Fit as many rows per page as the grid's cell has room for, so the
        # dashboard fills one screen without an empty band under the grid.
        "paginationAutoPageSize": True,
        "paginationPageSizeSelector": False,
    },
)


app.layout = ddk.App(
    className="app-shell",
    children=[
        dcc.Store(id="watchlist-store"),
        ddk.Header(
            className="app-header",
            children=[
                html.Div(
                    [
                        html.Div(
                            [html.Span() for _ in range(5)], className="brand-mark"
                        ),
                        html.Div("ASHGROVE CAPITAL", className="brand-name"),
                        html.Div(className="brand-divider"),
                        html.Div("Markets Live · Watchlist", className="brand-product"),
                    ],
                    className="brand",
                ),
                html.Div(
                    [
                        html.Div(
                            "Live trades: Finnhub · Bars: Yahoo Finance · USD · ET",
                            className="data-source-note",
                        ),
                        html.Div(
                            "Connecting…", id="stream-status", className="stream-status"
                        ),
                        code_panel(__file__),
                    ],
                    className="header-meta",
                ),
            ],
        ),
        # Shown by the stream while the market is closed.
        html.Div(
            [
                html.Span(className="market-banner-dot"),
                html.Strong("Markets are closed."),
                html.Span(
                    " Showing the latest session. Live trades resume at the "
                    "next open, 9:30 AM ET."
                ),
            ],
            id="market-banner",
            className="market-banner",
            hidden=True,
        ),
        # The watchlist loads inside the persistent stream callback, which Dash
        # leaves out of loading state, so the stream flips `display` itself.
        dcc.Loading(
            id="dashboard-loading",
            parent_className="dashboard-loading",
            color=BRAND_VIOLET,
            type="circle",
            display="auto",
            overlay_style={"visibility": "visible", "filter": "blur(2px)"},
            children=html.Div(
                [
                    html.Div(
                        [
                            ticker_card(i, symbol)
                            for i, symbol in enumerate(DEFAULT_SYMBOLS)
                        ],
                        className="watchlist-row",
                    ),
                    html.Div(
                        [
                            ddk.Card(
                                className="fill-card",
                                children=[
                                    ddk.CardHeader(
                                        title="Intraday performance · % vs previous close"
                                    ),
                                    ddk.Graph(
                                        id="performance-chart",
                                        figure=make_performance_chart(),
                                        config=GRAPH_CONFIG,
                                        className="fill-graph",
                                    ),
                                ],
                            ),
                            ddk.Card(
                                className="fill-card",
                                children=[
                                    ddk.CardHeader(title="Recent trades"),
                                    trades_grid,
                                ],
                            ),
                        ],
                        className="detail-row",
                    ),
                ],
                className="dashboard",
            ),
        ),
    ],
)


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------


def finnhub_get(path: str, params: dict) -> dict | None:
    query = urllib.parse.urlencode({**params, "token": FINNHUB_TOKEN})
    url = f"{FINNHUB_API_BASE}/{path}?{query}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url), context=SSL_CONTEXT
        ) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None


def is_market_open() -> bool | None:
    """True/False from Finnhub, or None if Finnhub couldn't be reached.

    None usually means a missing or rejected API key, which must not be
    mistaken for a closed market.
    """
    data = finnhub_get("stock/market-status", {"exchange": FINNHUB_EXCHANGE})
    return None if data is None else bool(data.get("isOpen"))


def fetch_previous_close(symbol: str) -> float | None:
    data = finnhub_get("quote", {"symbol": symbol})
    return (data or {}).get("pc") or None


@lru_cache(maxsize=64)
def _fetch_intraday_cached(symbol: str, _minute: int) -> tuple:
    history = yf.Ticker(symbol).history(period="1d", interval="1m")
    if history.empty:
        return (), (), ()
    history = history.tail(CHART_POINTS)
    times = tuple(
        ts.astimezone(MARKET_TZ).strftime("%Y-%m-%d %H:%M") for ts in history.index
    )
    return times, tuple(history["Close"].astype(float)), tuple(history["Volume"])


def fetch_intraday(symbol: str) -> tuple:
    # The minute bucket makes the cache expire every minute, so switching
    # tickers back and forth doesn't refetch the same bars.
    return _fetch_intraday_cached(symbol, int(time.time() // 60))


def load_symbol(symbol: str) -> dict:
    times, prices, volumes = fetch_intraday(symbol)
    previous_close = fetch_previous_close(symbol) or (prices[0] if prices else None)
    return {
        "symbol": symbol,
        "previous_close": previous_close,
        "times": list(times),
        "prices": list(prices),
        "volumes": list(volumes),
    }


async def load_watchlist(symbols: list[str]) -> list[dict]:
    unique = sorted(set(symbols))
    loaded = await asyncio.gather(
        *(asyncio.to_thread(load_symbol, symbol) for symbol in unique)
    )
    by_symbol = dict(zip(unique, loaded))
    # Each slot gets its own copy so duplicate tickers update independently.
    return [
        {
            **by_symbol[symbol],
            "times": list(by_symbol[symbol]["times"]),
            "prices": list(by_symbol[symbol]["prices"]),
        }
        for symbol in symbols
    ]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def percent_series(slot: dict) -> list[float]:
    base = slot["previous_close"]
    if not base:
        return []
    return [price / base - 1 for price in slot["prices"]]


def change_display(slot: dict) -> tuple[str, str]:
    if not slot["prices"] or not slot["previous_close"]:
        return "No data", "ticker-change flat"
    change = slot["prices"][-1] - slot["previous_close"]
    percent = change / slot["previous_close"]
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    arrow = {"up": "▲", "down": "▼", "flat": "■"}[direction]
    return f"{arrow} {change:+,.2f} ({percent:+.2%})", f"ticker-change {direction}"


def price_display(slot: dict) -> str:
    return f"${slot['prices'][-1]:,.2f}" if slot["prices"] else "—"


def render_quote(index: int, slot: dict):
    change_text, change_class = change_display(slot)
    set_props(
        {"type": "stock-price", "index": index}, {"children": price_display(slot)}
    )
    set_props(
        {"type": "stock-change", "index": index},
        {"children": change_text, "className": change_class},
    )


def render_slot(index: int, slot: dict):
    figure = make_sparkline(
        SLOT_COLORS[index], slot["times"], slot["prices"], slot["previous_close"]
    )
    set_props({"type": "stock-chart", "index": index}, {"figure": figure})
    render_quote(index, slot)


def patch_slot(index: int, slot: dict):
    patched = Patch()
    patched["data"][0]["x"] = slot["times"]
    patched["data"][0]["y"] = slot["prices"]
    set_props({"type": "stock-chart", "index": index}, {"figure": patched})
    render_quote(index, slot)


def patch_performance(slots: list[dict], changed: set[int]):
    patched = Patch()
    for index in changed:
        patched["data"][index]["x"] = slots[index]["times"]
        patched["data"][index]["y"] = percent_series(slots[index])
    set_props("performance-chart", {"figure": patched})


def grid_row(
    row_id: str,
    time_label: str,
    symbol: str,
    price: float,
    volume: float,
    previous_price: float | None,
) -> dict:
    if previous_price is None or price == previous_price:
        price_change = "neutral"
    else:
        price_change = "up" if price > previous_price else "down"
    return {
        "id": row_id,
        "Time": time_label,
        "Symbol": symbol,
        "Price": price,
        "Volume": volume,
        "priceChange": price_change,
    }


def history_rows(slots: list[dict]) -> list[dict]:
    """Most recent 1-minute bars across the watchlist, newest first."""
    rows = []
    seen = set()
    for slot in slots:
        if slot["symbol"] in seen:
            continue
        seen.add(slot["symbol"])
        bars = list(zip(slot["times"], slot["prices"], slot["volumes"]))
        for i, (minute, price, volume) in enumerate(bars):
            rows.append(
                grid_row(
                    f"bar-{slot['symbol']}-{minute}",
                    f"{minute[-5:]}:00",
                    slot["symbol"],
                    price,
                    volume,
                    bars[i - 1][1] if i else None,
                )
            )
    rows.sort(key=lambda row: row["Time"], reverse=True)
    return rows[:MAX_TRADES]


def add_price_point(slot: dict, minute: str, price: float):
    """Fold a live trade into the slot's 1-minute series."""
    if slot["times"] and slot["times"][-1] == minute:
        slot["prices"][-1] = price
    else:
        slot["times"].append(minute)
        slot["prices"].append(price)
        if len(slot["times"]) > CHART_POINTS:
            del slot["times"][0]
            del slot["prices"][0]


def apply_trades(
    slots: list[dict],
    rows: list[dict],
    trades: list[tuple],
    last_trade: dict,
    row_ids,
) -> list[dict]:
    changed = set()
    new_rows = []
    for symbol, timestamp_ms, price, volume in trades:
        traded_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=MARKET_TZ)
        minute = traded_at.strftime("%Y-%m-%d %H:%M")
        for index, slot in enumerate(slots):
            if slot["symbol"] == symbol:
                add_price_point(slot, minute, price)
                changed.add(index)
        new_rows.append(
            grid_row(
                f"trade-{next(row_ids)}",
                traded_at.strftime("%H:%M:%S"),
                symbol,
                price,
                volume,
                last_trade.get(symbol),
            )
        )
        last_trade[symbol] = price

    for index in changed:
        patch_slot(index, slots[index])
    patch_performance(slots, changed)

    rows = (new_rows[::-1] + rows)[:MAX_TRADES]
    set_props("trades-grid", {"rowData": rows})
    return rows


# ---------------------------------------------------------------------------
# AI agent tools (Dash MCP)
# ---------------------------------------------------------------------------

# Agents get these purpose-built tools plus a read-only view of the layout.
# The app's own callbacks stay hidden: stream_watchlist is a long-lived
# loop that would never return to an agent.
configure_mcp_server(
    include_callbacks=False,
    include_clientside_callbacks=False,
    include_pages=False,
)

TICKER_PATTERN = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")
MAX_QUOTE_SYMBOLS = 10


def clean_symbols(symbols: list[str]) -> list[str]:
    """Upper-case, de-duplicate and validate tickers before calling Finnhub."""
    cleaned = []
    for raw in symbols:
        symbol = str(raw).strip().upper()
        if not TICKER_PATTERN.match(symbol):
            raise ValueError(f"'{raw}' is not a valid US ticker symbol")
        if symbol not in cleaned:
            cleaned.append(symbol)
    if not cleaned:
        raise ValueError("Provide at least one ticker symbol")
    if len(cleaned) > MAX_QUOTE_SYMBOLS:
        raise ValueError(f"Ask for at most {MAX_QUOTE_SYMBOLS} symbols at a time")
    return cleaned


@lru_cache(maxsize=256)
def _quote_cached(symbol: str, _bucket: int) -> dict | None:
    return finnhub_get("quote", {"symbol": symbol})


def fetch_quote(symbol: str) -> dict | None:
    # 15-second buckets keep repeated agent calls inside Finnhub's free-tier
    # rate limit (60 requests/minute) while staying effectively live.
    return _quote_cached(symbol, int(time.time() // 15))


@mcp_enabled(expose_docstring=True)
def market_status() -> dict:
    """Whether the US stock market is open right now.

    Returns {"is_open": bool | null, "session": str, "as_of_et": str}.
    is_open is null if the market-data provider (Finnhub) can't be reached.
    """
    data = finnhub_get("stock/market-status", {"exchange": FINNHUB_EXCHANGE})
    return {
        "is_open": None if data is None else bool(data.get("isOpen")),
        "session": (data or {}).get("session") or "unknown",
        "as_of_et": datetime.now(MARKET_TZ).strftime("%Y-%m-%d %H:%M:%S"),
    }


@mcp_enabled(expose_docstring=True)
def get_quotes(symbols: list[str]) -> list[dict]:
    """Latest price and today's move for up to 10 US tickers, biggest movers first.

    symbols: tickers such as ["BAC", "JPM", "AAPL"].
    Each row has symbol, price, change (USD), change_pct (percent, e.g. -0.42
    means -0.42%), open, day_high, day_low and previous_close. Prices come
    from Finnhub and may lag the live tape by a few seconds.
    """
    rows = []
    for symbol in clean_symbols(symbols):
        q = fetch_quote(symbol)
        if not q or not q.get("c"):
            rows.append({"symbol": symbol, "error": "no quote available"})
            continue
        rows.append(
            {
                "symbol": symbol,
                "price": q["c"],
                "change": q.get("d"),
                "change_pct": q.get("dp"),
                "open": q.get("o"),
                "day_high": q.get("h"),
                "day_low": q.get("l"),
                "previous_close": q.get("pc"),
            }
        )
    return sorted(rows, key=lambda r: abs(r.get("change_pct") or 0), reverse=True)


@mcp_enabled(expose_docstring=True)
def get_intraday_bars(symbol: str, last_n_minutes: int = 30) -> list[dict]:
    """Today's 1-minute bars for one US ticker (the data behind the sparklines).

    symbol: a ticker such as "BAC". last_n_minutes: how many of the most
    recent bars to return (1-390). Each bar has time_et (HH:MM, US/Eastern),
    close (USD) and volume. When the market is closed this is the latest
    session. Source: Yahoo Finance, refreshed every minute.
    """
    (symbol,) = clean_symbols([symbol])
    n = max(1, min(int(last_n_minutes), CHART_POINTS))
    times, closes, volumes = fetch_intraday(symbol)
    return [
        {"time_et": t[-5:], "close": round(c, 4), "volume": int(v)}
        for t, c, v in list(zip(times, closes, volumes))[-n:]
    ]


@mcp_enabled(expose_docstring=True)
def list_watchlist_symbols() -> list[dict]:
    """The tickers offered in the dashboard's watchlist dropdowns.

    Each item has symbol and name. Other US tickers also work with the quote
    and bar tools; these are the ones the dashboard is set up to show.
    """
    return [
        {"symbol": o["value"], "name": o["label"].split(" · ", 1)[-1]}
        for o in SYMBOL_OPTIONS
    ]


@mcp_enabled(expose_docstring=True)
def get_default_watchlist() -> list[str]:
    """The five tickers the dashboard shows when it first opens."""
    return list(DEFAULT_SYMBOLS)


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


async def flush_props():
    # set_props schedules sends on the event loop; yield once so they go out
    # before anything slow (or the end of the callback) holds them up.
    await asyncio.sleep(0)


async def read_watchlist(ws) -> dict | None:
    """The page's current watchlist ({"symbols", "run_id"}), or None."""
    try:
        return await ws.get_prop("watchlist-store", "data", timeout=5)
    except TimeoutError:
        return None


async def show_watchlist(symbols: list[str]) -> tuple[list[dict], list[dict]]:
    """Load today's bars for the watchlist and draw every card, chart and grid."""
    set_props("stream-status", {"children": "Loading watchlist…"})
    set_props("dashboard-loading", {"display": "show"})
    await flush_props()
    try:
        slots = await load_watchlist(symbols)
        for index, slot in enumerate(slots):
            render_slot(index, slot)
        set_props("performance-chart", {"figure": make_performance_chart(slots)})
        rows = history_rows(slots)
        set_props("trades-grid", {"rowData": rows})
    finally:
        set_props("dashboard-loading", {"display": "auto"})
        await flush_props()
    return slots, rows


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@callback(
    Output("watchlist-store", "data"),
    Input({"type": "stock-select", "index": ALL}, "value"),
)
def sync_watchlist(symbols):
    # A fresh run_id tells the stream below the watchlist has changed.
    return {"symbols": symbols, "run_id": uuid.uuid4().hex}


@callback()
async def stream_watchlist():
    """One long-lived stream per browser session.

    With no Inputs and no Outputs this is a "persistent" websocket callback:
    Dash runs it on page load and restarts it automatically whenever the
    browser's websocket reconnects, so a dropped connection can't leave the
    page frozen. It follows the watchlist through get_prop and takes its
    trades from the shared Finnhub feed (see feed.py).
    """
    ws = ctx.websocket
    if ws is None:
        raise PreventUpdate

    loop = asyncio.get_running_loop()
    run_id = None
    slots, rows = [], []
    last_trade: dict[str, float] = {}
    row_ids = itertools.count()
    sub = None
    market_open = False
    next_watchlist_check = next_market_check = 0.0
    status = None

    def show_status(text: str):
        nonlocal status
        if text != status:
            status = text
            set_props("stream-status", {"children": text})

    try:
        while not ws.is_shutdown:
            now = loop.time()

            if now >= next_watchlist_check:
                watchlist = await read_watchlist(ws)
                # Poll quickly until the page has published its watchlist.
                next_watchlist_check = now + (STALE_CHECK_SECONDS if run_id else 0.5)
                if watchlist and watchlist.get("run_id") != run_id:
                    run_id = watchlist["run_id"]
                    if sub:
                        feed.unsubscribe(sub)
                        sub = None
                    status = None
                    slots, rows = await show_watchlist(watchlist["symbols"])
                    last_trade = {
                        s["symbol"]: s["prices"][-1] for s in slots if s["prices"]
                    }
                    next_market_check = 0.0

            if slots and now >= next_market_check:
                # Re-checked every minute so the page follows the open/close.
                market_open = await asyncio.to_thread(is_market_open)
                next_market_check = now + MARKET_CHECK_SECONDS
                # None means Finnhub was unreachable, not that the market closed.
                set_props("market-banner", {"hidden": market_open is not False})
                if market_open and sub is None:
                    sub = feed.subscribe({s["symbol"] for s in slots})
                elif not market_open and sub is not None:
                    feed.unsubscribe(sub)
                    sub = None

            if sub is not None:
                # Trades are pushed once per FLUSH_SECONDS so a busy tape
                # doesn't flood the browser with one update per print.
                trades = sub.drain()
                if trades:
                    rows = apply_trades(slots, rows, trades, last_trade, row_ids)
                show_status(
                    "Live · streaming trades"
                    if feed.connected
                    else "Connecting to live feed…"
                )
            elif slots and market_open is None:
                show_status("Live data unavailable · check API_KEY")
            elif slots:
                show_status("Market closed · latest session")

            await asyncio.sleep(FLUSH_SECONDS)
    finally:
        if sub is not None:
            feed.unsubscribe(sub)


if __name__ == "__main__":
    app.run(debug=True)
