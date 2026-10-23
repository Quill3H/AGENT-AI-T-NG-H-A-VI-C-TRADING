"""
src/execution/book_slippage.py
==============================
Forward-paper hook: record the public order book next to each simulated fill, so the fixed
slippage assumption (fees.slippage_pct, 0.03%) can later be compared with what the visible book
would have cost. Recording only: simulated fills keep their current rule and price.

- `walk_book` turns L2 levels into the average price a market order of a given size would get.
- `fill_comparison` sets that next to the simulated fill (bps, signed so positive = worse).
- `OrderBookRecorder` appends one JSON line per simulated fill. Its `fetch_book` is injected; the
  intended source is the public depth endpoint through the key-less fetcher
  (`fetch_public_order_book`). With no `fetch_book` the recorder does nothing, which is the
  backtest case (there is no historical book).

The book is captured when the hook runs, not at the fill instant; both times are written so the
delay can be judged. Nothing here places orders or needs credentials (AGENTS.md).
"""
import datetime as dt
import json
import math
from pathlib import Path

BUY, SELL = "buy", "sell"


def walk_book(levels, quantity):
    """Average fill price for `quantity` taken from `levels` ([[price, size], ...], best first).

    Returns {"avg_price", "filled", "levels_used", "complete"}; complete is False when the
    visible depth is smaller than the order (avg_price then covers the visible part only)."""
    if not (isinstance(quantity, (int, float)) and math.isfinite(quantity) and quantity > 0):
        raise ValueError(f"quantity must be a positive number, got {quantity!r}")
    remaining, cost, used = float(quantity), 0.0, 0
    for price, size in levels:
        price, size = float(price), float(size)
        if not (math.isfinite(price) and math.isfinite(size)) or price <= 0 or size < 0:
            raise ValueError(f"bad book level {price!r}, {size!r}")
        if remaining <= 0:
            break
        take = min(size, remaining)
        if take > 0:
            cost += take * price
            remaining -= take
            used += 1
    filled = float(quantity) - remaining
    return {"avg_price": cost / filled if filled > 0 else None, "filled": filled, "levels_used": used,
            "complete": remaining <= 1e-12 * max(1.0, float(quantity))}


def fill_comparison(book, side, quantity, simulated_price, reference_price):
    """Compare a simulated fill with a walk of the book. `book` is {"bids": [...], "asks": [...]};
    `reference_price` is the price the simulator slipped from (the bar open). Costs are in bps of
    the reference, positive = paid more than the reference (buy) / received less (sell)."""
    if side not in (BUY, SELL):
        raise ValueError(f"side must be {BUY!r} or {SELL!r}, got {side!r}")
    levels = book.get("asks" if side == BUY else "bids") or []
    walk = walk_book(levels, quantity)
    sign = 1.0 if side == BUY else -1.0

    def bps(price):
        return None if price is None else round(sign * (price - reference_price) / reference_price * 1e4, 4)

    best_bid, best_ask = (book.get("bids") or [[None]])[0][0], (book.get("asks") or [[None]])[0][0]
    mid = (float(best_bid) + float(best_ask)) / 2 if best_bid is not None and best_ask is not None else None
    return {
        "side": side, "quantity": float(quantity), "reference_price": float(reference_price),
        "simulated_price": float(simulated_price), "simulated_cost_bps": bps(float(simulated_price)),
        "book_avg_price": walk["avg_price"], "book_cost_bps": bps(walk["avg_price"]),
        "book_mid": mid, "book_half_spread_bps": None if mid is None else round((float(best_ask) - mid) / mid * 1e4, 4),
        "book_levels_used": walk["levels_used"], "book_complete": walk["complete"],
    }


class OrderBookRecorder:
    """Append-only JSONL log of book snapshots beside simulated fills (forward paper only)."""

    def __init__(self, path, fetch_book=None, depth=20, clock=None):
        self.path = Path(path)
        self.fetch_book = fetch_book
        self.depth = int(depth)
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))

    def on_simulated_fill(self, symbol, side, quantity, simulated_price, reference_price, fill_time, event_id=None):
        """Call after the broker books a simulated market fill. Never changes the fill; a failed
        snapshot is logged as such instead of raising into the paper run."""
        if self.fetch_book is None:
            return None
        captured_at = self.clock()
        entry = {"recorded_at": captured_at.isoformat(), "fill_time": str(fill_time), "symbol": symbol,
                 "event_id": event_id, "depth": self.depth}
        try:
            book = self.fetch_book(symbol, self.depth)
            entry["book_time"] = book.get("timestamp")
            entry.update(fill_comparison(book, side, quantity, simulated_price, reference_price))
            entry["status"] = "OK"
        except Exception as exc:  # recording must not stop the paper run
            entry.update({"status": "SNAPSHOT_FAILED", "error": f"{type(exc).__name__}: {exc}"})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, default=str) + "\n")
        return entry


def fetch_public_order_book(symbol, depth=20, exchange=None):
    """Public USD-M depth through the key-less fetcher exchange (network; not used in tests)."""
    if exchange is None:
        from src.data_layer.fetcher import _get_exchange
        exchange = _get_exchange()
    book = exchange.fetch_order_book(symbol, limit=depth)
    return {"bids": book["bids"][:depth], "asks": book["asks"][:depth], "timestamp": book.get("timestamp")}
