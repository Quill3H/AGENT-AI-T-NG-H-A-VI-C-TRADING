"""Run and audit the deterministic offline synthetic research quick-start."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _audit(output: Path) -> dict[str, object]:
    missing: list[str] = []
    leaks: list[str] = []
    required_names = {
        "summary.json",
        "summary.md",
        "trades.json",
        "trades.sqlite",
        "equity_curve.csv",
        "equity_curve.png",
    }
    artifact_files = [path for path in output.rglob("*") if path.is_file()]
    present_names = {path.name for path in artifact_files}
    for name in sorted(required_names - present_names):
        missing.append(name)

    machine_roots = {str(output.resolve()), str(ROOT.resolve())}
    for path in artifact_files:
        if path.stat().st_size == 0:
            missing.append(f"empty:{path.relative_to(output).as_posix()}")
            continue
        if path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".csv":
            import pandas as pd

            pd.read_csv(path)
        elif path.suffix == ".sqlite":
            with sqlite3.connect(path) as db:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    missing.append(f"sqlite-integrity:{path.relative_to(output).as_posix()}")
                text = "\n".join(
                    str(value)
                    for (table,) in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                    for row in db.execute(f'SELECT * FROM "{table}"')
                    for value in row
                    if isinstance(value, str)
                )
                if any(root in text for root in machine_roots):
                    leaks.append(path.relative_to(output).as_posix())
        if path.suffix in {".json", ".md", ".csv"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(root in text for root in machine_roots):
                leaks.append(path.relative_to(output).as_posix())

    return {
        "files_checked": len(artifact_files),
        "missing": sorted(set(missing)),
        "absolute_path_leaks": sorted(set(leaks)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a no-network synthetic paper-bot quick-start and audit artifacts."
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        sys.stderr.write(f"ERROR [OUTPUT_EXISTS]: output target already exists: {output}\n")
        return 2

    command = [
        sys.executable,
        str(ROOT / "scripts" / "verify_research_smoke.py"),
        "--output",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=150,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        return completed.returncode

    results = json.loads((output / "smoke_results.json").read_text(encoding="utf-8"))
    audit = _audit(output)
    if audit["missing"] or audit["absolute_path_leaks"]:
        sys.stderr.write(f"ERROR [ARTIFACT_AUDIT_FAILED]: {json.dumps(audit)}\n")
        return 2
    report = {
        "status": "AUTHOR_SELF_REVIEWED",
        "scope": "synthetic functional evidence only; not market performance",
        "network": (
            "DISABLED_AND_TEST_GUARDED"
            if os.environ.get("QUICKSTART_NETWORK_GUARD") == "1"
            else "NOT_USED_BY_SYNTHETIC_QUICKSTART"
        ),
        "results": results,
        "artifact_audit": audit,
    }
    temporary = output / "quickstart_report.json.tmp"
    temporary.write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(output / "quickstart_report.json")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
