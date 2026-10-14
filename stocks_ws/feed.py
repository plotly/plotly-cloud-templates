"""One shared Finnhub trade feed per server process.

Finnhub allows a single websocket per API key: opening a second connection
silently closes the first. So instead of one connection per browser session,
a background thread holds one connection, subscribes to the union of every
session's symbols, and fans trades out to each session through a queue.

This is shared market data, not user state, so a process-level feed is fine
under the app's "no user state in globals" rule.
"""

import asyncio
import json
import logging
import queue
import threading

import websockets

from constants import FINNHUB_URL, RECENT_TRADE_KEYS, SSL_CONTEXT

log = logging.getLogger("feed")

RECONNECT_MIN_SECONDS = 2.0
RECONNECT_MAX_SECONDS = 30.0


class Subscription:
    """A session's view of the feed: its symbols and a queue of their trades.

    Trades are (symbol, timestamp_ms, price, volume) tuples.
    """

    def __init__(self, symbols: set[str]):
        self.symbols = frozenset(symbols)
        self.trades: queue.Queue = queue.Queue(maxsize=10_000)

    def drain(self) -> list[tuple]:
        items = []
        while True:
            try:
                items.append(self.trades.get_nowait())
            except queue.Empty:
                return items


class MarketFeed:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscriptions: set[Subscription] = set()
        self._changed = threading.Event()
        self._thread: threading.Thread | None = None
        self.connected = False
        self.last_error: str | None = None

    # -- public API (called from callback threads) --------------------------

    def subscribe(self, symbols: set[str]) -> Subscription:
        sub = Subscription(symbols)
        with self._lock:
            self._subscriptions.add(sub)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._run_thread, name="finnhub-feed", daemon=True
                )
                self._thread.start()
        self._changed.set()
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            self._subscriptions.discard(sub)
        self._changed.set()

    # -- background thread --------------------------------------------------

    def _wanted_symbols(self) -> set[str]:
        with self._lock:
            return set().union(*(s.symbols for s in self._subscriptions))

    def _publish(self, trade: tuple) -> None:
        with self._lock:
            targets = [s for s in self._subscriptions if trade[0] in s.symbols]
        for sub in targets:
            try:
                sub.trades.put_nowait(trade)
            except queue.Full:
                pass  # a stalled session shouldn't back up everyone else

    def _run_thread(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        backoff = RECONNECT_MIN_SECONDS
        while True:
            if not self._wanted_symbols():
                # Nobody is watching: hold no connection until someone is.
                self.connected = False
                await asyncio.to_thread(self._changed.wait, 60)
                continue
            try:
                await self._stream()
                backoff = RECONNECT_MIN_SECONDS
            except (websockets.WebSocketException, OSError) as err:
                self.connected = False
                self.last_error = f"{type(err).__name__}: {err}"
                log.warning(
                    "Finnhub feed dropped (%s); retrying in %.0fs", err, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)

    async def _stream(self) -> None:
        async with websockets.connect(FINNHUB_URL, ssl=SSL_CONTEXT) as ws:
            self.connected = True
            self.last_error = None
            subscribed: set[str] = set()
            recent: dict[tuple, None] = {}  # Finnhub repeats some prints
            while True:
                wanted = self._wanted_symbols()
                if not wanted:
                    return  # close the connection while idle
                if self._changed.is_set() or wanted != subscribed:
                    self._changed.clear()
                    for symbol in sorted(wanted - subscribed):
                        await ws.send(
                            json.dumps({"type": "subscribe", "symbol": symbol})
                        )
                    for symbol in sorted(subscribed - wanted):
                        await ws.send(
                            json.dumps({"type": "unsubscribe", "symbol": symbol})
                        )
                    subscribed = wanted
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except TimeoutError:
                    continue
                payload = json.loads(message)
                if payload.get("type") != "trade":
                    continue
                for t in payload.get("data") or []:
                    trade = (t["s"], t["t"], t["p"], t["v"])
                    if trade in recent:
                        continue
                    recent[trade] = None
                    if len(recent) > RECENT_TRADE_KEYS:
                        del recent[next(iter(recent))]
                    self._publish(trade)


feed = MarketFeed()
