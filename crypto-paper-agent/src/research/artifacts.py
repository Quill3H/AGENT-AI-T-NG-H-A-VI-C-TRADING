"""Portable dataset identities and transactional research report persistence."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import numpy as np
import pandas as pd
from src.logging.trade_logger import canonicalize_config, compute_config_hash
from src.research.validation import time_index
from src.data_layer.cache_manager import timeframe_to_timedelta


def serializable(value):
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.name
    return value


def frame_digest(frame):
    time_index(frame)
    return hashlib.sha256(
        frame.to_csv(
            index=True, float_format="%.17g", date_format="%Y-%m-%dT%H:%M:%S.%f%z"
        ).encode("utf-8")
    ).hexdigest()


def dataset_manifest(frame, source, symbol, market_type, timeframe):
    time_index(frame)
    expected = pd.Timedelta(timeframe_to_timedelta(timeframe))
    diffs = frame.index.to_series().diff().dropna()
    return {
        "source": source,
        "symbol": symbol,
        "market_type": market_type,
        "timeframe": timeframe,
        "start": frame.index[0].isoformat() if len(frame) else None,
        "end": frame.index[-1].isoformat() if len(frame) else None,
        "rows": len(frame),
        "gaps": int((diffs > expected).sum()),
        "sha256": frame_digest(frame),
    }


def funding_settlement_coverage(basket, source_events):
    """Audit exact 8-hour source coverage without changing settlement availability.

    The source-event comparison is retrospective metadata only. A late source
    event is never made available at the earlier nominal boundary.
    """
    time_index(basket)
    time_index(source_events)
    required = {"funding_time", "funding_readiness"}
    if not required.issubset(basket.columns):
        raise ValueError("basket requires funding_time and funding_readiness")
    boundaries = (
        pd.date_range(basket.index[0].ceil("8h"), basket.index[-1], freq="8h")
        if len(basket)
        else pd.DatetimeIndex([], tz="UTC")
    )
    unready = []
    missing_rows = 0
    late_events = 0
    max_delay_ms = 0
    for boundary in boundaries:
        source_exact = boundary in source_events.index
        if not source_exact:
            next_pos = source_events.index.searchsorted(boundary, side="right")
            if next_pos < len(source_events):
                delay = source_events.index[next_pos] - boundary
                if pd.Timedelta(0) < delay < pd.Timedelta(minutes=1):
                    late_events += 1
                    delay_ms = int(delay / pd.Timedelta(milliseconds=1))
                    max_delay_ms = max(max_delay_ms, delay_ms)
        if boundary not in basket.index:
            missing_rows += 1
            unready.append(boundary.isoformat())
            continue
        row = basket.loc[boundary]
        ready = row["funding_readiness"]
        exact = (
            isinstance(ready, (bool, np.bool_))
            and bool(ready)
            and row["funding_time"] == boundary
            and source_exact
        )
        if exact:
            continue
        unready.append(boundary.isoformat())
    expected = len(boundaries)
    exact_ready = expected - len(unready)
    return {
        "schedule": "00:00/08:00/16:00 UTC",
        "expected": expected,
        "exact_ready": exact_ready,
        "unready": len(unready),
        "missing_basket_rows": missing_rows,
        "source_late_within_next_minute": late_events,
        "max_source_delay_ms": max_delay_ms,
        "unready_boundaries": unready,
        "exact_funding_coverage_complete": expected > 0 and exact_ready == expected,
    }


def persist_research_run(output, name, config, report):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    canonical = canonicalize_config(config)
    root = Path(__file__).resolve().parents[3]
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    payload = serializable(
        {
            "name": name,
            "code_commit_sha": sha,
            "config": canonical,
            "config_hash": compute_config_hash(canonical),
            "report": report,
        }
    )
    body = json.dumps(payload, sort_keys=True, allow_nan=False, indent=2)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    # Names are identity keys; conflicting repeated payloads fail closed.
    with sqlite3.connect(output / "research.sqlite") as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS runs (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        prior = db.execute("SELECT sha256 FROM runs WHERE name=?", (name,)).fetchone()
        if prior and prior[0] != digest:
            raise ValueError("research run identity conflict")
        db.execute("INSERT OR IGNORE INTO runs VALUES (?,?,?)", (name, digest, body))
    from src.report.generator import _atomic_write_text

    _atomic_write_text(output / f"{name}.report.json", body)
    _atomic_write_text(
        output / "config.canonical.json",
        json.dumps(canonical, sort_keys=True, indent=2, allow_nan=False),
    )
    files = {f"{name}.report.json": digest}
    if (output / "ppo_model.zip").is_file():
        files["ppo_model.zip"] = hashlib.sha256(
            (output / "ppo_model.zip").read_bytes()
        ).hexdigest()
    _atomic_write_text(
        output / "manifest.json",
        json.dumps(
            {
                "name": name,
                "code_commit_sha": sha,
                "config_hash": payload["config_hash"],
                "files": files,
            },
            indent=2,
            allow_nan=False,
        ),
    )
    return output / f"{name}.report.json"


def persist_basket(output, result, config, manifest):
    run_status = (
        "NO_TRADES"
        if not result.entered
        else "COMPLETED_WITH_OPEN_BASKET"
        if not result.exited
        else "COMPLETED"
    )
    report = {
        "status": "AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED",
        "run_status": run_status,
        "dataset": manifest,
        "metrics": result.metrics(),
        "basket": result.to_dict(),
    }
    path = persist_research_run(output, "funding_arbitrage", config, report)
    output = Path(output)
    pd.DataFrame(result.snapshots).to_csv(output / "equity_curve.csv", index=False)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    if result.snapshots:
        ax.plot(
            [s["timestamp"] for s in result.snapshots],
            [s["equity"] for s in result.snapshots],
        )
    ax.set_ylabel("USDT")
    fig.autofmt_xdate()
    fig.savefig(output / "equity_curve.png")
    plt.close(fig)
    (output / "summary.md").write_text(
        "Funding basket\n\nAUTHOR_REPORTED / REVIEWER_NOT_VERIFIED\n\n"
        f"Net PnL: {result.net_pnl:.8f} USDT\n\nEquity: {result.equity:.8f} USDT\n\n"
        f"Closed: {result.exited}; unrealized: {result.unrealized_pnl:.8f} USDT\n",
        encoding="utf-8",
    )
    return path
