"""
Inspection script to explore the 7 artifacts in reports/synthesized_backtest_1y.
"""
import os
import sys
import json
import sqlite3
import csv
from pathlib import Path

REPORT_DIR = Path(r"d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent\reports\synthesized_backtest_1y")

def inspect():
    print("=== INSPECTING REPORTS DIR ===")
    assert REPORT_DIR.exists(), f"Dir does not exist: {REPORT_DIR}"
    files = list(REPORT_DIR.iterdir())
    for f in sorted(files):
        print(f"File: {f.name}, Size: {f.stat().st_size:,} bytes")

    # 1. Inspect summary.json
    summary_path = REPORT_DIR / "summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
    print("\n=== SUMMARY.JSON KEYS ===")
    print(list(summary.keys()))
    print("Core metrics:")
    for k in [
        "initial_equity", "final_equity", "total_net_pnl", "total_gross_pnl",
        "total_fees_paid", "total_funding_pnl", "total_trades", "win_rate",
        "profit_factor", "max_drawdown_pct", "sharpe_ratio", "sortino_ratio",
        "accounting_invariants_verified"
    ]:
        print(f"  {k}: {summary.get(k)}")
    if "accounting_reconciliation" in summary:
        print("accounting_reconciliation:", summary["accounting_reconciliation"])

    # 2. Inspect trades.sqlite
    sqlite_path = REPORT_DIR / "trades.sqlite"
    conn = sqlite3.connect(sqlite_path)
    c = conn.cursor()
    tables = [row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("\n=== TRADES.SQLITE TABLES ===")
    print(tables)
    for t in tables:
        count = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        schema = c.execute(f"PRAGMA table_info({t})").fetchall()
        cols = [col[1] for col in schema]
        print(f"  Table '{t}': {count:,} rows. Columns: {cols}")

    # Check sum of net_pnl in sqlite
    trade_table = "trades"
    if trade_table in tables:
        sum_net = c.execute(f"SELECT sum(net_pnl) FROM {trade_table}").fetchone()[0]
        sum_gross = c.execute(f"SELECT sum(gross_price_pnl) FROM {trade_table}").fetchone()[0]
        sum_fees = c.execute(f"SELECT sum(entry_fee + exit_fee) FROM {trade_table}").fetchone()[0]
        sum_funding = c.execute(f"SELECT sum(funding_cashflow) FROM {trade_table}").fetchone()[0]
        print(f"\nSQLite Trades aggregates:")
        print(f"  sum(net_pnl): {sum_net}")
        print(f"  sum(gross_price_pnl): {sum_gross}")
        print(f"  sum(entry_fee + exit_fee): {sum_fees}")
        print(f"  sum(funding_cashflow): {sum_funding}")

    # 3. Inspect equity_curve.csv
    csv_path = REPORT_DIR / "equity_curve.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        first_row = next(reader)
    print("\n=== EQUITY_CURVE.CSV ===")
    print(f"Header: {header}")
    print(f"First row: {first_row}")

    # 4. Inspect dashboard.html
    html_path = REPORT_DIR / "dashboard.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html_head = f.read(2000)
    print("\n=== DASHBOARD.HTML (First 500 chars) ===")
    print(html_head[:500])

    # 5. Inspect equity_curve.png
    png_path = REPORT_DIR / "equity_curve.png"
    with open(png_path, "rb") as f:
        png_magic = f.read(8)
    print(f"\nPNG Magic: {png_magic} (Valid PNG: {png_magic == b'\\x89PNG\\r\\n\\x1a\\n'})")

if __name__ == "__main__":
    inspect()
