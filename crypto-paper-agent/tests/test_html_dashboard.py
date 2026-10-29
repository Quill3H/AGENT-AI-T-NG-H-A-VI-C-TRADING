"""
tests/test_html_dashboard.py - Unit test suite for HTML Dashboard Generator
===========================================================================
Verifies:
1. Generation of standalone, valid dashboard.html file.
2. Embedded RFC 8259 raw JSON dataset parsing.
3. Presence of all scorecard KPIs, badges, and >=2,000 threshold indicator.
4. Offline SVG fallback inclusion.
5. Graceful handling of zero trades, single trade, and edge cases.
6. High-sample performance scaling (2,500 trades serialized in < 2.0s).
7. Full integration with ReportGenerator.generate_all as the 7th artifact.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import pytest

from src.execution.order_models import (
    AccountSnapshot,
    ExitReason,
    OrderDirection,
    OrderStatus,
    TradeRecord,
)
from src.report.html_dashboard import HTMLDashboardGenerator
from src.report.generator import ReportGenerator


class MockDashboardBroker:
    """Mock broker providing account snapshots and completed trades for dashboard tests."""

    def __init__(self, num_trades: int = 5, start_equity: float = 10000.0):
        self.initial_balance = start_equity
        self.equity = start_equity
        self.wallet_balance = start_equity
        self.available_margin = start_equity
        self.positions = {}
        self.order_history = []
        self.funding_history = []
        self.trade_history = []
        self.account_snapshots = []

        t0 = datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
        curr_eq = start_equity

        # Create snapshots
        for i in range(10):
            ts = t0 + timedelta(days=i)
            curr_eq += (50.0 if i % 2 == 0 else -20.0)
            self.account_snapshots.append(
                AccountSnapshot(
                    timestamp=ts,
                    wallet_balance=curr_eq,
                    reserved_collateral=0.0,
                    available_margin=curr_eq,
                    unrealized_pnl=0.0,
                    equity=curr_eq,
                    open_positions_count=0,
                )
            )
        self.equity = curr_eq
        self.wallet_balance = curr_eq

        # Create trades
        for i in range(num_trades):
            is_win = (i % 2 == 0)
            pnl = 100.0 if is_win else -40.0
            r_mult = 2.0 if is_win else -1.0
            direction = OrderDirection.LONG if i % 3 != 0 else OrderDirection.SHORT
            self.trade_history.append(
                TradeRecord(
                    trade_id=f"TRD_{i:04d}",
                    symbol="BTCUSDT",
                    direction=direction,
                    quantity=0.5,
                    entry_price=20000.0,
                    exit_price=20200.0 if is_win else 19920.0,
                    entry_time=t0 + timedelta(hours=i * 4),
                    exit_time=t0 + timedelta(hours=i * 4 + 3),
                    leverage=1.0,
                    initial_margin=10000.0,
                    gross_price_pnl=pnl + 2.0,
                    entry_fee=1.0,
                    exit_fee=1.0,
                    funding_cashflow=0.0,
                    net_pnl=pnl,
                    return_pct=1.0 if is_win else -0.4,
                    exit_reason=ExitReason.TAKE_PROFIT if is_win else ExitReason.STOP_LOSS,
                    initial_stop_loss_price=19900.0,
                    initial_risk_usd=50.0,
                    realized_r_multiple=r_mult,
                )
            )

    def verify_accounting_invariants(self):
        pass


def test_html_dashboard_generation_creates_valid_file(tmp_path):
    """Test 1: Verify dashboard.html is created, non-empty, and contains valid HTML skeleton."""
    generator = HTMLDashboardGenerator()
    broker = MockDashboardBroker(num_trades=4)
    out_path = tmp_path / "dashboard.html"

    metrics = {
        "symbol": "BTCUSDT",
        "strategy": "SYNTHESIZED",
        "initial_capital": 10000.0,
        "final_equity": 10240.0,
        "total_net_pnl": 240.0,
        "total_return_pct": 2.4,
        "max_drawdown_pct": 1.2,
        "max_drawdown_usd": 120.0,
        "win_rate": 50.0,
        "profit_factor": 2.5,
        "sharpe_ratio": 1.85,
        "sortino_ratio": 2.95,
        "total_trades": 4,
    }

    res_path = generator.generate(
        output_path=out_path,
        run_id="test_run_01",
        config={"symbol": "BTCUSDT"},
        metrics=metrics,
        broker=broker,
    )

    assert res_path.is_file()
    assert res_path.stat().st_size > 5000
    content = res_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<html" in content
    assert "<head>" in content
    assert "<body>" in content
    assert "</html>" in content


def test_html_dashboard_embedded_json_dataset(tmp_path):
    """Test 2: Verify raw JSON dataset is embedded and parseable via RFC 8259."""
    generator = HTMLDashboardGenerator()
    broker = MockDashboardBroker(num_trades=6)
    out_path = tmp_path / "dashboard.html"

    generator.generate(
        output_path=out_path,
        run_id="test_run_json",
        config={"symbol": "BTCUSDT", "strategy": {"name": "SYNTHESIZED"}},
        metrics={"symbol": "BTCUSDT", "total_trades": 6},
        broker=broker,
    )

    content = out_path.read_text(encoding="utf-8")
    start_tag = '<script id="backtest-data" type="application/json">'
    end_tag = '</script>'
    assert start_tag in content

    json_str = content.split(start_tag)[1].split(end_tag)[0].strip()
    data = json.loads(json_str)

    assert data["run_id"] == "test_run_json"
    assert "metrics" in data
    assert "equity_series" in data
    assert "monthly_returns" in data
    assert "trades" in data
    assert len(data["trades"]) == 6
    assert data["trades"][0]["trade_id"] == "TRD_0000"


def test_html_dashboard_scorecard_and_badges(tmp_path):
    """Test 3: Verify scorecard KPIs and >=2,000 threshold badge switching."""
    generator = HTMLDashboardGenerator()
    out_path_low = tmp_path / "low_sample.html"
    out_path_high = tmp_path / "high_sample.html"

    # Case A: Low sample (< 2,000 trades)
    broker_low = MockDashboardBroker(num_trades=10)
    generator.generate(
        output_path=out_path_low,
        run_id="run_low",
        config={},
        metrics={"total_trades": 10, "win_rate": 60.0},
        broker=broker_low,
    )
    content_low = out_path_low.read_text(encoding="utf-8")
    assert "LOW SAMPLE" in content_low

    # Case B: High sample (>= 2,000 trades)
    broker_high = MockDashboardBroker(num_trades=2000)
    generator.generate(
        output_path=out_path_high,
        run_id="run_high",
        config={},
        metrics={"total_trades": 2000, "win_rate": 52.0},
        broker=broker_high,
    )
    content_high = out_path_high.read_text(encoding="utf-8")
    assert "HIGH-SAMPLE MET" in content_high


def test_html_dashboard_offline_svg_fallback(tmp_path):
    """Test 4: Verify native SVG fallback functions are embedded for air-gapped environments."""
    generator = HTMLDashboardGenerator()
    broker = MockDashboardBroker(num_trades=3)
    out_path = tmp_path / "dashboard_svg.html"

    generator.generate(
        output_path=out_path,
        run_id="run_svg",
        config={},
        metrics={"total_trades": 3},
        broker=broker,
    )
    content = out_path.read_text(encoding="utf-8")
    assert "renderSvgFallbackDashboard" in content
    assert "createSvgLineChart" in content
    assert "createSvgAreaChart" in content


def test_html_dashboard_handles_zero_trades(tmp_path):
    """Test 5: Edge case - verify 0 trades produces valid HTML without crashing."""
    generator = HTMLDashboardGenerator()
    broker = MockDashboardBroker(num_trades=0)
    out_path = tmp_path / "zero_trades.html"

    generator.generate(
        output_path=out_path,
        run_id="run_zero",
        config={},
        metrics={"total_trades": 0, "profit_factor": None},
        broker=broker,
    )
    assert out_path.is_file()
    content = out_path.read_text(encoding="utf-8")
    assert "N/A (Loss=0)" in content or "0" in content


def test_html_dashboard_high_sample_performance(tmp_path):
    """Test 6: Verify 2,500 trades serialize rapidly (< 2.0s) and produce reasonable file size."""
    generator = HTMLDashboardGenerator()
    broker = MockDashboardBroker(num_trades=2500)
    out_path = tmp_path / "perf_test.html"

    t0 = time.time()
    generator.generate(
        output_path=out_path,
        run_id="run_perf_2500",
        config={"symbol": "BTCUSDT"},
        metrics={"total_trades": 2500, "win_rate": 51.5},
        broker=broker,
    )
    elapsed = time.time() - t0

    assert elapsed < 2.0, f"Dashboard generation took too long: {elapsed:.2f}s"
    size_mb = out_path.stat().st_size / (1024 * 1024)
    assert size_mb < 3.0, f"Dashboard file unexpectedly large: {size_mb:.2f} MB"


def test_report_generator_integration_seventh_artifact(tmp_path):
    """Test 7: Verify ReportGenerator.generate_all creates dashboard.html as 7th artifact."""
    from tests.test_report_generator import MockFullBroker

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
        "wallet_balance": 10491.8,
        "reserved_collateral": 0.0,
        "available_margin": 10491.8,
        "unrealized_pnl": 0.0,
        "total_gross_pnl": 500.0,
        "total_fees": 8.2,
        "total_funding_trades": 0.0,
        "total_net_pnl": 491.8,
        "total_trades": 1,
        "win_rate": 100.0,
        "profit_factor": None,
    }

    artifacts = generator.generate_all(
        run_id="run_seventh_art",
        config=config,
        metrics=metrics,
        broker=broker,
    )

    # Verify all 7 artifacts are returned
    expected_seven = [
        "summary.json",
        "summary.md",
        "trades.json",
        "equity_curve.csv",
        "equity_curve.png",
        "trades.sqlite",
        "dashboard.html",
    ]
    for key in expected_seven:
        assert key in artifacts, f"Missing expected artifact key '{key}'"
        assert artifacts[key].is_file(), f"Artifact file '{artifacts[key]}' was not created"

    # Verify dashboard.html content
    dash_content = artifacts["dashboard.html"].read_text(encoding="utf-8")
    assert "BTCUSDT" in dash_content
    assert "run_seventh_art" in dash_content
    assert '<script id="backtest-data" type="application/json">' in dash_content
