from __future__ import annotations

from pathlib import Path
import subprocess
import sys


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
