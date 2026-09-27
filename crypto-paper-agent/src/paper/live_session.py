"""Prospective, loopback-only paper observation on public futures candles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from threading import RLock
import time
from uuid import uuid4

import pandas as pd
import requests
import yaml

from src.execution.paper_broker import PaperBroker
from src.features import add_all_features
from src.strategies.trend_following import TrendFollowingStrategy
from src.paper.public_stream import INTERVAL_MS, SYMBOLS


UTC = timezone.utc
PUBLIC_BASE = "https://fapi.binance.com"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def parse_klines(raw: list, interval: str, server_ms: int):
    """Validate ordered USD-M klines; keep the unfinished last bar out of decisions."""
    if interval not in INTERVAL_MS or not isinstance(raw, list) or not raw:
        raise ValueError("unsupported interval or empty kline response")
    step = INTERVAL_MS[interval]
    closed, provisional, previous = [], None, None
    for item in raw:
        if not isinstance(item, list) or len(item) < 7:
            raise ValueError("malformed kline row")
        opened, last_ms = item[0], item[6]
        if type(opened) is not int or type(last_ms) is not int or last_ms != opened + step - 1:
            raise ValueError("invalid kline event time")
        if previous is not None and opened <= previous:
            raise ValueError("duplicate or reversed kline sequence")
        if previous is not None and opened != previous + step:
            raise ValueError("kline gap in source sequence")
        previous = opened
        try:
            o, h, l, c, volume = (float(item[i]) for i in range(1, 6))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid kline numeric field") from exc
        if not all(math.isfinite(v) for v in (o, h, l, c, volume)) or min(o, h, l, c) <= 0 or volume < 0:
            raise ValueError("invalid kline numeric field")
        if h < max(o, c) or l > min(o, c) or h < l:
            raise ValueError("invalid kline OHLC geometry")
        bar = {
            "open_time": _utc(opened), "close_time": _utc(opened + step),
            "open": o, "high": h, "low": l, "close": c, "volume": volume,
            "provisional": opened + step > server_ms,
        }
        if bar["provisional"]:
            if provisional is not None or item is not raw[-1]:
                raise ValueError("unfinished kline is not last")
            provisional = bar
        else:
            closed.append(bar)
    return closed, provisional


class BinancePublicSource:
    """Allowlisted, unauthenticated USD-M market-data REST calls only."""

    def __init__(self):
        self.http = requests.Session()

    def _get(self, path: str, params: dict | None = None):
        if path not in ("/fapi/v1/time", "/fapi/v1/klines", "/fapi/v1/fundingRate"):
            raise ValueError("public endpoint not allowed")
        response = self.http.get(PUBLIC_BASE + path, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def server_time_ms(self):
        value = self._get("/fapi/v1/time")["serverTime"]
        if type(value) is not int or value <= 0:
            raise ValueError("invalid exchange server time")
        if abs(int(time.time() * 1000) - value) > 120_000:
            raise ValueError("local and exchange server clock drift exceeds two minutes")
        return value

    def klines(self, symbol: str, interval: str, limit: int):
        if symbol not in SYMBOLS or interval not in INTERVAL_MS or not 1 <= limit <= 500:
            raise ValueError("unsupported public kline request")
        return self._get("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})

    def funding(self, symbol: str, limit: int):
        if symbol not in SYMBOLS or not 1 <= limit <= 10:
            raise ValueError("unsupported public funding request")
        return self._get("/fapi/v1/fundingRate", {"symbol": symbol, "limit": limit})


def _config():
    with (PROJECT_ROOT / "config/default_config.yaml").open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    with (PROJECT_ROOT / "config/strategies/trend_following.yaml").open(encoding="utf-8") as stream:
        strategy = yaml.safe_load(stream)
    config.update(strategy)
    # Conservative, explicitly simulated maintenance-margin assumptions. They
    # are not Binance venue brackets; the UI exposes this fidelity limit.
    for symbol in ("ETHUSDT", "SOLUSDT"):
        config["leverage_brackets"][symbol] = [[5000, 0.02, 0]]
    return config


def _frame(bars):
    return pd.DataFrame(bars).drop(columns=["open_time", "close_time", "provisional"]).set_axis(
        pd.DatetimeIndex([bar["open_time"] for bar in bars], tz="UTC")
    )


class LocalPaperSession:
    def __init__(self, source=None, journal_dir=None):
        self.source = source or BinancePublicSource()
        self.config = _config()
        self.config_hash = sha256(json.dumps(self.config, sort_keys=True, default=str).encode()).hexdigest()
        self.journal_dir = Path(journal_dir or PROJECT_ROOT / "data/paper_sessions")
        self.lock = RLock()
        self.session_id = None
        self.status = "IDLE"
        self.error = None
        self.broker = None
        self.strategies = {}
        self.last_open = {}
        self.last_4h = {}
        self.chart = []
        self.markets = {}
        self.server_ms = None
        self.received_at = None
        self.last_processed = None
        self.stream_connected = False
        self.stream_error = "public stream not connected"
        self.stream_closed = {}
        self.stream_last_event_at = None
        self.recovery_snapshot = None
        self._load_existing_journal()

    def _load_existing_journal(self):
        existing = sorted(self.journal_dir.glob("*.jsonl")) if self.journal_dir.is_dir() else []
        if not existing:
            return
        latest = max(existing, key=lambda path: (path.stat().st_mtime_ns, path.name))
        self.session_id = latest.stem
        self.status = "RECOVERY_REQUIRED"
        self.error = "Prior paper journal exists; exact broker restoration is not available. No new orders admitted."
        try:
            pending_input = False
            for line in latest.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record.get("type") == "PAPER_INPUT":
                    pending_input = True
                if record.get("type") == "PAPER_BATCH" and isinstance(record.get("state"), dict):
                    self.recovery_snapshot = record["state"]
                    pending_input = False
                if record.get("type") == "SESSION_STOP" and isinstance(record.get("state"), dict):
                    self.recovery_snapshot = record["state"]
            if pending_input:
                self.error = "Last paper input has no durable batch result; account state is uncertain. Manual reconciliation required."
        except (OSError, ValueError, TypeError) as exc:
            self.error = f"Prior paper journal cannot be read safely: {exc}"

    def _journal(self, record):
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        path = self.journal_dir / f"{self.session_id}.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, default=str, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def on_connection(self, connected: bool, reason: str | None):
        with self.lock:
            if self.status in ("STOPPED", "RECOVERY_REQUIRED", "QUARANTINED", "IDLE"):
                return self.state()
            self.stream_connected = connected
            self.stream_error = reason if not connected else "awaiting fresh market events after reconnect"
            if not connected:
                self.stream_closed.clear()
                self.status = "WAITING_CONNECTION"
            else:
                self.status = "WAITING_SYNC"
            return self.state()

    def on_stream_event(self, event: dict):
        """Only a three-symbol closed 15m notification may trigger paper processing."""
        with self.lock:
            if not self.stream_connected or self.status not in ("SCANNING", "WAITING_SYNC"):
                return self.state()
            if event["symbol"] not in SYMBOLS or event["interval"] not in ("1m", "15m"):
                self.on_connection(False, "unexpected stream identity")
                return self.state()
            self.stream_last_event_at = event["received_at"].isoformat()
            self.stream_error = None
            if event["interval"] == "1m":
                point = {"time_utc": event["open_time"].isoformat(), "open": event["open"],
                         "high": event["high"], "low": event["low"], "close": event["close"],
                         "provisional": not event["closed"]}
                if event["symbol"] == "BTCUSDT":
                    self.chart = [bar for bar in self.chart if bar["time_utc"] != point["time_utc"]]
                    self.chart = sorted(self.chart + [point], key=lambda bar: bar["time_utc"])[-90:]
                return self.state()
            if not event["closed"]:
                self.markets.setdefault(event["symbol"], {})["forming_15m"] = {
                    "price": event["close"], "open_time_utc": event["open_time"].isoformat(),
                    "event_time_utc": event["event_time"].isoformat(),
                    "received_at_utc": event["received_at"].isoformat(), "source": "Binance USD-M WebSocket"}
                return self.state()
            symbol = event["symbol"]
            if event["open_time"] <= self.last_open[symbol]:
                return self.state()
            self._journal({"type": "STREAM_CLOSED_KLINE", "symbol": symbol,
                           "interval": event["interval"], "event_time_utc": event["event_time"].isoformat(),
                           "received_at_utc": event["received_at"].isoformat(),
                           "available_at_utc": event["available_at"].isoformat(),
                           "bar": {key: event[key] for key in ("open_time", "close_time", "open", "high", "low", "close", "volume")}})
            self.stream_closed[symbol] = event
            if len(self.stream_closed) != len(SYMBOLS):
                self.status = "WAITING_SYNC"
                return self.state()
            times = {bar["open_time"] for bar in self.stream_closed.values()}
            if len(times) != 1:
                self.on_connection(False, "closed stream candles disagree across symbols")
                return self.state()
            self.stream_closed.clear()
            return self.poll()

    def _refresh_chart(self, server_ms):
        bars, provisional = parse_klines(self.source.klines("BTCUSDT", "1m", 90), "1m", server_ms)
        self.chart = [
            {"time_utc": bar["open_time"].isoformat(), "open": bar["open"], "high": bar["high"],
             "low": bar["low"], "close": bar["close"], "provisional": bar["provisional"]}
            for bar in (bars + ([provisional] if provisional else []))
        ]

    def start(self):
        with self.lock:
            if self.status != "IDLE":
                return self.state()
            try:
                return self._start_unlocked()
            except Exception as exc:
                self.status = "QUARANTINED"
                self.error = str(exc)
                raise

    def _start_unlocked(self):
        server_ms = self.source.server_time_ms()
        self.broker = PaperBroker(config=self.config)
        raw_warmup, raw_baseline = {}, {}
        for symbol in SYMBOLS:
            raw_warmup[symbol] = self.source.klines(symbol, "4h", 250)
            bars, _ = parse_klines(raw_warmup[symbol], "4h", server_ms)
            if len(bars) < 200:
                raise ValueError(f"{symbol}: fewer than 200 closed 4h warmup bars")
            self.last_4h[symbol] = bars[-1]["open_time"]
            features = add_all_features(_frame(bars), self.config)
            strategy = TrendFollowingStrategy(self.config, symbol=symbol)
            for i in range(max(1, len(features) - 13), len(features)):
                bar = features.iloc[i].to_dict()
                bar.update(symbol=symbol, open_time=features.index[i].to_pydatetime(),
                           close_time=(features.index[i] + timedelta(hours=4)).to_pydatetime())
                strategy.on_candle_close(bar, features.iloc[:i + 1], self.broker)
            self.strategies[symbol] = strategy
            raw_baseline[symbol] = self.source.klines(symbol, "15m", 4)
            execution, _ = parse_klines(raw_baseline[symbol], "15m", server_ms)
            if not execution or server_ms - int(execution[-1]["close_time"].timestamp() * 1000) > INTERVAL_MS["15m"]:
                raise ValueError(f"{symbol}: stale or missing 15m baseline")
            self.last_open[symbol] = execution[-1]["open_time"]
            self.markets[symbol] = {"last_closed_15m_price": execution[-1]["close"],
                                    "as_of_utc": execution[-1]["close_time"].isoformat()}
        self._refresh_chart(server_ms)
        self.server_ms = server_ms
        self.received_at = datetime.now(UTC).isoformat()
        self.session_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
        self.status = "SCANNING"
        self._journal({"type": "SESSION_START", "session_id": self.session_id,
                       "config_sha256": self.config_hash, "server_time_utc": _utc(server_ms).isoformat(),
                       "baseline_open_utc": {key: value.isoformat() for key, value in self.last_open.items()},
                       "input_sha256": sha256(json.dumps({"warmup": raw_warmup, "baseline": raw_baseline}, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                       "raw_warmup_4h": raw_warmup, "raw_baseline_15m": raw_baseline,
                       "symbols": SYMBOLS, "mode": "PAPER_RESEARCH"})
        return self.state()

    def _funding_metadata(self, symbol, opened, observed_ms=None):
        events = self.source.funding(symbol, 3)
        observed_ms = int(time.time() * 1000) if observed_ms is None else observed_ms
        open_ms = int(opened.timestamp() * 1000)
        exact = [event for event in events if type(event.get("fundingTime")) is int and event["fundingTime"] == open_ms]
        if len(exact) != 1:
            raise ValueError(f"{symbol}: missing or late exact funding source at {opened.isoformat()}")
        try:
            rate = float(exact[0]["fundingRate"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{symbol}: invalid funding rate") from exc
        if not math.isfinite(rate):
            raise ValueError(f"{symbol}: non-finite funding rate")
        if observed_ms > open_ms:
            raise ValueError(f"{symbol}: exact funding event observed after settlement {opened.isoformat()}")
        return {"funding_rate": rate, "funding_time": opened, "funding_readiness": True}

    def _rebaseline_after_gap(self, server_ms):
        if self.broker.positions or self.broker.pending_orders or self.broker.pending_closes:
            raise ValueError("prospective gap with open or pending exposure requires recovery")
        validated, signals, raw_15m, raw_4h = {}, {}, {}, {}
        for symbol in SYMBOLS:
            raw_15m[symbol] = self.source.klines(symbol, "15m", 500)
            bars, _ = parse_klines(raw_15m[symbol], "15m", server_ms)
            opens = [bar["open_time"] for bar in bars]
            if self.last_open[symbol] not in opens or bars[-1]["open_time"] <= self.last_open[symbol]:
                raise ValueError(f"{symbol}: gap exceeds verifiable public kline window")
            if server_ms - int(bars[-1]["close_time"].timestamp() * 1000) > INTERVAL_MS["15m"] + 120_000:
                raise ValueError(f"{symbol}: stale public kline during gap recovery")
            validated[symbol] = bars[-1]
            raw_4h[symbol] = self.source.klines(symbol, "4h", 250)
            signal_bars, _ = parse_klines(raw_4h[symbol], "4h", server_ms)
            if len(signal_bars) < 200:
                raise ValueError(f"{symbol}: insufficient 4h recovery warmup")
            signals[symbol] = signal_bars
        if len({bar["open_time"] for bar in validated.values()}) != 1:
            raise ValueError("gap recovery symbol time mismatch")
        receipt = datetime.now(UTC).isoformat()
        self._journal({"type": "PAPER_GAP_SKIPPED", "received_at_utc": receipt,
                       "source_time_utc": _utc(server_ms).isoformat(),
                       "from_open_utc": {symbol: self.last_open[symbol].isoformat() for symbol in SYMBOLS},
                       "to_open_utc": validated["BTCUSDT"]["open_time"].isoformat(),
                       "raw_15m": raw_15m, "raw_4h": raw_4h,
                       "reason": "no exposure; skipped historical fills and signals"})
        for symbol in SYMBOLS:
            bars = signals[symbol]
            features = add_all_features(_frame(bars), self.config)
            strategy = TrendFollowingStrategy(self.config, symbol=symbol)
            for i in range(max(1, len(features) - 13), len(features)):
                candle = features.iloc[i].to_dict()
                candle.update(symbol=symbol, open_time=features.index[i].to_pydatetime(),
                              close_time=(features.index[i] + timedelta(hours=4)).to_pydatetime())
                strategy.on_candle_close(candle, features.iloc[:i + 1], self.broker)
            self.strategies[symbol] = strategy
            self.last_4h[symbol] = bars[-1]["open_time"]
            self.last_open[symbol] = validated[symbol]["open_time"]
            self.markets[symbol] = {"last_closed_15m_price": validated[symbol]["close"],
                                    "as_of_utc": validated[symbol]["close_time"].isoformat()}
        self.server_ms, self.received_at = server_ms, receipt
        self.status = "WAITING_SYNC"

    def poll(self):
        with self.lock:
            if self.status not in ("SCANNING", "WAITING_SYNC"):
                return self.state()
            try:
                server_ms = self.source.server_time_ms()
                self._refresh_chart(server_ms)
                next_bars = {}
                raw_by_symbol = {}
                for symbol in SYMBOLS:
                    raw = self.source.klines(symbol, "15m", 4)
                    raw_by_symbol[symbol] = raw
                    bars, _ = parse_klines(raw, "15m", server_ms)
                    if not bars or server_ms - int(bars[-1]["close_time"].timestamp() * 1000) > INTERVAL_MS["15m"] + 120_000:
                        raise ValueError(f"{symbol}: stale closed 15m source")
                    fresh = [bar for bar in bars if bar["open_time"] > self.last_open[symbol]]
                    if len(fresh) > 1 or (fresh and fresh[0]["open_time"] != self.last_open[symbol] + timedelta(minutes=15)):
                        self._rebaseline_after_gap(server_ms)
                        return self.state()
                    if fresh:
                        next_bars[symbol] = fresh[0]
                if next_bars and len(next_bars) != len(SYMBOLS):
                    self.status = "WAITING_SYNC"
                    return self.state()
                if not next_bars:
                    self.status = "SCANNING"
                    self.server_ms = server_ms
                    self.received_at = datetime.now(UTC).isoformat()
                    return self.state()
                opened = {bar["open_time"] for bar in next_bars.values()}
                if len(opened) != 1:
                    raise ValueError("symbol candle time mismatch")
                for symbol, bar in next_bars.items():
                    if symbol in self.broker.positions and bar["open_time"].hour in self.broker.funding_hours and bar["open_time"].minute == 0:
                        bar.update(self._funding_metadata(symbol, bar["open_time"]))
                    bar.update(symbol=symbol, timeframe="15m")
                receipt = datetime.now(UTC).isoformat()
                raw_hash = sha256(json.dumps(raw_by_symbol, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                batch_close = next_bars["BTCUSDT"]["close_time"]
                signal_frames = None
                if batch_close.hour % 4 == 0 and batch_close.minute == 0:
                    signal_frames = self._prepare_signal_close(batch_close, server_ms)
                self._journal({"type": "PAPER_INPUT", "received_at_utc": receipt,
                               "source_time_utc": _utc(server_ms).isoformat(),
                               "raw_sha256": raw_hash, "raw_15m": raw_by_symbol,
                               "funding_metadata": {symbol: {key: bar[key] for key in ("funding_rate", "funding_time", "funding_readiness") if key in bar}
                                                    for symbol, bar in next_bars.items()}})
                self.broker.process_batch(list(next_bars.values()))
                for symbol, bar in next_bars.items():
                    self.last_open[symbol] = bar["open_time"]
                    self.markets[symbol] = {"last_closed_15m_price": bar["close"],
                                            "as_of_utc": bar["close_time"].isoformat()}
                self.last_processed = next_bars["BTCUSDT"]["open_time"]
                if signal_frames is not None:
                    self._on_signal_close(batch_close, signal_frames)
                self.broker.verify_accounting_invariants()
                self.status = "SCANNING"
                self.server_ms, self.received_at = server_ms, receipt
                self._journal({"type": "PAPER_BATCH", "received_at_utc": receipt,
                               "source_time_utc": _utc(server_ms).isoformat(), "raw_sha256": raw_hash,
                               "candles": next_bars, "equity_usd": self.broker.equity,
                               "orders": len(self.broker.order_history), "realizations": len(self.broker.trade_history),
                               "state": self._state_unlocked()})
                return self.state()
            except Exception as exc:
                self.status = "QUARANTINED"
                self.error = str(exc)
                if self.session_id:
                    self._journal({"type": "QUARANTINE", "received_at_utc": datetime.now(UTC).isoformat(), "error": self.error})
                return self.state()

    def _prepare_signal_close(self, close_time, server_ms):
        candidates = {}
        for symbol in SYMBOLS:
            bars, _ = parse_klines(self.source.klines(symbol, "4h", 250), "4h", server_ms)
            expected_open = close_time - timedelta(hours=4)
            if bars[-1]["open_time"] != expected_open or expected_open != self.last_4h[symbol] + timedelta(hours=4):
                raise ValueError(f"{symbol}: 4h signal gap or unavailable close")
            candidates[symbol] = add_all_features(_frame(bars), self.config)
        return candidates

    def _on_signal_close(self, close_time, candidates):
        expected_open = close_time - timedelta(hours=4)
        for symbol, features in candidates.items():
            candle = features.iloc[-1].to_dict()
            candle.update(symbol=symbol, open_time=features.index[-1].to_pydatetime(), close_time=close_time)
            strategy = self.strategies[symbol]
            strategy.update_trailing_stop(candle, self.broker)
            request = strategy.on_candle_close(candle, features, self.broker)
            if request is not None:
                self.broker.submit_order(request)
            self.last_4h[symbol] = expected_open

    def stop(self):
        with self.lock:
            if self.status in ("SCANNING", "WAITING_SYNC", "WAITING_CONNECTION", "QUARANTINED"):
                self.status = "STOPPED"
                if self.broker and self.broker.current_time:
                    self.broker.finalize(timestamp=self.broker.current_time, force_close=False)
                if self.session_id:
                    self._journal({"type": "SESSION_STOP", "received_at_utc": datetime.now(UTC).isoformat(),
                                   "open_positions_retained": len(self.broker.positions) if self.broker else 0,
                                   "state": self._state_unlocked()})
            return self.state()

    def state(self):
        with self.lock:
            return self._state_unlocked()

    def _state_unlocked(self):
        broker = self.broker
        if self.status == "RECOVERY_REQUIRED" and self.recovery_snapshot is not None:
            saved = dict(self.recovery_snapshot)
            saved.update(status=self.status, error=self.error, connection={
                "connected": False, "error": "restart requires exact broker recovery",
                "last_event_received_at_utc": None})
            saved["risk_gate"] = {"admission_open": False, "reason": self.error, "halted": True}
            return saved
        trades = [] if broker is None else [
            {"id": trade.trade_id, "symbol": trade.symbol, "side": trade.direction.value,
             "entry_time_utc": trade.entry_time.isoformat(), "exit_time_utc": trade.exit_time.isoformat(),
             "entry_price": trade.entry_price, "exit_price": trade.exit_price,
             "net_pnl_usd": trade.net_pnl, "fee_usd": trade.entry_fee + trade.exit_fee,
             "funding_usd": trade.funding_cashflow, "exit_reason": trade.exit_reason.value}
            for trade in broker.trade_history
        ]
        return {
            "mode": "PAPER_RESEARCH", "status": self.status, "error": self.error,
            "session_id": self.session_id, "symbols": list(SYMBOLS),
            "venue": "Binance USD-M perpetual public data", "strategy": "Trend Following 4h/15m fixed rules",
            "source_time_utc": _utc(self.server_ms).isoformat() if self.server_ms else None,
            "received_at_utc": self.received_at,
            "connection": {"connected": self.stream_connected, "error": self.stream_error,
                           "last_event_received_at_utc": self.stream_last_event_at,
                           "source": "Binance USD-M public kline WebSocket"},
            "last_processed_open_utc": self.last_processed.isoformat() if self.last_processed else None,
            "config_sha256": self.config_hash,
            "chart": self.chart,
            "markets": self.markets,
            "account": {"initial_equity_usd": broker.initial_balance if broker else 10000.0,
                        "wallet_usd": broker.wallet_balance if broker else 10000.0,
                        "equity_usd": broker.equity if broker else 10000.0,
                        "available_margin_usd": broker.available_margin if broker else 10000.0,
                        "reserved_collateral_usd": broker.reserved_collateral if broker else 0.0,
                        "unrealized_pnl_usd": broker.unrealized_pnl if broker else 0.0,
                        "breaker_locked": broker.circuit_breaker.is_locked if broker else False},
            "open_positions": [] if broker is None else [
                {"symbol": symbol, "side": pos.direction.value, "quantity": pos.quantity,
                 "entry_price": pos.entry_price, "stop_loss_price": pos.stop_loss_price,
                 "liquidation_price": pos.liquidation_price, "leverage": pos.leverage,
                 "opened_at_utc": pos.opened_at.isoformat(),
                 "isolated_collateral_usd": pos.isolated_collateral,
                 "entry_fee_usd": pos.entry_fee, "cumulative_funding_usd": pos.cumulative_funding}
                for symbol, pos in sorted(broker.positions.items())],
            "completed_trades": len(trades), "trades": trades,
            "orders": [] if broker is None else [
                {"id": order.order_id, "symbol": order.symbol, "side": order.direction.value,
                 "status": order.status.value, "rejection_reasons": order.rejection_reasons,
                 "requested_at_utc": order.requested_at.isoformat(),
                 "processed_at_utc": order.processed_at.isoformat() if order.processed_at else None,
                 "fill_price": order.actual_fill_price, "quantity": order.filled_quantity,
                 "fee_usd": order.fee_usd, "slippage_usd": order.slippage_usd}
                for order in broker.order_history[-30:]],
            "pending_orders": [] if broker is None else [
                {"symbol": order.symbol, "side": order.direction.value,
                 "signal_time_utc": order.signal_time.isoformat(),
                 "signal_price": order.signal_price, "stop_loss_price": order.stop_loss_price,
                 "leverage": order.leverage}
                for order in broker.pending_orders],
            "funding_events": [] if broker is None else [
                {"id": event.event_id, "symbol": event.symbol,
                 "timestamp_utc": event.timestamp.isoformat(),
                 "rate": event.funding_rate, "cashflow_usd": event.cashflow_usd}
                for event in broker.funding_history],
            "risk_gate": {"admission_open": self.status == "SCANNING" and self.stream_connected
                          and bool(broker) and not broker.is_halted and not broker.circuit_breaker.is_locked,
                          "reason": self.error or (
                              "broker halted or circuit breaker locked" if broker and
                              (broker.is_halted or broker.circuit_breaker.is_locked) else self.stream_error),
                          "halted": broker.is_halted if broker else False},
            "risk_note": "ETH/SOL use conservative simulated maintenance brackets, not venue-verified Binance brackets.",
        }
