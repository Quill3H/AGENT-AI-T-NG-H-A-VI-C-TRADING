"""The ccxt fetcher stays public-only (AGENTS.md: no trading keys, no testnet) and ccxt is pinned."""
import re
from pathlib import Path

import ccxt

from src.data_layer.fetcher import _get_exchange

ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS = ("apiKey", "secret", "password", "uid", "login", "twofa", "privateKey", "walletAddress", "token")


def test_fetcher_exchange_has_no_credentials_and_no_sandbox(monkeypatch):
    for name in ("BINANCE_API_KEY", "BINANCE_SECRET", "BINANCE_APIKEY", "CCXT_API_KEY"):
        monkeypatch.setenv(name, "must-not-be-read")
    exchange = _get_exchange()
    assert isinstance(exchange, ccxt.binance)
    assert not [name for name in CREDENTIALS if getattr(exchange, name, None)]
    assert exchange.check_required_credentials(False) is False
    assert getattr(exchange, "isSandboxModeEnabled", False) is False
    assert exchange.urls["api"]["fapiPublic"].startswith("https://fapi.binance.com/")
    assert "testnet" not in str(exchange.urls["api"])


def test_ccxt_is_pinned_to_the_lock_file_version():
    pins = [re.search(r"^ccxt([^\s#]*)", line, re.M) for line in
            ((ROOT / f).read_text(encoding="utf-8-sig") for f in ("requirements.txt", "requirements-repair-lock.txt"))]
    assert pins[0] and pins[1] and pins[0].group(1) == pins[1].group(1)
    assert pins[0].group(1).startswith("==")
    assert ccxt.__version__ == pins[0].group(1)[2:], "installed ccxt differs from the pin: pip install -r requirements.txt"
