"""Forward-paper order-book recording (src/execution/book_slippage.py); offline."""
import datetime as dt
import json

import pytest

from src.execution import book_slippage as bs

BOOK = {"bids": [[99.9, 1.0], [99.8, 2.0]], "asks": [[100.1, 1.0], [100.3, 2.0]], "timestamp": 1}


def test_walk_book_averages_across_levels_and_flags_thin_books():
    assert bs.walk_book(BOOK["asks"], 0.5) == {"avg_price": 100.1, "filled": 0.5, "levels_used": 1, "complete": True}
    two = bs.walk_book(BOOK["asks"], 2.0)
    assert two["avg_price"] == pytest.approx(100.2) and two["levels_used"] == 2 and two["complete"]
    thin = bs.walk_book(BOOK["asks"], 5.0)
    assert not thin["complete"] and thin["filled"] == 3.0
    with pytest.raises(ValueError):
        bs.walk_book(BOOK["asks"], 0)


def test_fill_comparison_signs_costs_so_positive_is_worse_for_both_sides():
    buy = bs.fill_comparison(BOOK, "buy", 2.0, simulated_price=100.03, reference_price=100.0)
    assert buy["simulated_cost_bps"] == pytest.approx(3.0) and buy["book_cost_bps"] == pytest.approx(20.0)
    sell = bs.fill_comparison(BOOK, "sell", 1.0, simulated_price=99.97, reference_price=100.0)
    assert sell["simulated_cost_bps"] == pytest.approx(3.0) and sell["book_cost_bps"] == pytest.approx(10.0)
    assert buy["book_mid"] == pytest.approx(100.0) and buy["book_half_spread_bps"] == pytest.approx(10.0)


def test_recorder_appends_without_touching_the_fill_and_survives_a_failed_snapshot(tmp_path):
    clock = lambda: dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc)
    path = tmp_path / "books.jsonl"
    assert bs.OrderBookRecorder(path, clock=clock).on_simulated_fill("BTCUSDT", "buy", 1, 100.03, 100, "t") is None
    assert not path.exists()  # backtest: no book source, nothing written
    calls = []
    ok = bs.OrderBookRecorder(path, fetch_book=lambda s, d: calls.append((s, d)) or BOOK, clock=clock)
    ok.on_simulated_fill("BTCUSDT", "buy", 1.0, 100.03, 100.0, "2026-10-23T00:00:00Z", event_id="e1")

    def down(symbol, depth):
        raise TimeoutError("no network")

    bs.OrderBookRecorder(path, fetch_book=down, clock=clock).on_simulated_fill("BTCUSDT", "sell", 1.0, 99.97, 100.0, "t")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert calls == [("BTCUSDT", 20)]
    assert rows[0]["status"] == "OK" and rows[0]["simulated_price"] == 100.03 and rows[0]["event_id"] == "e1"
    assert rows[1]["status"] == "SNAPSHOT_FAILED" and "TimeoutError" in rows[1]["error"]


def test_public_fetch_uses_the_given_exchange_and_trims_depth():
    class Exchange:
        def fetch_order_book(self, symbol, limit):
            return {"bids": [[1, 1]] * 30, "asks": [[2, 1]] * 30, "timestamp": 5}

    book = bs.fetch_public_order_book("BTC/USDT:USDT", 20, exchange=Exchange())
    assert len(book["bids"]) == len(book["asks"]) == 20 and book["timestamp"] == 5
