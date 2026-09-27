"""State snapshot and safe recovery manager for local paper sessions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

UTC = timezone.utc
PERSISTENT_FILE = "persistent_state.json"


def save_persistent_state(
    journal_dir: Path,
    session_id: str,
    broker: Any,
    last_processed: Optional[datetime],
    last_open: Dict[str, datetime],
    last_4h: Dict[str, datetime],
) -> Path:
    """Save an atomic persistent snapshot of account, positions, and trades."""
    journal_dir.mkdir(parents=True, exist_ok=True)
    target = journal_dir / PERSISTENT_FILE
    temp_target = journal_dir / f"{PERSISTENT_FILE}.tmp"

    positions_data = []
    if broker and broker.positions:
        for symbol, pos in sorted(broker.positions.items()):
            positions_data.append({
                "symbol": symbol,
                "direction": pos.direction.value if hasattr(pos.direction, "value") else str(pos.direction),
                "quantity": float(pos.quantity),
                "entry_price": float(pos.entry_price),
                "entry_time_utc": pos.entry_time.isoformat() if hasattr(pos.entry_time, "isoformat") else str(pos.entry_time),
                "leverage": int(pos.leverage),
                "stop_loss_price": float(pos.stop_loss_price),
                "liquidation_price": float(pos.liquidation_price),
                "isolated_margin": float(getattr(pos, "isolated_margin", 0.0)),
            })

    trades_data = []
    if broker and broker.trade_history:
        for trade in broker.trade_history:
            trades_data.append({
                "trade_id": getattr(trade, "trade_id", ""),
                "symbol": trade.symbol,
                "direction": trade.direction.value if hasattr(trade.direction, "value") else str(trade.direction),
                "entry_time_utc": trade.entry_time.isoformat() if hasattr(trade.entry_time, "isoformat") else str(trade.entry_time),
                "exit_time_utc": trade.exit_time.isoformat() if hasattr(trade.exit_time, "isoformat") else str(trade.exit_time),
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "quantity": float(trade.quantity),
                "net_pnl": float(trade.net_pnl),
                "entry_fee": float(getattr(trade, "entry_fee", 0.0)),
                "exit_fee": float(getattr(trade, "exit_fee", 0.0)),
                "funding_cashflow": float(getattr(trade, "funding_cashflow", 0.0)),
                "exit_reason": trade.exit_reason.value if hasattr(trade.exit_reason, "value") else str(trade.exit_reason),
            })

    orders_data = []
    if broker and broker.order_history:
        for order in broker.order_history[-50:]:
            orders_data.append({
                "order_id": getattr(order, "order_id", ""),
                "symbol": order.symbol,
                "direction": order.direction.value if hasattr(order.direction, "value") else str(order.direction),
                "status": order.status.value if hasattr(order.status, "value") else str(order.status),
                "rejection_reasons": list(getattr(order, "rejection_reasons", [])),
            })

    payload = {
        "saved_at_utc": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "account": {
            "initial_balance": float(broker.initial_balance if broker else 10000.0),
            "wallet_balance": float(broker.wallet_balance if broker else 10000.0),
            "equity": float(broker.equity if broker else 10000.0),
            "available_margin": float(broker.available_margin if broker else 10000.0),
            "circuit_breaker": {
                "is_locked": bool(broker.circuit_breaker.is_locked if (broker and broker.circuit_breaker) else False),
                "consecutive_losses": int(broker.circuit_breaker.consecutive_losses if (broker and broker.circuit_breaker) else 0),
            },
        },
        "positions": positions_data,
        "trades": trades_data,
        "orders": orders_data,
        "last_processed_utc": last_processed.isoformat() if last_processed else None,
        "last_open_utc": {k: v.isoformat() for k, v in last_open.items()} if last_open else {},
        "last_4h_utc": {k: v.isoformat() for k, v in last_4h.items()} if last_4h else {},
    }

    with temp_target.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
    temp_target.replace(target)
    return target


def load_persistent_state(journal_dir: Path) -> Optional[Dict[str, Any]]:
    """Load the latest saved persistent state if present and valid."""
    target = journal_dir / PERSISTENT_FILE
    if not target.is_file():
        return None
    try:
        with target.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if isinstance(data, dict) and "account" in data and "wallet_balance" in data["account"]:
            return data
    except Exception:
        pass
    return None


def evaluate_recovery_safety(
    saved_state: Optional[Dict[str, Any]],
    server_ms: int,
    source: Any,
) -> Tuple[bool, Optional[str]]:
    """Determine whether previous state can be safely restored without lookahead or gap ambiguity.

    Returns:
        (is_safe, error_message_if_unsafe)
    """
    if not saved_state:
        return True, None

    open_positions = saved_state.get("positions", [])
    if not open_positions:
        # No active positions to protect. Preserved wallet and trade ledger are completely safe.
        return True, None

    # There were open positions held when the server was shut down.
    # Check if the market moved past stop-loss or liquidation price during downtime.
    saved_time_str = saved_state.get("saved_at_utc")
    for pos in open_positions:
        sym = pos["symbol"]
        sl = pos["stop_loss_price"]
        liq = pos["liquidation_price"]
        side = pos["direction"]

        try:
            # Query recent 15m klines from source
            raw = source.klines(sym, "15m", 12)
            from src.paper.live_session import parse_klines
            bars, _ = parse_klines(raw, "15m", server_ms)
            if not bars:
                return False, f"{sym}: không thể lấy nến đối soát vị thế mở sau khi khởi động lại"

            for bar in bars:
                if side == "LONG":
                    if bar["low"] <= sl or bar["low"] <= liq:
                        return False, (
                            f"{sym}: vị thế mở từ phiên trước ({saved_time_str}) đã chạm stop-loss/thanh lý "
                            f"(Low: {bar['low']}, SL: {sl}) trong thời gian server offline. "
                            f"Cần can thiệp xác nhận trạng thái tài khoản thủ công."
                        )
                else:
                    if bar["high"] >= sl or bar["high"] >= liq:
                        return False, (
                            f"{sym}: vị thế mở từ phiên trước ({saved_time_str}) đã chạm stop-loss/thanh lý "
                            f"(High: {bar['high']}, SL: {sl}) trong thời gian server offline. "
                            f"Cần can thiệp xác nhận trạng thái tài khoản thủ công."
                        )
        except Exception as exc:
            return False, f"Không thể kiểm tra an toàn vị thế mở {sym}: {exc}"

    return True, None
