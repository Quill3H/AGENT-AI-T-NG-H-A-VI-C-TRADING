"""Versioned, data-only checkpoint for the local paper machine."""

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import math

import numpy as np

from src.execution.order_models import (
    AccountSnapshot, ExitReason, FundingEvent, OrderDirection,
    OrderExecutionRecord, OrderRequest, OrderSide, OrderStatus, OrderType,
    Position, PositionStatus, TradeRecord,
)
from src.execution.paper_broker import PaperBroker
from src.risk.circuit_breakers import CircuitBreakerState
from src.strategies.trend_following import SetupContext, SetupState, TrendFollowingStrategy


CLASSES = {cls.__name__: cls for cls in (
    AccountSnapshot, FundingEvent, OrderExecutionRecord, OrderRequest,
    Position, TradeRecord, SetupContext,
)}
ENUMS = {cls.__name__: cls for cls in (
    ExitReason, OrderDirection, OrderSide, OrderStatus, OrderType,
    PositionStatus, SetupState,
)}
BROKER_STATIC = {"initial_balance", "slippage_pct", "taker_fee_pct", "maker_fee_pct", "funding_hours"}


def pack(value):
    """Encode only explicitly supported data types; no executable pickle payloads."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, Enum):
        return {"kind": "enum", "class": type(value).__name__, "value": value.value}
    if isinstance(value, CircuitBreakerState):
        return {"kind": "breaker", "value": pack(vars(value))}
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive checkpoint time")
        return {"kind": "time", "value": value.astimezone(timezone.utc).isoformat()}
    if is_dataclass(value) and not isinstance(value, type):
        if type(value).__name__ not in CLASSES or CLASSES[type(value).__name__] is not type(value):
            raise TypeError("unsupported checkpoint record")
        data = {field.name: pack(getattr(value, field.name)) for field in fields(value)}
        if isinstance(value, Position):
            data["_last_unrealized_pnl"] = pack(getattr(value, "_last_unrealized_pnl", 0.0))
        return {"kind": "record", "class": type(value).__name__, "value": data}
    if isinstance(value, dict):
        if not all(type(key) is str for key in value):
            raise TypeError("checkpoint map keys must be strings")
        return {"kind": "map", "value": {key: pack(item) for key, item in value.items()}}
    if isinstance(value, (list, tuple, set)):
        items = [pack(item) for item in value]
        if isinstance(value, set):
            items.sort(key=str)
        return {"kind": "set" if isinstance(value, set) else "tuple" if isinstance(value, tuple) else "list",
                "value": items}
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise TypeError(f"unsupported or non-finite checkpoint value: {type(value).__name__}")


def unpack(value):
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite checkpoint value")
        return value
    if not isinstance(value, dict) or type(value.get("kind")) is not str:
        raise ValueError("invalid checkpoint node")
    kind = value["kind"]
    if kind == "time" and set(value) == {"kind", "value"}:
        result = datetime.fromisoformat(value["value"])
        if result.tzinfo is None or result.utcoffset() != timezone.utc.utcoffset(result):
            raise ValueError("checkpoint time is not UTC")
        return result
    if kind == "enum" and set(value) == {"kind", "class", "value"}:
        return ENUMS[value["class"]](value["value"])
    if kind == "breaker" and set(value) == {"kind", "value"}:
        return {"__circuit_breaker__": unpack(value["value"])}
    if kind == "map" and set(value) == {"kind", "value"} and isinstance(value["value"], dict):
        if not all(type(key) is str for key in value["value"]):
            raise ValueError("invalid checkpoint map key")
        return {key: unpack(item) for key, item in value["value"].items()}
    if kind in ("list", "tuple", "set") and set(value) == {"kind", "value"} and isinstance(value["value"], list):
        items = [unpack(item) for item in value["value"]]
        return items if kind == "list" else tuple(items) if kind == "tuple" else set(items)
    if kind == "record" and set(value) == {"kind", "class", "value"}:
        cls = CLASSES[value["class"]]
        raw = value["value"]
        names = {field.name for field in fields(cls)}
        extras = {"_last_unrealized_pnl"} if cls is Position else set()
        if not isinstance(raw, dict) or set(raw) != names | extras:
            raise ValueError("checkpoint record fields do not match")
        record = cls(**{key: unpack(raw[key]) for key in names})
        if cls is Position:
            record._last_unrealized_pnl = unpack(raw["_last_unrealized_pnl"])
        return record
    raise ValueError("unsupported checkpoint node")


def capture_session(session):
    broker = session.broker
    if broker is None:
        raise ValueError("no paper broker to checkpoint")
    broker_values = {key: value for key, value in vars(broker).items()
                     if key not in ("config", "news_filter")}
    return {
        "version": 2,
        "config_sha256": session.config_hash,
        "status": session.status,
        "broker": pack(broker_values),
        "news_source_sha256": broker.news_filter.source_sha256,
        "strategies": pack({symbol: ({"setup": strategy.setup,
                                       "setup_count": strategy.setup_count,
                                       "candidate_count": strategy.candidate_count}
                                      if isinstance(strategy, TrendFollowingStrategy)
                                      else {"unsupported": type(strategy).__name__})
                            for symbol, strategy in session.strategies.items()}),
        "last_open": pack(session.last_open),
        "last_4h": pack(session.last_4h),
        "last_processed": pack(session.last_processed),
        "server_ms": session.server_ms,
        "received_at": session.received_at,
        "markets": pack(session.markets),
        "chart": pack(session.chart),
        "charts": pack(session.charts),
        "strategy_decisions": pack(session.strategy_decisions),
    }


def restore_session(session, payload, saved_view):
    required = {
        "version", "config_sha256", "status", "broker", "news_source_sha256",
        "strategies", "last_open", "last_4h", "last_processed", "server_ms",
        "received_at", "markets", "chart",
    }
    allowed_keys = (required, required | {"charts"}, required | {"strategy_decisions"},
                    required | {"charts", "strategy_decisions"})
    if (not isinstance(payload, dict) or set(payload) not in allowed_keys
            or payload["version"] != 2 or payload["config_sha256"] != session.config_hash):
        raise ValueError("checkpoint version or configuration mismatch")
    if payload["status"] not in ("SCANNING", "WAITING_SYNC", "WAITING_CONNECTION", "STOPPED"):
        raise ValueError("saved session was not resumable")
    broker = PaperBroker(config=session.config)
    decoded = unpack(payload["broker"])
    expected = set(vars(broker)) - {"config", "news_filter"}
    if type(decoded) is not dict or set(decoded) != expected:
        raise ValueError("incomplete broker checkpoint")
    for name in BROKER_STATIC:
        if decoded[name] != getattr(broker, name):
            raise ValueError(f"broker configuration mismatch: {name}")
    if broker.news_filter.source_sha256 != payload["news_source_sha256"]:
        raise ValueError("news calendar source changed")
    breaker = decoded.pop("circuit_breaker", None)
    if type(breaker) is not dict or set(breaker) != {"__circuit_breaker__"}:
        raise ValueError("missing circuit breaker checkpoint")
    restored_breaker = CircuitBreakerState.from_config(session.config)
    breaker_state = breaker["__circuit_breaker__"]
    if type(breaker_state) is not dict or set(breaker_state) != set(vars(restored_breaker)):
        raise ValueError("invalid circuit breaker checkpoint")
    restored_breaker.__dict__.update(breaker_state)
    broker.circuit_breaker = restored_breaker
    expected.remove("circuit_breaker")
    if set(decoded) != expected:
        raise ValueError("incomplete broker checkpoint")
    for name, value in decoded.items():
        setattr(broker, name, value)
    if (type(broker.positions) is not dict or
            any(symbol not in session_symbols() or type(pos) is not Position or pos.symbol != symbol
                for symbol, pos in broker.positions.items()) or
            type(broker.pending_orders) is not list or
            any(type(order) is not OrderRequest for order in broker.pending_orders) or
            any(type(record) is not OrderExecutionRecord for record in broker.order_history) or
            any(type(record) is not TradeRecord for record in broker.trade_history) or
            any(type(record) is not FundingEvent for record in broker.funding_history) or
            any(type(record) is not AccountSnapshot for record in broker.account_snapshots) or
            broker._is_handling_cb_lock or broker._defer_cb_lock_for_batch):
        raise ValueError("invalid broker ledger or transient state")
    broker.verify_accounting_invariants()
    session.broker = broker
    strategies = unpack(payload["strategies"])
    if set(strategies) != set(session_symbols()):
        raise ValueError("incomplete strategy checkpoint")
    session.strategies = {}
    for symbol, data in strategies.items():
        if set(data) != {"setup", "setup_count", "candidate_count"} or type(data["setup"]) is not SetupContext:
            raise ValueError("invalid strategy checkpoint")
        strategy = TrendFollowingStrategy(session.config, symbol=symbol)
        strategy.setup = data["setup"]
        strategy.setup_count = data["setup_count"]
        strategy.candidate_count = data["candidate_count"]
        session.strategies[symbol] = strategy
    session.last_open = unpack(payload["last_open"])
    session.last_4h = unpack(payload["last_4h"])
    session.last_processed = unpack(payload["last_processed"])
    if (set(session.last_open) != set(session_symbols()) or
            set(session.last_4h) != set(session_symbols()) or
            any(type(value) is not datetime for value in (*session.last_open.values(), *session.last_4h.values()))):
        raise ValueError("missing processing watermark")
    session.server_ms = payload["server_ms"]
    session.received_at = payload["received_at"]
    session.markets = unpack(payload["markets"])
    session.chart = unpack(payload["chart"])
    session.charts = unpack(payload["charts"]) if "charts" in payload else {
        symbol: (session.chart if symbol == "BTCUSDT" else []) for symbol in session_symbols()
    }
    if (type(session.charts) is not dict or set(session.charts) != set(session_symbols())
            or any(type(chart) is not list for chart in session.charts.values())
            or session.chart != session.charts["BTCUSDT"]):
        raise ValueError("invalid chart checkpoint")
    session.strategy_decisions = unpack(payload["strategy_decisions"]) if "strategy_decisions" in payload else {
        symbol: {"state": "SCANNING", "symbol": symbol, "time_utc": None,
                 "order_id": None, "trade_id": None, "reason": None}
        for symbol in session_symbols()
    }
    if (type(session.strategy_decisions) is not dict or
            set(session.strategy_decisions) != set(session_symbols()) or
            any(type(item) is not dict or item.get("symbol") != symbol
                for symbol, item in session.strategy_decisions.items())):
        raise ValueError("invalid strategy decision checkpoint")
    session.status = payload["status"]
    rendered = session._state_unlocked()
    for key in ("account", "open_positions", "pending_orders", "orders", "trades",
                "funding_events", "last_processed_open_utc", "completed_trades"):
        if rendered[key] != saved_view[key]:
            raise ValueError(f"restored broker does not match saved {key}")
    if "strategy_decisions" in saved_view and rendered["strategy_decisions"] != saved_view["strategy_decisions"]:
        raise ValueError("restored strategy decisions do not match saved view")


def session_symbols():
    from src.paper.public_stream import SYMBOLS
    return SYMBOLS
