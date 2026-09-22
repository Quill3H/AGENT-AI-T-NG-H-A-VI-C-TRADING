from __future__ import annotations

import os
import io
from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(script: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / script), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


@pytest.mark.parametrize(
    "script",
    [
        "run_backtest.py",
        "scripts/fetch_market_data.py",
        "scripts/run_funding_arbitrage.py",
        "scripts/run_walk_forward.py",
        "scripts/train_ppo.py",
        "scripts/evaluate_ppo.py",
    ],
)
def test_help_runs_from_external_cwd_without_business_dependencies(
    tmp_path: Path, script: str
) -> None:
    result = _run(script, "--help", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert result.stderr == ""
    assert not any(tmp_path.iterdir())


def test_fetch_requires_explicit_network_opt_in_without_creating_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / "market-data"

    result = _run(
        "scripts/fetch_market_data.py",
        "--output-dir",
        str(output),
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "NETWORK_DISABLED" in result.stderr
    assert not output.exists()


def test_backtest_rejects_contradictory_network_flags_before_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / "reports"

    result = _run(
        "run_backtest.py",
        "--no-fetch",
        "--allow-network",
        "--output-dir",
        str(output),
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "INVALID_ARGUMENTS" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    ("script", "args"),
    [
        (
            "scripts/run_funding_arbitrage.py",
            ["--input", "missing.parquet", "--source", "test"],
        ),
        (
            "scripts/run_walk_forward.py",
            [
                "--data-dir",
                "missing-data",
                "--train-bars",
                "10",
                "--test-bars",
                "10",
                "--source",
                "test",
            ],
        ),
        (
            "scripts/train_ppo.py",
            [
                "--train",
                "missing-train.parquet",
                "--validation",
                "missing-validation.parquet",
                "--holdout",
                "missing-holdout.parquet",
                "--config",
                "missing.yaml",
            ],
        ),
        (
            "scripts/evaluate_ppo.py",
            [
                "--model-dir",
                "missing-model",
                "--input",
                "missing.parquet",
                "--config",
                "missing.yaml",
            ],
        ),
    ],
)
def test_missing_required_input_fails_before_output_creation(
    tmp_path: Path, script: str, args: list[str]
) -> None:
    output = tmp_path / "output"

    result = _run(script, *args, "--output", str(output), cwd=tmp_path)

    assert result.returncode != 0
    assert "DATASET_UNAVAILABLE" in result.stderr
    assert not output.exists()


def test_existing_output_is_rejected_without_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    result = _run(
        "scripts/run_funding_arbitrage.py",
        "--input",
        "missing.parquet",
        "--source",
        "test",
        "--output",
        str(output),
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "OUTPUT_EXISTS" in result.stderr
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    ("strategy", "input_flag", "input_value"),
    [
        ("funding_arbitrage", "--basket-input", "missing.parquet"),
        ("all", "--comparison-data-dir", "missing-data"),
    ],
)
def test_backtest_special_modes_name_missing_dataset_before_output(
    tmp_path: Path, strategy: str, input_flag: str, input_value: str
) -> None:
    output = tmp_path / "reports"

    result = _run(
        "run_backtest.py",
        "--strategy",
        strategy,
        input_flag,
        input_value,
        "--output-dir",
        str(output),
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "DATASET_UNAVAILABLE" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_fetch_output_collision_precedes_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import importlib.util

    script = PROJECT_ROOT / "scripts" / "fetch_market_data.py"
    spec = importlib.util.spec_from_file_location("fetch_market_data_contract", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "cache"
    target = output / "binance" / "BTCUSDT" / "15m" / "ohlcv.parquet"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing")

    def unexpected_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("network called before output collision validation")

    monkeypatch.setattr(module.requests, "get", unexpected_network)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--allow-network",
            "--output-dir",
            str(output),
        ],
    )

    assert module.main() != 0
    assert "OUTPUT_EXISTS" in capsys.readouterr().err
    assert target.read_bytes() == b"existing"


def test_fetch_operator_output_is_windows_console_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.util
    import pandas as pd

    script = PROJECT_ROOT / "scripts" / "fetch_market_data.py"
    spec = importlib.util.spec_from_file_location("fetch_market_data_encoding", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    timestamp = pd.DatetimeIndex([pd.Timestamp("2024-01-01T00:00:00Z")])
    klines = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
        index=timestamp,
    )
    funding = pd.DataFrame(
        {"funding_rate": [0.0001], "mark_price": [1.0]}, index=timestamp
    )
    monkeypatch.setattr(module, "fetch_klines", lambda **kwargs: klines)
    monkeypatch.setattr(module, "fetch_funding_rate", lambda **kwargs: funding)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--allow-network",
            "--output-dir",
            str(tmp_path / "cache"),
        ],
    )
    console_bytes = io.BytesIO()
    console = io.TextIOWrapper(console_bytes, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", console)

    assert module.main() == 0
    console.flush()
    assert b"completed" in console_bytes.getvalue().lower()


@pytest.mark.parametrize(
    "extra_args",
    [
        ["--interval", "bad"],
        ["--kline-limit", "1501"],
        ["--funding-limit", "1001"],
        ["--symbol", "BTC-USDT"],
    ],
)
def test_fetch_rejects_invalid_request_before_network_or_output(
    tmp_path: Path, extra_args: list[str]
) -> None:
    output = tmp_path / "cache"
    result = _run(
        "scripts/fetch_market_data.py",
        "--allow-network",
        "--output-dir",
        str(output),
        *extra_args,
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "INVALID_ARGUMENTS" in result.stderr
    assert not output.exists()
