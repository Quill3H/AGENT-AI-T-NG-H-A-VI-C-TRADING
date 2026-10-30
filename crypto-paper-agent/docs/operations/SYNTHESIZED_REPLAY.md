# Synthesized replay inputs

The default is `--mode historical`: local cache only, fail closed. Missing
history or funding never switches to generated prices, even with the legacy
`--allow-network` argument. Prepare and independently verify the source data
before replay; this runner does not acquire market history.

For a software smoke test, select synthetic explicitly and a new output:

```powershell
python scripts/run_synthesized_backtest.py --mode synthetic --start-date 2025-01-01 --end-date 2025-02-01 --seed 42 --output-dir reports/synthetic-smoke-new
```

Dates are UTC, aligned to four-hour boundaries, with the end excluded. The last
15m candle closes exactly at the end. Existing nonempty output directories are
refused. Synthetic caches are isolated under `data/raw/synthetic/v1/seed-N/`
by window and universe identity. Generated funding is constant and disclosed;
these reports receive economic `REJECTED` irrespective of their profit.

Historical cache layout is `data/raw/binance/SYMBOL/TIMEFRAME.parquet`, with the
legacy canonical cache path also checked for conflicts. Each Parquet needs a
matching `.parquet.source.json` sidecar containing:

```json
{
  "mode": "historical",
  "source": "binance_usdm",
  "market": "perpetual",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "source_uri": "<actual source locator>",
  "sha256": "<SHA256 of these exact Parquet bytes>",
  "funding_source": "binance_usdm"
}
```

This is a manifest contract, not proof that a source declaration is authentic.
Keep the original source files/checksums, acquisition details and independent
audit. Do not relabel synthetic or unproven files as historical. The loader's
`historical_verified` field denotes successful cache-contract checks; economic
eligibility still only requests review and cannot grant owner acceptance.

Both 15m and 4h frames require a continuous UTC OHLCV index for the requested
window. The 15m frame also requires finite numeric `funding_rate`, boolean
`funding_readiness`, `funding_time` (normalized event), `funding_source_time`,
`funding_available_time` and explicit `funding_interval_hours` in 1/2/4/8.
Repeated as-of observations may share an event; conflicting rate/time/interval
records reject. Every scheduled settlement must be present. Settlement source
and availability may differ from the normalized event only within the declared
one-second jitter; decision availability is checked separately at candle close.

Absent a declared `--max-drawdown-pct`, positive otherwise valid historical
metrics receive `NOT_EVALUATED`. An explicit ceiling and `--min-trades` supply
the evaluation contract; they are not default owner risk policy. Losses,
nonpositive expectancy, PF <= 1, invalid metrics and insufficient samples reject.
`ELIGIBLE_FOR_REVIEW` still requires independent source/protocol/economic review.
No strategy tuning or extra trades are performed to achieve a sample target.

The default pytest artifact audit concerns the frozen old seven-artifact set.
Set `PAPER_ARTIFACT_DIR` to that preserved directory; do not point those fixed
historical-count tests at a new replay. The E2E suite generates new explicit
synthetic outputs in pytest scratch storage. Set `PYTEST_FAST_E2E=1` for its
one-month engineering smoke; leave it unset for the one-year run.
