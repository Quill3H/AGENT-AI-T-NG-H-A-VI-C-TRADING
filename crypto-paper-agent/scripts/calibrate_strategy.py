"""
scripts/calibrate_strategy.py
=============================
Quant calibration script to optimize SynthesizedStrategy for:
1. Annualized trade velocity >= 2,000 completed trades (170-250 per month across 10 pairs).
2. Net positive profitability and favorable win rate (> 50%).
3. Fully accounting for taker fees (0.05% + 0.05%) and slippage.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_synthesized_backtest import run_universe_backtest

if __name__ == "__main__":
    print("Testing 1-month calibration (2025-01-01 to 2025-02-01)...")
    res = run_universe_backtest(
        start_date="2025-01-01",
        end_date="2025-02-01",
        initial_equity=50000.0,
        output_dir="reports/calibration_test",
        min_trades=150,
    )
    m = res["metrics"]
    print("\n--- Calibration Results ---")
    print(f"Total Trades: {m.get('total_trades')}")
    print(f"Win Rate:     {m.get('win_rate', 0):.2f}%")
    print(f"Net PnL:      ${m.get('net_profit_abs', 0):,.2f}")
    print(f"Return:       {m.get('net_return_pct', 0):.2f}%")
    print(f"Profit Factor:{m.get('profit_factor', 0):.3f}")
    print(f"Max DD:       {m.get('max_drawdown_pct', 0):.2f}%")

