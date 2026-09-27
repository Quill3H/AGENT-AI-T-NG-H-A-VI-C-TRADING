"""Strict public USD-M kline stream parsing and reconnecting transport."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from threading import Event, Thread
import time


INTERVAL_MS = {"1m": 60_000, "15m": 900_000, "4h": 14_400_000}
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
STREAM_URL = "wss://fstream.binance.com/stream?streams=" + "/".join(
    f"{symbol.lower()}@kline_{interval}"
    for symbol in SYMBOLS for interval in ("1m", "15m")
)


def _utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def parse_stream_event(raw: dict, received_ms: int) -> dict:
    if not isinstance(raw, dict) or not isinstance(raw.get("data"), dict):
        raise ValueError("invalid stream envelope")
    data = raw["data"]
    bar = data.get("k")
    if data.get("e") != "kline" or not isinstance(bar, dict):
        raise ValueError("invalid kline event")
    symbol, interval = data.get("s"), bar.get("i")
    if symbol not in SYMBOLS or interval not in INTERVAL_MS or bar.get("s") != symbol:
        raise ValueError("unsupported or mismatched kline")
    if raw.get("stream") != f"{symbol.lower()}@kline_{interval}":
        raise ValueError("stream identity mismatch")
    opened, last, emitted = bar.get("t"), bar.get("T"), data.get("E")
    if any(type(value) is not int or value <= 0 for value in (opened, last, emitted, received_ms)):
        raise ValueError("invalid kline timestamp")
    close_ms = opened + INTERVAL_MS[interval]
    if last != close_ms - 1 or opened % INTERVAL_MS[interval] != 0:
        raise ValueError("invalid kline interval")
    closed = bar.get("x")
    if type(closed) is not bool:
        raise ValueError("invalid closed flag")
    if emitted < opened or emitted > received_ms or received_ms - emitted > 30_000:
        raise ValueError("stale or future stream event")
    if closed and emitted < close_ms:
        raise ValueError("closed kline emitted before close")
    if not closed and emitted >= close_ms:
        raise ValueError("unfinished kline emitted after close")
    try:
        if any(type(bar[name]) is bool for name in ("o", "h", "l", "c", "v")):
            raise ValueError("boolean kline numeric field")
        prices = [float(bar[name]) for name in ("o", "h", "l", "c", "v")]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid kline numeric field") from exc
    opening, high, low, closing, volume = prices
    if (not all(math.isfinite(value) for value in prices) or min(prices[:4]) <= 0
            or volume < 0 or high < max(opening, closing) or low > min(opening, closing)):
        raise ValueError("invalid kline OHLC geometry")
    return {
        "symbol": symbol, "interval": interval, "closed": closed,
        "open_time": _utc(opened), "close_time": _utc(close_ms),
        "event_time": _utc(emitted), "available_at": _utc(max(emitted, received_ms)),
        "received_at": _utc(received_ms),
        "open": opening, "high": high, "low": low, "close": closing, "volume": volume,
    }


class PublicKlineStream:
    """Read-only market socket. Session owns all trading decisions and gates."""

    def __init__(self, on_event, on_connection, stop_event: Event):
        self.on_event = on_event
        self.on_connection = on_connection
        self.stop_event = stop_event
        self.socket = None

    def run(self):
        try:
            import websocket
        except ImportError as exc:
            self.on_connection(False, "websocket-client dependency missing")
            raise RuntimeError("install websocket-client from requirements.txt") from exc
        delay = 1
        while not self.stop_event.is_set():
            self.on_connection(False, "connecting to Binance public futures stream")
            watch_stop = Event()
            last_message = time.monotonic()
            disconnect_reason = None

            def opened(_socket):
                nonlocal delay, last_message
                delay = 1
                last_message = time.monotonic()
                self.on_connection(True, None)

            def message(_socket, payload):
                nonlocal last_message
                try:
                    event = parse_stream_event(json.loads(payload), int(time.time() * 1000))
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    self.on_connection(False, f"invalid public stream payload: {exc}")
                    _socket.close()
                    return
                last_message = time.monotonic()
                try:
                    state = self.on_event(event)
                    if state and (state.get("connection", {}).get("reconnect_required") or
                                  state.get("status") in ("QUARANTINED", "RECOVERY_REQUIRED", "STOPPED")):
                        _socket.close()
                        if state.get("status") in ("QUARANTINED", "RECOVERY_REQUIRED", "STOPPED"):
                            self.stop_event.set()
                except Exception as exc:
                    self.on_connection(False, f"paper stream admission failed: {exc}")
                    _socket.close()

            def failed(_socket, error):
                nonlocal disconnect_reason
                if disconnect_reason is None:
                    disconnect_reason = f"public stream disconnected: {error}"
                self.on_connection(False, disconnect_reason)

            self.socket = websocket.WebSocketApp(
                STREAM_URL, on_open=opened, on_message=message,
                on_error=failed, on_close=lambda _ws, _code, _reason: failed(_ws, _reason),
            )
            def watchdog():
                nonlocal disconnect_reason
                while not watch_stop.wait(2) and not self.stop_event.is_set():
                    if time.monotonic() - last_message > 15:
                        disconnect_reason = "public stream has no fresh kline for 15 seconds"
                        self.on_connection(False, disconnect_reason)
                        self.socket.close()
                        return

            watcher = Thread(target=watchdog, name="public-kline-watchdog", daemon=True)
            watcher.start()
            try:
                self.socket.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as exc:
                failed(self.socket, exc)
            finally:
                watch_stop.set()
                watcher.join(timeout=3)
            self.on_connection(False, disconnect_reason or "public stream disconnected")
            if self.stop_event.wait(delay):
                break
            delay = min(delay * 2, 30)

    def close(self):
        if self.socket is not None:
            self.socket.close()
