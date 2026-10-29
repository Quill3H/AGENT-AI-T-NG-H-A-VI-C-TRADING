"""
tests/forensic_auditor_m2_checks.py
====================================
Comprehensive forensic audit script executed by teamwork_auditor_m2.
Conducts rigorous empirical checks across:
1. Check 1 — Code Authenticity & Zero Hardcoding
2. Check 2 — Paper-Only Boundary Audit (Zero Credentials, Zero Live Orders, Zero Network)
3. Check 3 — Genuine Multi-Asset Simulation Verification
4. Check 4 — Test Suite Authenticity (Zero Tautological Assertions)
5. Check 5 — Empirical Math & Double-Entry Invariance Verification
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
import socket
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ForensicAuditRunner:
    def __init__(self):
        self.repo_root = REPO_ROOT
        self.reports_dir = self.repo_root / "reports" / "synthesized_backtest_1y"
        self.results: Dict[str, Dict[str, Any]] = {}

    def log_result(self, check_name: str, passed: bool, details: Dict[str, Any]):
        self.results[check_name] = {
            "verdict": "PASS" if passed else "FAIL",
            "passed": passed,
            "details": details,
        }

    # =========================================================================
    # CHECK 1: Code Authenticity & Zero Hardcoding
    # =========================================================================
    def audit_check_1_code_authenticity(self):
        print("\n" + "=" * 80)
        print("RUNNING CHECK 1: Code Authenticity & Zero Hardcoding Audit")
        print("=" * 80)

        target_files = [
            self.repo_root / "scripts" / "run_synthesized_backtest.py",
            self.repo_root / "src" / "strategies" / "synthesized.py",
            self.repo_root / "src" / "risk" / "invariant_checks.py",
        ]

        suspicious_constants = [
            6455,          # Completed trades count
            49.2,          # Win rate percent
            -91280.33,     # Total net PnL
            8719.67,       # Final equity
            -46319.86,     # Gross price PnL
            44916.96,      # Total fees
        ]

        found_hardcoded_literals = []

        for fpath in target_files:
            if not fpath.is_file():
                found_hardcoded_literals.append(f"Missing file: {fpath}")
                continue

            with open(fpath, "r", encoding="utf-8") as f:
                code_text = f.read()

            parsed = ast.parse(code_text, filename=str(fpath))

            # Inspect all Constant nodes in AST
            for node in ast.walk(parsed):
                if isinstance(node, ast.Constant):
                    val = node.value
                    if isinstance(val, (int, float)):
                        for susp in suspicious_constants:
                            if abs(val - susp) < 0.01:
                                found_hardcoded_literals.append({
                                    "file": str(fpath.relative_to(self.repo_root)),
                                    "line": getattr(node, "lineno", -1),
                                    "constant": val,
                                    "matched_suspicious": susp,
                                })

        # Check summary.json correspondence to trades.json and trades.sqlite
        summary_json_path = self.reports_dir / "summary.json"
        trades_json_path = self.reports_dir / "trades.json"
        trades_sqlite_path = self.reports_dir / "trades.sqlite"

        reconciliation_checks = {}
        if summary_json_path.is_file() and trades_json_path.is_file() and trades_sqlite_path.is_file():
            with open(summary_json_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)

            with open(trades_json_path, "r", encoding="utf-8") as f:
                trades_data = json.load(f)

            with sqlite3.connect(trades_sqlite_path) as conn:
                cur = conn.cursor()
                sqlite_trade_count = cur.execute("SELECT count(*) FROM trades;").fetchone()[0]
                sqlite_sum_gross = cur.execute("SELECT sum(gross_price_pnl) FROM trades;").fetchone()[0] or 0.0
                sqlite_sum_entry_fee = cur.execute("SELECT sum(entry_fee) FROM trades;").fetchone()[0] or 0.0
                sqlite_sum_exit_fee = cur.execute("SELECT sum(exit_fee) FROM trades;").fetchone()[0] or 0.0
                sqlite_sum_funding = cur.execute("SELECT sum(funding_cashflow) FROM trades;").fetchone()[0] or 0.0
                sqlite_sum_net = cur.execute("SELECT sum(net_pnl) FROM trades;").fetchone()[0] or 0.0

            trades_json_count = len(trades_data)
            json_sum_net = sum(float(t.get("outcome", {}).get("pnl_usd", 0.0)) for t in trades_data)
            json_sum_fees = sum(float(t.get("outcome", {}).get("fees_paid_usd", 0.0)) for t in trades_data)

            # Check trade counts match
            match_counts = (sqlite_trade_count == trades_json_count)
            # Check sums match within 0.1 (accounting for 4-decimal JSON rounding per trade)
            net_match = abs(sqlite_sum_net - json_sum_net) < 0.1
            fees_match = abs((sqlite_sum_entry_fee + sqlite_sum_exit_fee) - json_sum_fees) < 0.1
            summary_net_match = abs(summary_data.get("total_net_pnl", 0.0) - sqlite_sum_net) < 1e-4

            reconciliation_checks = {
                "sqlite_trade_count": sqlite_trade_count,
                "trades_json_count": trades_json_count,
                "summary_total_trades": summary_data.get("total_trades"),
                "summary_realization_slices": summary_data.get("realization_slices", {}).get("total_trades"),
                "sqlite_sum_net": sqlite_sum_net,
                "json_sum_net": json_sum_net,
                "summary_net_pnl": summary_data.get("total_net_pnl"),
                "counts_match": match_counts,
                "net_match": net_match,
                "fees_match": fees_match,
                "summary_net_match": summary_net_match,
            }
            print(f"Artifact Reconciliation: {reconciliation_checks}")

        passed = (
            len(found_hardcoded_literals) == 0
            and reconciliation_checks.get("counts_match", False)
            and reconciliation_checks.get("net_match", False)
            and reconciliation_checks.get("summary_net_match", False)
        )
        print(f"Check 1 Result: {'PASS' if passed else 'FAIL'}")
        if found_hardcoded_literals:
            print(f"Suspicious hardcoded literals found: {found_hardcoded_literals}")

        self.log_result(
            "Check 1 — Code Authenticity & Zero Hardcoding",
            passed,
            {
                "suspicious_hardcoded_literals": found_hardcoded_literals,
                "artifact_reconciliation": reconciliation_checks,
            },
        )

    # =========================================================================
    # CHECK 2: Paper-Only Boundary Audit (ZERO TOLERANCE)
    # =========================================================================
    def audit_check_2_paper_boundary(self):
        print("\n" + "=" * 80)
        print("RUNNING CHECK 2: Paper-Only Boundary Audit (Zero Credentials, Zero Live Orders)")
        print("=" * 80)

        forbidden_patterns = [
            (r"\b(private_key|secret_key|api_secret|wallet_seed|mnemonic)\s*=\s*['\"][0-9a-zA-Z]{12,}['\"]", "Real credential assignment"),
            (r"\b(eth_account|web3\.eth\.account)\b", "Web3 wallet account initialization"),
            (r"\b(ccxt\.[a-z_]+\.create_order|exchange\.create_order)\b", "CCXT live order placement"),
            (r"\b(requests|httpx|urllib)\.(post|put|delete)\([^)]*(fapi|api/v3|order)[^)]*\)", "Direct exchange REST order mutation"),
        ]

        # Scan all python files in src/, scripts/, config/
        scan_dirs = [self.repo_root / "src", self.repo_root / "scripts", self.repo_root / "config"]
        flagged_violations = []

        for sdir in scan_dirs:
            for fpath in sdir.rglob("*"):
                if fpath.suffix in [".py", ".yaml", ".yml", ".json"]:
                    try:
                        content = fpath.read_text(encoding="utf-8")
                    except Exception:
                        continue

                    for pat, desc in forbidden_patterns:
                        matches = re.findall(pat, content, re.IGNORECASE)
                        if matches:
                            flagged_violations.append({
                                "file": str(fpath.relative_to(self.repo_root)),
                                "pattern": pat,
                                "description": desc,
                                "matches": [str(m) for m in matches[:3]],
                            })

        # Intercept socket test during a real simulation slice
        socket_attempts = []
        original_socket_connect = socket.socket.connect

        def intercept_connect(sock_self, address):
            socket_attempts.append(str(address))
            raise PermissionError(f"Network call blocked by auditor: {address}")

        socket.socket.connect = intercept_connect
        try:
            from scripts.run_synthesized_backtest import run_universe_backtest
            test_out_dir = self.repo_root / ".pytest_cache" / "auditor_socket_test"
            res = run_universe_backtest(
                start_date="2025-01-01",
                end_date="2025-01-03",
                symbols=["BTCUSDT", "ETHUSDT"],
                initial_equity=50000.0,
                output_dir=str(test_out_dir),
                allow_network=False,
                min_trades=1,
            )
            sim_success = True
        except Exception as e:
            sim_success = False
            sim_error = str(e)
        finally:
            socket.socket.connect = original_socket_connect

        passed = (len(flagged_violations) == 0) and (len(socket_attempts) == 0) and sim_success
        print(f"Check 2 Result: {'PASS' if passed else 'FAIL'}")
        print(f"Flagged violations: {len(flagged_violations)}")
        print(f"Socket connection attempts detected: {len(socket_attempts)}")

        self.log_result(
            "Check 2 — Paper-Only Boundary Audit",
            passed,
            {
                "flagged_violations": flagged_violations,
                "socket_connection_attempts": socket_attempts,
                "sim_slice_executed_offline": sim_success,
            },
        )

    # =========================================================================
    # CHECK 3: Genuine Multi-Asset Simulation Verification
    # =========================================================================
    def audit_check_3_multi_asset_simulation(self):
        print("\n" + "=" * 80)
        print("RUNNING CHECK 3: Genuine Multi-Asset Simulation Verification")
        print("=" * 80)

        trades_sqlite_path = self.reports_dir / "trades.sqlite"
        if not trades_sqlite_path.is_file():
            self.log_result("Check 3 — Genuine Multi-Asset Simulation", False, {"error": "Missing trades.sqlite"})
            return

        with sqlite3.connect(trades_sqlite_path) as conn:
            cur = conn.cursor()
            symbols_dist = cur.execute("SELECT symbol, count(*) FROM trades GROUP BY symbol;").fetchall()
            exit_reasons_dist = cur.execute("SELECT exit_reason, count(*) FROM trades GROUP BY exit_reason;").fetchall()
            order_counts = cur.execute("SELECT count(*) FROM orders;").fetchone()[0]
            trade_count = cur.execute("SELECT count(*) FROM trades;").fetchone()[0]
            distinct_entry_prices = cur.execute("SELECT count(DISTINCT entry_price) FROM trades;").fetchone()[0]
            distinct_timestamps = cur.execute("SELECT count(DISTINCT exit_time) FROM trades;").fetchone()[0]
            min_exit = cur.execute("SELECT min(exit_time) FROM trades;").fetchone()[0]
            max_exit = cur.execute("SELECT max(exit_time) FROM trades;").fetchone()[0]

        symbols_map = {s: c for s, c in symbols_dist}
        exit_map = {e: c for e, c in exit_reasons_dist}

        print(f"Total trades: {trade_count}")
        print(f"Total orders: {order_counts}")
        print(f"Symbols traded ({len(symbols_map)}): {symbols_map}")
        print(f"Exit reasons: {exit_map}")
        print(f"Distinct entry prices: {distinct_entry_prices}")
        print(f"Distinct exit timestamps: {distinct_timestamps}")
        print(f"Temporal span: {min_exit} to {max_exit}")

        # Invariant: Must have all 10 symbols traded
        from src.data_layer.universe_loader import DEFAULT_UNIVERSE
        all_10_traded = all(s in symbols_map for s in DEFAULT_UNIVERSE) and len(symbols_map) == 10
        # Invariant: Each symbol has substantial trades (> 500)
        sufficient_per_symbol = all(symbols_map[s] >= 500 for s in DEFAULT_UNIVERSE)
        # Invariant: Distinct prices close to total position count (6454 distinct prices for 6455 positions, >99.9% unique)
        has_realistic_diversity = (distinct_entry_prices > 6000) and (distinct_timestamps > 3000)
        # Invariant: Full year temporal continuity
        temporal_continuity = ("2025-01" in min_exit) and ("2025-12" in max_exit)
        # Invariant: Exit reasons have multiple genuine paths
        multi_exit_paths = len(exit_map) >= 2 and "STOP_LOSS" in exit_map and "TAKE_PROFIT" in exit_map

        passed = all_10_traded and sufficient_per_symbol and has_realistic_diversity and temporal_continuity and multi_exit_paths
        print(f"Check 3 Result: {'PASS' if passed else 'FAIL'}")

        self.log_result(
            "Check 3 — Genuine Multi-Asset Simulation",
            passed,
            {
                "symbols_distribution": symbols_map,
                "all_10_symbols_present": all_10_traded,
                "sufficient_per_symbol": sufficient_per_symbol,
                "exit_reasons": exit_map,
                "total_orders": order_counts,
                "total_trades": trade_count,
                "distinct_entry_prices": distinct_entry_prices,
                "distinct_exit_timestamps": distinct_timestamps,
                "temporal_span": f"{min_exit} -> {max_exit}",
                "realistic_diversity": has_realistic_diversity,
            },
        )

    # =========================================================================
    # CHECK 4: Test Suite Authenticity
    # =========================================================================
    def audit_check_4_test_suite_authenticity(self):
        print("\n" + "=" * 80)
        print("RUNNING CHECK 4: Test Suite Authenticity Audit")
        print("=" * 80)

        test_file = self.repo_root / "tests" / "test_e2e_synthesized_backtest.py"
        with open(test_file, "r", encoding="utf-8") as f:
            test_content = f.read()

        parsed = ast.parse(test_content, filename=str(test_file))

        test_funcs = []
        tautological_asserts = []
        real_assert_count = 0

        for node in ast.walk(parsed):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_funcs.append(node.name)
                # Walk statements within test function
                func_assert_count = 0
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Assert):
                        func_assert_count += 1
                        real_assert_count += 1
                        # Check if test expression is a constant True
                        if isinstance(sub.test, ast.Constant) and sub.test.value is True:
                            tautological_asserts.append({
                                "func": node.name,
                                "line": sub.lineno,
                                "type": "assert True",
                            })
                        # Check if comparing identical names
                        elif isinstance(sub.test, ast.Compare):
                            if (
                                len(sub.test.ops) == 1
                                and isinstance(sub.test.ops[0], ast.Eq)
                                and isinstance(sub.test.left, ast.Name)
                                and len(sub.test.comparators) == 1
                                and isinstance(sub.test.comparators[0], ast.Name)
                                and sub.test.left.id == sub.test.comparators[0].id
                            ):
                                tautological_asserts.append({
                                    "func": node.name,
                                    "line": sub.lineno,
                                    "type": "assert x == x",
                                })

                if func_assert_count == 0:
                    tautological_asserts.append({
                        "func": node.name,
                        "line": node.lineno,
                        "type": "no_assertions",
                    })

        print(f"Total test functions: {len(test_funcs)}")
        print(f"Total assert statements: {real_assert_count}")
        print(f"Tautological assertions found: {len(tautological_asserts)}")

        passed = (len(test_funcs) >= 20) and (len(tautological_asserts) == 0) and (real_assert_count >= 40)
        print(f"Check 4 Result: {'PASS' if passed else 'FAIL'}")

        self.log_result(
            "Check 4 — Test Suite Authenticity",
            passed,
            {
                "test_functions_count": len(test_funcs),
                "total_assert_statements": real_assert_count,
                "tautological_assertions": tautological_asserts,
                "test_function_names": test_funcs,
            },
        )

    # =========================================================================
    # CHECK 5: Empirical Double-Entry Accounting & Math Verification
    # =========================================================================
    def audit_check_5_math_and_accounting(self):
        print("\n" + "=" * 80)
        print("RUNNING CHECK 5: Empirical Double-Entry Accounting & Math Verification")
        print("=" * 80)

        summary_json_path = self.reports_dir / "summary.json"
        trades_sqlite_path = self.reports_dir / "trades.sqlite"

        with open(summary_json_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        recon = summary["accounting_reconciliation"]
        init_equity = recon["initial_capital"]
        gross_pnl = recon["gross_price_pnl"]
        fees = recon["fees_paid"]
        funding = recon["funding_cashflow"]
        final_equity = recon["final_equity"]
        wallet_balance = recon["wallet_balance"]
        tolerance = recon["tolerance"]

        calculated_final = init_equity + gross_pnl - fees + funding
        diff = abs(final_equity - calculated_final)

        # Independent verification from SQLite trade-by-trade ledger
        with sqlite3.connect(trades_sqlite_path) as conn:
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT trade_id, gross_price_pnl, entry_fee, exit_fee, funding_cashflow, net_pnl FROM trades;"
            ).fetchall()

        trade_mismatches = []
        for tid, g, ef, xf, fc, net in rows:
            expected_net = g - ef - xf + fc
            if abs(net - expected_net) > 1e-4:
                trade_mismatches.append({
                    "trade_id": tid,
                    "net_pnl": net,
                    "expected_net": expected_net,
                    "diff": abs(net - expected_net),
                })

        # Win rate check
        win_count = summary["win_trades_count"]
        loss_count = summary["loss_trades_count"]
        total_trades = summary["total_trades"]
        expected_win_rate = (win_count / total_trades) * 100.0
        win_rate_diff = abs(summary["win_rate"] - round(expected_win_rate, 2))

        print(f"Double-entry formula: {recon['formula']}")
        print(f"Calculated final: {calculated_final:.10f}")
        print(f"Recorded final:   {final_equity:.10f}")
        print(f"Difference:       {diff:.2e} (tolerance: {tolerance})")
        print(f"Trade-level Net PnL conservation mismatches: {len(trade_mismatches)}")
        print(f"Win rate math check: recorded={summary['win_rate']}%, calculated={expected_win_rate:.4f}%")

        passed = (diff <= tolerance) and (len(trade_mismatches) == 0) and (win_rate_diff < 0.05)
        print(f"Check 5 Result: {'PASS' if passed else 'FAIL'}")

        self.log_result(
            "Check 5 — Empirical Math & Double-Entry Invariance",
            passed,
            {
                "equity_formula_diff": diff,
                "tolerance": tolerance,
                "trade_conservation_mismatches_count": len(trade_mismatches),
                "recorded_win_rate": summary["win_rate"],
                "calculated_win_rate": expected_win_rate,
            },
        )

    def run_all(self) -> Dict[str, Any]:
        self.audit_check_1_code_authenticity()
        self.audit_check_2_paper_boundary()
        self.audit_check_3_multi_asset_simulation()
        self.audit_check_4_test_suite_authenticity()
        self.audit_check_5_math_and_accounting()

        all_passed = all(res["passed"] for res in self.results.values())
        overall_verdict = "CLEAN" if all_passed else "INTEGRITY VIOLATION"

        print("\n" + "=" * 80)
        print(f"OVERALL FORENSIC AUDIT VERDICT: {overall_verdict}")
        print("=" * 80)
        return {
            "verdict": overall_verdict,
            "results": self.results,
        }


if __name__ == "__main__":
    runner = ForensicAuditRunner()
    summary = runner.run_all()
    # Write audit findings JSON in auditor folder
    audit_report_json = Path(r"d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_auditor_m2\audit_results.json")
    with open(audit_report_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Audit findings saved to {audit_report_json}")
    if summary["verdict"] != "CLEAN":
        sys.exit(1)
    sys.exit(0)
