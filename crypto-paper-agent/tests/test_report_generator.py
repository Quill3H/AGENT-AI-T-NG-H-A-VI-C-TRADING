"""
tests/test_report_generator.py - Test suite for Multi-format Report Generator
=============================================================================
Kiểm tra:
1. Sinh đầy đủ 6 artifacts trong thư mục `reports/<run_id>/`:
   - summary.json
   - summary.md (kèm benchmark caveats và disclosures)
   - trades.json
   - equity_curve.csv
   - equity_curve.png
   - trades.sqlite
2. Tính toàn vẹn của summary.json (allow_nan=False, không chứa NaN/Inf)
3. Tính toàn vẹn của equity_curve.png (non-empty file ảnh PNG hợp lệ)
4. Hỗ trợ custom_output_dir và custom db_path
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import pytest

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    OrderDirection,
    OrderStatus,
    TradeRecord,
)
from src.report.generator import ReportGenerator


class MockFullBroker:
    def __init__(self):
        self.initial_balance = 10000.0
        self.equity = 10491.8
        self.wallet_balance = 10491.8
        self.available_margin = 10491.8
        self.positions = {}
        self.funding_history = []
        t0 = datetime(2023, 1, 1, tzinfo=timezone.utc)
        self.trade_history = [
            TradeRecord(
                trade_id="TRD_001",
                symbol="BTCUSDT",
                direction=OrderDirection.LONG,
                quantity=0.5,
                entry_price=20000.0,
                exit_price=21000.0,
                entry_time=t0,
                exit_time=t0 + timedelta(hours=4),
                leverage=2.0,
                initial_margin=5000.0,
                gross_price_pnl=500.0,
                entry_fee=4.0,
                exit_fee=4.2,
                funding_cashflow=0.0,
                net_pnl=491.8,
                return_pct=9.836,
                exit_reason=ExitReason.TAKE_PROFIT,
                intrabar_estimated=False,
                initial_stop_loss_price=19500.0,
                initial_risk_usd=250.0,
                realized_r_multiple=1.967,
                conviction_tier="strong",
            )
        ]
        self.order_history = []
        self.account_snapshots = [
            AccountSnapshot(
                timestamp=t0,
                wallet_balance=10000.0,
                reserved_collateral=0.0,
                available_margin=10000.0,
                unrealized_pnl=0.0,
                equity=10000.0,
                open_positions_count=0,
            ),
            AccountSnapshot(
                timestamp=t0 + timedelta(days=1),
                wallet_balance=10491.8,
                reserved_collateral=0.0,
                available_margin=10491.8,
                unrealized_pnl=0.0,
                equity=10491.8,
                open_positions_count=0,
            ),
        ]

    def verify_accounting_invariants(self):
        return True


def test_generator_produces_all_six_artifacts(tmp_path):
    """Kiểm tra tạo đủ 6 file artifact chuẩn xác."""
    run_id = "run_gen_test_01"
    generator = ReportGenerator(base_reports_dir=tmp_path)
    broker = MockFullBroker()

    config = {
        "strategy": "trend_following",
        "symbol": "BTCUSDT",
        "timeframe_signal": "4h",
        "timeframe_execution": "15m",
        "start_date": "2023-01-01",
        "end_date": "2023-01-02",
        "data": {"raw_data_dir": str(tmp_path / "author_machine_cache")},
    }
    metrics = {
        "strategy": "trend_following",
        "symbol": "BTCUSDT",
        "initial_capital": 10000.0,
        "final_equity": 10491.8,
        "total_return_pct": 4.918,
        "max_drawdown_usd": 0.0,
        "max_drawdown_pct": 0.0,
        "daily_sharpe": 2.1,
        "sharpe_ratio": 2.1,
        "profit_factor": None,
        "expectancy_usd": 491.8,
        "expectancy_r": 1.97,
        "total_trades": 1,
        "win_trades_count": 1,
        "loss_trades_count": 0,
        "breakeven_trades_count": 0,
        "win_rate": 100.0,
        "loss_rate": 0.0,
        "average_realized_rrr": 1.97,
        "circuit_breaker_lock_count": 2,
        "circuit_breaker_rejections_count": 1,
        "margin_rejections_count": 3,
        "total_fees": 8.2,
        "total_gross_pnl": 500.0,
        "total_funding_trades": 0.0,
        "total_net_pnl": 491.8,
    }

    artifacts = generator.generate_all(
        run_id=run_id,
        config=config,
        metrics=metrics,
        broker=broker,
    )

    # 1. Kiểm tra 6 file tồn tại
    expected_keys = [
        "summary.json",
        "summary.md",
        "trades.json",
        "equity_curve.csv",
        "equity_curve.png",
        "trades.sqlite",
    ]
    for key in expected_keys:
        assert key in artifacts, f"Missing artifact key '{key}'"
        assert artifacts[key].is_file(), f"Artifact file '{artifacts[key]}' was not created"

    # 2. Kiểm tra summary.json
    with open(artifacts["summary.json"], "r", encoding="utf-8") as f:
        summary_data = json.load(f)
    assert summary_data["symbol"] == "BTCUSDT"
    assert summary_data["final_equity"] == 10491.8
    assert summary_data["total_trades"] == 1
    assert "data_provenance" in summary_data
    assert "candle_counts" in summary_data
    assert "candle_gaps" in summary_data
    assert "accounting_reconciliation" in summary_data
    assert summary_data["verification_status"] == "AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED"
    assert "reproduction_command" in summary_data

    # 3. Kiểm tra summary.md có nhãn kiểm định bắt buộc
    with open(artifacts["summary.md"], "r", encoding="utf-8") as f:
        md_text = f.read()
    assert "AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED" in md_text
    assert "Disclosures & Benchmark Caveats" in md_text
    assert "BTCUSDT" in md_text
    assert "Accounting Reconciliation & Risk Audit" in md_text
    assert "Loss Rate" in md_text
    assert "0.00%" in md_text
    assert "Average Realized RRR" in md_text
    assert "+1.97 R" in md_text
    assert "Circuit Breaker Activations / Lock Count" in md_text
    assert "`2` lần" in md_text

    # 4. Kiểm tra trades.json chuẩn xác schema Master Spec Mục 4.6
    with open(artifacts["trades.json"], "r", encoding="utf-8") as f:
        trades_data = json.load(f)
    assert len(trades_data) == 1
    t0_data = trades_data[0]
    assert t0_data["trade_id"] == "TRD_001"
    assert t0_data["asset"] == "BTCUSDT"
    assert t0_data["direction"] == "LONG"
    assert t0_data["strategy_used"] == "TREND_FOLLOWING"
    assert t0_data["conviction_tier"] == "HIGH_5_PERCENT"
    assert t0_data["entry_price"] == 20000.0
    assert t0_data["stop_loss_price"] == 19500.0
    assert t0_data["market_context"] == {
        "oi_trend_4h": None,
        "funding_rate_8h": None,
        "cvd_divergence": None,
        "fvg_consequent_encroachment": None,
    }
    assert t0_data["outcome"]["exit_price"] == 21000.0
    assert t0_data["outcome"]["pnl_usd"] == 491.8
    assert t0_data["outcome"]["fees_paid_usd"] == 8.2
    assert t0_data["outcome"]["rule_compliance"] is True

    # 5. Kiểm tra equity_curve.csv
    with open(artifacts["equity_curve.csv"], "r", encoding="utf-8") as f:
        csv_header = f.readline().strip()
    assert "timestamp,equity,wallet_balance,unrealized_pnl,margin_used,available_balance,drawdown_usd,drawdown_pct" in csv_header

    # 6. Kiểm tra equity_curve.png là file ảnh không rỗng
    png_path = artifacts["equity_curve.png"]
    assert png_path.stat().st_size > 1000
    with open(png_path, "rb") as f:
        header = f.read(8)
    assert header == b"\x89PNG\r\n\x1a\n", "File must have valid PNG magic bytes"

    # 7. Kiểm tra trades.sqlite
    with sqlite3.connect(str(artifacts["trades.sqlite"])) as conn:
        cur = conn.cursor()
        cur.execute("SELECT config_json FROM runs WHERE run_id = ?", (run_id,))
        config_json = cur.fetchone()[0]
        assert config_json is not None
        assert str(tmp_path) not in config_json


def test_generator_custom_output_dir_and_db(tmp_path):
    """Kiểm tra xuất ra thư mục tuỳ chọn và chỉ định database ngoài."""
    custom_dir = tmp_path / "custom_reports"
    custom_db = tmp_path / "shared_db.sqlite"

    generator = ReportGenerator(base_reports_dir=tmp_path)
    broker = MockFullBroker()
    config = {"symbol": "BTCUSDT", "strategy": "trend_following"}
    metrics = {"initial_capital": 10000.0, "final_equity": 10491.8, "total_trades": 1}

    artifacts = generator.generate_all(
        run_id="run_custom_01",
        config=config,
        metrics=metrics,
        broker=broker,
        custom_output_dir=custom_dir,
        db_path=custom_db,
    )

    assert custom_dir.is_dir()
    assert artifacts["summary.json"].parent == custom_dir / "run_custom_01"
    assert custom_db.is_file()


def test_sanitize_for_json_fail_closed():
    """Kiểm tra _sanitize_for_json từ chối fail-closed khi gặp NaN hoặc Inf."""
    from src.report.generator import _sanitize_for_json

    assert _sanitize_for_json(123) == 123
    assert _sanitize_for_json(12.34) == 12.34
    assert _sanitize_for_json(True) is True
    assert _sanitize_for_json(None) is None
    assert _sanitize_for_json({"a": 1, "b": "str"}) == {"a": 1, "b": "str"}

    with pytest.raises(ValueError, match="NaN/Inf"):
        _sanitize_for_json(float("nan"))

    with pytest.raises(ValueError, match="NaN/Inf"):
        _sanitize_for_json({"nested": {"val": float("inf")}})

    with pytest.raises(ValueError, match="NaN/Inf"):
        _sanitize_for_json([1.0, 2.0, float("-inf")])


def test_deterministic_json_output(tmp_path):
    """Kiểm tra sinh JSON có tính tất định, byte-for-byte nhất quán qua các lần chạy."""
    generator = ReportGenerator(base_reports_dir=tmp_path)
    broker = MockFullBroker()
    config = {
        "strategy": "trend_following",
        "symbol": "BTCUSDT",
        "timeframe_signal": "4h",
        "timeframe_execution": "15m",
    }
    metrics = {
        "strategy": "trend_following",
        "symbol": "BTCUSDT",
        "initial_capital": 10000.0,
        "final_equity": 10491.8,
        "total_trades": 1,
        "code_commit_sha": "test_sha_deterministic",
        "reproduction_command": "python test.py",
    }

    art1 = generator.generate_all(run_id="run_det_1", config=config, metrics=metrics, broker=broker)
    art2 = generator.generate_all(run_id="run_det_2", config=config, metrics=metrics, broker=broker)

    # Đọc summary.json (bỏ qua generated_at vì generated_at thay đổi theo thời gian hiện tại)
    with open(art1["summary.json"], "r", encoding="utf-8") as f1, open(art2["summary.json"], "r", encoding="utf-8") as f2:
        d1 = json.load(f1)
        d2 = json.load(f2)
        d1.pop("generated_at", None)
        d2.pop("generated_at", None)
        d1.pop("run_id", None)
        d2.pop("run_id", None)
        assert d1 == d2

    # trades.json phải giống nhau từng byte
    with open(art1["trades.json"], "rb") as f1, open(art2["trades.json"], "rb") as f2:
        assert f1.read() == f2.read()


def test_generator_rejects_supplied_accounting_mismatch_before_artifacts(tmp_path):
    generator = ReportGenerator(base_reports_dir=tmp_path)
    broker = MockFullBroker()
    bad_metrics = {
        "initial_capital": 10000.0,
        "final_equity": 10500.0,
        "total_gross_pnl": 500.0,
        "total_fees": 8.2,
        "total_funding_trades": 0.0,
        "total_net_pnl": 500.0,
    }

    with pytest.raises(AssertionError, match="Report accounting mismatch"):
        generator.generate_all(
            run_id="run_bad_accounting",
            config={"symbol": "BTCUSDT", "strategy": "trend_following"},
            metrics=bad_metrics,
            broker=broker,
        )

    out_dir = tmp_path / "run_bad_accounting"
    assert not out_dir.exists() or not any(out_dir.iterdir())

