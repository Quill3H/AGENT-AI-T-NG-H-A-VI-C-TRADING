# Backtest Lab: crypto ORB + FVG portfolio

Run from `crypto-paper-agent` using the project's Python environment:

```powershell
python scripts/backtest_lab.py --data-dir <VISION_ZIP_DIRECTORY> --portfolio-config config/research/crypto_orb_portfolio.yaml --output <NEW_OUTPUT_DIRECTORY> --cache-dir <CACHE_DIRECTORY>
```

This is an additive mode of Backtest Lab. Existing `--batch` jobs retain their
behavior. Choose one mode. Results are historical paper research, not an
economic acceptance verdict. No orders are sent to an exchange.

The default is ten crypto USDT perpetuals, a shared $10,000 account, one
position per symbol and at most **four portfolio positions**. Pending orders
reserve slots. The fixed YAML symbol order resolves simultaneous signals.
No daily trade limit applies. A new three-candle pattern must start after the
previous exit on that symbol; busy/capacity signals are discarded, not queued.
60 completed trades per full Monday–Sunday week and 240 per full calendar
month are sample targets. Empty windows fail; partial windows are labelled
PARTIAL. No signal or parameter is changed to meet these targets.

## Frozen setup

- Seven days/week. New York time (DST aware): reference range 09:30–09:44;
  signal candles 09:51–15:44; next minute opening fill; request flat at 16:00.
  This time anchor is a crypto adaptation, not a crypto exchange opening.
- Three closed 1m bars. Long: third low above first high by at least one
  observed price-grid increment, first high above range high; short is mirrored.
  Middle body follows the trade direction, >=1.5 times median true range of
  the preceding 20 bars (excluding the middle bar), and >=60% of its range.
  Signal close must agree with session VWAP (typical price weighted by volume).
- Stop one observed increment beyond the first bar; target 1R referenced to
  **signal close**, already known when submitting. Unknown next opening price
  is never used to construct a decision. Gap/slippage can change achieved R;
  invalid stop/target bounds at actual fill are rejected by the broker.
- Risk budget 0.25% marked equity per trade before the existing streak
  reduction, notional ceiling 25% equity per entry, leverage 1x, aggregate
  gross notional <=100% equity on admission. Prices/equity can subsequently
  drift; this is not an automatic continuous rebalance rule.
- Assumed taker fee 0.05% and adverse slippage 0.02% each side. Set
  `cost_multiplier: 2` for the predeclared stress case. Slippage is embedded
  in price PnL; its diagnostic amount must not be deducted a second time.

## Execution and input limits

The existing PaperBroker supplies gap exits, stop-first intrabar priority,
fees, funding, isolated-margin calculations, accounting checks, a rolling
24h loss breaker and loss-streak sizing. `process_batch` puts a barrier between
each phase across all symbols: opening marks, gap exits, funding, manual
closes, entries, intrabar protection and closing marks. This prevents one
symbol's minute close/profit from financing another's earlier opening fill.
Same-minute exit ordering remains a fixed-order OHLC approximation.

Use official Binance Vision monthly ZIPs and `.CHECKSUM` sidecars named:

```
klines_BTCUSDT-1m-2026-09.zip
klines_BTCUSDT-15m-2026-09.zip
fundingRate_BTCUSDT-fundingRate-2026-09.zip
```

Repeat for every configured symbol/month. Full monthly minute continuity,
UTC uniqueness, OHLCV and checksums are required. An independent 15m archive
is compared with 1m aggregation; a conflict publishes an audit and computes
no PnL. Funding uses actual archived interval/event records (not an assumed
8h schedule), with the project's <=1-second boundary normalization; original
source timestamps remain in raw ZIPs and the exported funding-source ledger.

Broker conventions supersede the earlier output-only protocol where they
differ: gap exits precede funding, manual closes follow it, funding is valued
at the **trade-bar open proxy**, and favorable gap TP exits use the opening
price with adverse slippage. The unused downloaded mark-price archives are
not claimed as settlement inputs. All entries/funding precede intrabar exits.

Each day's price-grid increment is inferred and frozen from that symbol's
completed 09:30–09:44 opening-range OHLC only, before any signal. The monthly
increment in the data audit is diagnostic and never sets historical stops.
These are not verified exchange tick filters. Fractional quantity is allowed; lot step,
minimum notional, queue position, spread history and partial fills are not
reconstructed. This 1x research configuration supplies synthetic conservative
1% maintenance-margin brackets, explicitly not historical venue brackets.
The manually fixed universe has survivorship/selection limitations. Correlated
crypto trades are not independent statistical samples.

## Artifacts and repeat runs

`result.json` includes settings, source/code/runtime hashes, summary, orders,
trades, source audit, sample targets, rejection reasons and portfolio equity.
CSV ledgers and `report.md` accompany it. Content-addressed cache reuses the
complete artifact set only for identical data/code/config/runtime. Choose a
new output folder on every invocation; outputs/cache cannot overlap inputs
or source/config. An input change during execution prevents publication.

Research claims need untouched historical or forward evidence; selecting
only winners after this replay is not validation. Default September 2026
results are retrospective and do not tune the setup.
