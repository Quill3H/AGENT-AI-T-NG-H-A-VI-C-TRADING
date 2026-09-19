"""
src/logging/trade_logger.py - SQLite Event Store and JSON Exporter
==================================================================
Triển khai lưu trữ có cấu trúc toàn bộ sự kiện backtest/paper trading
vào SQLite database tuân thủ ACID transaction, foreign key constraints,
và tính luỹ thừa (idempotency).

Cung cấp khả năng xuất dữ liệu giao dịch chuẩn hoá ra JSON theo đặc tả
Master Spec Section 4.6.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
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
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


class TradeLogger:
    """
    Quản lý lưu trữ SQLite và xuất báo cáo dữ liệu giao dịch.
    Đảm bảo tính toàn vẹn dữ liệu (foreign keys = ON), transaction atomic,
    và idempotency dựa trên run_id.
    """

    DDL_STATEMENTS = [
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            strategy_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
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
            order_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
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
            metadata_json TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
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
            metadata_json TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS funding_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            funding_rate REAL NOT NULL,
            mark_price REAL NOT NULL,
            position_quantity REAL NOT NULL,
            payment REAL NOT NULL,
            direction TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS account_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            wallet_balance REAL NOT NULL,
            equity REAL NOT NULL,
            unrealized_pnl REAL NOT NULL,
            margin_used REAL NOT NULL,
            available_balance REAL NOT NULL,
            active_positions INTEGER NOT NULL,
            realized_pnl REAL NOT NULL,
            drawdown_pct REAL NOT NULL,
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
        with self.get_connection() as conn:
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
        - Nếu payload khớp: trả về True (không ghi trùng).
        - Nếu payload xung đột: raise ValueError(fail-closed).
        """
        run_id = str(run_id).strip()
        if not run_id:
            raise ValueError("run_id cannot be empty")

        strategy_name = str(config.get("strategy", config.get("strategy_name", "trend_following")))
        symbol = str(config.get("symbol", "BTCUSDT")).upper()
        timeframe = str(config.get("timeframe", "15m"))
        start_time = _to_iso(config.get("start_date", config.get("start_time", ""))) or ""
        end_time = _to_iso(config.get("end_date", config.get("end_time", ""))) or ""
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

        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                # 1. Kiểm tra run_id đã tồn tại chưa (Idempotency Check)
                cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
                existing_run = cursor.fetchone()

                if existing_run is not None:
                    # So khớp payload
                    if (
                        existing_run["strategy_name"] == strategy_name
                        and existing_run["symbol"] == symbol
                        and existing_run["timeframe"] == timeframe
                        and math.isclose(existing_run["initial_capital"], initial_capital, abs_tol=1e-5)
                        and math.isclose(existing_run["final_equity"], final_equity, abs_tol=1e-5)
                        and existing_run["total_trades"] == total_trades
                    ):
                        logger.info(f"Run ID '{run_id}' already logged identically. Skipping (idempotent).")
                        return True
                    else:
                        raise ValueError(
                            f"Run ID '{run_id}' already exists with differing payload: "
                            f"existing (eq={existing_run['final_equity']}, trades={existing_run['total_trades']}) "
                            f"vs new (eq={final_equity}, trades={total_trades})"
                        )

                # 2. Insert vào bảng runs
                cursor.execute(
                    """
                    INSERT INTO runs (
                        run_id, strategy_name, symbol, timeframe, start_time, end_time,
                        initial_capital, final_equity, total_trades, win_rate, profit_factor,
                        max_drawdown, sharpe_ratio, config_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        strategy_name,
                        symbol,
                        timeframe,
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

                    meta = o.get("metadata", {})
                    meta_json = json.dumps(meta, ensure_ascii=False, allow_nan=False, default=str) if meta else None

                    cursor.execute(
                        """
                        INSERT INTO orders (
                            order_id, run_id, symbol, direction, order_type, status,
                            requested_at, processed_at, reference_price, actual_fill_price,
                            slippage_usd, filled_quantity, notional_usd, fee_usd, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(o["order_id"]),
                            run_id,
                            str(o["symbol"]),
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

                    meta = t.get("metadata", {})
                    meta_json = json.dumps(meta, ensure_ascii=False, allow_nan=False, default=str) if meta else None

                    cursor.execute(
                        """
                        INSERT INTO trades (
                            trade_id, run_id, symbol, direction, quantity, entry_price, exit_price,
                            entry_time, exit_time, leverage, initial_margin, gross_price_pnl,
                            entry_fee, exit_fee, funding_cashflow, net_pnl, return_pct,
                            exit_reason, intrabar_estimated, initial_stop_loss_price,
                            initial_risk_usd, realized_r_multiple, conviction_tier, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(t["trade_id"]),
                            run_id,
                            str(t["symbol"]),
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
                            meta_json,
                        ),
                    )

                # 5. Insert vào bảng funding_events
                for fe_item in funding_events:
                    fe = fe_item if isinstance(fe_item, dict) else fe_item.__dict__
                    dir_val = fe.get("direction")
                    if isinstance(dir_val, OrderDirection):
                        dir_str = dir_val.value
                    else:
                        dir_str = str(dir_val) if dir_val is not None else ""

                    cursor.execute(
                        """
                        INSERT INTO funding_events (
                            run_id, symbol, timestamp, funding_rate, mark_price,
                            position_quantity, payment, direction
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            str(fe["symbol"]),
                            _to_iso(fe["timestamp"]),
                            float(fe["funding_rate"]),
                            float(fe.get("mark_price", fe.get("settlement_mark_price", 0.0))),
                            float(fe["position_quantity"]),
                            float(fe.get("payment", fe.get("cashflow_usd", 0.0))),
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
                            margin_used, available_balance, active_positions, realized_pnl,
                            drawdown_pct
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            _to_iso(s["timestamp"]),
                            float(s["wallet_balance"]),
                            float(s["equity"]),
                            float(s.get("unrealized_pnl", 0.0)),
                            float(s.get("margin_used", 0.0)),
                            float(s.get("available_balance", s["wallet_balance"])),
                            int(s.get("active_positions", 0)),
                            float(s.get("realized_pnl", 0.0)),
                            float(s.get("drawdown_pct", 0.0)),
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
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_trades(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các trade theo run_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE run_id = ? ORDER BY entry_time ASC", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_orders(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách order theo run_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE run_id = ? ORDER BY requested_at ASC", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_account_snapshots(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách account snapshots theo run_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM account_snapshots WHERE run_id = ? ORDER BY timestamp ASC", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_funding_events(self, run_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách funding events theo run_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM funding_events WHERE run_id = ? ORDER BY timestamp ASC", (run_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_run_metrics(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Lấy metrics chi tiết theo run_id."""
        with self.get_connection() as conn:
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
        Master Spec Section 4.6:
        - Epoch seconds UTC timestamps
        - Không cho phép NaN/Inf (allow_nan=False)
        - Null cho các giá trị chưa đo lường (market_context, MAE/MFE)
        """
        trades_rows = self.get_trades(run_id)
        json_trades = []

        for row in trades_rows:
            entry_epoch = _to_epoch(row["entry_time"])
            exit_epoch = _to_epoch(row["exit_time"])

            fee_total = float(row["entry_fee"]) + float(row["exit_fee"])
            pnl_gross = float(row["gross_price_pnl"])
            pnl_net = float(row["net_pnl"])

            trade_obj = {
                "trade_id": str(row["trade_id"]),
                "symbol": str(row["symbol"]),
                "direction": str(row["direction"]),
                "entry_time": entry_epoch,
                "exit_time": exit_epoch,
                "entry_price": float(row["entry_price"]),
                "exit_price": float(row["exit_price"]),
                "quantity": float(row["quantity"]),
                "leverage": float(row["leverage"]),
                "initial_margin": float(row["initial_margin"]),
                "pnl_gross": pnl_gross,
                "pnl_net": pnl_net,
                "fee_total": fee_total,
                "funding_total": float(row["funding_cashflow"]),
                "return_pct": float(row["return_pct"]),
                "exit_reason": str(row["exit_reason"]),
                "conviction_tier": str(row["conviction_tier"] or "normal").upper(),
                "initial_stop_loss": _clean_float(row["initial_stop_loss_price"]),
                "initial_risk_usd": _clean_float(row["initial_risk_usd"]),
                "realized_r_multiple": _clean_float(row["realized_r_multiple"]),
                "market_context": None,
                "mae_usd": None,
                "mfe_usd": None,
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
