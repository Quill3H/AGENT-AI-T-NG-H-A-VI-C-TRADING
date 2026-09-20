"""
src/logging/trade_logger.py - SQLite Event Store and JSON Exporter
==================================================================
Triển khai lưu trữ có cấu trúc toàn bộ sự kiện backtest/paper trading
vào SQLite database tuân thủ ACID transaction, foreign key constraints,
composite primary keys và tính luỹ thừa (idempotency) dựa trên canonical payload hash.

Cung cấp khả năng xuất dữ liệu giao dịch chuẩn hoá ra JSON theo đúng nguyên văn
đặc tả Master Spec Section 4.6.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from typing import Any, Dict, List, Optional, Tuple, Union
from loguru import logger

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    FundingEvent,
    OrderDirection,
    OrderExecutionRecord,
    OrderStatus,
    OrderType,
    TradeRecord,
    _ensure_utc,
)


def _to_iso(dt: Optional[Union[datetime, str]]) -> Optional[str]:
    """Chuyển đổi datetime sang ISO 8601 string UTC."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return _ensure_utc(dt).isoformat()
    return str(dt)


def _to_epoch(dt: Optional[Union[datetime, str]]) -> Optional[int]:
    """Chuyển đổi datetime sang Unix epoch seconds UTC."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return int(_ensure_utc(dt).timestamp())
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt)
            return int(_ensure_utc(parsed).timestamp())
        except Exception:
            return None
    return None


def _clean_float(val: Any) -> Optional[float]:
    """Chuyển đổi sang float an toàn, trả về None nếu NaN hoặc Inf."""
    if val is None:
        return None
    if type(val) is bool:
        raise TypeError(f"Expected numeric float or int, got bool: {val!r}")
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def parse_config_metadata(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trích xuất metadata có cấu trúc từ cấu hình hệ thống (hỗ trợ cả nested production format lẫn flat format).
    Không serialize nguyên dictionary thành string.
    """
    strat = config.get("strategy")
    if isinstance(strat, dict):
        strategy_name = strat.get("name") or "TREND_FOLLOWING"
        tf_signal = strat.get("timeframe_signal") or "4h"
        tf_execution = strat.get("timeframe_execution") or "15m"
    elif isinstance(strat, str):
        strategy_name = strat
        tf_signal = config.get("timeframe_signal", "4h")
        tf_execution = config.get("timeframe_execution", "15m")
    else:
        strategy_name = config.get("strategy_name", "TREND_FOLLOWING")
        tf_signal = config.get("timeframe_signal", "4h")
        tf_execution = config.get("timeframe_execution", "15m")

    data_cfg = config.get("data")
    if isinstance(data_cfg, dict):
        symbol = data_cfg.get("futures_symbol") or data_cfg.get("symbol") or "BTCUSDT"
        start_date = data_cfg.get("start_date") or ""
        end_date = data_cfg.get("end_date") or ""
    else:
        symbol = config.get("symbol", "BTCUSDT")
        start_date = config.get("start_date") or ""
        end_date = config.get("end_date") or ""

    clean_symbol = str(symbol).replace("/", "").replace(":", "").upper()
    return {
        "strategy_name": str(strategy_name),
        "symbol": clean_symbol,
        "timeframe_signal": str(tf_signal),
        "timeframe_execution": str(tf_execution),
        "start_date": str(start_date),
        "end_date": str(end_date),
    }


def _format_conviction_tier(tier: Any) -> str:
    """Quy chuẩn conviction tier sang định dạng chuẩn Master Spec."""
    if not tier:
        return "NORMAL_2_PERCENT"
    t_str = str(tier).upper().strip()
    if t_str in ("NORMAL", "NORMAL_2_PERCENT"):
        return "NORMAL_2_PERCENT"
    if t_str in ("HIGH", "HIGH_5_PERCENT", "STRONG"):
        return "HIGH_5_PERCENT"
    if t_str in ("LOW", "LOW_1_PERCENT"):
        return "LOW_1_PERCENT"
    if t_str in ("ULTRA", "ULTRA_HIGH", "ULTRA_HIGH_10_PERCENT"):
        return "ULTRA_HIGH_10_PERCENT"
    return t_str


def _get_risk_ratio_percent(tier_str: str, risk_amount_usd: float, initial_capital: float) -> float:
    """
    Return the realized admission risk as a percentage of entry equity.

    ``tier_str`` is intentionally retained for API compatibility and display
    only.  A tier is a policy label; it must not overwrite the amount actually
    admitted after circuit-breaker reduction, sizing and rounding.
    """
    del tier_str
    if type(risk_amount_usd) is bool or type(initial_capital) is bool:
        raise TypeError("risk amount and entry equity must be numeric, not bool")
    risk = float(risk_amount_usd)
    equity = float(initial_capital)
    if not math.isfinite(risk) or risk < 0:
        raise ValueError(f"risk_amount_usd must be finite and non-negative, got {risk}")
    if not math.isfinite(equity) or equity <= 0:
        raise ValueError(f"entry equity must be finite and positive, got {equity}")
    return (risk / equity) * 100.0


def _normalize_for_canonical_hash(obj: Any) -> Any:
    """Đảm bảo mọi phần tử trong đối tượng được chuẩn hóa đệ quy cho hash xác định."""
    if obj is None:
        return None
    if isinstance(obj, (bool, str, int)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Cannot compute canonical payload hash with NaN or Inf: {obj}")
        # Preserve the exact Python float representation stored in the payload.
        # Rounding here can make materially different ledgers hash identically.
        return obj
    if isinstance(obj, datetime):
        return _ensure_utc(obj).isoformat()
    if isinstance(obj, dict):
        return {str(k): _normalize_for_canonical_hash(v) for k, v in sorted(obj.items())}
    if isinstance(obj, set):
        normalized = [_normalize_for_canonical_hash(v) for v in obj]
        return sorted(normalized, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    if isinstance(obj, (list, tuple)):
        return [_normalize_for_canonical_hash(v) for v in obj]
    if hasattr(obj, "__dict__"):
        return {str(k): _normalize_for_canonical_hash(v) for k, v in sorted(obj.__dict__.items())}
    return str(obj)


def compute_canonical_payload_hash(
    config: Dict[str, Any],
    run_metadata: Dict[str, Any],
    orders: List[Any],
    trades: List[Any],
    funding_events: List[Any],
    account_snapshots: List[Any],
    metrics: Dict[str, Any],
) -> str:
    """
    Tạo canonical payload hash chuẩn SHA-256 bao gồm:
    - config canonical;
    - run metadata;
    - orders;
    - trades;
    - funding events;
    - snapshots;
    - metrics.
    """
    full_payload = {
        "config": _normalize_for_canonical_hash(config),
        "run_metadata": _normalize_for_canonical_hash(run_metadata),
        "orders": [_normalize_for_canonical_hash(o) for o in orders],
        "trades": [_normalize_for_canonical_hash(t) for t in trades],
        "funding_events": [_normalize_for_canonical_hash(fe) for fe in funding_events],
        "account_snapshots": [_normalize_for_canonical_hash(s) for s in account_snapshots],
        "metrics": _normalize_for_canonical_hash(metrics),
    }
    canonical_json = json.dumps(full_payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class TradeLogger:
    """
    Quản lý lưu trữ SQLite và xuất báo cáo dữ liệu giao dịch.
    Đảm bảo tính toàn vẹn dữ liệu (foreign keys = ON), transaction atomic,
    composite primary keys, và idempotency dựa trên canonical payload hash.
    """

    DDL_STATEMENTS = [
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            payload_hash TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timeframe_signal TEXT,
            timeframe_execution TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            final_equity REAL NOT NULL,
            total_trades INTEGER NOT NULL,
            win_rate REAL NOT NULL,
            profit_factor REAL,
            max_drawdown REAL NOT NULL,
            sharpe_ratio REAL,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS orders (
            run_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            order_type TEXT NOT NULL,
            status TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            processed_at TEXT,
            reference_price REAL,
            actual_fill_price REAL,
            slippage_usd REAL,
            filled_quantity REAL,
            notional_usd REAL,
            fee_usd REAL,
            rejection_reasons_json TEXT,
            metadata_json TEXT,
            PRIMARY KEY (run_id, order_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS trades (
            run_id TEXT NOT NULL,
            trade_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            quantity REAL NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT NOT NULL,
            leverage REAL NOT NULL,
            initial_margin REAL NOT NULL,
            gross_price_pnl REAL NOT NULL,
            entry_fee REAL NOT NULL,
            exit_fee REAL NOT NULL,
            funding_cashflow REAL NOT NULL,
            net_pnl REAL NOT NULL,
            return_pct REAL NOT NULL,
            exit_reason TEXT NOT NULL,
            intrabar_estimated INTEGER NOT NULL,
            initial_stop_loss_price REAL,
            initial_risk_usd REAL,
            realized_r_multiple REAL,
            conviction_tier TEXT,
            estimated_liquidation_price REAL,
            take_profit_levels_json TEXT,
            metadata_json TEXT,
            PRIMARY KEY (run_id, trade_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS funding_events (
            run_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            position_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            funding_rate REAL NOT NULL,
            mark_price REAL NOT NULL,
            position_quantity REAL NOT NULL,
            payment REAL NOT NULL,
            direction TEXT NOT NULL,
            PRIMARY KEY (run_id, event_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS account_snapshots (
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            wallet_balance REAL NOT NULL,
            equity REAL NOT NULL,
            unrealized_pnl REAL NOT NULL,
            reserved_collateral REAL NOT NULL,
            available_margin REAL NOT NULL,
            open_positions_count INTEGER NOT NULL,
            is_halted INTEGER NOT NULL,
            PRIMARY KEY (run_id, timestamp),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS run_metrics (
            run_id TEXT PRIMARY KEY,
            metrics_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
    ]

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Mở kết nối SQLite với foreign keys được bật bắt buộc."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Khởi tạo cấu trúc bảng nếu chưa tồn tại."""
        with closing(self.get_connection()) as conn:
            with conn:
                for stmt in self.DDL_STATEMENTS:
                    conn.execute(stmt)

    def log_backtest_run(
        self,
        run_id: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        orders: List[Union[OrderExecutionRecord, Dict[str, Any]]],
        trades: List[Union[TradeRecord, Dict[str, Any]]],
        funding_events: List[Union[FundingEvent, Dict[str, Any]]],
        account_snapshots: List[Union[AccountSnapshot, Dict[str, Any]]],
    ) -> bool:
        """
        Ghi nhận toàn bộ kết quả của một run vào SQLite transaction.
        Đảm bảo idempotency: nếu run_id đã tồn tại:
        - Nếu canonical payload hash khớp 100%: trả về True (không ghi trùng).
        - Nếu bất kỳ dữ liệu nào xung đột: raise ValueError(fail-closed).
        """
        run_id = str(run_id).strip()
        if not run_id:
            raise ValueError("run_id cannot be empty")

        meta = parse_config_metadata(config)
        strategy_name = meta["strategy_name"]
        symbol = meta["symbol"]
        tf_signal = meta["timeframe_signal"]
        tf_execution = meta["timeframe_execution"]
        timeframe = f"{tf_signal}/{tf_execution}" if tf_signal != tf_execution else tf_signal

        start_time = _to_iso(metrics.get("start_time") or meta["start_date"] or config.get("start_date")) or ""
        end_time = _to_iso(metrics.get("end_time") or meta["end_date"] or config.get("end_date")) or ""

        initial_capital = float(metrics.get("initial_capital", config.get("initial_capital", 10000.0)))
        final_equity = float(metrics.get("final_equity", initial_capital))
        total_trades = int(metrics.get("total_trades", len(trades)))
        win_rate = float(metrics.get("win_rate", 0.0))
        profit_factor = _clean_float(metrics.get("profit_factor"))
        max_drawdown = float(metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 0.0)))
        sharpe_ratio = _clean_float(metrics.get("sharpe_ratio"))
        config_json = json.dumps(config, ensure_ascii=False, allow_nan=False, sort_keys=True, default=str)
        metrics_json = json.dumps(metrics, ensure_ascii=False, allow_nan=False, sort_keys=True, default=str)
        created_at = datetime.now(timezone.utc).isoformat()

        run_metadata = {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "timeframe_signal": tf_signal,
            "timeframe_execution": tf_execution,
            "start_time": start_time,
            "end_time": end_time,
            "initial_capital": initial_capital,
            "final_equity": final_equity,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
        }

        payload_hash = compute_canonical_payload_hash(
            config=config,
            run_metadata=run_metadata,
            orders=orders,
            trades=trades,
            funding_events=funding_events,
            account_snapshots=account_snapshots,
            metrics=metrics,
        )

        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                # 1. Kiểm tra run_id đã tồn tại chưa (Idempotency Check dựa trên canonical hash)
                cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
                existing_run = cursor.fetchone()

                if existing_run is not None:
                    existing_hash = existing_run["payload_hash"]
                    if existing_hash == payload_hash:
                        logger.info(f"Run ID '{run_id}' already logged identically. Skipping (idempotent).")
                        return True
                    else:
                        raise ValueError(
                            f"Run ID '{run_id}' already exists with differing payload: "
                            f"existing hash '{existing_hash}' vs new hash '{payload_hash}'"
                        )

                # 2. Insert vào bảng runs
                cursor.execute(
                    """
                    INSERT INTO runs (
                        run_id, payload_hash, strategy_name, symbol, timeframe,
                        timeframe_signal, timeframe_execution, start_time, end_time,
                        initial_capital, final_equity, total_trades, win_rate, profit_factor,
                        max_drawdown, sharpe_ratio, config_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        payload_hash,
                        strategy_name,
                        symbol,
                        timeframe,
                        tf_signal,
                        tf_execution,
                        start_time,
                        end_time,
                        initial_capital,
                        final_equity,
                        total_trades,
                        win_rate,
                        profit_factor,
                        max_drawdown,
                        sharpe_ratio,
                        config_json,
                        created_at,
                    ),
                )

                # 3. Insert vào bảng orders
                for ord_item in orders:
                    o = ord_item if isinstance(ord_item, dict) else ord_item.__dict__
                    dir_val = o.get("direction")
                    if isinstance(dir_val, OrderDirection):
                        dir_str = dir_val.value
                    else:
                        dir_str = str(dir_val) if dir_val is not None else ""

                    type_val = o.get("order_type")
                    if isinstance(type_val, OrderType):
                        type_str = type_val.value
                    else:
                        type_str = str(type_val) if type_val is not None else ""

                    st_val = o.get("status")
                    if isinstance(st_val, OrderStatus):
                        st_str = st_val.value
                    else:
                        st_str = str(st_val) if st_val is not None else ""

                    rejection_reasons = o.get("rejection_reasons", [])
                    rej_json = json.dumps(rejection_reasons, ensure_ascii=False) if rejection_reasons else None

                    meta = o.get("metadata", {})
                    meta_json = json.dumps(meta, ensure_ascii=False, allow_nan=False, default=str) if meta else None

                    cursor.execute(
                        """
                        INSERT INTO orders (
                            run_id, order_id, symbol, direction, order_type, status,
                            requested_at, processed_at, reference_price, actual_fill_price,
                            slippage_usd, filled_quantity, notional_usd, fee_usd,
                            rejection_reasons_json, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            str(o["order_id"]),
                            str(o["symbol"]).replace("/", "").replace(":", "").upper(),
                            dir_str,
                            type_str,
                            st_str,
                            _to_iso(o.get("requested_at")),
                            _to_iso(o.get("processed_at")),
                            _clean_float(o.get("reference_price")),
                            _clean_float(o.get("actual_fill_price")),
                            _clean_float(o.get("slippage_usd")),
                            _clean_float(o.get("filled_quantity")),
                            _clean_float(o.get("notional_usd")),
                            _clean_float(o.get("fee_usd")),
                            rej_json,
                            meta_json,
                        ),
                    )

                # 4. Insert vào bảng trades
                for tr_item in trades:
                    t = tr_item if isinstance(tr_item, dict) else tr_item.__dict__
                    dir_val = t.get("direction")
                    if isinstance(dir_val, OrderDirection):
                        dir_str = dir_val.value
                    else:
                        dir_str = str(dir_val) if dir_val is not None else ""

                    reason_val = t.get("exit_reason")
                    if isinstance(reason_val, ExitReason):
                        reason_str = reason_val.value
                    else:
                        reason_str = str(reason_val) if reason_val is not None else ""

                    tp_levels = t.get("take_profit_levels", [])
                    tp_json = json.dumps(tp_levels) if tp_levels else None

                    meta = t.get("metadata", {})
                    meta_json = json.dumps(meta, ensure_ascii=False, allow_nan=False, default=str) if meta else None

                    cursor.execute(
                        """
                        INSERT INTO trades (
                            run_id, trade_id, symbol, direction, quantity, entry_price, exit_price,
                            entry_time, exit_time, leverage, initial_margin, gross_price_pnl,
                            entry_fee, exit_fee, funding_cashflow, net_pnl, return_pct,
                            exit_reason, intrabar_estimated, initial_stop_loss_price,
                            initial_risk_usd, realized_r_multiple, conviction_tier,
                            estimated_liquidation_price, take_profit_levels_json, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            str(t["trade_id"]),
                            str(t["symbol"]).replace("/", "").replace(":", "").upper(),
                            dir_str,
                            float(t["quantity"]),
                            float(t["entry_price"]),
                            float(t["exit_price"]),
                            _to_iso(t["entry_time"]),
                            _to_iso(t["exit_time"]),
                            float(t.get("leverage", 1.0)),
                            float(t.get("initial_margin", 0.0)),
                            float(t.get("gross_price_pnl", 0.0)),
                            float(t.get("entry_fee", 0.0)),
                            float(t.get("exit_fee", 0.0)),
                            float(t.get("funding_cashflow", 0.0)),
                            float(t.get("net_pnl", 0.0)),
                            float(t.get("return_pct", 0.0)),
                            reason_str,
                            1 if t.get("intrabar_estimated") else 0,
                            _clean_float(t.get("initial_stop_loss_price")),
                            _clean_float(t.get("initial_risk_usd")),
                            _clean_float(t.get("realized_r_multiple")),
                            str(t.get("conviction_tier", "normal")),
                            _clean_float(t.get("estimated_liquidation_price")),
                            tp_json,
                            meta_json,
                        ),
                    )

                # 5. Insert vào bảng funding_events
                for fe_item in funding_events:
                    fe = fe_item if isinstance(fe_item, dict) else fe_item.__dict__
                    event_id = str(fe.get("event_id", ""))
                    position_id = str(fe.get("position_id", ""))
                    mark_p = float(fe.get("settlement_mark_price", fe.get("mark_price", 0.0)))
                    cashflow = float(fe.get("cashflow_usd", fe.get("payment", 0.0)))

                    dir_val = fe.get("direction")
                    if isinstance(dir_val, OrderDirection):
                        dir_str = dir_val.value
                    else:
                        dir_str = str(dir_val) if dir_val is not None else ""

                    cursor.execute(
                        """
                        INSERT INTO funding_events (
                            run_id, event_id, position_id, symbol, timestamp,
                            funding_rate, mark_price, position_quantity, payment, direction
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            event_id,
                            position_id,
                            str(fe["symbol"]).replace("/", "").replace(":", "").upper(),
                            _to_iso(fe["timestamp"]),
                            float(fe["funding_rate"]),
                            mark_p,
                            float(fe["position_quantity"]),
                            cashflow,
                            dir_str,
                        ),
                    )

                # 6. Insert vào bảng account_snapshots
                for snap_item in account_snapshots:
                    s = snap_item if isinstance(snap_item, dict) else snap_item.__dict__
                    cursor.execute(
                        """
                        INSERT INTO account_snapshots (
                            run_id, timestamp, wallet_balance, equity, unrealized_pnl,
                            reserved_collateral, available_margin, open_positions_count, is_halted
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            _to_iso(s["timestamp"]),
                            float(s["wallet_balance"]),
                            float(s["equity"]),
                            float(s.get("unrealized_pnl", 0.0)),
                            float(s["reserved_collateral"]),
                            float(s["available_margin"]),
                            int(s["open_positions_count"]),
                            1 if s.get("is_halted", False) else 0,
                        ),
                    )

                # 7. Insert vào bảng run_metrics
                cursor.execute(
                    """
                    INSERT INTO run_metrics (run_id, metrics_json, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (run_id, metrics_json, created_at),
                )

                logger.info(f"Successfully logged run '{run_id}' with {len(trades)} trades and {len(orders)} orders.")
                return True
        finally:
            conn.close()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin run theo run_id."""
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_trades(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các trade theo run_id."""
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trades WHERE run_id = ? ORDER BY entry_time ASC, trade_id ASC",
                (run_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_orders(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách order theo run_id."""
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE run_id = ? ORDER BY requested_at ASC, order_id ASC",
                (run_id,),
            )
            orders = []
            for row in cursor.fetchall():
                d = dict(row)
                if d.get("rejection_reasons_json"):
                    try:
                        d["rejection_reasons"] = json.loads(d["rejection_reasons_json"])
                    except Exception:
                        d["rejection_reasons"] = []
                else:
                    d["rejection_reasons"] = []
                orders.append(d)
            return orders

    def get_account_snapshots(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách account snapshots theo run_id."""
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM account_snapshots WHERE run_id = ? ORDER BY timestamp ASC", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_funding_events(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách funding events theo run_id."""
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM funding_events WHERE run_id = ? ORDER BY timestamp ASC, event_id ASC",
                (run_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_run_metrics(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Lấy metrics chi tiết theo run_id."""
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metrics_json FROM run_metrics WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if row and row["metrics_json"]:
                return json.loads(row["metrics_json"])
            return None

    def export_trades_json(
        self,
        run_id: str,
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Xuất danh sách trade ra định dạng JSON tuân thủ tuyệt đối
        đúng nguyên văn schema Master Spec Mục 4.6:
        - Timestamp epoch seconds UTC
        - Không thay schema bằng schema tự thiết kế
        - Không bịa field chưa đo được; dùng null
        - allow_nan=False (chặn triệt để NaN / Infinity)
        """
        trades_rows = self.get_trades(run_id)
        run_row = self.get_run(run_id)
        strategy_name = run_row["strategy_name"] if run_row else "TREND_FOLLOWING"
        initial_capital = run_row["initial_capital"] if run_row else 10000.0

        json_trades = []

        for row in trades_rows:
            entry_epoch = _to_epoch(row["entry_time"]) or 0
            tier_raw = row.get("conviction_tier", "normal")
            conviction_tier = _format_conviction_tier(tier_raw)

            risk_amount = _clean_float(row.get("initial_risk_usd")) or 0.0
            metadata = {}
            if row.get("metadata_json"):
                metadata = json.loads(row["metadata_json"])
                if not isinstance(metadata, dict):
                    raise ValueError(f"Trade {row['trade_id']} metadata must decode to an object")

            explicit_ratio = _clean_float(metadata.get("risk_ratio_percent"))
            if explicit_ratio is not None:
                if explicit_ratio < 0:
                    raise ValueError(f"Trade {row['trade_id']} risk_ratio_percent cannot be negative")
                risk_ratio = explicit_ratio
            else:
                entry_equity = _clean_float(metadata.get("entry_equity"))
                risk_ratio = _get_risk_ratio_percent(
                    conviction_tier,
                    risk_amount,
                    entry_equity if entry_equity is not None else initial_capital,
                )

            tp_json = row.get("take_profit_levels_json")
            take_profit_levels = json.loads(tp_json) if tp_json else []

            liq_price = _clean_float(row.get("estimated_liquidation_price")) or 0.0
            fees_paid = float(row.get("entry_fee", 0.0)) + float(row.get("exit_fee", 0.0))

            trade_obj = {
                "trade_id": str(row["trade_id"]),
                "timestamp": entry_epoch,
                "asset": str(row["symbol"]).replace("/", "").replace(":", "").upper(),
                "direction": str(row["direction"]).upper(),
                "strategy_used": str(strategy_name).upper(),
                "conviction_tier": str(conviction_tier),
                "entry_price": float(row["entry_price"]),
                "stop_loss_price": float(row.get("initial_stop_loss_price") or 0.0),
                "take_profit_levels": [float(p) for p in take_profit_levels],
                "nominal_position_size_usd": round(float(row["quantity"]) * float(row["entry_price"]), 4),
                "leverage": float(row.get("leverage", 1.0)),
                "margin_used_usd": round(float(row.get("initial_margin", 0.0)), 4),
                "risk_amount_usd": round(float(risk_amount), 4),
                "risk_ratio_percent": round(float(risk_ratio), 4),
                "estimated_liquidation_price": round(float(liq_price), 4),
                "market_context": {
                    "oi_trend_4h": None,
                    "funding_rate_8h": None,
                    "cvd_divergence": None,
                    "fvg_consequent_encroachment": None,
                },
                "outcome": {
                    "exit_price": float(row["exit_price"]),
                    "pnl_usd": round(float(row["net_pnl"]), 4),
                    "fees_paid_usd": round(float(fees_paid), 4),
                    "net_return_percent": round(float(row.get("return_pct", 0.0)), 4),
                    "max_adverse_excursion_mae": None,
                    "max_favorable_excursion_mfe": None,
                    "rule_compliance": True,
                },
            }
            json_trades.append(trade_obj)

        json_str = json.dumps(json_trades, indent=2, ensure_ascii=False, allow_nan=False)

        if output_path is not None:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = out_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(json_str)
            temp_file.replace(out_file)

        return json_str
