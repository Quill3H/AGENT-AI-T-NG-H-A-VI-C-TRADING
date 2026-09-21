"""G0 behavioral oracles: source settlement identity and completed positions."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.data_layer.fetcher import merge_ohlcv_with_oi_and_funding
from src.execution.order_models import (
    ExitReason,
    OrderDirection,
    OrderRequest,
    Position,
)
from src.execution.paper_broker import PaperBroker
from src.report.metrics import calculate_backtest_metrics, calculate_trade_metrics
from src.strategies.funding_arbitrage import FundingArbitrageSimulator

T = datetime(2024, 1, 1, 7, 59, tzinfo=timezone.utc)


def candle(t, **values):
    return dict(
        symbol="BTCUSDT",
        timeframe="1m",
        open_time=t,
        close_time=t + timedelta(minutes=1),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
        **values,
    )


def broker():
    b = PaperBroker({"fees": {"taker_pct": 0.0, "slippage_pct": 0.0}})
    b.submit_order(
        OrderRequest(
            "BTCUSDT",
            OrderDirection.LONG,
            100.0,
            95.0,
            T,
            requested_quantity=10.0,
            leverage=2.0,
        )
    )
    b.process_candle(candle(T))
    return b


@pytest.mark.parametrize("rate", [0.001, 0.002, 0.0])
def test_broker_reused_or_revised_source_rejected_atomically(rate):
    b = broker()
    source = T + timedelta(minutes=1)
    b.process_candle(
        candle(source, funding_rate=0.001, funding_time=source, funding_readiness=True)
    )
    before = deepcopy(b.__dict__)
    with pytest.raises(ValueError, match="FUNDING_SOURCE_EVENT_MISMATCH"):
        b.process_candle(
            candle(
                source + timedelta(hours=8),
                funding_rate=rate,
                funding_time=source,
                funding_readiness=True,
            )
        )
    assert b.wallet_balance == before["wallet_balance"] == 9999.0
    assert b.funding_history == before["funding_history"]
    assert b.positions == before["positions"]
    assert b._settled_funding_keys == before["_settled_funding_keys"]
    assert (
        b.last_candle_open_time_per_symbol == before["last_candle_open_time_per_symbol"]
    )
    assert b.circuit_breaker.__dict__ == before["circuit_breaker"].__dict__
    for name in (
        "trade_history",
        "order_history",
        "pending_orders",
        "account_snapshots",
        "current_batch_open_time",
        "symbols_in_current_batch",
        "last_mark_prices",
        "current_time",
        "pending_closes",
    ):
        assert getattr(b, name) == before[name]


def basket_frame():
    idx = pd.to_datetime(
        [
            "2024-01-01T00:00Z",
            "2024-01-01T01:00Z",
            "2024-01-01T08:00Z",
            "2024-01-01T16:00Z",
        ]
    )
    return pd.DataFrame(
        dict(
            spot_close=100.0,
            perp_close=100.0,
            observed_funding_rate=0.0002,
            observed_funding_time=idx,
            funding_rate=0.0002,
            funding_time=idx,
            funding_readiness=True,
        ),
        index=idx,
    )


@pytest.mark.parametrize("rate", [0.0002, 0.0003, 0.0])
def test_basket_reused_or_revised_source_rejected_before_simulation(rate):
    f = basket_frame()
    f.loc[f.index[-1], "funding_time"] = f.index[-2]
    f.loc[f.index[-1], "funding_rate"] = rate
    sim = FundingArbitrageSimulator({"fees": {"taker_pct": 0.0, "slippage_pct": 0.0}})
    with pytest.raises(ValueError, match="FUNDING_SOURCE_EVENT_MISMATCH"):
        sim.simulate(f, 10000.0, 4000.0)
    assert sim.cb.current_timestamp is None


def test_exact_distinct_zero_settlement_remains_valid():
    b = broker()
    source = T + timedelta(minutes=1)
    for ts in (source, source + timedelta(hours=8)):
        b.process_candle(
            candle(ts, funding_rate=0.0, funding_time=ts, funding_readiness=True)
        )
    assert len(b.funding_history) == 2
    assert b.wallet_balance == 10000.0
    assert calculate_trade_metrics(b.trade_history)["total_trades"] == 0
    b.verify_accounting_invariants()


@pytest.mark.parametrize("path", ["full", "force", "partial_final", "breaker"])
def test_direct_position_lifecycle_identity_across_close_paths(path):
    b = PaperBroker(
        {
            "fees": {"taker_pct": 0.0, "slippage_pct": 0.0},
            "circuit_breakers": {
                "daily_loss_limit_pct": 0.00001 if path == "breaker" else 0.05
            },
        }
    )
    b.positions["BTCUSDT"] = Position(
        position_id="DIRECT",
        symbol="BTCUSDT",
        direction=OrderDirection.LONG,
        quantity=10.0,
        entry_price=100.0,
        initial_margin=500.0,
        isolated_collateral=500.0,
        leverage=2.0,
        stop_loss_price=95.0,
        liquidation_price=50.0,
        opened_at=T,
    )
    if path in ("partial_final", "breaker"):
        b._execute_exit(
            b.positions["BTCUSDT"], 99.0, T, ExitReason.MANUAL, quantity=4.0
        )
    if path == "force":
        b.finalize(T, force_close=True)
    elif path != "breaker":
        b.close_all_positions(100.0, T, ExitReason.MANUAL)
    assert not b.positions
    rows = b.trade_history
    assert len(rows) == (2 if path in ("partial_final", "breaker") else 1)
    assert {t.metadata["lifecycle_id"] for t in rows} == {"DIRECT"}
    assert {t.metadata["lifecycle_quantity"] for t in rows} == {10.0}
    assert sum(t.metadata["lifecycle_complete"] for t in rows) == 1
    assert calculate_trade_metrics(rows)["total_trades"] == 1
    b.verify_accounting_invariants()


def test_merge_observation_is_not_missing_settlement_readiness():
    idx = pd.to_datetime(
        ["2024-01-01T08:00Z", "2024-01-01T15:59Z", "2024-01-01T16:00Z"]
    )
    f = pd.DataFrame({"close": [100.0] * 3}, index=idx)
    funding = pd.DataFrame({"funding_rate": [0.001]}, index=idx[:1])
    merged = merge_ohlcv_with_oi_and_funding(f, pd.DataFrame(), funding, "1m", {})
    assert merged.funding_rate.iloc[-1] == 0.001  # still a historical observation
    assert bool(merged.funding_readiness.iloc[0])
    assert not bool(merged.funding_readiness.iloc[-1])  # no source event at16:00


def test_metrics_group_explicit_position_identity_before_classification():
    rows = [
        {"position_id": p, "net_pnl": n}
        for p, n in [("A", 10.0), ("A", 10.0), ("A", -30.0), ("B", 5.0)]
    ]
    result = calculate_trade_metrics(rows)
    assert result["total_trades"] == 2
    assert result["win_rate"] == 50.0
    assert result["expectancy_usd"] == -2.5
    assert result["total_net_pnl"] == -5.0
    assert result["sqn"] == pytest.approx(-0.3333)


def partial_broker(finish):
    b = PaperBroker({"fees": {"taker_pct": 0.0, "slippage_pct": 0.0}})
    b.submit_order(
        OrderRequest(
            "BTCUSDT",
            OrderDirection.LONG,
            100.0,
            95.0,
            T,
            requested_quantity=10.0,
            leverage=2.0,
            partial_exits=[[1.5, 0.4], [3.0, 0.3]],
        )
    )
    bar = candle(T)
    bar.update(high=120.0, close=118.0)
    b.process_candle(bar)
    if finish:
        b.finalize(T + timedelta(minutes=1), force_close=True)
    return b


def report_metrics(b):
    return calculate_backtest_metrics(
        b, {}, T, T + timedelta(minutes=1), 1, 1, force_close=not bool(b.positions)
    )


def test_three_slices_one_lifecycle_with_sum_risk_not_mean_slice_r():
    b = partial_broker(True)
    assert len(b.trade_history) == 3
    result = report_metrics(b)
    assert result["total_trades"] == result["long_trades_count"] == 1
    assert result["win_rate"] == 100.0
    assert result["total_net_pnl"] == 129.0  # 4*7.5 + 3*15 + 3*18
    assert result["expectancy_usd"] == 129.0
    assert result["expectancy_r"] == 2.58  # 129 / original risk50
    assert result["sqn"] is None
    assert result["realization_slices"]["total_trades"] == 3
    assert result["accounting_reconciliation"]["wallet_difference"] == 0.0
    assert result["benchmark_comparison"]["status"] == "ABOVE_EXPECTED_RANGE"


def test_unfinished_position_cash_reconciles_but_is_not_completed_trade():
    b = partial_broker(False)
    result = report_metrics(b)
    assert result["total_trades"] == result["long_trades_count"] == 0
    assert result["expectancy_usd"] == 0.0
    assert (
        result["total_net_pnl"] == 75.0
    )  # realized partials, separate from expectancy
    assert result["unrealized_pnl"] == 54.0
    assert result["realization_slices"]["total_trades"] == 2
    assert result["accounting_reconciliation"]["equity_difference"] == 0.0
    assert result["benchmark_comparison"]["status"] == "INSUFFICIENT_DATA"


@pytest.mark.parametrize(
    "change", ["missing_slice", "duplicate_slice", "bad_terminal", "bad_quantity"]
)
def test_corrupt_lifecycle_records_fail_closed(change):
    rows = deepcopy(partial_broker(True).trade_history)
    if change == "missing_slice":
        rows.pop(0)
    elif change == "duplicate_slice":
        rows.insert(0, deepcopy(rows[0]))
    elif change == "bad_terminal":
        rows[0].metadata["lifecycle_complete"] = True
    else:
        rows[-1].metadata["lifecycle_quantity"] = 123.0
    with pytest.raises(ValueError, match="[Ll]ifecycle"):
        calculate_trade_metrics(rows)


def test_legacy_partial_without_identity_is_not_assumed_complete():
    with pytest.raises(ValueError, match="[Ll]ifecycle"):
        calculate_trade_metrics([{"net_pnl": 10.0, "metadata": {"partial_exit": True}}])


@pytest.mark.parametrize("finish,completed", [(True, 1), (False, 0)])
def test_report_persists_raw_slices_and_labels_completed_positions(
    tmp_path, finish, completed
):
    from src.report.generator import ReportGenerator

    b = partial_broker(finish)
    metrics = report_metrics(b)
    ReportGenerator(base_reports_dir=tmp_path).generate_all(
        run_id="g0",
        broker=b,
        metrics=metrics,
        config={},
    )
    folder = tmp_path / "g0"
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_trades"] == completed
    with sqlite3.connect(folder / "trades.sqlite") as db:
        assert db.execute("SELECT total_trades FROM runs").fetchone()[0] == completed
        rows = db.execute("SELECT metadata_json FROM trades").fetchall()
        assert len(rows) == len(b.trade_history)
        assert sum(json.loads(r[0])["lifecycle_complete"] for r in rows) == completed
    text = (folder / "summary.md").read_text(encoding="utf-8")
    assert "Completed Position Lifecycles" in text
    assert "Realization Slices" in text


def test_completion_order_drives_streak_not_first_partial_time():
    rows = [
        {"position_id": "A", "net_pnl": 10.0, "exit_time": T},
        {"position_id": "B", "net_pnl": 5.0, "exit_time": T + timedelta(minutes=1)},
        {"position_id": "C", "net_pnl": 5.0, "exit_time": T + timedelta(minutes=2)},
        {"position_id": "A", "net_pnl": -30.0, "exit_time": T + timedelta(minutes=3)},
    ]
    result = calculate_trade_metrics(rows)
    assert result["total_trades"] == 3
    assert result["max_consecutive_wins"] == 2
    assert result["expectancy_usd"] == pytest.approx(-3.3333)


def test_legacy_lifecycle_identity_is_scoped_to_run_and_symbol():
    rows = [
        {"position_id": "P", "run_id": run, "symbol": symbol, "net_pnl": pnl}
        for run, symbol, pnl in [
            ("a", "BTCUSDT", 5.0),
            ("a", "ETHUSDT", -3.0),
            ("b", "BTCUSDT", 1.0),
        ]
    ]
    assert calculate_trade_metrics(rows)["total_trades"] == 3


def test_external_cwd_replay_cli_emits_nonempty_both_sides_and_checksums(tmp_path):
    import hashlib

    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_g0_replay.py"
    output = tmp_path / "artifacts"
    run = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads((output / "g0_replay.json").read_text(encoding="utf-8"))
    assert set(result["cases"]) == {"LONG", "SHORT"}
    for case in result["cases"].values():
        assert case["completed_trades"] == 1
        assert case["realization_slices"] == 3
        assert case["accounting_verified"] is True
    assert result["funding"]["reused_source_rejected"] is True
    assert result["funding"]["distinct_settlement_cashflow"] == pytest.approx(1.6)
    checksums = json.loads((output / "checksums.json").read_text(encoding="utf-8"))
    for name, digest in checksums.items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


def test_public_preparation_marks_missing_boundary_unready_offline(
    tmp_path, monkeypatch
):
    import importlib.util
    from io import BytesIO
    from zipfile import ZipFile

    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_public_research_sample.py"
    )
    spec = importlib.util.spec_from_file_location("g0_sample_preparation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    idx = pd.date_range("2024-01-02", periods=1440, freq="min", tz="UTC")
    candles = "\n".join(f"{ts.value // 1000000},100,101,99,100,1" for ts in idx)
    funding = "calc_time,last_funding_rate\n" + "\n".join(
        f"{ts.value // 1000000},0.001" for ts in idx[[0, 480]]
    )

    def archive_response(url, timeout):
        buf = BytesIO()
        with ZipFile(buf, "w") as z:
            z.writestr("recorded.csv", funding if "fundingRate" in url else candles)
        buf.seek(0)
        return buf

    monkeypatch.setattr(module, "urlopen", archive_response)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(path), "--output", str(tmp_path), "--start", "2024-01-02", "--days", "1"],
    )
    assert module.main() == 0
    for name in ("1m", "5m", "15m", "4h", "basket"):
        data = pd.read_parquet(tmp_path / f"{name}.parquet")
        assert not bool(data.loc[idx[960], "funding_readiness"])
        assert bool(data.loc[idx[480], "funding_readiness"])
