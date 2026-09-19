"""
tests/test_stage_06_integration.py - Integration Test Suite for Stage 6
=======================================================================
Kiểm tra tích hợp toàn diện:
1. Thực thi CLI end-to-end hermetic (không phụ thuộc network hay data/raw)
2. Kiểm tra sinh đầy đủ 6 artifacts trong custom output directory
3. Kiểm tra cờ --no-report (không sinh file)
4. Kiểm tra độc lập CWD khi chạy từ thư mục bên ngoài
5. Đảm bảo Zero Semantic Drift: kết quả backtest không bị biến dạng bởi logger/reporter
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import pandas as pd
import pytest
import yaml

from src.data_layer.cache_manager import save_to_cache


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _generate_synthetic_multitimeframe_data(start_dt: datetime, n_days: int = 4):
    """Tạo dữ liệu tổng hợp đồng bộ giữa khung 4h và 15m."""
    n_4h = n_days * 6
    idx_4h = pd.date_range(start=start_dt, periods=n_4h, freq="4h", tz="UTC")

    prices_4h = []
    base_p = 20000.0
    for i in range(n_4h):
        if i < 10:
            prices_4h.append(base_p)
        elif i < 15:
            base_p += 100.0
            prices_4h.append(base_p)
        else:
            base_p -= 50.0
            prices_4h.append(base_p)

    df_4h = pd.DataFrame(
        {
            "open": prices_4h,
            "high": [p + 40.0 for p in prices_4h],
            "low": [p - 40.0 for p in prices_4h],
            "close": prices_4h,
            "volume": 1000.0,
            "open_interest": [50000.0 + i * 50.0 for i in range(n_4h)],
        },
        index=idx_4h,
    )

    n_15m = n_days * 96
    idx_15m = pd.date_range(start=start_dt, periods=n_15m, freq="15min", tz="UTC")
    records_15m = []

    for t in idx_15m:
        parent_4h = t.floor("4h")
        c_4h = df_4h.loc[parent_4h]
        records_15m.append(
            {
                "open": c_4h["open"],
                "high": c_4h["high"],
                "low": c_4h["low"],
                "close": c_4h["close"],
                "volume": 250.0,
                "open_interest": c_4h["open_interest"],
                "funding_rate": 0.0001 if (t.hour in (0, 8, 16) and t.minute == 0) else None,
                "funding_time": t if (t.hour in (0, 8, 16) and t.minute == 0) else None,
                "funding_readiness": True if (t.hour in (0, 8, 16) and t.minute == 0) else False,
            }
        )

    df_15m = pd.DataFrame(records_15m, index=idx_15m)
    return df_4h, df_15m


@pytest.fixture
def hermetic_env(tmp_path):
    """Thiết lập môi trường cache và config tổng hợp hermetic."""
    cache_dir = tmp_path / "mock_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    df_4h, df_15m = _generate_synthetic_multitimeframe_data(
        start_dt=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        n_days=4,
    )
    df_4h.index.name = "timestamp"
    df_15m.index.name = "timestamp"

    save_to_cache(df_4h[["open", "high", "low", "close", "volume"]], str(cache_dir), "binance", "BTCUSDT", "4h", "ohlcv")
    save_to_cache(df_15m[["open", "high", "low", "close", "volume"]], str(cache_dir), "binance", "BTCUSDT", "15m", "ohlcv")
    save_to_cache(pd.DataFrame({"open_interest": 50000.0}, index=df_4h.index), str(cache_dir), "binance", "BTCUSDT", "4h", "open_interest")
    save_to_cache(df_15m[["open_interest"]], str(cache_dir), "binance", "BTCUSDT", "15m", "open_interest")

    df_funding = df_15m[df_15m["funding_rate"].notna()][["funding_rate"]]
    save_to_cache(df_funding, str(cache_dir), "binance", "BTCUSDT", "8h", "funding_rate")
    save_to_cache(df_funding, str(cache_dir), "binance", "BTCUSDT", "15m", "funding_rate")

    with open(PROJECT_ROOT / "config" / "default_config.yaml", "r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f)

    base_cfg["data"]["raw_data_dir"] = str(cache_dir)
    cfg_file = tmp_path / "test_config.yaml"
    with open(cfg_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(base_cfg, f)

    return cfg_file, tmp_path


def test_cli_end_to_end_with_report_generation(hermetic_env):
    """Kiểm tra CLI chạy end-to-end xuất đủ 6 artifacts vào thư mục chỉ định."""
    cfg_file, tmp_dir = hermetic_env
    output_dir = tmp_dir / "my_reports"
    run_id = "test_run_e2e_01"

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-03",
        "--no-fetch",
        "--output-dir", str(output_dir),
        "--run-id", run_id,
    ]

    res = subprocess.run(
        cmd,
        cwd=str(tmp_dir),  # Chạy từ thư mục bên ngoài project root
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert res.returncode == 0, f"CLI error:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "BACKTEST EXECUTION REPORT" in res.stdout
    assert "Daily Sharpe Ratio" in res.stdout
    assert "Profit Factor" in res.stdout
    assert "Expectancy (USD)" in res.stdout
    assert "Expectancy (R)" in res.stdout

    run_report_dir = output_dir / run_id
    assert run_report_dir.is_dir()

    expected_files = [
        "summary.json",
        "summary.md",
        "trades.json",
        "equity_curve.csv",
        "equity_curve.png",
        "trades.sqlite",
    ]
    for fn in expected_files:
        p = run_report_dir / fn
        assert p.is_file(), f"Expected artifact {fn} was not generated in {run_report_dir}"
        assert p.stat().st_size > 0, f"Artifact {fn} is empty"


def test_cli_no_report_flag(hermetic_env):
    """Kiểm tra cờ --no-report ngăn chặn xuất artifacts."""
    cfg_file, tmp_dir = hermetic_env
    output_dir = tmp_dir / "no_report_dir"
    run_id = "test_no_report_run"

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-02",
        "--no-fetch",
        "--output-dir", str(output_dir),
        "--run-id", run_id,
        "--no-report",
    ]

    res = subprocess.run(
        cmd,
        cwd=str(tmp_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert res.returncode == 0
    assert "Report Output  : DISABLED (--no-report)" in res.stdout
    # Thư mục report cho run này không được tạo
    assert not (output_dir / run_id).exists()


def test_zero_semantic_drift_between_reporting_modes(hermetic_env):
    """
    Xác nhận nguyên lý Zero Semantic Drift:
    Việc bật hay tắt report generator không được phép làm sai lệch bất kỳ kết quả,
    giá khớp, số lượng lệnh, hay trạng thái số dư nào của backtest engine.
    """
    cfg_file, tmp_dir = hermetic_env
    out_dir_1 = tmp_dir / "reports_drift_1"
    out_dir_2 = tmp_dir / "reports_drift_2"

    cmd_base = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-03",
        "--no-fetch",
    ]

    # Chạy 1: Có sinh report
    cmd1 = cmd_base + ["--output-dir", str(out_dir_1), "--run-id", "run_with_report"]
    res1 = subprocess.run(cmd1, cwd=str(tmp_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res1.returncode == 0

    # Chạy 2: Không sinh report (--no-report)
    cmd2 = cmd_base + ["--output-dir", str(out_dir_2), "--run-id", "run_without_report", "--no-report"]
    res2 = subprocess.run(cmd2, cwd=str(tmp_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res2.returncode == 0

    # So sánh các chỉ số trong stdout
    def _extract_metric_line(stdout, prefix):
        for line in stdout.splitlines():
            if line.strip().startswith(prefix):
                return line.strip()
        return None

    for metric_prefix in [
        "Final Equity",
        "Total Return",
        "Max Drawdown",
        "Total Orders Sent",
        "Orders Filled",
        "Total Closed Trades",
        "Gross Price PnL",
        "Net Realized PnL",
    ]:
        line1 = _extract_metric_line(res1.stdout, metric_prefix)
        line2 = _extract_metric_line(res2.stdout, metric_prefix)
        assert line1 == line2, f"Semantic drift detected for {metric_prefix}: '{line1}' vs '{line2}'"

