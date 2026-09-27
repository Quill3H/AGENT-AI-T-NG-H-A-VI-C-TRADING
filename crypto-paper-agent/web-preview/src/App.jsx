/**
 * App.jsx — Binance Futures-style Paper Research Console
 *
 * PAPER / RESEARCH ONLY — NO LIVE ORDERS, NO EXCHANGE CONNECTION.
 * All market data is either from committed public artifacts or browser-side simulation.
 *
 * Features:
 *   • Exact Binance Futures visual layout (desktop-only)
 *   • Coin switcher: BTCUSDT / ETHUSDT / SOLUSDT with reactive candlestick chart
 *   • TradingView-style candlestick chart using lightweight-charts v5
 *   • Live ticker updates for 24h change, high, low, volume
 *   • "Khởi động Bot" paper trading simulation with EMA crossover strategy
 *   • Real-time account balances, open positions, trade history ledger
 */

import { useEffect, useReducer, useRef } from 'react'
import './styles.css'
import { evidence } from './data/evidence'
import {
  SYMBOL_SEED, INITIAL_EQUITY,
  simulatePriceWalk, generateNextTick, generateSignal,
  createPaperBroker, executePaperTrade, tickPositions,
} from './lib/paperEngine'
import { CandlestickChart } from './CandlestickChart'

// ─── Constants ──────────────────────────────────────────────────────────────

export const COINS = [
  { symbol: 'BTCUSDT', name: 'BTC', display: 'BTCUSDT', color: '#F7931A' },
  { symbol: 'ETHUSDT', name: 'ETH', display: 'ETHUSDT', color: '#627EEA' },
  { symbol: 'SOLUSDT', name: 'SOL', display: 'SOLUSDT', color: '#9945FF' },
]

const STRATEGIES = [
  { id: 'ema_cross',    label: 'EMA Cross 9/21', timeframe: '1m' },
  { id: 'trend_follow', label: 'Trend Follow',   timeframe: '15m' },
  { id: 'breakout',     label: 'Breakout',       timeframe: '4h' },
]

const TICK_INTERVAL_MS = 1200 // Live price update speed

const money = (v, prec = 2) =>
  Number(v).toLocaleString('en-US', {
    minimumFractionDigits: prec,
    maximumFractionDigits: prec,
  })

// ─── Initial Market Data Factory ─────────────────────────────────────────────

function createInitialMarket() {
  const candles = {}
  const prices = {}
  const priceDir = {}
  const stats = {}

  for (const coin of COINS) {
    const sym = coin.symbol
    const seed = sym.charCodeAt(0) * 100 + sym.charCodeAt(1)
    const list = simulatePriceWalk(sym, 120, seed)
    candles[sym] = list
    const last = list[list.length - 1]
    const first = list[0]
    prices[sym] = last.close
    priceDir[sym] = 'up'

    const change = last.close - first.open
    const changePct = (change / first.open) * 100
    const highs = list.map((c) => c.high)
    const lows = list.map((c) => c.low)

    stats[sym] = {
      change24h: change,
      changePct24h: changePct,
      high24h: Math.max(...highs),
      low24h: Math.min(...lows),
      volume24h: Number((last.close * 32.4).toFixed(2)),
    }
  }

  return { candles, prices, priceDir, stats }
}

function getInitialCoin() {
  if (typeof window !== 'undefined' && window.location?.search) {
    const param = new URLSearchParams(window.location.search).get('coin')
    if (param && COINS.some((c) => c.symbol === param.toUpperCase())) {
      return param.toUpperCase()
    }
  }
  return 'BTCUSDT'
}

const initialMarket = createInitialMarket()

const initialState = {
  activeCoin: getInitialCoin(),
  botRunning: false,
  botCycle: 0,
  strategy: 'ema_cross',
  broker: createPaperBroker(INITIAL_EQUITY),
  candles: initialMarket.candles,
  prices: initialMarket.prices,
  priceDir: initialMarket.priceDir,
  stats: initialMarket.stats,
  toasts: [],
  tradeTab: 'closed',
}

// ─── State Reducer ───────────────────────────────────────────────────────────

function reducer(state, action) {
  switch (action.type) {
    case 'SET_COIN': {
      if (typeof window !== 'undefined' && window.history?.replaceState) {
        const url = new URL(window.location.href)
        url.searchParams.set('coin', action.coin)
        window.history.replaceState(null, '', url.toString())
      }
      return { ...state, activeCoin: action.coin }
    }

    case 'SET_STRATEGY':
      return { ...state, strategy: action.strategy }

    case 'BOT_START':
      return {
        ...state,
        botRunning: true,
        broker: createPaperBroker(INITIAL_EQUITY),
      }

    case 'BOT_STOP':
      return { ...state, botRunning: false }

    case 'PRICE_TICK': {
      const { symbol, candle, prevPrice, newPrice, signal, broker } = action
      const dir = newPrice >= prevPrice ? 'up' : 'down'

      // Update candles immutably
      const coinCandles = state.candles[symbol] || []
      const nextCandles = [...coinCandles.slice(0, -1), candle]

      // Update stats
      const first = coinCandles[0] || candle
      const change = newPrice - first.open
      const changePct = (change / first.open) * 100
      const currentStats = state.stats[symbol] || {}
      const updatedStats = {
        ...state.stats,
        [symbol]: {
          change24h: change,
          changePct24h: changePct,
          high24h: Math.max(currentStats.high24h || newPrice, candle.high),
          low24h: Math.min(currentStats.low24h || newPrice, candle.low),
          volume24h: Number(((currentStats.volume24h || 100) + 0.15).toFixed(2)),
        },
      }

      let toasts = state.toasts
      if (signal) {
        toasts = [...toasts.slice(-3), { id: Date.now(), symbol, side: signal }]
      }

      return {
        ...state,
        candles: { ...state.candles, [symbol]: nextCandles },
        prices: { ...state.prices, [symbol]: newPrice },
        priceDir: { ...state.priceDir, [symbol]: dir },
        stats: updatedStats,
        broker: broker || state.broker,
        botCycle: state.botRunning ? state.botCycle + 1 : state.botCycle,
        toasts,
      }
    }

    case 'DISMISS_TOAST':
      return {
        ...state,
        toasts: state.toasts.filter((t) => t.id !== action.id),
      }

    case 'SET_TRADE_TAB':
      return { ...state, tradeTab: action.tab }

    default:
      return state
  }
}

// ─── App Component ───────────────────────────────────────────────────────────

export function App() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const brokerRef = useRef(state.broker)
  brokerRef.current = state.broker
  const stateRef = useRef(state)
  stateRef.current = state

  // Live continuous market ticking (like a real exchange)
  useEffect(() => {
    const timer = setInterval(() => {
      const current = stateRef.current
      const symbol = current.activeCoin
      const candleList = current.candles[symbol]
      if (!candleList || candleList.length === 0) return

      const lastCandle = candleList[candleList.length - 1]
      const prevPrice = lastCandle.close
      const updatedCandle = generateNextTick(lastCandle, symbol, false)
      const newPrice = updatedCandle.close

      let signal = null
      let updatedBroker = null

      // If Bot is running, process strategy logic
      if (current.botRunning) {
        const broker = { ...brokerRef.current }
        broker.positions = [...broker.positions]
        broker.trades = [...broker.trades]
        broker.orders = [...broker.orders]

        // Signal check on recent candles
        const recentCandles = [...candleList.slice(0, -1), updatedCandle]
        signal = generateSignal(recentCandles)

        const hasOpen = broker.positions.some((p) => p.symbol === symbol)
        if (signal && !hasOpen && !broker.breaker) {
          executePaperTrade(
            broker,
            symbol,
            signal,
            newPrice,
            new Date().toISOString()
          )
        }

        // Tick stop-loss / liquidation
        tickPositions(broker, symbol, newPrice, new Date().toISOString())
        updatedBroker = broker
      }

      dispatch({
        type: 'PRICE_TICK',
        symbol,
        candle: updatedCandle,
        prevPrice,
        newPrice,
        signal,
        broker: updatedBroker,
      })
    }, TICK_INTERVAL_MS)

    return () => clearInterval(timer)
  }, [])

  // Auto-dismiss signal toasts
  useEffect(() => {
    if (state.toasts.length === 0) return
    const timer = setTimeout(() => {
      dispatch({ type: 'DISMISS_TOAST', id: state.toasts[0].id })
    }, 4000)
    return () => clearTimeout(timer)
  }, [state.toasts])

  const activeCoinObj =
    COINS.find((c) => c.symbol === state.activeCoin) || COINS[0]
  const currentPrice =
    state.prices[state.activeCoin] || SYMBOL_SEED[state.activeCoin].price
  const priceDir = state.priceDir[state.activeCoin] || 'up'
  const activeCandles = state.candles[state.activeCoin] || []
  const activeStats = state.stats[state.activeCoin] || {
    change24h: 0,
    changePct24h: 0,
    high24h: currentPrice,
    low24h: currentPrice,
    volume24h: 0,
  }

  return (
    <div className="app-shell">
      {/* Top Header with Binance Style & Coin Switcher */}
      <Header
        coins={COINS}
        activeCoin={state.activeCoin}
        prices={state.prices}
        priceDirs={state.priceDir}
        currentPrice={currentPrice}
        priceDir={priceDir}
        activeStats={activeStats}
        onCoinChange={(symbol) => dispatch({ type: 'SET_COIN', coin: symbol })}
        botRunning={state.botRunning}
      />

      {/* Main Trading Layout */}
      <div className="trading-layout">
        {/* LEFT: Market Info + Historical Strategies + Account */}
        <LeftPanel
          broker={state.broker}
          strategies={evidence.strategies}
          coins={COINS}
          prices={state.prices}
          priceDirs={state.priceDir}
          activeCoin={state.activeCoin}
          onCoinChange={(symbol) => dispatch({ type: 'SET_COIN', coin: symbol })}
        />

        {/* CENTER: Candlestick Chart + Trade Log */}
        <CenterPanel
          activeCandles={activeCandles}
          activeCoin={activeCoinObj}
          currentPrice={currentPrice}
          botRunning={state.botRunning}
          botCycle={state.botCycle}
          broker={state.broker}
          tradeTab={state.tradeTab}
          onTabChange={(tab) => dispatch({ type: 'SET_TRADE_TAB', tab })}
        />

        {/* RIGHT: Bot Control (Start/Stop) + Positions + Risk */}
        <RightPanel
          botRunning={state.botRunning}
          broker={state.broker}
          strategy={state.strategy}
          onStrategyChange={(s) => dispatch({ type: 'SET_STRATEGY', strategy: s })}
          onStart={() => dispatch({ type: 'BOT_START' })}
          onStop={() => dispatch({ type: 'BOT_STOP' })}
        />
      </div>

      {/* Signal Toasts */}
      <div className="signal-toasts">
        {state.toasts.map((toast) => (
          <div
            key={toast.id}
            className={`signal-toast ${toast.side === 'LONG' ? 'buy' : 'sell'}`}
          >
            <span>{toast.side === 'LONG' ? '▲' : '▼'}</span>
            <span>
              {toast.symbol} {toast.side} — Tín hiệu EMA Cross 9/21
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Header Component ────────────────────────────────────────────────────────

function Header({
  coins,
  activeCoin,
  prices,
  priceDirs,
  currentPrice,
  priceDir,
  activeStats,
  onCoinChange,
  botRunning,
}) {
  const precision = SYMBOL_SEED[activeCoin]?.precision || 2
  const isPos = activeStats.changePct24h >= 0

  return (
    <header className="exchange-header" role="banner">
      {/* Brand Logo */}
      <a className="header-logo" href="#" aria-label="Quill3H Paper Trading">
        <div className="header-logo-mark" aria-hidden="true">
          Q
        </div>
        <div>
          <div className="header-logo-text">Quill3H</div>
          <div className="header-logo-sub">Futures Paper</div>
        </div>
      </a>

      {/* Coin Switcher Tabs */}
      <nav className="coin-switcher" aria-label="Chọn cặp giao dịch">
        {coins.map((coin) => (
          <button
            key={coin.symbol}
            className={`coin-tab ${activeCoin === coin.symbol ? 'active' : ''}`}
            onClick={() => onCoinChange(coin.symbol)}
            type="button"
            aria-pressed={activeCoin === coin.symbol}
          >
            <span
              className="coin-dot"
              style={{ background: coin.color }}
              aria-hidden="true"
            />
            {coin.display}
          </button>
        ))}
      </nav>

      {/* Real-time Ticker Statistics */}
      <div className="header-ticker" aria-live="polite" aria-atomic="false">
        <span
          className={`ticker-price mono ${priceDir}`}
          aria-label={`Giá hiện tại ${money(currentPrice, precision)}`}
        >
          {money(currentPrice, precision)}
        </span>

        <div className="ticker-stat">
          <span className="ticker-stat-label">24h Thay đổi</span>
          <span
            className={`ticker-stat-value mono ${isPos ? 'text-buy' : 'text-sell'}`}
          >
            {isPos ? '+' : ''}
            {money(activeStats.change24h, precision)} {isPos ? '+' : ''}
            {activeStats.changePct24h.toFixed(2)}%
          </span>
        </div>

        <div className="ticker-stat">
          <span className="ticker-stat-label">24h Cao nhất</span>
          <span className="ticker-stat-value mono">
            {money(activeStats.high24h, precision)}
          </span>
        </div>

        <div className="ticker-stat">
          <span className="ticker-stat-label">24h Thấp nhất</span>
          <span className="ticker-stat-value mono">
            {money(activeStats.low24h, precision)}
          </span>
        </div>

        <div className="ticker-stat">
          <span className="ticker-stat-label">24h Khối lượng</span>
          <span className="ticker-stat-value mono">
            {money(activeStats.volume24h, 2)} USDT
          </span>
        </div>

        <div className="ticker-stat">
          <span className="ticker-stat-label">Chế độ</span>
          <span className="ticker-stat-value" style={{ color: '#F0B90B' }}>
            PAPER SIM
          </span>
        </div>

        <div className="ticker-stat">
          <span className="ticker-stat-label">Bot</span>
          <span
            className="ticker-stat-value"
            style={{ color: botRunning ? '#0ECB81' : '#848E9C' }}
          >
            {botRunning ? '● Đang chạy' : '○ Đã dừng'}
          </span>
        </div>
      </div>

      {/* Header Right Safety Badge */}
      <div className="header-right">
        <span className="header-badge">PAPER ONLY</span>
      </div>
    </header>
  )
}

// ─── Left Panel ──────────────────────────────────────────────────────────────

function LeftPanel({
  broker,
  strategies,
  coins,
  prices,
  priceDirs,
  activeCoin,
  onCoinChange,
}) {
  const pnlColor = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')

  return (
    <aside className="market-info-panel" aria-label="Thông tin thị trường và tài khoản">
      {/* Symbol List */}
      <div className="panel-title">Cặp giao dịch</div>
      <div className="symbol-list" role="list">
        {coins.map((coin) => {
          const p = prices[coin.symbol] || SYMBOL_SEED[coin.symbol].price
          const dir = priceDirs[coin.symbol] || 'up'
          const prec = SYMBOL_SEED[coin.symbol].precision
          return (
            <div
              key={coin.symbol}
              className={`symbol-row ${activeCoin === coin.symbol ? 'active' : ''}`}
              onClick={() => onCoinChange(coin.symbol)}
              role="listitem"
              aria-label={`${coin.display} giá ${money(p, prec)}`}
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onCoinChange(coin.symbol)}
            >
              <div>
                <div className="sym-name">{coin.display}</div>
                <div className="sym-sub">USD-M PERP · PAPER</div>
              </div>
              <div className={`sym-price mono ${dir}`}>
                {money(p, prec)}
              </div>
            </div>
          )
        })}
      </div>

      {/* Historical Strategies */}
      <div className="panel-title" style={{ marginTop: '1px' }}>
        Chiến lược lịch sử
      </div>
      <div className="strategy-list" role="list">
        {strategies.map((s) => (
          <div className="strategy-item" key={s.id} role="listitem">
            <div>
              <div className="strategy-name">{s.nameVi || s.name}</div>
              <div className="strategy-timeframe">
                {s.timeframe} · {s.stateVi}
              </div>
            </div>
            <div className={`strategy-pnl mono ${pnlColor(s.rawPnl)}`}>
              {s.rawPnl > 0 ? '+' : ''}
              {money(s.rawPnl)}
            </div>
          </div>
        ))}
      </div>

      {/* Paper Account Summary */}
      <div className="account-panel" aria-label="Tài khoản mô phỏng">
        <div className="account-title">Tài khoản PAPER</div>
        <div className="account-row">
          <span className="account-key">Equity</span>
          <span
            className={`account-value mono ${
              broker.equity >= INITIAL_EQUITY ? 'green' : 'red'
            }`}
          >
            {money(broker.equity)} USDT
          </span>
        </div>
        <div className="account-row">
          <span className="account-key">Wallet</span>
          <span className="account-value mono">{money(broker.wallet)} USDT</span>
        </div>
        <div className="account-row">
          <span className="account-key">Khả dụng</span>
          <span className="account-value mono">
            {money(broker.available)} USDT
          </span>
        </div>
        <div className="account-row">
          <span className="account-key">Lãi/lỗ chưa chốt</span>
          <span
            className={`account-value mono ${
              broker.unrealized >= 0 ? 'green' : 'red'
            }`}
          >
            {broker.unrealized >= 0 ? '+' : ''}
            {money(broker.unrealized)} USDT
          </span>
        </div>
        <div className="account-row">
          <span className="account-key">Circuit breaker</span>
          <span
            className={`account-value ${broker.breaker ? 'red' : 'green'}`}
          >
            {broker.breaker ? 'ĐÃ KHÓA' : 'Bình thường'}
          </span>
        </div>
      </div>
    </aside>
  )
}

// ─── Center Panel ─────────────────────────────────────────────────────────────

function CenterPanel({
  activeCandles,
  activeCoin,
  currentPrice,
  botRunning,
  botCycle,
  broker,
  tradeTab,
  onTabChange,
}) {
  const allTrades = broker.trades.slice().reverse()
  const precision = SYMBOL_SEED[activeCoin.symbol]?.precision || 2

  return (
    <main className="center-panel" aria-label="Biểu đồ và nhật ký giao dịch">
      {/* Chart Toolbar */}
      <div className="chart-toolbar" role="toolbar" aria-label="Tùy chọn biểu đồ">
        <span className="toolbar-btn active">{activeCoin.display}</span>
        <div className="toolbar-divider" aria-hidden="true" />
        <span
          className="toolbar-btn"
          style={{ color: activeCoin.color, cursor: 'default', fontWeight: 700 }}
        >
          ● {activeCoin.name}
        </span>
        <div className="toolbar-divider" aria-hidden="true" />
        <span className="toolbar-btn active">1m</span>
        <span className="toolbar-btn">5m</span>
        <span className="toolbar-btn">15m</span>
        <span className="toolbar-btn">1h</span>
        <div className="toolbar-divider" aria-hidden="true" />
        <span
          className="toolbar-btn"
          style={{ color: '#F0B90B', cursor: 'default' }}
        >
          📊 Biểu đồ nến TradingView · EMA 9/21
        </span>
        <div className="toolbar-spacer" />
        <span style={{ fontSize: '11px', color: '#848E9C' }}>
          {activeCandles.length} nến 1m mô phỏng
        </span>
      </div>

      {/* Candlestick Chart Area — Keyed by coin symbol for clean remount */}
      <div className="chart-area">
        <CandlestickChart
          key={activeCoin.symbol}
          symbol={activeCoin.symbol}
          candles={activeCandles}
          precision={precision}
        />

        {/* Subtle Coin Label Overlay */}
        <div className="chart-overlay" aria-hidden="true">
          <div className="chart-label">
            <span
              className="chart-label-dot"
              style={{ background: activeCoin.color }}
            />
            {activeCoin.display} Perpetual · Nến 1m (PAPER)
          </div>
        </div>
      </div>

      {/* Bot Status Bar */}
      <div className="bot-status-bar" aria-live="polite">
        <span
          className={`bot-status-indicator ${botRunning ? 'running' : 'idle'}`}
          aria-hidden="true"
        />
        <span className="bot-status-text">
          {botRunning ? (
            <>
              <strong>Bot đang tự tính toán & trade thử</strong> · Vòng #{botCycle} ·{' '}
              {broker.positions.length} vị thế mở · {broker.trades.length} lệnh hoàn tất
            </>
          ) : (
            <>
              Bot <strong>đã dừng</strong> · Nhấn &quot;Khởi động Bot&quot; để bot tự tính toán & giao dịch thử
            </>
          )}
        </span>
        <span
          style={{
            marginLeft: 'auto',
            color: '#474D57',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {evidence.mode} · Không có lệnh thật
        </span>
      </div>

      {/* Trade Log Tabs */}
      <div className="trade-log">
        <div className="trade-log-tabs" role="tablist">
          {[
            { id: 'closed', label: `Lệnh đã đóng (${broker.trades.length})` },
            { id: 'open', label: `Vị thế mở (${broker.positions.length})` },
            { id: 'orders', label: `Lệnh gần đây (${broker.orders.length})` },
            { id: 'audit', label: 'Nguồn dữ liệu & Giới hạn' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              className={`trade-log-tab ${tradeTab === tab.id ? 'active' : ''}`}
              onClick={() => onTabChange(tab.id)}
              aria-selected={tradeTab === tab.id}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="trade-log-body" role="tabpanel">
          {tradeTab === 'closed' &&
            (allTrades.length === 0 ? (
              <div className="trade-log-empty">
                Chưa có lệnh hoàn tất. Nhấn &quot;Khởi động Bot&quot; để bot tự động phân tích và tạo lệnh mô phỏng.
              </div>
            ) : (
              <table aria-label="Lệnh đã đóng">
                <thead>
                  <tr>
                    <th>Thời gian đóng</th>
                    <th>Mã</th>
                    <th>Hướng</th>
                    <th>Giá vào</th>
                    <th>Giá ra</th>
                    <th>Phí</th>
                    <th>Net PnL</th>
                    <th>Lý do đóng</th>
                  </tr>
                </thead>
                <tbody>
                  {allTrades.map((t) => (
                    <tr key={t.id}>
                      <td className="mono">
                        {t.exitTime?.slice(11, 19) || '—'}
                      </td>
                      <td>{t.symbol}</td>
                      <td className={t.side === 'LONG' ? 'buy' : 'sell'}>
                        {t.side}
                      </td>
                      <td className="mono">
                        {money(
                          t.entryPrice,
                          SYMBOL_SEED[t.symbol]?.precision || 2
                        )}
                      </td>
                      <td className="mono">
                        {money(
                          t.exitPrice,
                          SYMBOL_SEED[t.symbol]?.precision || 2
                        )}
                      </td>
                      <td className="mono">{money(t.feeUsd)}</td>
                      <td className={`mono ${t.netPnl >= 0 ? 'pos' : 'neg'}`}>
                        {t.netPnl >= 0 ? '+' : ''}
                        {money(t.netPnl)}
                      </td>
                      <td style={{ color: '#848E9C' }}>{t.closeReason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ))}

          {tradeTab === 'open' &&
            (broker.positions.length === 0 ? (
              <div className="trade-log-empty">Không có vị thế đang mở.</div>
            ) : (
              <table aria-label="Vị thế đang mở">
                <thead>
                  <tr>
                    <th>Mã</th>
                    <th>Hướng</th>
                    <th>Số lượng</th>
                    <th>Giá vào</th>
                    <th>Stop-loss</th>
                    <th>Đòn bẩy</th>
                    <th>PnL chưa chốt</th>
                  </tr>
                </thead>
                <tbody>
                  {broker.positions.map((p) => (
                    <tr key={p.id}>
                      <td>{p.symbol}</td>
                      <td className={p.side === 'LONG' ? 'buy' : 'sell'}>
                        {p.side}
                      </td>
                      <td className="mono">{p.quantity.toFixed(4)}</td>
                      <td className="mono">
                        {money(
                          p.entryPrice,
                          SYMBOL_SEED[p.symbol]?.precision || 2
                        )}
                      </td>
                      <td className="mono">
                        {money(
                          p.stopLoss,
                          SYMBOL_SEED[p.symbol]?.precision || 2
                        )}
                      </td>
                      <td>{p.leverage}×</td>
                      <td
                        className={`mono ${
                          (p.unrealizedPnl || 0) >= 0 ? 'pos' : 'neg'
                        }`}
                      >
                        {(p.unrealizedPnl || 0) >= 0 ? '+' : ''}
                        {money(p.unrealizedPnl || 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ))}

          {tradeTab === 'orders' &&
            (broker.orders.length === 0 ? (
              <div className="trade-log-empty">Chưa có lệnh nào được tạo.</div>
            ) : (
              <table aria-label="Lệnh gần đây">
                <thead>
                  <tr>
                    <th>Mã</th>
                    <th>Hướng</th>
                    <th>Giá</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {[...broker.orders]
                    .reverse()
                    .slice(0, 50)
                    .map((o) => (
                      <tr key={o.id}>
                        <td>{o.symbol}</td>
                        <td className={o.side === 'LONG' ? 'buy' : 'sell'}>
                          {o.side}
                        </td>
                        <td className="mono">
                          {money(
                            o.price,
                            SYMBOL_SEED[o.symbol]?.precision || 2
                          )}
                        </td>
                        <td style={{ color: '#0ECB81' }}>{o.status}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            ))}

          {tradeTab === 'audit' && (
            <div style={{ padding: '12px 14px' }}>
              <div
                style={{
                  fontSize: '11px',
                  color: '#848E9C',
                  marginBottom: '8px',
                }}
              >
                Nguồn dữ liệu đã đối chiếu · Cam kết Git
              </div>
              <table aria-label="Nguồn dữ liệu">
                <thead>
                  <tr>
                    <th>Tập dữ liệu</th>
                    <th>Loại</th>
                    <th>Trạng thái xác minh</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Equity curve G0 (BTC 2024)</td>
                    <td>Lịch sử · Artifact commit</td>
                    <td style={{ color: '#0ECB81' }}>AUTHOR_REPORTED</td>
                  </tr>
                  <tr>
                    <td>Walk-forward fold report</td>
                    <td>Lịch sử · {evidence.evidenceLevel}</td>
                    <td style={{ color: '#0ECB81' }}>AUTHOR_REPORTED</td>
                  </tr>
                  <tr>
                    <td>Nến mô phỏng BTC/ETH/SOL</td>
                    <td>Minh họa · Paper engine</td>
                    <td style={{ color: '#F0B90B' }}>
                      ILLUSTRATIVE · Mô phỏng nghiên cứu
                    </td>
                  </tr>
                  <tr>
                    <td>Dữ liệu Funding G2</td>
                    <td>Chẩn đoán · {evidence.fundingCoverage.status}</td>
                    <td style={{ color: '#F6465D' }}>
                      FAIL_CLOSED · Không đủ dữ liệu
                    </td>
                  </tr>
                </tbody>
              </table>
              <div
                style={{
                  marginTop: '10px',
                  fontSize: '10px',
                  color: '#848E9C',
                  lineHeight: '1.7',
                }}
              >
                Ghi chú: Lệnh, phí, trượt giá và stop-loss do PaperBroker mô phỏng.
                Không có bất kỳ lệnh sàn thật, testnet, hay khóa API nào được sử dụng.
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}

// ─── Right Panel ─────────────────────────────────────────────────────────────

function RightPanel({
  botRunning,
  broker,
  strategy,
  onStrategyChange,
  onStart,
  onStop,
}) {
  const pnlTotal = broker.trades.reduce(
    (sum, t) => sum + (t.netPnl || 0),
    0
  )

  return (
    <aside className="order-panel" aria-label="Điều khiển bot và vị thế">
      {/* Bot Control */}
      <div className="bot-control">
        <div className="bot-control-title">Bot Mô Phỏng · PAPER</div>
        <div className="bot-config-row">
          <span className="bot-config-key">Chiến lược</span>
          <span className="bot-config-value">EMA Cross 9/21</span>
        </div>
        <div className="bot-config-row">
          <span className="bot-config-key">Rủi ro/lệnh</span>
          <span className="bot-config-value">2% wallet</span>
        </div>
        <div className="bot-config-row">
          <span className="bot-config-key">Đòn bẩy</span>
          <span className="bot-config-value">2×</span>
        </div>
        <div className="bot-config-row">
          <span className="bot-config-key">Stop-loss</span>
          <span className="bot-config-value">3%</span>
        </div>
        <div className="bot-config-row">
          <span className="bot-config-key">Vốn khởi đầu</span>
          <span className="bot-config-value mono">10,000 USDT</span>
        </div>
        <div className="bot-config-row">
          <span className="bot-config-key">Mã theo dõi</span>
          <span className="bot-config-value">BTC · ETH · SOL</span>
        </div>

        {/* Buttons */}
        <div className="bot-btn-group">
          <button
            type="button"
            className="btn-start"
            onClick={onStart}
            disabled={botRunning}
            aria-label="Khởi động bot mô phỏng paper trading"
          >
            {botRunning ? '▶ Đang chạy...' : '▶ Khởi động Bot'}
          </button>
          <button
            type="button"
            className="btn-stop"
            onClick={onStop}
            disabled={!botRunning}
            aria-label="Dừng bot mô phỏng"
          >
            ■ Dừng
          </button>
        </div>

        {broker.breaker && (
          <div
            role="alert"
            style={{
              marginTop: '8px',
              padding: '8px 10px',
              background: 'rgba(246,70,93,0.1)',
              border: '1px solid #F6465D',
              borderRadius: '3px',
              fontSize: '11px',
              color: '#F6465D',
            }}
          >
            ⚠ Circuit breaker đã khóa: 3 lệnh thua liên tiếp. Nhấn Khởi động lại để reset.
          </div>
        )}
      </div>

      {/* Strategy Selector */}
      <div className="strategy-select-section">
        <div className="select-label">Chiến lược tín hiệu</div>
        <div className="select-group">
          {STRATEGIES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`strategy-chip ${strategy === s.id ? 'active' : ''}`}
              onClick={() => onStrategyChange(s.id)}
              aria-pressed={strategy === s.id}
              disabled={botRunning}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Open Positions List */}
      <div className="positions-section" aria-label="Vị thế đang mở">
        <div className="panel-title">
          Vị thế đang mở ({broker.positions.length})
        </div>
        {broker.positions.length === 0 ? (
          <div
            style={{
              padding: '20px 14px',
              color: '#474D57',
              fontSize: '12px',
            }}
          >
            Chưa có vị thế. Khởi động bot để tạo lệnh khi xuất hiện tín hiệu.
          </div>
        ) : (
          broker.positions.map((pos) => (
            <div
              key={pos.id}
              className={`position-card ${
                pos.side === 'LONG' ? 'long' : 'short'
              }`}
              aria-label={`Vị thế ${pos.side} ${pos.symbol}`}
            >
              <div className="position-header">
                <span className="position-sym">{pos.symbol}</span>
                <span
                  className={`position-side ${
                    pos.side === 'LONG' ? 'long' : 'short'
                  }`}
                >
                  {pos.side}
                </span>
              </div>
              <div className="position-grid">
                <div>
                  <div className="position-stat-key">Giá vào</div>
                  <div className="position-stat-val mono">
                    {money(
                      pos.entryPrice,
                      SYMBOL_SEED[pos.symbol]?.precision || 2
                    )}
                  </div>
                </div>
                <div>
                  <div className="position-stat-key">Đòn bẩy</div>
                  <div className="position-stat-val">{pos.leverage}×</div>
                </div>
                <div>
                  <div className="position-stat-key">Stop-loss</div>
                  <div className="position-stat-val mono">
                    {money(
                      pos.stopLoss,
                      SYMBOL_SEED[pos.symbol]?.precision || 2
                    )}
                  </div>
                </div>
                <div>
                  <div className="position-stat-key">Số lượng</div>
                  <div className="position-stat-val mono">
                    {pos.quantity.toFixed(4)}
                  </div>
                </div>
              </div>
              <div className="position-pnl">
                <span>PnL chưa chốt</span>
                <strong
                  className={(pos.unrealizedPnl || 0) >= 0 ? 'pos' : 'neg'}
                >
                  {(pos.unrealizedPnl || 0) >= 0 ? '+' : ''}
                  {money(pos.unrealizedPnl || 0)} USDT
                </strong>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Session Risk Summary */}
      <div className="risk-audit-section" aria-label="Tóm tắt rủi ro">
        <div className="account-title">Tóm tắt phiên</div>
        <div className="risk-row">
          <span className="risk-key">Tổng PnL</span>
          <span
            className={`risk-val mono ${pnlTotal >= 0 ? 'green' : 'red'}`}
          >
            {pnlTotal >= 0 ? '+' : ''}
            {money(pnlTotal)} USDT
          </span>
        </div>
        <div className="risk-row">
          <span className="risk-key">Số lệnh đóng</span>
          <span className="risk-val">{broker.trades.length}</span>
        </div>
        <div className="risk-row">
          <span className="risk-key">Thua liên tiếp</span>
          <span
            className={`risk-val ${
              broker.breakerConsecutiveLosses >= 2 ? 'red' : 'green'
            }`}
          >
            {broker.breakerConsecutiveLosses}/3
          </span>
        </div>
        <div className="risk-row">
          <span className="risk-key">Đòn bẩy tối đa</span>
          <span className="risk-val yellow">5× (giới hạn cứng)</span>
        </div>
        <div className="risk-note">
          PaperBroker mô phỏng. Phí taker 0.05%, stop-loss 3%, không có lệnh sàn thật hoặc testnet.
        </div>
      </div>
    </aside>
  )
}
