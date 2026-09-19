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


def test_deterministic_run_id_across_invocations(hermetic_env):
    """Kiểm tra tính tất định của run_id khi không truyền cờ --run-id."""
    cfg_file, tmp_dir = hermetic_env
    output_dir = tmp_dir / "det_runs"

    cmd_base = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-03",
        "--no-fetch",
        "--output-dir", str(output_dir),
    ]

    # Run 1
    res1 = subprocess.run(cmd_base, cwd=str(tmp_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res1.returncode == 0
    run_id_1 = None
    for line in res1.stdout.splitlines():
        if "Run ID" in line and ":" in line:
            run_id_1 = line.split(":", 1)[1].strip()
            break
    assert run_id_1 is not None and len(run_id_1) > 0

    # Run 2 (same parameters)
    res2 = subprocess.run(cmd_base, cwd=str(tmp_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res2.returncode == 0
    run_id_2 = None
    for line in res2.stdout.splitlines():
        if "Run ID" in line and ":" in line:
            run_id_2 = line.split(":", 1)[1].strip()
            break
    assert run_id_2 == run_id_1, f"Run ID must be deterministic: {run_id_1} vs {run_id_2}"

    # Run 3 (different end date -> must produce different Run ID)
    cmd3 = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-02",
        "--no-fetch",
        "--output-dir", str(output_dir),
    ]
    res3 = subprocess.run(cmd3, cwd=str(tmp_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res3.returncode == 0
    run_id_3 = None
    for line in res3.stdout.splitlines():
        if "Run ID" in line and ":" in line:
            run_id_3 = line.split(":", 1)[1].strip()
            break
    assert run_id_3 != run_id_1, "Different parameters must yield different Run ID"


def test_cwd_independence_and_path_resolution(hermetic_env, tmp_path):
    """
    Kiểm tra độc lập CWD:
    Khi truyền đường dẫn tuyệt đối hay tương đối, kết quả ghi chính xác không bị phụ thuộc CWD bên ngoài.
    """
    cfg_file, tmp_dir = hermetic_env
    cwd_1 = tmp_path / "external_cwd_1"
    cwd_2 = tmp_path / "external_cwd_2"
    cwd_1.mkdir()
    cwd_2.mkdir()

    abs_out_dir = tmp_path / "absolute_reports"

    # Chạy từ cwd_1 với absolute output-dir
    cmd1 = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-02",
        "--no-fetch",
        "--output-dir", str(abs_out_dir),
        "--run-id", "run_abs_cwd_1",
    ]
    res1 = subprocess.run(cmd1, cwd=str(cwd_1), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res1.returncode == 0
    assert (abs_out_dir / "run_abs_cwd_1" / "summary.json").is_file()

    # Chạy từ cwd_2 với absolute output-dir tương tự
    cmd2 = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-02",
        "--no-fetch",
        "--output-dir", str(abs_out_dir),
        "--run-id", "run_abs_cwd_2",
    ]
    res2 = subprocess.run(cmd2, cwd=str(cwd_2), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res2.returncode == 0
    assert (abs_out_dir / "run_abs_cwd_2" / "summary.json").is_file()


def test_future_perturbation_report_invariance(hermetic_env, tmp_path):
    """
    Kiểm tra tính bất biến trước nhiễu loạn tương lai (Future Perturbation Invariance):
    Báo cáo và các trade phát sinh cho khoảng thời gian [T_start, T_split] không được phép
    thay đổi khi dữ liệu trong tương lai (T > T_split) bị biến đổi hay sửa đổi.
    """
    cfg_file, tmp_dir = hermetic_env
    cache_dir = tmp_dir / "mock_cache"
    out_dir_1 = tmp_path / "rep_perturb_1"
    out_dir_2 = tmp_path / "rep_perturb_2"

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-02",
        "--no-fetch",
        "--output-dir", str(out_dir_1),
        "--run-id", "run_perturb_pre",
    ]
    res1 = subprocess.run(cmd, cwd=str(tmp_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res1.returncode == 0

    # Đọc trades.json lần 1
    with open(out_dir_1 / "run_perturb_pre" / "trades.json", "r", encoding="utf-8") as f:
        trades_pre = json.load(f)
    with open(out_dir_1 / "run_perturb_pre" / "summary.json", "r", encoding="utf-8") as f:
        summary_pre = json.load(f)

    # Nhiễu loạn dữ liệu tương lai (ngày 2023-01-03, 2023-01-04) trong cache
    df_4h_corrupt, df_15m_corrupt = _generate_synthetic_multitimeframe_data(
        start_dt=datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        n_days=4,
    )
    # Tăng giá đột biến ở ngày 3 và 4 (sau T_split 2023-01-02)
    mask_future_4h = df_4h_corrupt.index >= pd.Timestamp("2023-01-03", tz="UTC")
    df_4h_corrupt.loc[mask_future_4h, ["open", "high", "low", "close"]] *= 10.0
    mask_future_15m = df_15m_corrupt.index >= pd.Timestamp("2023-01-03", tz="UTC")
    df_15m_corrupt.loc[mask_future_15m, ["open", "high", "low", "close"]] *= 10.0

    df_4h_corrupt.index.name = "timestamp"
    df_15m_corrupt.index.name = "timestamp"
    save_to_cache(df_4h_corrupt[["open", "high", "low", "close", "volume"]], str(cache_dir), "binance", "BTCUSDT", "4h", "ohlcv")
    save_to_cache(df_15m_corrupt[["open", "high", "low", "close", "volume"]], str(cache_dir), "binance", "BTCUSDT", "15m", "ohlcv")

    # Chạy lại backtest từ 2023-01-01 đến 2023-01-02
    cmd2 = [
        sys.executable,
        str(PROJECT_ROOT / "run_backtest.py"),
        "--config", str(cfg_file),
        "--strategy", "trend_following",
        "--start", "2023-01-01",
        "--end", "2023-01-02",
        "--no-fetch",
        "--output-dir", str(out_dir_2),
        "--run-id", "run_perturb_post",
    ]
    res2 = subprocess.run(cmd2, cwd=str(tmp_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res2.returncode == 0

    with open(out_dir_2 / "run_perturb_post" / "trades.json", "r", encoding="utf-8") as f:
        trades_post = json.load(f)
    with open(out_dir_2 / "run_perturb_post" / "summary.json", "r", encoding="utf-8") as f:
        summary_post = json.load(f)

    assert trades_pre == trades_post, "Trades for [T_start, T_split] must not be affected by future perturbation"
    for k in ["initial_capital", "final_equity", "total_trades", "total_return_pct", "max_drawdown_usd"]:
        assert summary_pre[k] == summary_post[k], f"Metric {k} changed under future perturbation: {summary_pre[k]} vs {summary_post[k]}"


