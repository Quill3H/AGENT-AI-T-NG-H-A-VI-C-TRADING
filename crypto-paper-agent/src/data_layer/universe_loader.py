"""
src/data_layer/universe_loader.py
===================================
Universe Data Loader & Multi-Timeframe Causal Alignment Pipeline.

Target Universe:
    10 Liquid Perpetual Pairs on Binance Futures:
    BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT,
    DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, SUIUSDT.

Timeframes:
    - 15m: Execution time series (35,040 bars/year)
    - 4h:  Macro regime time series (2,190 bars/year)

Key Capabilities:
    1. Historical replay from explicitly sourced local perpetual OHLCV/funding caches.
    2. SHA-bound cache manifests; missing/unproven historical inputs fail closed.
    3. Explicit deterministic synthetic mode in a separate cache namespace.
    4. Rigorous Mathematical Invariant Validation matching BacktestEngine requirements.
    5. Anti-Lookahead Causal Alignment for multi-timeframe 15m/4h strategy execution.
"""
from __future__ import annotations

import os
import hashlib
import json
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from loguru import logger

from src.data_layer.cache_manager import (
    ensure_utc_index,
    timeframe_to_timedelta,
)


# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------

DEFAULT_UNIVERSE = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "SUIUSDT",
]

EXTENDED_UNIVERSE = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "APTUSDT",
    "OPUSDT",
    "ARBUSDT",
    "INJUSDT",
    "TIAUSDT",
    "RENDERUSDT",
    "FETUSDT",
    "PEPEUSDT",
    "WIFUSDT",
]

DEFAULT_TIMEFRAMES = ["15m", "4h"]
BINANCE_FAPI_BASE_URL = "https://fapi.binance.com"
MAX_KLINES_PER_REQUEST = 1000
HTTP_TIMEOUT_SECONDS = 15
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.5

# Canonical Asset Parameters for Correlated Synthetic Dynamics
ASSET_PROFILES: Dict[str, Dict[str, float]] = {
    "BTCUSDT": {"base_price": 60000.0, "beta": 1.0,  "volatility": 0.45, "base_volume": 500.0},
    "ETHUSDT": {"base_price": 3200.0,  "beta": 1.15, "volatility": 0.55, "base_volume": 4000.0},
    "SOLUSDT": {"base_price": 150.0,   "beta": 1.40, "volatility": 0.70, "base_volume": 25000.0},
    "BNBUSDT": {"base_price": 580.0,   "beta": 0.85, "volatility": 0.40, "base_volume": 3000.0},
    "XRPUSDT": {"base_price": 0.55,    "beta": 1.10, "volatility": 0.65, "base_volume": 5000000.0},
    "DOGEUSDT": {"base_price": 0.12,   "beta": 1.50, "volatility": 0.85, "base_volume": 15000000.0},
    "ADAUSDT": {"base_price": 0.38,    "beta": 1.20, "volatility": 0.65, "base_volume": 8000000.0},
    "AVAXUSDT": {"base_price": 28.0,   "beta": 1.35, "volatility": 0.75, "base_volume": 200000.0},
    "LINKUSDT": {"base_price": 14.5,   "beta": 1.25, "volatility": 0.65, "base_volume": 400000.0},
    "SUIUSDT":  {"base_price": 1.85,   "beta": 1.60, "volatility": 0.90, "base_volume": 2000000.0},
    "NEARUSDT": {"base_price": 4.80,   "beta": 1.45, "volatility": 0.80, "base_volume": 1200000.0},
    "APTUSDT":  {"base_price": 9.20,   "beta": 1.40, "volatility": 0.75, "base_volume": 800000.0},
    "OPUSDT":   {"base_price": 1.65,   "beta": 1.50, "volatility": 0.85, "base_volume": 2500000.0},
    "ARBUSDT":  {"base_price": 0.55,   "beta": 1.35, "volatility": 0.75, "base_volume": 4000000.0},
    "INJUSDT":  {"base_price": 22.0,   "beta": 1.55, "volatility": 0.85, "base_volume": 350000.0},
    "TIAUSDT":  {"base_price": 5.40,   "beta": 1.65, "volatility": 0.95, "base_volume": 1100000.0},
    "RENDERUSDT": {"base_price": 5.80, "beta": 1.50, "volatility": 0.85, "base_volume": 900000.0},
    "FETUSDT":  {"base_price": 1.35,   "beta": 1.60, "volatility": 0.90, "base_volume": 2200000.0},
    "PEPEUSDT": {"base_price": 0.000009, "beta": 1.80, "volatility": 1.10, "base_volume": 50000000000.0},
    "WIFUSDT":  {"base_price": 2.45,   "beta": 1.90, "volatility": 1.15, "base_volume": 1800000.0},
}


@dataclass
class UniverseConfig:
    """Configuration container for UniverseDataLoader."""
    symbols: List[str] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))
    timeframes: List[str] = field(default_factory=lambda: list(DEFAULT_TIMEFRAMES))
    raw_data_dir: Path = field(default_factory=lambda: Path("data/raw"))
    exchange: str = "binance"
    allow_network: bool = False
    rate_limit_delay_sec: float = 0.08
    min_cache_coverage_pct: float = 0.99
    compression: str = "snappy"
    mode: str = "historical"
    seed: int = 42


# ---------------------------------------------------------------------------
# UniverseDataLoader Class
# ---------------------------------------------------------------------------

class UniverseDataLoader:
    """
    High-performance multi-pair, multi-timeframe universe data loader.
    Supports local Parquet caching, public Binance REST fetching, and
    deterministic synthetic generation for offline research and backtesting.
    """

    def __init__(
        self,
        config: Optional[Union[Dict[str, Any], UniverseConfig]] = None,
        raw_data_dir: Optional[Union[str, Path]] = None,
        allow_network: Optional[bool] = None,
        universe: Optional[List[str]] = None,
        mode: Optional[str] = None,
        seed: Optional[int] = None,
    ):
        if isinstance(config, UniverseConfig):
            self.cfg = config
        elif isinstance(config, dict):
            symbols = config.get("universe", config.get("symbols", DEFAULT_UNIVERSE))
            timeframes = config.get("timeframes", DEFAULT_TIMEFRAMES)
            data_dir = config.get("data", {}).get("raw_data_dir", config.get("raw_data_dir", "data/raw"))
            exchange = config.get("data", {}).get("exchange", config.get("exchange", "binance"))
            net_allowed = config.get("allow_network", allow_network)
            self.cfg = UniverseConfig(
                symbols=list(symbols),
                timeframes=list(timeframes),
                raw_data_dir=Path(data_dir),
                exchange=exchange,
                allow_network=net_allowed,
                mode=config.get("mode", "historical"),
                seed=config.get("seed", 42),
            )
        else:
            self.cfg = UniverseConfig(
                symbols=list(universe) if universe else list(DEFAULT_UNIVERSE),
                raw_data_dir=Path(raw_data_dir) if raw_data_dir else Path("data/raw"),
                allow_network=bool(allow_network),
            )

        if raw_data_dir:
            self.cfg.raw_data_dir = Path(raw_data_dir)
        if allow_network is not None:
            self.cfg.allow_network = allow_network
        if universe:
            self.cfg.symbols = list(universe)
        if mode is not None:
            self.cfg.mode = mode
        if seed is not None:
            self.cfg.seed = seed
        if self.cfg.mode not in ("historical", "synthetic"):
            raise ValueError("mode must be historical or synthetic")
        self.provenance: Dict[str, Any] = {}
        self._synthetic_window = "unloaded"

        self.root_dir = self.cfg.raw_data_dir.resolve()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CryptoPaperUniverseLoader/1.0",
            "Accept": "application/json",
        })

    # -----------------------------------------------------------------------
    # Path & Cache Resolution
    # -----------------------------------------------------------------------

    def get_cache_path(self, symbol: str, timeframe: str) -> Path:
        """
        Returns canonical path: data/raw/<exchange>/<symbol>/<timeframe>.parquet.
        """
        safe_symbol = symbol.replace("/", "").replace(":", "").upper()
        root = self.root_dir
        if self.cfg.mode == "synthetic":
            root = root / "synthetic" / "v1" / f"seed-{self.cfg.seed}" / self._synthetic_window
        return root / self.cfg.exchange / safe_symbol / f"{timeframe}.parquet"

    def get_legacy_cache_path(self, symbol: str, timeframe: str) -> Path:
        """
        Returns legacy subfolder path: data/raw/<exchange>/<symbol>/<timeframe>/ohlcv.parquet.
        """
        safe_symbol = symbol.replace("/", "").replace(":", "").upper()
        return self.get_cache_path(safe_symbol, timeframe).parent / timeframe / "ohlcv.parquet"

    def is_cached(
        self,
        symbol: str,
        timeframe: str,
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
    ) -> bool:
        """
        Verifies if local Parquet cache exists and provides sufficient coverage.
        """
        path = self.get_cache_path(symbol, timeframe)
        if not path.is_file():
            path = self.get_legacy_cache_path(symbol, timeframe)
            if not path.is_file():
                return False

        try:
            schema = pq.read_schema(path)
            col_candidates = [c for c in ["timestamp", "__index_level_0__"] if c in schema.names]
            cols = [col_candidates[0]] if col_candidates else []
            table_idx = pq.read_table(path, columns=cols).to_pandas()
            if "__index_level_0__" in table_idx.columns:
                table_idx = table_idx.rename(columns={"__index_level_0__": "timestamp"})
            df_idx = ensure_utc_index(table_idx)
            if len(df_idx.index) == 0 or not isinstance(df_idx.index, pd.DatetimeIndex):
                return False

            min_ts = df_idx.index.min()
            max_ts = df_idx.index.max()
            freq = timeframe_to_timedelta(timeframe)
            expected_bars = int((end_dt - start_dt) / freq) + 1

            sub_idx = df_idx.loc[start_dt:end_dt]
            actual_bars = len(sub_idx)

            if min_ts <= start_dt and max_ts >= (end_dt - freq):
                return actual_bars >= expected_bars * self.cfg.min_cache_coverage_pct
            return False
        except Exception as exc:
            logger.warning(f"Error checking cache metadata for {symbol} {timeframe}: {exc}")
            return False

    # -----------------------------------------------------------------------
    # Public Binance REST Ingestion
    # -----------------------------------------------------------------------

    def fetch_binance_klines(
        self,
        symbol: str,
        interval: str,
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
    ) -> pd.DataFrame:
        """
        Paginates Binance USD-M Futures public REST API without authentication.
        """
        if not self.cfg.allow_network:
            raise PermissionError(
                "Network access disabled (allow_network=False). Cannot fetch Binance API."
            )

        safe_symbol = symbol.replace("/", "").replace(":", "").upper()
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        url = f"{BINANCE_FAPI_BASE_URL}/fapi/v1/klines"

        all_records: List[Dict[str, Any]] = []
        current_start = start_ms

        logger.info(f"Fetching public Binance klines {safe_symbol} {interval} from {start_dt} to {end_dt}...")

        while current_start < end_ms:
            params = {
                "symbol": safe_symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ms,
                "limit": MAX_KLINES_PER_REQUEST,
            }

            resp = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = self.session.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
                    if resp.status_code == 429:
                        wait = float(resp.headers.get("Retry-After", 10.0))
                        logger.warning(f"Binance 429 Rate Limit. Sleeping {wait}s...")
                        time.sleep(wait)
                        continue
                    resp.raise_for_status()
                    break
                except requests.RequestException as err:
                    if attempt == MAX_RETRIES:
                        raise ConnectionError(f"Binance API failure after {MAX_RETRIES} retries: {err}") from err
                    sleep_time = INITIAL_BACKOFF ** attempt
                    time.sleep(sleep_time)

            if resp is None:
                break

            data = resp.json()
            if not data or not isinstance(data, list):
                break

            for item in data:
                all_records.append({
                    "timestamp": pd.to_datetime(item[0], unit="ms", utc=True),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                })

            last_open_time = data[-1][0]
            if len(data) < MAX_KLINES_PER_REQUEST or last_open_time >= end_ms:
                break
            current_start = last_open_time + 1
            time.sleep(self.cfg.rate_limit_delay_sec)

        if not all_records:
            return pd.DataFrame()

        df = pd.DataFrame(all_records).drop_duplicates(subset=["timestamp"]).set_index("timestamp").sort_index()
        df = df.loc[start_dt:end_dt]
        return df

    # -----------------------------------------------------------------------
    # Deterministic Correlated Synthetic Fallback Generator
    # -----------------------------------------------------------------------

    def generate_synthetic_universe(
        self,
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
        symbols: Optional[List[str]] = None,
        seed: int = 42,
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Generates deterministic, correlated 15m base execution candles and causally
        aggregates them into 4h macro regime candles for all universe symbols.
        Guarantees 100% offline test reproducibility with realistic market dynamics.
        """
        rng = np.random.default_rng(seed)
        target_symbols = symbols if symbols else self.cfg.symbols

        # Generate continuous 15m timestamp sequence
        timestamps_15m = pd.date_range(start_dt, end_dt, freq="15min", tz="UTC", inclusive="both", name="timestamp")
        n_bars = len(timestamps_15m)
        if n_bars == 0:
            raise ValueError(f"Invalid date range: start {start_dt} >= end {end_dt}")

        dt_year_fraction = 15.0 / (365.25 * 24.0 * 60.0)

        # 1. Macro Market Factor Driver (Bitcoin Proxy Market Return)
        market_vol = 0.50
        market_drift = 0.10
        market_shocks = rng.standard_normal(n_bars)
        market_returns = (market_drift - 0.5 * market_vol ** 2) * dt_year_fraction + \
                         market_vol * np.sqrt(dt_year_fraction) * market_shocks

        universe_data: Dict[str, Dict[str, pd.DataFrame]] = {}

        for sym in target_symbols:
            safe_sym = sym.replace("/", "").replace(":", "").upper()
            profile = ASSET_PROFILES.get(safe_sym, {
                "base_price": 50.0,
                "beta": 1.20,
                "volatility": 0.65,
                "base_volume": 100000.0,
            })

            base_price = profile["base_price"]
            beta = profile["beta"]
            asset_vol = profile["volatility"]
            base_vol = profile["base_volume"]

            # Idiosyncratic component
            idio_shocks = rng.standard_normal(n_bars)
            idio_vol = np.sqrt(max(0.01, asset_vol ** 2 - (beta * market_vol) ** 2))
            asset_returns = beta * market_returns + idio_vol * np.sqrt(dt_year_fraction) * idio_shocks

            # Price path via exponentiated log returns
            log_price_path = np.log(base_price) + np.cumsum(asset_returns)
            close_prices = np.exp(log_price_path)

            # Intraday 15m OHLC construction
            intraday_vol = asset_vol * np.sqrt(dt_year_fraction)
            high_wick_ratio = np.abs(rng.normal(1.2, 0.4, n_bars)) * intraday_vol
            low_wick_ratio = np.abs(rng.normal(1.2, 0.4, n_bars)) * intraday_vol

            # Open of bar k is Close of bar k-1 (first bar Open = base_price)
            open_prices = np.empty(n_bars, dtype=np.float64)
            open_prices[0] = base_price
            open_prices[1:] = close_prices[:-1]

            max_oc = np.maximum(open_prices, close_prices)
            min_oc = np.minimum(open_prices, close_prices)

            high_prices = max_oc * (1.0 + high_wick_ratio)
            low_prices = min_oc * (1.0 - low_wick_ratio)
            low_prices = np.maximum(low_prices, min_oc * 0.0001)  # Strictly positive

            # Volume simulation with volume-volatility correlation
            abs_ret = np.abs(asset_returns)
            volume = base_vol * (1.0 + 3.0 * (abs_ret / np.mean(abs_ret))) * rng.uniform(0.7, 1.4, n_bars)
            volume = np.maximum(volume, 1.0)  # Positive volume

            df_15m = pd.DataFrame(
                {
                    "open": np.round(open_prices, 6),
                    "high": np.round(high_prices, 6),
                    "low": np.round(low_prices, 6),
                    "close": np.round(close_prices, 6),
                    "volume": np.round(volume, 4),
                },
                index=timestamps_15m,
            )

            df_15m = ensure_utc_index(df_15m)
            self.validate_dataset(df_15m, safe_sym, "15m")

            # 2. Causal Bar Aggregation: 15m -> 4h
            df_4h = self._resample_15m_to_4h(df_15m)
            df_4h = ensure_utc_index(df_4h)
            self.validate_dataset(df_4h, safe_sym, "4h")

            universe_data[safe_sym] = {
                "15m": df_15m,
                "4h": df_4h,
            }

        return universe_data

    @staticmethod
    def _resample_15m_to_4h(df_15m: pd.DataFrame) -> pd.DataFrame:
        """
        Causally aggregates 15m candles into 4h candles matching standard exchange conventions.
        """
        grouped = df_15m.resample("4h", closed="left", label="left")
        df_4h = pd.DataFrame({
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
            "volume": grouped["volume"].sum(),
        }).dropna()
        df_4h.index.name = "timestamp"
        return df_4h

    # -----------------------------------------------------------------------
    # Data Validation & Mathematical Invariants
    # -----------------------------------------------------------------------

    @staticmethod
    def validate_dataset(df: Any, symbol: str, timeframe: str) -> None:
        """
        Rigorous fail-closed validation matching BacktestEngine.validate_dataset.
        """
        name = f"{symbol}:{timeframe}"
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Dataset {name} must be a pd.DataFrame, got {type(df).__name__}")
        if df.empty:
            raise ValueError(f"Dataset {name} is empty.")

        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError(f"Dataset {name} index must be DatetimeIndex, got {type(df.index).__name__}")
        if df.index.tz is None or str(df.index.tz) not in ("UTC", "UTC+00:00"):
            raise ValueError(f"Dataset {name} DatetimeIndex must have UTC timezone.")

        if not df.index.is_monotonic_increasing:
            raise ValueError(f"Dataset {name} timestamps must be strictly monotonic increasing.")
        if df.index.has_duplicates:
            raise ValueError(f"Dataset {name} contains duplicate timestamps.")

        req_cols = ["open", "high", "low", "close", "volume"]
        for c in req_cols:
            if c not in df.columns:
                raise ValueError(f"Dataset {name} missing required column '{c}'")

        for c in ["open", "high", "low", "close"]:
            col_data = df[c]
            if col_data.isna().any():
                raise ValueError(f"Dataset {name} column '{c}' contains NaN values.")
            if (col_data.apply(lambda x: type(x) is bool)).any():
                raise TypeError(f"Dataset {name} column '{c}' contains boolean values.")
            arr = col_data.to_numpy(dtype=float)
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"Dataset {name} column '{c}' contains non-finite values (Inf/-Inf).")
            if not np.all(arr > 0):
                raise ValueError(f"Dataset {name} column '{c}' contains non-positive values (<= 0).")

        vol_arr = df["volume"].to_numpy(dtype=float)
        if not np.all(np.isfinite(vol_arr)):
            raise ValueError(f"Dataset {name} volume contains non-finite values.")
        if not np.all(vol_arr >= 0):
            raise ValueError(f"Dataset {name} volume contains negative values (< 0).")

        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)

        max_oc = np.maximum(opens, closes)
        min_oc = np.minimum(opens, closes)

        if np.any(highs < lows):
            raise ValueError(f"Dataset {name} contains candles where high < low.")
        if np.any(highs < max_oc - 1e-6):
            raise ValueError(f"Dataset {name} contains candles where high < max(open, close).")
        if np.any(lows > min_oc + 1e-6):
            raise ValueError(f"Dataset {name} contains candles where low > min(open, close).")

    # -----------------------------------------------------------------------
    # Causal Multi-Timeframe Alignment
    # -----------------------------------------------------------------------

    @staticmethod
    def get_causal_4h_for_15m(
        timestamp_15m: pd.Timestamp,
        df_4h: pd.DataFrame,
    ) -> Optional[pd.Series]:
        """
        Extracts the latest completed 4h candle available at the close of 15m bar timestamp_15m.
        Zero Lookahead Bias Guarantee:
            15m candle opened at T closes at T + 15m.
            A 4h candle opened at T_4h closes at T_4h + 4h.
            Condition: T_4h + 4h <= T + 15m -> T_4h <= T - 3h45m.
        """
        close_15m = timestamp_15m + pd.Timedelta(minutes=15)
        cutoff_4h_open = close_15m - pd.Timedelta(hours=4)
        available_4h = df_4h.loc[:cutoff_4h_open]
        if available_4h.empty:
            return None
        return available_4h.iloc[-1]

    @staticmethod
    def align_multi_timeframe(
        df_15m: pd.DataFrame,
        df_4h: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Builds a causal lookup table mapping each 15m bar to the latest closed 4h bar.
        Uses merge_asof on close_time to guarantee mathematical causal invariance.
        """
        df_15m_temp = df_15m.copy()
        df_4h_temp = df_4h.copy()

        df_15m_temp["close_time"] = df_15m_temp.index + pd.Timedelta(minutes=15)
        df_4h_temp["close_time"] = df_4h_temp.index + pd.Timedelta(hours=4)
        df_4h_temp["macro_4h_open_time"] = df_4h_temp.index

        aligned = pd.merge_asof(
            df_15m_temp.sort_values("close_time"),
            df_4h_temp[["close_time", "macro_4h_open_time", "open", "high", "low", "close"]].sort_values("close_time"),
            on="close_time",
            direction="backward",
            suffixes=("", "_4h_closed"),
        )
        aligned = aligned.set_index(df_15m.index)
        aligned = aligned.drop(columns=["close_time"])
        return aligned

    # -----------------------------------------------------------------------
    # Primary Ingestion & Caching Orchestrator
    # -----------------------------------------------------------------------

    def save_to_cache(self, df: pd.DataFrame, symbol: str, timeframe: str,
                      provenance: Optional[Dict[str, Any]] = None) -> Path:
        """
        Atomically saves DataFrame to Parquet under data/raw/<exchange>/<symbol>/<timeframe>.parquet.
        """
        # A cache writer must declare its source; old unlabelled files are never upgraded.
        if provenance is None:
            raise ValueError("cache write requires explicit source provenance")
        dest_path = self.get_cache_path(symbol, timeframe)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        df_to_save = ensure_utc_index(df.copy())
        if df_to_save.index.name is None:
            df_to_save.index.name = "timestamp"
        table = pa.Table.from_pandas(df_to_save, preserve_index=True)

        fd, temp_file = tempfile.mkstemp(prefix=f".{dest_path.name}.", suffix=".tmp", dir=dest_path.parent)
        os.close(fd)
        temp_path = Path(temp_file)

        try:
            pq.write_table(table, temp_path, compression=self.cfg.compression)
            os.replace(temp_path, dest_path)
            manifest = dict(provenance, schema_version=1, mode=self.cfg.mode,
                            symbol=symbol, timeframe=timeframe,
                            sha256=hashlib.sha256(dest_path.read_bytes()).hexdigest())
            manifest_path = dest_path.with_suffix(dest_path.suffix + ".source.json")
            temp_manifest = manifest_path.with_suffix(".tmp")
            temp_manifest.write_text(json.dumps(manifest, sort_keys=True, allow_nan=False), encoding="utf-8")
            os.replace(temp_manifest, manifest_path)
        finally:
            temp_path.unlink(missing_ok=True)

        logger.debug(f"Saved {symbol} {timeframe} ({len(df)} rows) to cache: {dest_path}")
        return dest_path

    def load_symbol(
        self,
        symbol: str,
        timeframe: str,
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
        force_synthetic: bool = False,
    ) -> pd.DataFrame:
        """
        Loads symbol data from cache, Binance public API, or synthetic fallback generator.
        """
        safe_symbol = symbol.replace("/", "").replace(":", "").upper()
        if force_synthetic or self.cfg.mode == "synthetic":
            return self.load_universe(start_dt, end_dt, [timeframe], [safe_symbol], force_synthetic)[safe_symbol][timeframe]
        paths = [p for p in (self.get_cache_path(safe_symbol, timeframe),
                             self.get_legacy_cache_path(safe_symbol, timeframe)) if p.is_file()]
        if not paths:
            # This pipeline requires independently sourced funding as well as bars.
            # Public OHLCV alone cannot satisfy that historical input contract.
            raise ValueError(f"historical cache missing for {safe_symbol}:{timeframe}; prepare verified bars and funding")
        manifests, cache_bytes = [], []
        for path in paths:
            try:
                manifest = json.loads(path.with_suffix(path.suffix + ".source.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ValueError(f"historical provenance missing or corrupt: {path}") from exc
            raw = path.read_bytes()
            if (manifest.get("mode") != "historical" or manifest.get("source") != "binance_usdm"
                    or manifest.get("market") != "perpetual" or not manifest.get("source_uri")
                    or manifest.get("symbol") != safe_symbol or manifest.get("timeframe") != timeframe
                    or manifest.get("sha256") != hashlib.sha256(raw).hexdigest()):
                raise ValueError(f"historical provenance identity/hash mismatch: {path}")
            if timeframe == "15m" and manifest.get("funding_source") != "binance_usdm":
                raise ValueError(f"historical funding provenance missing: {path}")
            manifests.append(manifest)
            cache_bytes.append(raw)
        if len({m['sha256'] for m in manifests}) != 1:
            raise ValueError(f"historical cache conflict for {safe_symbol}:{timeframe}")
        try:
            # Parse exactly the bytes whose hash was checked, even if a cache writer races us.
            df = pq.read_table(pa.BufferReader(cache_bytes[0])).to_pandas()
            df = ensure_utc_index(df)
            df = df.loc[start_dt:end_dt].copy()
            self.validate_dataset(df, safe_symbol, timeframe)
            expected = pd.date_range(start_dt, end_dt, freq=timeframe_to_timedelta(timeframe), name=df.index.name)
            if not df.index.equals(expected):
                raise ValueError("missing/misaligned historical timestamps")
            if timeframe == "15m":
                self.validate_funding(df)
        except Exception as exc:
            raise ValueError(f"invalid historical input {safe_symbol}:{timeframe}: {exc}") from exc
        self.provenance.setdefault("datasets", []).append(manifests[0])
        return df

    @staticmethod
    def validate_funding(df: pd.DataFrame) -> None:
        """Validate settled-event identity without converting observations to events.

        A source timestamp may lag its normalized settlement by at most one second,
        matching vision_dataset. This tolerance never admits a later decision input.
        """
        required = ('funding_rate', 'funding_time', 'funding_readiness',
                    'funding_source_time', 'funding_available_time', 'funding_interval_hours')
        if any(c not in df for c in required):
            raise ValueError("funding event/source/availability columns required")
        rates = df['funding_rate']
        if any(type(v) is bool or not isinstance(v, (int, float)) for v in rates):
            raise ValueError("invalid funding rate type")
        if not np.isfinite(rates.to_numpy(dtype=float)).all():
            raise ValueError("nonfinite funding rate")
        if not all(isinstance(v, (bool, np.bool_)) and bool(v) for v in df['funding_readiness']):
            raise ValueError("funding not ready")
        intervals = df['funding_interval_hours']
        if any(type(v) is bool or not isinstance(v, (int, float)) or v not in (1, 2, 4, 8) for v in intervals):
            raise ValueError("unsupported funding interval; explicit 1/2/4/8h schedule required")
        event = pd.to_datetime(df['funding_time'], utc=True, errors='coerce')
        source = pd.to_datetime(df['funding_source_time'], utc=True, errors='coerce')
        available = pd.to_datetime(df['funding_available_time'], utc=True, errors='coerce')
        if event.isna().any() or source.isna().any() or available.isna().any():
            raise ValueError("invalid funding timestamps")
        if ((event > df.index) | (event < df.index - pd.to_timedelta(intervals.to_numpy(), unit='h'))).any():
            raise ValueError("missing/stale/future funding event")
        if not ((event.dt.hour % intervals == 0) & (event == event.dt.floor('h'))).all():
            raise ValueError("invalid funding settlement event")
        if ((source < event) | (source > event + pd.Timedelta(seconds=1)) | (available < source)).any():
            raise ValueError("funding source/event/availability mismatch")
        if (available > df.index + pd.Timedelta(minutes=15)).any():
            raise ValueError("funding unavailable at decision time")
        settlements = (df.index.hour % intervals.to_numpy() == 0) & (df.index == df.index.floor('h'))
        if (event.loc[settlements].array != df.index[settlements]).any():
            raise ValueError("missing funding settlement")
        # Settlement cashflow precedes open-time admissions. Close-time availability
        # alone cannot make a later observation available at that earlier phase.
        if (available.loc[settlements] > event.loc[settlements] + pd.Timedelta(seconds=1)).any():
            raise ValueError("funding settlement availability exceeds declared jitter")
        # Repeated as-of observations are legal; conflicting records for one event are not.
        events = pd.DataFrame({'event': event, 'rate': rates, 'source': source, 'available': available,
                               'interval': intervals})
        if (events.groupby('event').nunique() > 1).any().any():
            raise ValueError("duplicate/conflicting funding event")

    def load_universe(
        self,
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
        timeframes: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        force_synthetic: bool = False,
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Loads the complete multi-pair, multi-timeframe universe dictionary.
        Returns: {symbol: {"15m": df_15m, "4h": df_4h}}
        """
        target_symbols = symbols if symbols else self.cfg.symbols
        target_tfs = timeframes if timeframes else self.cfg.timeframes

        if force_synthetic and self.cfg.mode != "synthetic":
            loader = UniverseDataLoader(raw_data_dir=self.root_dir, mode="synthetic", seed=self.cfg.seed)
            result = loader.load_universe(start_dt, end_dt, target_tfs, target_symbols)
            self.provenance = loader.provenance
            return result
        self.provenance = {'mode': self.cfg.mode, 'historical_verified': False,
                           'source': 'synthetic_generator' if self.cfg.mode == 'synthetic' else 'binance_usdm',
                           'funding_source': 'synthetic_constant' if self.cfg.mode == 'synthetic' else 'binance_usdm',
                           'datasets': []}
        if self.cfg.mode == 'synthetic':
            self.provenance['seed'] = self.cfg.seed
            self._synthetic_window = hashlib.sha256(f'{start_dt}|{end_dt}|{target_symbols}'.encode()).hexdigest()[:16]
            generated = self.generate_synthetic_universe(start_dt, end_dt, target_symbols, seed=self.cfg.seed)
            results = {}
            for sym in target_symbols:
                results[sym] = {}
                for tf in target_tfs:
                    df = generated[sym][tf]
                    if tf == '15m':
                        event = df.index.floor('8h')
                        df['funding_rate'] = 0.0001
                        df['funding_time'] = event
                        df['funding_source_time'] = event
                        df['funding_available_time'] = event
                        df['funding_readiness'] = True
                        df['funding_source'] = 'synthetic_constant'
                        df['funding_interval_hours'] = 8
                    path = self.save_to_cache(df, sym, tf, provenance={'source': 'synthetic_generator',
                        'market': 'synthetic_perpetual', 'funding_source': 'synthetic_constant', 'seed': self.cfg.seed})
                    self.provenance['datasets'].append(json.loads(path.with_suffix(path.suffix + '.source.json').read_text()))
                    results[sym][tf] = df
            return results

        results: Dict[str, Dict[str, pd.DataFrame]] = {}
        for sym in target_symbols:
            results[sym] = {}
            for tf in target_tfs:
                results[sym][tf] = self.load_symbol(sym, tf, start_dt, end_dt, force_synthetic=force_synthetic)
        self.provenance['historical_verified'] = True
        return results
