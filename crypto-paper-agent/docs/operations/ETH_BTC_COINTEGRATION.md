# ETH–BTC cointegration v1 — paper research only

This is a separate shared-account workflow, not a single-symbol directional
strategy alias. It cannot submit exchange orders. Parameters are fixed in the
approved 2026-10-22 plan under docs/superpowers/plans/.

Install the ordinary project dependencies plus statsmodels>=0.14.4,<0.16.
The independent tests use pytest; optional RL/pandas-ta are not needed here.

## Reproduce

From crypto-paper-agent (scripts also accept an external working directory):

```text
python scripts/prepare_eth_btc_data.py --output <NEW_DATA> --allow-network
python scripts/run_eth_btc_cointegration.py --data-dir <NEW_DATA> --lot-metadata <LOTS.json> --output <NEW_RESULTS>
```

The downloader is bounded to ETHUSDT/BTCUSDT, 4h/15m/funding, September 2020
through September 2026: 438 monthly ZIPs plus checksum sidecars, 8 workers,
2 attempts per HTTP call. It never downloads spot. Missing sources stop the
preparation. An interrupted directory is marked FAILED and is not performance.

To normalize already-downloaded, checksummed archives offline:

```text
python scripts/prepare_eth_btc_data.py --raw-dir <RAW> --manifest <SOURCE_MANIFEST.json> --output <NEW_DATA>
```

Lot metadata JSON must explicitly identify its source. Example of the snapshot
observed in this task (NOT a claim about all historical contract filters):

```json
{
  "source_url": "https://fapi.binance.com/fapi/v1/exchangeInfo",
  "collected_at": "2026-10-22T04:38:13.102166+00:00",
  "historical_assumption": true,
  "symbols": {
    "ETHUSDT": {"step": 0.001, "min_quantity": 0.001, "min_notional": 20.0},
    "BTCUSDT": {"step": 0.001, "min_quantity": 0.001, "min_notional": 50.0}
  }
}
```

Both fixed periods and six scenarios each run by default: actual/no-positive
funding at costs1x/2x, plus both funding modes with a one-15m-bar BTC-leg delay.
Use --period 2021-2023 or --period 2024-2026 for a bounded rerun. Output must be
new. Missing candles/funding fail before any metrics directory is created.
The legacy --append-ledger option is rejected before reading data or creating
output: main requires preregistration for new ledger runs. Run without that
option to export retrospective artifacts. Existing historical ledger rows are
preserved; do not retroactively preregister them or relabel these windows
untouched OOS.

## Evidence limits

Pair primary samples require both legs to have entered. Aborted entries retain
their real cashflows in account totals, separately from paired win statistics.
No-positive funding clips each positive payment before wallet/risk updates;
this is a separate account rerun, not a post-hoc subtraction.

Price-level regression gives fixed-q price PnL q*change(spread) before lot
rounding. A >1% pair-gross hedge rounding error rejects entry. Quantities stay
fixed; there is no continuous rebalancing or claim of perfect beta neutrality.

Stops have unknown order inside 15m bars. A stopped leg realizes at its stop
(or gap open) with adverse slippage; its partner exits on the next available
open. Intrabar timestamps are conservatively end-labelled. Funding cashflows
use the settlement bar open as an explicit price proxy, not actual mark data.
Historical lot/bracket/fee assumptions, last-price marking, independent review
and prospective paper evidence all remain limits on economic conclusions.
