# OKX public data check — 2026-11-02

Owner asked why Binance blocked and whether OKX offers free market data. Research and read-only diagnostic only; no venue adapter, wallet migration or trading rule change.

## Evidence
Observed at2026-11-02T08:56:39.678Z (15:56:39 Asia/Bangkok) from existing Render Singapore service, commit3533381. https://paper-studio-connectivity.onrender.com/okx-probe returned ok:true, authenticated:false. All12fixed requests returned HTTP200, OKX code0 and nonempty data:

- Public clock.
- Live BTC/ETH/SOL/HYPE USDT-SWAP instrument definitions.
- BTC-USDT-SWAP ticker.
- BTC candles15m/1H/4H:50rows each,49confirmed closed rows each.
- BTC historical1m candles, funding-rate history and historical public trades:3records each.

Source instrument contract units: BTC ctVal0.01BTC/contract, lotSz0.01; ETH0.1ETH/contract, lotSz0.01; SOL1SOL/contract, lotSz0.01; HYPE0.1HYPE/contract, lotSz1. Do not reuse Binance quantity filters blindly. Probe does not establish continuous uptime, complete historical coverage, correct replay/funding conversion or successful paper execution on OKX. No credentials sent; requests sequential250ms apart; cache5min. Separate reviewer13scoped tests passed.

## Source documentation
- https://www.okx.com/docs-v5/en/ — Market Data and Public Data require no authentication. History-candles20requests/2sec/IP; funding-rate-history10requests/2sec/IP+instrument; funding history up to3months. Confirm1means a closed candle.
- https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info —418denotes IP auto-ban after rate limiting; limits are per IP. Our cloud failure captured418on/fapi/v1/time but not prior429, Retry-After or full ban message. Specific trigger, culprit and expiry are unknown; shared-host egress is only a possible explanation, not established fact. Do not blame the user's Binance account or Gemini API key.

Original Binance paper ledger remains unchanged. If owner later elects OKX, create venue-specific configuration/accounting/tests and preserve venue identity for existing positions; do not silently settle Binance positions with OKX prices.
