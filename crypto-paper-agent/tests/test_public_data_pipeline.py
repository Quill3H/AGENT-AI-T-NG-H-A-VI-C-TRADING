from __future__ import annotations

from pathlib import Path
from io import BytesIO
import importlib.util
import json
import subprocess
import sys
from zipfile import ZipFile

import pandas as pd

from src.research.artifacts import funding_settlement_coverage


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_sample_requires_network_opt_in_before_output(tmp_path: Path) -> None:
    output = tmp_path / "public"

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "prepare_public_research_sample.py"),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode != 0
    assert "NETWORK_DISABLED" in result.stderr
    assert not output.exists()


def test_funding_coverage_distinguishes_exact_late_and_absent_events() -> None:
    idx = pd.date_range("2026-08-20", periods=961, freq="min", tz="UTC")
    exact, late_boundary, absent = idx[[0, 480, 960]]
    late = late_boundary + pd.Timedelta(milliseconds=2)
    frame = pd.DataFrame(
        {
            "funding_time": [exact] * 481 + [late] * 480,
            "funding_readiness": [True] * 480 + [False] + [True] * 479 + [False],
        },
        index=idx,
    )
    source = pd.DataFrame(index=pd.DatetimeIndex([exact, late]))

    coverage = funding_settlement_coverage(frame, source)

    assert coverage == {
        "schedule": "00:00/08:00/16:00 UTC",
        "expected": 3,
        "exact_ready": 1,
        "unready": 2,
        "missing_basket_rows": 0,
        "source_late_within_next_minute": 1,
        "max_source_delay_ms": 2,
        "unready_boundaries": [late_boundary.isoformat(), absent.isoformat()],
        "exact_funding_coverage_complete": False,
    }


def test_funding_coverage_requires_source_and_counts_missing_candle() -> None:
    idx = pd.date_range("2026-08-20", periods=961, freq="min", tz="UTC")
    frame = pd.DataFrame(
        {"funding_time": [idx[0], idx[960]], "funding_readiness": [True, True]},
        index=pd.DatetimeIndex([idx[0], idx[960]]),
    )
    # The basket's 16:00 flag cannot substitute for a missing raw source event.
    source = pd.DataFrame(
        index=pd.DatetimeIndex([idx[0], idx[480] + pd.Timedelta(milliseconds=4)])
    )

    coverage = funding_settlement_coverage(frame, source)

    assert coverage["expected"] == 3
    assert coverage["exact_ready"] == 1
    assert coverage["unready"] == 2
    assert coverage["missing_basket_rows"] == 1
    assert coverage["source_late_within_next_minute"] == 1
    assert coverage["max_source_delay_ms"] == 4
    assert not coverage["exact_funding_coverage_complete"]


def test_public_sample_manifest_records_funding_coverage_without_backdating(
    tmp_path: Path, monkeypatch
) -> None:
    path = PROJECT_ROOT / "scripts" / "prepare_public_research_sample.py"
    spec = importlib.util.spec_from_file_location("coverage_sample", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    idx = pd.date_range("2026-08-20", periods=1440, freq="min", tz="UTC")
    # Spot archives use microseconds after 2025; perpetuals still use milliseconds.
    spot = "\n".join(f"{ts.value // 1000},100,101,99,100,1" for ts in idx)
    perp = "\n".join(f"{ts.value // 1000000},100,101,99,100,1" for ts in idx)
    exact = idx[0]
    late = idx[480] + pd.Timedelta(milliseconds=3)
    funding = "calc_time,last_funding_rate\n" + "\n".join(
        f"{ts.value // 1000000},0.001" for ts in (exact, late)
    )

    def archive_response(url, timeout):
        body = funding if "fundingRate" in url else perp if "futures/um/daily" in url else spot
        buf = BytesIO()
        with ZipFile(buf, "w") as archive:
            archive.writestr("source.csv", body)
        buf.seek(0)
        return buf

    monkeypatch.setattr(module, "urlopen", archive_response)
    output = tmp_path / "sample"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(path), "--output", str(output), "--start", "2026-08-20",
            "--days", "1", "--allow-network",
        ],
    )

    assert module.main() == 0
    manifest = json.loads((output / "dataset_manifest.json").read_text(encoding="utf-8"))
    coverage = manifest["funding_settlement_coverage"]
    assert (coverage["expected"], coverage["exact_ready"], coverage["unready"]) == (3, 1, 2)
    assert coverage["source_late_within_next_minute"] == 1
    assert coverage["max_source_delay_ms"] == 3
    assert not coverage["exact_funding_coverage_complete"]
    basket = pd.read_parquet(output / "basket.parquet")
    assert basket.loc[idx[480], "funding_time"] == exact
    assert not basket.loc[idx[480], "funding_readiness"]
    assert basket.loc[idx[481], "funding_time"] == late
