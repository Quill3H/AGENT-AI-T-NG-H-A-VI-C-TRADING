"""
src/report/trade_journal.py
===========================
Owner rule 2026-10-21: a journal line for every paper trade (entry, stop, target, exit and
why), so each forward week can be reviewed trade by trade. One line per exit slice; partial
exits of one position share its `position_id`.
"""
import csv

COLUMNS = ("strategy", "symbol", "position_id", "direction", "entry_time", "entry_price", "initial_stop",
           "stop_at_exit", "take_profit", "exit_time", "exit_price", "exit_reason", "quantity", "fees_usd",
           "funding_usd", "net_pnl_usd", "r_multiple")


def journal_rows(trades, strategy):
    rows = []
    for t in trades:
        meta = t.metadata or {}
        rows.append({
            "strategy": strategy,
            "symbol": t.symbol,
            "position_id": meta.get("lifecycle_id", t.trade_id),
            "direction": getattr(t.direction, "value", str(t.direction)),
            "entry_time": t.entry_time.isoformat(),
            "entry_price": t.entry_price,
            "initial_stop": t.initial_stop_loss_price,
            "stop_at_exit": meta.get("stop_at_exit"),
            "take_profit": t.take_profit_levels[0] if t.take_profit_levels else None,
            "exit_time": t.exit_time.isoformat(),
            "exit_price": t.exit_price,
            "exit_reason": getattr(t.exit_reason, "value", str(t.exit_reason)),
            "quantity": t.quantity,
            "fees_usd": round(t.entry_fee + t.exit_fee, 6),
            "funding_usd": round(t.funding_cashflow, 6),
            "net_pnl_usd": round(t.net_pnl, 6),
            "r_multiple": None if t.realized_r_multiple is None else round(t.realized_r_multiple, 4),
        })
    return sorted(rows, key=lambda r: (r["entry_time"], r["symbol"], r["exit_time"]))


def write_journal(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
