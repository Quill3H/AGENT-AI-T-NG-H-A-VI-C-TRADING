from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_quickstart_runs_offline_from_external_cwd_and_audits_artifacts(
    tmp_path: Path,
) -> None:
    guard = tmp_path / "network_guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        """
import socket

def blocked(*args, **kwargs):
    raise RuntimeError("NETWORK_CALL_BLOCKED_BY_QUICKSTART_TEST")

socket.create_connection = blocked
socket.socket.connect = blocked
""",
        encoding="utf-8",
    )
    output = tmp_path / "quickstart-output"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(guard)
    env["QUICKSTART_NETWORK_GUARD"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "verify_quickstart.py"),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "quickstart_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "AUTHOR_SELF_REVIEWED"
    assert report["network"] == "DISABLED_AND_TEST_GUARDED"
    assert report["artifact_audit"]["missing"] == []
    assert report["artifact_audit"]["absolute_path_leaks"] == []
    for name in (
        "trend_long",
        "trend_short",
        "breakout_long",
        "breakout_short",
        "smc_long",
        "smc_short",
    ):
        assert report["results"][name]["fills"] >= 1
        assert report["results"][name]["realizations"] >= 1
    assert report["results"]["synthetic_ppo"]["actual_timesteps"] >= 256
    assert report["results"]["synthetic_ppo"]["save_load_equal"] is True
