#!/usr/bin/env python3
"""One-off: load rounds 3-6 of the futures research into the research ledger (paper only).

  python scripts/ledger_backfill.py --results-dir <binance-vision-usdm dir>

Rounds 1-2 left no per-run result files; their final data is recorded as spent so later
rounds cannot reuse it. Results come from the round documents in docs/research/.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.research import ledger  # noqa: E402

CORE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
DEV, FULL, B = ("2021-01-01", "2023-12-31"), ("2021-01-01", "2026-09-30"), ("2024-01-01", "2026-09-30")
# (round, file, candidate key, strategy, frozen commit, {label regex: (stage, window, symbols)})
SOURCES = [
    (3, "results_indicator_final.json", "I5", "adx_donchian", "355b5dd", {
        r"^validation": ("final", B, CORE),
        r"^holdout BNB": ("final", FULL, ["BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"])}),
    (4, "results_new_directions_final_N2.json", "N2", "regime_switch", "6449d41", {
        r"^final A: ": ("final", FULL, ["LINKUSDT", "AVAXUSDT", "LTCUSDT", "DOTUSDT"]),
        r"^final B": ("final", B, CORE)}),
    (5, "results_trading_styles_final_W1.json", "W1", "swing_ema_pullback", "ee36faf", {
        r"^A: .*risk (\S+)$": ("final", FULL, ["ETCUSDT", "ATOMUSDT", "NEARUSDT", "FILUSDT"]),
        r"^B: .*risk (\S+)$": ("final", B, CORE)}),
    (6, "results_candles_final_K3-rr2.json", "K3-rr2", "candle_continuation", "fd9096f", {
        r"^A: .*risk (\S+)$": ("final", FULL, ["XLMUSDT", "BCHUSDT", "UNIUSDT", "AAVEUSDT"]),
        r"^B: .*risk (\S+)$": ("final", B, CORE)}),
    (6, "results_candles_whatif_x20.json", "K3-rr2", "candle_continuation", "fd9096f", {
        r"^x20/x5 A: .*risk (\S+)$": ("final-whatif", FULL, ["XLMUSDT", "BCHUSDT", "UNIUSDT", "AAVEUSDT"]),
        r"^x20/x5 B: .*risk (\S+)$": ("final-whatif", B, CORE)}),
]
DEV_SOURCES = [(5, "results_trading_styles_dev.json"), (6, "results_candles_dev.json")]
SPENT_EARLY = [(1, "donchian_trend", ("2024-01-01", "2025-12-31"), CORE), (2, "carry/trend", ("2026-01-01", "2026-09-30"), CORE)]
LESSONS = [
    (1, "A daily Donchian trend system chosen on 2021-23 lost on 2024-25; 20-50% a month is not realistic."),
    (2, "Funding carry made money only when funding was high; in 2026 it took no trades."),
    (3, "Indicator systems that win big in development (mostly SOL 2021) fail on later data."),
    (4, "One coin (AVAX) carried a +183% holdout; returns spread over few coins are luck, not edge."),
    (5, "Every scalp (1m-1h) lost after fees, even with 55% wins; 4h EMA pullback was weakly positive at 1-2% risk."),
    (6, "Fast take-profits raise the win rate but lose money; 4h continuation patterns with a 2R target were "
        "small but positive on unseen coins with very few trades. x20 leverage cut BTC/ETH trades because "
        "liquidation sits about 5% away."),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()
    if ledger.load():
        raise SystemExit("ledger already has records; backfill runs once")
    directory = Path(args.results_dir)
    for round_id, strategy, window, symbols in SPENT_EARLY:
        ledger.record(round_id, "final", "-", strategy, "spent final data (no per-run file)", *window, symbols, "-", {})
    for round_id, name in DEV_SOURCES:
        for label, summary in json.loads((directory / name).read_text()).items():
            if isinstance(summary, dict) and "total_return_pct" in summary:
                key, risk = label.split(" risk ")[0], label.split(" risk ")[-1].split(",")[0]
                stage = "dev" if "costs" not in label else "dev-costs"
                ledger.record(round_id, stage, key, "", label, *DEV, CORE, risk, summary)
    for round_id, name, key, strategy, commit, patterns in SOURCES:
        path = directory / name
        if not path.is_file():
            print("missing", name)
            continue
        for label, summary in json.loads(path.read_text()).items():
            for pattern, (stage, window, symbols) in patterns.items():
                match = re.search(pattern, label)
                if match and isinstance(summary, dict):
                    risk = match.group(1) if match.groups() else ("10%" if round_id in (3, 4) else "-")
                    ledger.record(round_id, stage, key, strategy, label, *window, symbols, risk, summary, frozen_commit=commit)
    for round_id, lesson in LESSONS:
        ledger.note(round_id, lesson)
    print(len(ledger.load()), "records")


if __name__ == "__main__":
    main()
