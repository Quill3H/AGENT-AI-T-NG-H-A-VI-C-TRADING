"""Offline audit diagnostics, not acceptance tests and not a trading runner.

Use the project's .venv-paper interpreter. All storage/listeners are temporary;
no public feed, operator journal, Windows task or repository config is changed.
Outputs observed behavior, including known defects; exit 0 is NOT a gate pass.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT = Path(__file__).resolve().parents[2] / "crypto-paper-agent"
sys.path.insert(0, str(PROJECT))

import pandas as pd
from src.backtest.engine import BacktestEngine
from src.data_layer.cache_manager import (
    has_complete_cache, load_from_cache, save_to_cache,
)
from src.paper.live_session import LocalPaperSession
from src.paper.local_server import create_server


def main():
    result = {"evidence_level": "AUTHOR_SELF_REVIEWED", "network": "NOT_USED"}
    index = pd.date_range("2026-01-01", periods=200, freq="15min", tz="UTC")
    base = pd.DataFrame({"open": 100., "high": 101., "low": 99.,
                         "close": 100., "volume": 1.}, index=index)
    result["volume_validation"] = []
    for label, value in (("NaN", float("nan")), ("Inf", float("inf")),
                         ("negative", -1.), ("boolean", True)):
        frame = base.copy()
        frame["volume"] = value
        try:
            BacktestEngine.validate_dataset(frame, "15m")
            observation = "ACCEPTED"
        except (ValueError, TypeError) as exc:
            observation = f"REJECTED: {exc}"
        result["volume_validation"].append({"input": label, "observed": observation})

    with TemporaryDirectory(prefix="paper-audit-cache-") as directory:
        sparse = base.drop(index[50:100])
        save_to_cache(sparse, directory, "binance", "BTCUSDT", "15m", "ohlcv")
        result["cache_gap"] = {
            "expected_rows": 200, "actual_rows": 150,
            "fast_complete": has_complete_cache(directory, "binance", "BTCUSDT",
                                                 "15m", "ohlcv", index[0], index[-1]),
            "load_returns_none": load_from_cache(directory, "binance", "BTCUSDT",
                                                   "15m", "ohlcv", index[0], index[-1]) is None,
        }

    with TemporaryDirectory(prefix="paper-audit-writer-") as directory:
        first = create_server(port=0, journal_dir=directory)
        second = None
        try:
            try:
                second = create_server(port=0, journal_dir=directory)
                result["same_journal_two_servers"] = {
                    "second_listener_accepted": True,
                    "different_ports": first.server_port != second.server_port,
                    "statuses": [first.session.status, second.session.status],
                    "writes_attempted": False,
                }
            except (OSError, ValueError, RuntimeError) as exc:
                result["same_journal_two_servers"] = {
                    "second_listener_accepted": False, "reason": str(exc),
                }
        finally:
            if second is not None:
                second.server_close()
            first.server_close()

    opened = datetime(2026, 9, 27, 8, tzinfo=timezone.utc)
    open_ms = int(opened.timestamp() * 1000)

    class ExactFundingSource:
        def funding(self, symbol, limit):
            return [{"fundingTime": open_ms, "fundingRate": "0.0001"}]

    with TemporaryDirectory(prefix="paper-audit-funding-") as directory:
        session = LocalPaperSession(source=ExactFundingSource(), journal_dir=directory)
        observations = []
        for delay in (0, 900_000):
            try:
                session._funding_metadata("BTCUSDT", opened, observed_ms=open_ms + delay)
                observation = "ACCEPTED"
            except (ValueError, TypeError) as exc:
                observation = f"REJECTED: {exc}"
            observations.append({"receipt_delay_ms": delay, "observed": observation})
        result["exact_funding_source"] = observations
        result["funding_probe_wrote_account"] = bool(list(Path(directory).iterdir()))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
