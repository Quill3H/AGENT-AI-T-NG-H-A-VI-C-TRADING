#!/usr/bin/env python3
"""Where do a strategy's losses come from? Paper trades on development data, grouped by the
market state at entry (docs/research/2026-10-18-round8-plan.md).

  python scripts/analyze_losses.py --data-dir <dir> --strategy swing_ema_pullback --output losses.json

Tags at entry, from closed bars only:
- trend: the coin's daily close vs its 200-day SMA (up / down);
- side: long or short, and whether it agrees with that trend;
- volatility: ATR(14)/close of the daily bars, split at the development median;
- exit: stop, take profit, strategy exit, ...;
- fees and funding as a share of gross P&L.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_vision_backtest  # noqa: E402
from src.data_layer.vision_dataset import load_bars  # noqa: E402
from src.strategies.indicator_suite import atr  # noqa: E402

DEV = ("2021-01-01", "2023-12-31")
CORE = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def daily_state(data_dir, symbol):
    """Per-day trend and volatility, shifted one day so a trade only sees closed days."""
    daily = load_bars(data_dir, "1d", symbol=symbol)
    sma = daily["close"].rolling(200).mean()
    state = pd.DataFrame({"trend_up": daily["close"] > sma, "atr_pct": atr(daily, 14) / daily["close"],
                          "ready": sma.notna()}, index=daily.index)
    return state.shift(1)


def trade_rows(data_dir, strategy, symbol, start, end, overrides):
    broker = run_vision_backtest.run(data_dir, strategy, start, end, overrides, summarize=False, symbol=symbol)
    state = daily_state(data_dir, symbol)
    rows = []
    for t in broker.trade_history:
        day = pd.Timestamp(t.entry_time).tz_convert("UTC").normalize()
        s = state.loc[:day].iloc[-1] if len(state.loc[:day]) else None
        long = str(getattr(t.direction, "value", t.direction)).upper() in ("LONG", "BUY")
        rows.append({
            "symbol": symbol, "entry_time": str(t.entry_time), "long": long, "net_pnl": t.net_pnl,
            "gross": t.gross_price_pnl, "fees": t.entry_fee + t.exit_fee, "funding": t.funding_cashflow,
            "r": t.realized_r_multiple, "exit": str(getattr(t.exit_reason, "value", t.exit_reason)),
            "hours": (pd.Timestamp(t.exit_time) - pd.Timestamp(t.entry_time)).total_seconds() / 3600.0,
            "trend_up": None if s is None or not s["ready"] else bool(s["trend_up"]),
            "atr_pct": None if s is None else float(s["atr_pct"]),
        })
    return rows


def group(frame, column):
    out = {}
    for key, part in frame.groupby(column, dropna=False):
        out[str(key)] = {"trades": len(part), "net_usd": round(part["net_pnl"].sum(), 1),
                         "win_pct": round(100.0 * (part["net_pnl"] > 0).mean(), 1),
                         "fees_usd": round(part["fees"].sum(), 1), "mean_r": round(part["r"].mean(), 3)}
    return out


def analyze(rows):
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {"trades": 0}
    median = frame["atr_pct"].median()
    frame["with_trend"] = frame.apply(lambda r: None if r["trend_up"] is None else r["long"] == r["trend_up"], axis=1)
    frame["volatility"] = frame["atr_pct"].map(lambda v: "high" if v > median else "low")
    frame["year"] = frame["entry_time"].str[:4]
    gross = frame["gross"].sum()
    return {
        "trades": len(frame), "net_usd": round(frame["net_pnl"].sum(), 1), "gross_usd": round(gross, 1),
        "fees_usd": round(frame["fees"].sum(), 1), "funding_usd": round(frame["funding"].sum(), 1),
        "atr_pct_median": round(float(median), 4),
        "by_with_trend": group(frame, "with_trend"), "by_side": group(frame, "long"),
        "by_volatility": group(frame, "volatility"), "by_exit": group(frame, "exit"),
        "by_symbol": group(frame, "symbol"), "by_year": group(frame, "year"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = []
    for symbol in CORE:
        rows += trade_rows(args.data_dir, args.strategy, symbol, *DEV, args.config)
    result = {"strategy": args.strategy, "window": DEV, "config": args.config, **analyze(rows)}
    Path(args.output).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=1, default=str))


if __name__ == "__main__":
    main()
