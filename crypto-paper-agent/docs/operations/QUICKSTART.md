# Paper research quick-start

Code-under-test commit: `51b039b5e1b4ec0b649e9d2604a93a83f01b0a73`.

Run from `crypto-paper-agent/` with Python 3.12 and the pinned project dependencies. Use a **new** output directory each time. The first command is entirely synthetic, uses no exchange credentials or network, and creates six LONG/SHORT strategy lifecycles, a four-account comparison, a 256-step CPU PPO train/save/load/evaluate smoke, and an artifact audit:

```text
python scripts/verify_quickstart.py --output <NEW_OUTPUT_DIRECTORY>
```

Inspect `<NEW_OUTPUT_DIRECTORY>/quickstart_report.json`. `artifact_audit.missing` and `artifact_audit.absolute_path_leaks` must both be empty. The synthetic PnL figures demonstrate execution paths, not market performance. A `NO_TRADES` result on a valid dataset is not a command failure.

For a bounded public sample, explicitly authorize only public-data HTTP for that command:

```text
python scripts/prepare_public_research_sample.py --start 2024-01-01 --days 3 --output <NEW_PUBLIC_DIRECTORY> --allow-network
python scripts/verify_research_smoke.py --public-dir <NEW_PUBLIC_DIRECTORY> --output <NEW_RESEARCH_DIRECTORY>
```

The first command fetches Binance Vision spot/perpetual 1m and funding archives and writes `dataset_manifest.json` with raw URL and archive/CSV hashes. It allows 1–7 days and 0–3 retries, and refuses an existing output target. The second command evaluates the public sample without tuning strategy parameters and also runs synthetic evidence. Read `smoke_results.json`, walk-forward reports and PPO manifests before interpreting results. Three days do not establish economic validity.

For a near-current read-only public REST snapshot, use `scripts/fetch_market_data.py --symbol BTCUSDT --interval 15m --kline-limit 500 --funding-limit 100 --output-dir <NEW_CACHE_DIRECTORY> --allow-network`. This is a downloader/cache operation, **not** a prospective paper session or proof of complete candles. Inspect timestamps and source availability before replay. Repeated runs require a fresh cache root; existing parquet targets are never overwritten.

All order effects stay inside PaperBroker/the funded basket simulator. No command here submits an exchange or testnet order, uses a trading API key, or recommends a trade. To test a custom strategy, start with `python run_backtest.py --help` and the command matrix; keep `--no-fetch` for offline replay and use `--allow-network` only when public download is intended. The old `--run-id` help text describes a timestamp convention, but the actual default identity is deterministic; this wording is a low-priority documentation/UI debt, not the run-ID implementation.
