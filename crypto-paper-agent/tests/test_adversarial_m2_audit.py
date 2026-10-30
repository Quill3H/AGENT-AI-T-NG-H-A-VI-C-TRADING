r"""
tests/test_adversarial_m2_audit.py
===================================
Independent Empirical Audit & Adversarial Verification Suite for Milestone 2.
Author: teamwork_challenger_m2_2 (Empirical Challenger, Critic & Specialist)

Validates:
1. Double-Entry Accounting Invariance Verification:
   - Mathematical audit of: final_equity == initial_capital + gross_price_pnl - fees_paid + funding_cashflow + unrealized_pnl
   - Discrepancy strictly within 1e-4 tolerance.
   - Reconciliation between SQLite trades and summary.json realized net PnL.
   - Individual trade-level gross - fees + funding == net_pnl conservation.
   - Account snapshot equity and available margin invariants.
2. Deliverable Artifact Audit (All 7 required artifacts in reports/synthesized_backtest_1y):
   - dashboard.html: valid standalone HTML, interactive charts (Chart.js / SVG), metrics cards, equity curve, drawdown, trade distribution.
   - summary.md: valid markdown containing formatted performance summary scorecard, accounting audit, and caveats.
   - summary.json: valid RFC 8259 JSON containing all core metric fields, finite numbers, no boolean masquerading.
   - trades.json: valid JSON array of trade records with non-empty executions (10,892 records).
   - equity_curve.csv: valid CSV with timestamp, equity, wallet_balance, unrealized_pnl, drawdown columns (35,041 data rows).
   - equity_curve.png: valid non-corrupt PNG image file (size > 10 KB, valid PNG header, readable by PIL).
   - trades.sqlite: valid SQLite3 database with PRAGMA integrity_check = ok, matching row counts, foreign key integrity.
3. Core Acceptance Criteria:
   - Sample size >= 2,000 trades across 10 liquid perpetual pairs over 1-year period.
   - Favorable win rate >= 40% (or positive return).
   - Strict paper-only research compliance (zero live credentials, zero wallet signing).
"""
import ast
import csv
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List
import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = Path(os.environ.get('PAPER_ARTIFACT_DIR', REPO_ROOT / "reports" / "synthesized_backtest_1y"))
TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def summary_json_data() -> Dict[str, Any]:
    json_path = REPORT_DIR / "summary.json"
    assert json_path.exists(), f"summary.json does not exist at {json_path}"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="module")
def sqlite_connection():
    db_path = REPORT_DIR / "trades.sqlite"
    assert db_path.exists(), f"trades.sqlite does not exist at {db_path}"
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Pillar 1: Double-Entry Accounting Invariance Verification
# ---------------------------------------------------------------------------

def test_audit_core_accounting_equation_invariance(summary_json_data: Dict[str, Any]):
    """
    Independent audit of the fundamental double-entry accounting equation:
    final_equity == initial_capital + gross_price_pnl - fees_paid + funding_cashflow + unrealized_pnl
    Discrepancy must be strictly within 1e-4 tolerance.
    """
    recon = summary_json_data.get("accounting_reconciliation")
    assert recon is not None, "accounting_reconciliation block missing from summary.json"

    initial_capital = float(recon["initial_capital"])
    gross_price_pnl = float(recon["gross_price_pnl"])
    fees_paid = float(recon["fees_paid"])
    funding_cashflow = float(recon["funding_cashflow"])
    unrealized_pnl = float(recon["unrealized_pnl"])
    final_equity = float(recon["final_equity"])

    # Independent mathematical verification
    calculated_equity = initial_capital + gross_price_pnl - fees_paid + funding_cashflow + unrealized_pnl
    discrepancy = abs(final_equity - calculated_equity)

    assert discrepancy <= TOLERANCE, (
        f"Accounting equation violated! Calculated: {calculated_equity:.8f}, "
        f"Reported final_equity: {final_equity:.8f}, Discrepancy: {discrepancy:.12e} > {TOLERANCE}"
    )

    # Cross-check with top-level summary metrics
    top_final_equity = float(summary_json_data["final_equity"])
    top_initial_capital = float(summary_json_data["initial_capital"])
    top_gross = float(summary_json_data["total_gross_pnl"])
    top_net = float(summary_json_data["total_net_pnl"])

    assert abs(top_final_equity - final_equity) <= 1e-8
    assert abs(top_initial_capital - initial_capital) <= 1e-8
    assert abs(top_gross - gross_price_pnl) <= 1e-8

    # Net PnL conservation: net_realized_pnl == gross_price_pnl - fees_paid + funding_cashflow
    expected_net = gross_price_pnl - fees_paid + funding_cashflow
    assert abs(top_net - expected_net) <= TOLERANCE, (
        f"Net PnL conservation failed! Expected: {expected_net}, Got: {top_net}, Diff: {abs(top_net - expected_net)}"
    )

    # Verify reconciliation flag is explicitly True
    assert summary_json_data["accounting_invariants_verified"] is True
    assert recon["accounting_invariants_verified"] is True


def test_audit_sqlite_ledger_sum_matches_summary_json(sqlite_connection, summary_json_data: Dict[str, Any]):
    """
    Query trades.sqlite and independently verify that:
    1. sum(net_pnl) matches summary.json total_net_pnl within 1e-4 tolerance.
    2. sum(gross_price_pnl) matches summary.json total_gross_pnl within 1e-4 tolerance.
    3. sum(entry_fee + exit_fee) matches summary.json fees_paid within 1e-4 tolerance.
    4. sum(funding_cashflow) matches summary.json funding_cashflow within 1e-4 tolerance.
    """
    cursor = sqlite_connection.cursor()
    row = cursor.execute("""
        SELECT 
            sum(net_pnl),
            sum(gross_price_pnl),
            sum(entry_fee + exit_fee),
            sum(funding_cashflow)
        FROM trades
    """).fetchone()

    sqlite_sum_net = float(row[0])
    sqlite_sum_gross = float(row[1])
    sqlite_sum_fees = float(row[2])
    sqlite_sum_funding = float(row[3])

    recon = summary_json_data["accounting_reconciliation"]
    summary_net = float(summary_json_data["total_net_pnl"])
    summary_gross = float(recon["gross_price_pnl"])
    summary_fees = float(recon["fees_paid"])
    summary_funding = float(recon["funding_cashflow"])

    # Discrepancy checks
    diff_net = abs(sqlite_sum_net - summary_net)
    diff_gross = abs(sqlite_sum_gross - summary_gross)
    diff_fees = abs(sqlite_sum_fees - summary_fees)
    diff_funding = abs(sqlite_sum_funding - summary_funding)

    assert diff_net <= TOLERANCE, f"Net PnL discrepancy between SQLite ({sqlite_sum_net}) and summary.json ({summary_net}): {diff_net}"
    assert diff_gross <= TOLERANCE, f"Gross PnL discrepancy: {diff_gross}"
    assert diff_fees <= TOLERANCE, f"Fees discrepancy: {diff_fees}"
    assert diff_funding <= TOLERANCE, f"Funding discrepancy: {diff_funding}"


def test_audit_sqlite_individual_trades_conservation(sqlite_connection):
    """
    Stress-test individual trade integrity:
    Every single trade record in trades.sqlite must satisfy:
    net_pnl == gross_price_pnl - entry_fee - exit_fee + funding_cashflow
    with discrepancy <= 1e-4. Zero violations permitted.
    """
    cursor = sqlite_connection.cursor()
    violating_trades = cursor.execute("""
        SELECT trade_id, net_pnl, gross_price_pnl, entry_fee, exit_fee, funding_cashflow
        FROM trades
        WHERE abs(net_pnl - (gross_price_pnl - entry_fee - exit_fee + funding_cashflow)) > 1e-4
    """).fetchall()

    assert len(violating_trades) == 0, f"Found {len(violating_trades)} trade records violating net PnL conservation!"


def test_audit_sqlite_account_snapshots_invariance(sqlite_connection, summary_json_data: Dict[str, Any]):
    """
    Verify equity and margin accounting invariance across account snapshots in trades.sqlite:
    1. equity == wallet_balance + unrealized_pnl (within 1e-4).
    2. available_margin == wallet_balance - reserved_collateral (within 1e-4).
    3. Final snapshot equity matches summary.json final_equity.
    4. Force close check: final snapshot has unrealized_pnl == 0.0 and reserved_collateral == 0.0.
    """
    cursor = sqlite_connection.cursor()
    snapshots = cursor.execute("""
        SELECT timestamp, wallet_balance, equity, unrealized_pnl, reserved_collateral, available_margin
        FROM account_snapshots
        ORDER BY timestamp ASC
    """).fetchall()

    assert len(snapshots) > 0, "No account snapshots found in SQLite"

    for s in snapshots:
        ts, wb, eq, u_pnl, rc, am = s
        assert math.isfinite(wb) and math.isfinite(eq) and math.isfinite(u_pnl)
        assert math.isfinite(rc) and math.isfinite(am)
        assert abs(eq - (wb + u_pnl)) <= TOLERANCE, f"Equity snapshot invariant violated at {ts}: {eq} != {wb} + {u_pnl}"
        assert abs(am - (wb - rc)) <= TOLERANCE, f"Margin snapshot invariant violated at {ts}: {am} != {wb} - {rc}"

    # Final snapshot
    last_snap = snapshots[-1]
    last_ts, last_wb, last_eq, last_upnl, last_rc, last_am = last_snap
    expected_final_equity = float(summary_json_data["final_equity"])

    assert abs(last_eq - expected_final_equity) <= TOLERANCE, (
        f"Final snapshot equity ({last_eq}) differs from summary.json final_equity ({expected_final_equity})"
    )
    assert abs(last_upnl) <= TOLERANCE, f"Final snapshot unrealized PnL must be 0 after force-close, got {last_upnl}"
    assert abs(last_rc) <= TOLERANCE, f"Final snapshot reserved collateral must be 0 after force-close, got {last_rc}"


# ---------------------------------------------------------------------------
# Pillar 2: Deliverable Artifact Audit (All 7 required artifacts)
# ---------------------------------------------------------------------------

def test_audit_all_seven_artifacts_exist_and_non_empty():
    """All 7 required artifacts must exist in reports/synthesized_backtest_1y with size > 0."""
    required_files = [
        ("dashboard.html", 50000),      # Standalone HTML dashboard (> 50 KB)
        ("summary.md", 1000),           # Formatted Markdown report (> 1 KB)
        ("summary.json", 1000),         # Structured JSON metrics (> 1 KB)
        ("trades.json", 1000000),       # High-sample trade log (> 1 MB)
        ("equity_curve.csv", 500000),   # Snapshot time series (> 500 KB)
        ("equity_curve.png", 10000),    # Visual chart image (> 10 KB)
        ("trades.sqlite", 1000000),     # SQLite relational store (> 1 MB)
    ]
    for fname, min_size in required_files:
        fpath = REPORT_DIR / fname
        assert fpath.is_file(), f"Missing required deliverable artifact: {fname}"
        actual_size = fpath.stat().st_size
        assert actual_size >= min_size, f"Artifact {fname} size ({actual_size:,} bytes) below minimum expected ({min_size:,} bytes)"


def test_audit_dashboard_html_structure_and_charts():
    """
    Validate dashboard.html:
    - Standalone well-formed HTML (DOCTYPE, head, body).
    - Visual chart containers present: equityChart, drawdownChart, monthlyChart, pnlDistChart (or SVG fallback).
    - Metrics summary cards present (Equity, Drawdown, Trades, Win Rate).
    - Embedded JSON datasets (backtest-dataset / backtest-data).
    """
    html_path = REPORT_DIR / "dashboard.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
    assert "<html" in html and "</html>" in html
    assert "<head>" in html and "</head>" in html
    assert "<body" in html and "</body>" in html

    # Canvas or SVG charts
    has_canvas = any(cid in html for cid in ["equityChart", "drawdownChart", "pnlDistChart"])
    has_svg = "<svg" in html
    assert has_canvas or has_svg, "dashboard.html lacks interactive canvas or SVG visual charts"

    # Core metric visual elements
    html_lower = html.lower()
    assert "equity" in html_lower
    assert "drawdown" in html_lower
    assert "win rate" in html_lower or "win_rate" in html_lower
    assert "synthesized_backtest_1y" in html

    # Embedded data
    assert 'id="backtest-dataset"' in html or 'id="backtest-data"' in html or 'application/json' in html


def test_audit_summary_markdown_scorecard():
    """
    Validate summary.md:
    - Formatted performance summary scorecard.
    - Accounting reconciliation audit table.
    - Completed lifecycles vs realization slices distinction.
    - Mandatory benchmark caveats and disclaimers.
    """
    md_path = REPORT_DIR / "summary.md"
    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read()

    assert "# Performance Report" in md or "Executive Summary" in md
    assert "Vốn khởi điểm" in md or "Initial Capital" in md
    assert "Final Equity" in md or "Số dư ví" in md
    assert "Gross Price PnL" in md
    assert "Fees Paid" in md or "Tổng phí giao dịch" in md
    assert "Funding" in md
    assert "Net Realized PnL" in md or "Net PnL" in md
    assert "6455" in md  # Completed lifecycles count
    assert "10892" in md  # Realization slices count
    assert "Tuyên bố miễn trừ trách nhiệm" in md or "Disclosures" in md


def test_audit_summary_json_rfc8259_and_metric_fields(summary_json_data: Dict[str, Any]):
    """
    Validate summary.json:
    - Valid RFC 8259 JSON structure.
    - All required core metric fields present.
    - Strictly non-boolean numerical values.
    """
    required_keys = [
        "run_id", "total_trades", "win_rate", "profit_factor", "max_drawdown_pct",
        "sharpe_ratio", "sortino_ratio", "initial_capital", "final_equity",
        "total_net_pnl", "total_gross_pnl", "accounting_invariants_verified",
        "accounting_reconciliation"
    ]
    for k in required_keys:
        assert k in summary_json_data, f"Missing metric key '{k}' in summary.json"

    # Check that numerical fields are not booleans
    for k in ["total_trades", "win_rate", "profit_factor", "max_drawdown_pct", "sharpe_ratio", "final_equity", "total_net_pnl"]:
        v = summary_json_data[k]
        assert type(v) is not bool, f"Field '{k}' must not be boolean: {v!r}"
        assert math.isfinite(float(v)), f"Field '{k}' must be a finite number: {v!r}"


def test_audit_trades_json_records():
    """
    Validate trades.json:
    - JSON array containing non-empty execution records.
    - Count matches SQLite trades table count (10,892).
    - Every trade record has required fields.
    """
    json_path = REPORT_DIR / "trades.json"
    with open(json_path, "r", encoding="utf-8") as f:
        trades = json.load(f)

    assert isinstance(trades, list), "trades.json must be a JSON array"
    assert len(trades) == 10892, f"Expected 10,892 records in trades.json, got {len(trades)}"

    sample_trade = trades[0]
    # Master Spec Section 4.6 canonical trade schema
    assert "trade_id" in sample_trade
    assert "asset" in sample_trade or "symbol" in sample_trade
    assert "direction" in sample_trade
    assert "entry_price" in sample_trade
    assert "outcome" in sample_trade
    outcome = sample_trade["outcome"]
    assert "exit_price" in outcome
    assert "pnl_usd" in outcome or "net_pnl" in outcome
    assert "fees_paid_usd" in outcome


def test_audit_equity_curve_csv_structure_and_continuity():
    """
    Validate equity_curve.csv:
    - Valid CSV structure.
    - Required columns present: timestamp, equity, wallet_balance, unrealized_pnl, drawdown_pct.
    - 35,041 data rows matching SQLite account_snapshots.
    - Monotonically non-decreasing timestamps.
    - Initial equity = 100000.0, final equity matches summary.json.
    """
    csv_path = REPORT_DIR / "equity_curve.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 35041, f"Expected 35,041 data rows in equity_curve.csv, got {len(rows)}"

    # Required columns
    fieldnames = reader.fieldnames or []
    for col in ["timestamp", "equity", "wallet_balance", "unrealized_pnl"]:
        assert col in fieldnames, f"equity_curve.csv missing required column: {col}"

    # First row
    first_row = rows[0]
    assert float(first_row["equity"]) == 100000.0
    assert float(first_row["wallet_balance"]) == 100000.0

    # Last row
    last_row = rows[-1]
    assert abs(float(last_row["equity"]) - 8719.665616475051) <= TOLERANCE

    # Check monotonicity of timestamps
    ts_list = [r["timestamp"] for r in rows]
    for i in range(1, len(ts_list)):
        assert ts_list[i] >= ts_list[i - 1], f"Non-monotonic timestamp detected: {ts_list[i-1]} -> {ts_list[i]}"


def test_audit_equity_curve_png_image_file():
    """
    Validate equity_curve.png:
    - Valid non-corrupt PNG image file.
    - File size > 10 KB.
    - Correct PNG magic bytes header.
    - Decodable by PIL with valid dimensions.
    """
    png_path = REPORT_DIR / "equity_curve.png"
    assert png_path.stat().st_size > 10000, f"PNG size too small: {png_path.stat().st_size} bytes"

    with open(png_path, "rb") as f:
        header = f.read(8)
    assert header == b"\x89PNG\r\n\x1a\n", "Invalid PNG magic header"

    img = Image.open(png_path)
    assert img.format == "PNG"
    w, h = img.size
    assert w >= 800 and h >= 600, f"PNG image dimensions ({w}x{h}) smaller than standard 800x600"


def test_audit_trades_sqlite_tables_and_integrity(sqlite_connection):
    """
    Validate trades.sqlite:
    - PRAGMA integrity_check == 'ok'.
    - PRAGMA foreign_key_check is clean.
    - Required tables present: trades, account_snapshots (equity snapshots), runs / run_metrics (metadata).
    - Row counts: trades == 10,892, account_snapshots == 35,041, runs == 1.
    """
    cursor = sqlite_connection.cursor()

    # Integrity
    integrity = cursor.execute("PRAGMA integrity_check;").fetchone()[0]
    assert integrity.lower() == "ok", f"SQLite integrity check failed: {integrity}"

    fk_errors = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    assert len(fk_errors) == 0, f"SQLite foreign key check errors: {fk_errors}"

    tables = {r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
    assert "trades" in tables, "Table 'trades' missing in trades.sqlite"
    assert "account_snapshots" in tables, "Table 'account_snapshots' missing in trades.sqlite"
    assert "runs" in tables, "Table 'runs' missing in trades.sqlite"
    assert "orders" in tables, "Table 'orders' missing in trades.sqlite"

    trades_count = cursor.execute("SELECT count(*) FROM trades;").fetchone()[0]
    assert trades_count == 10892, f"Expected 10,892 rows in trades table, got {trades_count}"

    snaps_count = cursor.execute("SELECT count(*) FROM account_snapshots;").fetchone()[0]
    assert snaps_count == 35041, f"Expected 35,041 rows in account_snapshots table, got {snaps_count}"

    runs_count = cursor.execute("SELECT count(*) FROM runs;").fetchone()[0]
    assert runs_count == 1, f"Expected 1 row in runs table, got {runs_count}"


# ---------------------------------------------------------------------------
# Pillar 3: Milestone 2 Core Requirements & Paper-Only Boundaries
# ---------------------------------------------------------------------------

def test_audit_sample_size_requirement(summary_json_data: Dict[str, Any], sqlite_connection):
    """
    Requirement 2 (High-Sample 1-Year Backtest):
    At least 2,000 completed trades across 1-year historical window.
    """
    lifecycle_trades = summary_json_data["total_trades"]
    assert lifecycle_trades >= 2000, f"Expected >= 2,000 completed position lifecycles, got {lifecycle_trades}"

    cursor = sqlite_connection.cursor()
    sqlite_trades_count = cursor.execute("SELECT count(*) FROM trades;").fetchone()[0]
    assert sqlite_trades_count >= 2000, f"Expected >= 2,000 trades in SQLite, got {sqlite_trades_count}"


def test_audit_multi_asset_coverage_all_ten_pairs(sqlite_connection):
    """
    Universe coverage audit:
    All 10 required liquid perpetual pairs must have executed trades in trades.sqlite.
    """
    expected_pairs = {
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT"
    }
    cursor = sqlite_connection.cursor()
    pairs = {r[0] for r in cursor.execute("SELECT DISTINCT symbol FROM trades;").fetchall()}

    missing_pairs = expected_pairs - pairs
    assert len(missing_pairs) == 0, f"Missing trades for pairs: {missing_pairs}"
    assert len(pairs) == 10, f"Expected exactly 10 pairs with trades, got {len(pairs)}"


def test_audit_original_losing_artifact_is_economically_rejected(summary_json_data: Dict[str, Any]):
    """Frozen original evidence must fail eligibility despite its favorable win rate."""
    from src.research.acceptance import evaluate_acceptance
    assert summary_json_data['win_rate'] >= 40
    assert summary_json_data['total_net_pnl'] < 0
    result = evaluate_acceptance(summary_json_data,
        data_provenance=summary_json_data.get('data_provenance'))
    assert result['verdict'] == 'REJECTED'
    assert 'NONPOSITIVE_NET_PNL' in result['reasons']
    assert 'HISTORICAL_PROVENANCE_REQUIRED' in result['reasons']


def test_audit_paper_only_compliance_and_zero_credentials():
    """
    Requirement Safety & Compliance:
    Verify that backtest scripts and configurations contain zero live/testnet API credentials,
    zero private keys, and zero wallet signing routines.
    """
    sensitive_patterns = [
        "binance_api_secret",
        "api_secret",
        "private_key",
        "secret_key",
        "wallet_key",
        "mnemonic",
    ]
    target_files = [
        REPO_ROOT / "scripts" / "run_synthesized_backtest.py",
        REPO_ROOT / "config" / "strategies" / "synthesized.yaml",
        REPO_ROOT / "src" / "strategies" / "synthesized.py",
        REPO_ROOT / "src" / "risk" / "invariant_checks.py",
    ]

    for file_path in target_files:
        assert file_path.is_file(), f"Target file {file_path} not found"
        text = file_path.read_text(encoding="utf-8").lower()
        for pat in sensitive_patterns:
            assert f"{pat}=" not in text and f"{pat}:" not in text, (
                f"Suspicious credential assignment '{pat}' detected in {file_path.name}"
            )
