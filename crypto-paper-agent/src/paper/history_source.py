"""Bounded read-only Futures pagination with exact half-open coverage."""
from datetime import datetime, timedelta, timezone
from threading import RLock
import time

import requests

from src.paper.live_session import BinancePublicSource, parse_klines
from src.paper.public_stream import SYMBOLS, INTERVAL_MS


class PaperInterrupted(RuntimeError):
    """Cooperative stop at a committed account boundary, not corrupt evidence."""


def check_interruption(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise PaperInterrupted('paper service shutdown requested')


class BinanceHistorySource(BinancePublicSource):
    def __init__(self):
        super().__init__()
        self._http_lock = RLock()

    def _get(self, path, params=None):
        # Chart and account workers share the adapter, not concurrent Session mutations.
        with self._http_lock:
            return super()._get(path, params)

    def klines_range(self, symbol, interval, start_ms, end_ms, limit=500):
        if (symbol not in SYMBOLS or interval not in INTERVAL_MS or type(limit) is not int
                or not 1 <= limit <= 500 or type(start_ms) is not int
                or type(end_ms) is not int or start_ms < 0 or end_ms < start_ms):
            raise ValueError('invalid public Futures historical request')
        return self._get('/fapi/v1/klines', {'symbol': symbol, 'interval': interval,
                        'startTime': start_ms, 'endTime': end_ms, 'limit': limit})


def fetch_closed_range(source, symbol, interval, start, end, server_ms, cancel_event=None):
    step_ms = INTERVAL_MS[interval]
    if (start.tzinfo is None or end.tzinfo is None or start.utcoffset().total_seconds()
            or end.utcoffset().total_seconds() or start > end
            or int(start.timestamp() * 1000) % step_ms or int(end.timestamp() * 1000) % step_ms
            or int(end.timestamp() * 1000) > server_ms):
        raise ValueError('invalid closed history range/availability')
    result, cursor = [], start
    while cursor < end:
        check_interruption(cancel_event)
        page_end = min(cursor + timedelta(milliseconds=step_ms * 500), end)
        raw = None
        for attempt in range(3):
            check_interruption(cancel_event)
            try:
                if hasattr(source, 'klines_range'):
                    raw = source.klines_range(symbol, interval, int(cursor.timestamp() * 1000),
                                               int(page_end.timestamp() * 1000) - 1, 500)
                else:
                    # Legacy/test adapters may provide only a latest window.
                    # It is accepted only when it actually covers this entire page.
                    raw = source.klines(symbol, interval, 500)
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(0.1 * (2 ** attempt))
        check_interruption(cancel_event)
        closed, _ = parse_klines(raw, interval, server_ms)
        page = [b for b in closed if cursor <= b['open_time'] < page_end]
        receipt = datetime.now(timezone.utc).isoformat()
        for bar in page:
            bar['received_at_utc'] = receipt
        expected = int((page_end - cursor).total_seconds() * 1000) // step_ms
        if (len(page) != expected or not page or page[0]['open_time'] != cursor
                or page[-1]['close_time'] != page_end):
            raise ValueError(f'{symbol}: missing full {interval} historical page from {cursor.isoformat()}')
        result.extend(page)
        cursor = page_end
    return result
