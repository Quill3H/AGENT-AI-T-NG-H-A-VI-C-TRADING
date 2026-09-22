from __future__ import annotations

import json
from pathlib import Path

from run_backtest import _run_status
from src.research.artifacts import persist_basket
from src.strategies.funding_arbitrage import FundingArbitrageResult


def test_directional_status_distinguishes_valid_zero_trade_run() -> None:
    assert _run_status({"total_trades": 0}) == "NO_TRADES"
    assert _run_status({"total_trades": 1}) == "COMPLETED"


def test_basket_artifact_distinguishes_no_entry_from_open_at_end(
    tmp_path: Path,
) -> None:
    manifest = {
        "source": "SYNTHETIC_TEST",
        "symbol": "BTCUSDT",
        "market_type": "spot_and_perpetual",
        "timeframe": "1m",
        "start": None,
        "end": None,
        "rows": 0,
        "gaps": 0,
        "sha256": "0" * 64,
    }
    no_entry = FundingArbitrageResult(cash=10000, equity=10000)
    persist_basket(tmp_path / "none", no_entry, {}, manifest)
    no_entry_report = json.loads(
        (tmp_path / "none" / "funding_arbitrage.report.json").read_text(
            encoding="utf-8"
        )
    )
    assert no_entry_report["report"]["run_status"] == "NO_TRADES"

    open_basket = FundingArbitrageResult(
        entered=True,
        exited=False,
        cash=5000,
        equity=10000,
        quantity=1,
        spot_inventory=1,
        spot_value=5000,
    )
    persist_basket(tmp_path / "open", open_basket, {}, manifest)
    open_report = json.loads(
        (tmp_path / "open" / "funding_arbitrage.report.json").read_text(
            encoding="utf-8"
        )
    )
    assert open_report["report"]["run_status"] == "COMPLETED_WITH_OPEN_BASKET"
