"""Owner rules 2026-10-21: a stop is never widened; every paper trade gets a journal line."""
import csv
from datetime import timedelta

import pytest

from src.execution.order_models import ExitReason, OrderDirection
from src.report.trade_journal import COLUMNS, journal_rows, write_journal
from tests.test_g0_settlement_lifecycle import T, broker, candle


def test_update_stop_loss_only_tightens():
    b = broker()
    assert not b.update_stop_loss("BTCUSDT", 94.0)  # wider for a long
    assert b.positions["BTCUSDT"].stop_loss_price == 95.0
    assert b.update_stop_loss("BTCUSDT", 97.0)
    assert not b.update_stop_loss("BTCUSDT", 96.0)  # back down is wider again
    assert b.positions["BTCUSDT"].stop_loss_price == 97.0


def test_a_directly_widened_stop_stops_the_run():
    b = broker()
    b.positions["BTCUSDT"].stop_loss_price = 90.0
    with pytest.raises(ValueError, match="STOP_WIDENED"):
        b.process_candle(candle(T + timedelta(minutes=1)))


def test_journal_has_entry_stop_target_exit_and_reason(tmp_path):
    b = broker()
    b.update_stop_loss("BTCUSDT", 97.0)
    b.close_all_positions(100.0, T + timedelta(minutes=2), ExitReason.MANUAL)
    rows = journal_rows(b.trade_history, "test_rule")
    assert len(rows) == 1
    row = rows[0]
    assert row["direction"] == OrderDirection.LONG.value and row["entry_price"] == 100.0
    assert row["initial_stop"] == 95.0 and row["stop_at_exit"] == 97.0
    assert row["exit_reason"] == ExitReason.MANUAL.value and row["exit_time"] > row["entry_time"]
    path = tmp_path / "journal.csv"
    write_journal(rows, path)
    with open(path, encoding="utf-8") as handle:
        read = list(csv.DictReader(handle))
    assert tuple(read[0]) == COLUMNS and read[0]["strategy"] == "test_rule"
