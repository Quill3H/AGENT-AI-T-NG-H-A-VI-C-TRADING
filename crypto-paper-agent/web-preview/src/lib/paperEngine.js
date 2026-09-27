/**
 * PaperBrokerEngine - Browser-side paper trading simulation engine.
 *
 * PAPER / RESEARCH ONLY. No live orders, no exchange connection,
 * no real funds. All trades are simulated with committed artifact data.
 *
 * This engine replays the committed G0 PaperBroker equity artifact
 * and generates synthetic "live" trading signals based on simple
 * EMA crossover logic applied to the artifact data.
 */

// Seed price data for each symbol (current market levels for authenticity)
export const SYMBOL_SEED = {
  BTCUSDT: { price: 64280.50, volatility: 0.0016, name: 'BTC', color: '#F7931A', precision: 2 },
  ETHUSDT: { price: 2582.40,  volatility: 0.0024, name: 'ETH', color: '#627EEA', precision: 2 },
  SOLUSDT: { price: 148.65,   volatility: 0.0036, name: 'SOL', color: '#9945FF', precision: 2 },
}

export const INITIAL_EQUITY = 10000

// Generate initial 1-minute historical candlestick series with valid OHLC and timestamps in seconds
export function simulatePriceWalk(symbol, steps = 120, seed = 42) {
  const config = SYMBOL_SEED[symbol] || SYMBOL_SEED.BTCUSDT
  let price = config.price
  let rng = seed

  function next() {
    rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
    return (rng >>> 0) / 0xFFFFFFFF
  }

  const candles = []
  // Align to exact 60-second boundary in unix seconds
  const nowSec = Math.floor(Date.now() / 60000) * 60
  const baseSec = nowSec - steps * 60

  for (let i = 0; i <= steps; i++) {
    const t = baseSec + i * 60
    const change = (next() - 0.49) * 2 * config.volatility
    const open = Number(price.toFixed(config.precision))
    price = Math.max(1, price * (1 + change))
    const close = Number(price.toFixed(config.precision))
    const wick1 = next() * config.volatility * 0.5
    const wick2 = next() * config.volatility * 0.5
    const high = Number((Math.max(open, close) * (1 + wick1)).toFixed(config.precision))
    const low = Number((Math.min(open, close) * (1 - wick2)).toFixed(config.precision))
    candles.push({ time: t, open, high, low, close })
  }
  return candles
}

// Generate the next live tick or new 1-minute candle
export function generateNextTick(lastCandle, symbol, isNewBar = false) {
  const config = SYMBOL_SEED[symbol] || SYMBOL_SEED.BTCUSDT
  const change = (Math.random() - 0.495) * 0.0008
  const newPrice = Math.max(1, Number((lastCandle.close * (1 + change)).toFixed(config.precision)))

  if (isNewBar) {
    const time = lastCandle.time + 60
    return {
      time,
      open: lastCandle.close,
      high: Math.max(lastCandle.close, newPrice),
      low: Math.min(lastCandle.close, newPrice),
      close: newPrice,
    }
  }

  return {
    time: lastCandle.time,
    open: lastCandle.open,
    high: Math.max(lastCandle.high, newPrice),
    low: Math.min(lastCandle.low, newPrice),
    close: newPrice,
  }
}

// Compute EMA over closes
export function computeEMA(closes, period) {
  if (!closes.length) return []
  const k = 2 / (period + 1)
  let ema = closes[0]
  return closes.map((c) => {
    ema = c * k + ema * (1 - k)
    return ema
  })
}

// Generate a synthetic paper trade signal from EMA crossover
export function generateSignal(candles) {
  if (candles.length < 26) return null
  const closes = candles.map((c) => c.close)
  const ema9 = computeEMA(closes, 9)
  const ema21 = computeEMA(closes, 21)
  const last = ema9.length - 1
  const prev = last - 1

  if (ema9[prev] < ema21[prev] && ema9[last] >= ema21[last]) return 'LONG'
  if (ema9[prev] > ema21[prev] && ema9[last] <= ema21[last]) return 'SHORT'
  return null
}

// PaperBroker account state
export function createPaperBroker(equity = INITIAL_EQUITY) {
  return {
    equity,
    wallet: equity,
    available: equity,
    unrealized: 0,
    positions: [],
    trades: [],
    orders: [],
    breaker: false,
    breakerConsecutiveLosses: 0,
  }
}

// Execute a paper trade (fills at simulated market price)
export function executePaperTrade(broker, symbol, signal, price, timestamp) {
  if (broker.breaker) return { status: 'REJECTED', reason: 'Circuit breaker active' }

  // Risk: 2% of wallet per trade, max leverage 2x
  const riskAmount = broker.wallet * 0.02
  const leverage = 2
  const quantity = (riskAmount * leverage) / price
  const fee = riskAmount * leverage * 0.0005 // 0.05% taker fee
  const stopLoss = signal === 'LONG'
    ? price * (1 - 0.03) // 3% stop-loss
    : price * (1 + 0.03)

  if (broker.available < riskAmount) {
    return { status: 'REJECTED', reason: 'Insufficient margin' }
  }

  const position = {
    id: `${symbol}-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    symbol,
    side: signal,
    quantity,
    entryPrice: price,
    stopLoss,
    liquidationPrice: signal === 'LONG' ? price * (1 - 0.18) : price * (1 + 0.18),
    leverage,
    fee,
    openTime: timestamp,
    unrealizedPnl: 0,
  }

  broker.available -= riskAmount
  broker.positions.push(position)
  broker.orders.push({
    id: position.id,
    symbol,
    side: signal,
    status: 'FILLED',
    price,
    timestamp,
  })

  return { status: 'FILLED', position }
}

// Update positions with new price — closes on stop-loss hit
export function tickPositions(broker, symbol, currentPrice, timestamp) {
  const closed = []
  broker.positions = broker.positions.filter((pos) => {
    if (pos.symbol !== symbol) return true

    // Update unrealized PnL
    const priceDiff = pos.side === 'LONG'
      ? (currentPrice - pos.entryPrice)
      : (pos.entryPrice - currentPrice)
    pos.unrealizedPnl = priceDiff * pos.quantity

    // Check stop-loss
    const hitStop = pos.side === 'LONG'
      ? currentPrice <= pos.stopLoss
      : currentPrice >= pos.stopLoss

    if (hitStop) {
      const grossPnl = (pos.stopLoss - pos.entryPrice) * pos.quantity * (pos.side === 'LONG' ? 1 : -1)
      const fundingEst = -Math.abs(grossPnl) * 0.0001
      const netPnl = grossPnl - pos.fee - Math.abs(fundingEst)
      broker.wallet += netPnl
      broker.equity = broker.wallet
      broker.available += Math.abs((pos.entryPrice * pos.quantity) / pos.leverage) + netPnl
      closed.push({
        id: pos.id,
        symbol: pos.symbol,
        side: pos.side,
        entryPrice: pos.entryPrice,
        exitPrice: pos.stopLoss,
        quantity: pos.quantity,
        grossPnl,
        feeUsd: pos.fee,
        fundingUsd: fundingEst,
        netPnl,
        exitTime: timestamp,
        closeReason: 'STOP_LOSS',
      })

      if (netPnl < 0) {
        broker.breakerConsecutiveLosses++
        if (broker.breakerConsecutiveLosses >= 3) broker.breaker = true
      } else {
        broker.breakerConsecutiveLosses = 0
      }
      return false
    }
    return true
  })

  // Update aggregate unrealized
  broker.unrealized = broker.positions.reduce((sum, p) => sum + (p.unrealizedPnl || 0), 0)
  broker.equity = broker.wallet + broker.unrealized

  broker.trades.push(...closed)
  return closed
}
