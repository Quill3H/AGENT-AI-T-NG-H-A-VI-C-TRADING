#!/usr/bin/env python3
"""Rewrite docs/research/ledger/LEARNING_LOG.md from the research ledger (run after each round)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.research import ledger  # noqa: E402

HEADER = """# Learning log (generated from ledger.jsonl; do not edit by hand)

Paper-only research. Every run of every round is one row. A new round starts by reading
this file and the lessons at the bottom. Final-test data listed under "Spent final data"
cannot be reused for a new final test (src/research/ledger.py refuses it); new evidence has
to come from coins or months no final test has used, or from forward paper trading.

"""


def main():
    records = ledger.load()
    spent = ledger.spent_final_data(records)
    lines = [HEADER, "## Spent final data", ""]
    lines += [f"- {symbol}: " + ", ".join(f"{a}..{b}" for a, b in windows) for symbol, windows in sorted(spent.items())]
    lines += ["", "## Research integrity", "", ledger.integrity_markdown(records),
              "The Bonferroni value is a reference threshold for a declared search family, not proof of an edge.",
              "", "## Runs", "", ledger.summary_markdown(records)]
    target = ledger.LEDGER.parent / "LEARNING_LOG.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
