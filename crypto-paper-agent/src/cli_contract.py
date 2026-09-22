"""Small, side-effect-free validation helpers for public CLI entrypoints."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Iterable


def fail(code: str, message: str) -> int:
    sys.stderr.write(f"ERROR [{code}]: {message}\n")
    return 2


def missing_paths(paths: Iterable[Path]) -> list[Path]:
    return [path for path in paths if not path.is_file()]


def output_exists(path: Path) -> bool:
    return path.exists()

