"""
conftest.py - Pytest shared fixtures
====================================
Cung cap cac fixture dung chung cho toan bo test suite.
"""
from pathlib import Path
import pytest
import yaml


@pytest.fixture
def project_root() -> Path:
    """Tra ve duong dan thu muc goc cua project."""
    return Path(__file__).parent.parent


@pytest.fixture
def config(project_root) -> dict:
    """Nap toan bo default_config.yaml."""
    config_path = project_root / "config" / "default_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
