"""ML evidence census (scripts/ml_evidence_census.py): data guard, labels and power formulas."""
import numpy as np
import pandas as pd
import pytest

from scripts import ml_evidence_census as census
from src.research import ledger

SUMMARY = {"total_return_pct": 1.0, "max_drawdown_pct": 1.0, "completed_trades": 1}


def _records(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(9, "final", "I1", "s", "A", "2021-01-01", "2026-09-30", ["XRPUSDT"], "5%", SUMMARY, path=path)
    return ledger.load(path)


def test_guard_refuses_reserved_coins_fresh_days_and_unspent_coins(tmp_path):
    records = _records(tmp_path)
    census.guard_seen("XRPUSDT", "2026-09-30", records)
    for symbol, end in (("ALGOUSDT", "2026-09-30"), ("XRPUSDT", "2026-10-18"), ("MATICUSDT", "2026-09-30")):
        with pytest.raises(ValueError):
            census.guard_seen(symbol, end, records)


def _frame(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h", tz="UTC")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c, "volume": 1.0}, index=idx)


def test_triple_barrier_fills_next_open_and_charges_costs_and_funding():
    closes = [100.0] * 120 + [104.0] + [104.0 + 2 * i for i in range(1, 20)]
    frame = _frame(closes)
    funding = pd.DataFrame({"funding_rate": [0.001]}, index=pd.DatetimeIndex([frame.index[122]], name="timestamp"))
    events, n = census.triple_barrier(frame, funding, k=2.0, horizon=6)
    first = events.iloc[0]
    assert first["start"] == 121  # signal on the 104 jump's close, filled at the next bar's open
    assert first["net_long"] == pytest.approx(first["gross"] - census.COST_ROUND_TRIP - 0.001)
    assert first["net_short"] == pytest.approx(-first["gross"] - census.COST_ROUND_TRIP + 0.001)
    assert 0 < census.uniqueness(events, n).min() <= 1


def test_power_formulas_match_known_values():
    assert census.n_for_accuracy(0.52) == 3863
    assert census.n_for_ic(0.05) == 2472
    assert census.min_track_record(0.1, skew=0.0, kurt=3.0) == pytest.approx(1 + (1 + 0.005) * (1.6449 / 0.1) ** 2, abs=1)
    assert census.expected_max_sr(100, 1 / 1095) > census.expected_max_sr(10, 1 / 1095)
