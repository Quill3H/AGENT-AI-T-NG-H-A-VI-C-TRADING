/**
 * App.jsx — Binance Futures-style Paper Research Console
 *
 * PAPER / RESEARCH ONLY — NO LIVE ORDERS, NO EXCHANGE CONNECTION.
 * All data is from committed public artifacts or browser-side simulation.
 *
 * Features:
 *   • Dark theme mirroring Binance Futures UI
 *   • Coin switcher: BTCUSDT / ETHUSDT / SOLUSDT
 *   • Paper Bot: start/stop simulated EMA-crossover paper trading
 *   • SVG equity chart with live price simulation
 *   • Trade log, open positions, account panel
 *   • All historical data from checked-in artifacts (evidence.js)
 */

import { useCallback, useEffect, useMemo, useReducer, useRef } from 'react'
import './styles.css'
import { evidence } from './data/evidence'
import { buildOfflineReplay, toPolyline } from './lib/replay'
import {
  SYMBOL_SEED, INITIAL_EQUITY,
  simulatePriceWalk, generateSignal,
  createPaperBroker, executePaperTrade, tickPositions,
} from './lib/paperEngine'

// ─── Constants ──────────────────────────────────────────────────────────────

const COINS = [
  { symbol: 'BTCUSDT', name: 'BTC', display: 'BTCUSDT', color: '#F7931A' },
  { symbol: 'ETHUSDT', name: 'ETH', display: 'ETHUSDT', color: '#627EEA' },
  { symbol: 'SOLUSDT', name: 'SOL', display: 'SOLUSDT', color: '#9945FF' },
]

const STRATEGIES = [
  { id: 'ema_cross',     label: 'EMA Cross 9/21', timeframe: '1m',  selected: true },
  { id: 'trend_follow',  label: 'Trend Follow',   timeframe: '15m', selected: false },
  { id: 'breakout',      label: 'Breakout',        timeframe: '4h',  selected: false },
]

const BOT_TICK_MS = 1500  // Simulate one candle per 1.5s when running

const money = (v, prec = 2) => Number(v).toLocaleString('en-US', {
  minimumFractionDigits: prec,
  maximumFractionDigits: prec,
})

// ─── State Reducer ───────────────────────────────────────────────────────────

const initialState = {
  activeCoin:     'BTCUSDT',
  botRunning:     false,
  botCycle:       0,
  strategy:       'ema_cross',
  broker:         createPaperBroker(INITIAL_EQUITY),
  candles:        {},   // { symbol -> candle[] }
  prices:         {},   // { symbol -> number }
  priceDir:       {},   // { symbol -> 'up'|'down' }
  toasts:         [],   // [{ id, symbol, side }]
  tradeTab:       'closed',
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_COIN':
      return { ...state, activeCoin: action.coin }

    case 'SET_STRATEGY':
      return { ...state, strategy: action.strategy }

    case 'BOT_START': {
      // Initialize candles for all symbols from seed walks
      const candles = {}
      const prices  = {}
      const priceDir = {}
      for (const { symbol } of COINS) {
        const seed = symbol.charCodeAt(0) + symbol.charCodeAt(1)
        candles[symbol] = simulatePriceWalk(symbol, 120, seed)
        const last = candles[symbol].at(-1)
        prices[symbol]   = last.close
        priceDir[symbol] = 'up'
      }
      return {
        ...state,
        botRunning: true,
        broker: createPaperBroker(INITIAL_EQUITY),
        candles,
        prices,
        priceDir,
      }
    }

    case 'BOT_STOP':
      return { ...state, botRunning: false }

    case 'BOT_TICK': {
      const { symbol, candle, newPrice, signal, closedTrades } = action
      const prevPrice = state.prices[symbol] ?? newPrice

      // Immutably update candles: append new candle, keep last 150
      const prevCandles = state.candles[symbol] ?? []
      const nextCandles = [...prevCandles, candle].slice(-150)

      // Update prices
      const prices  = { ...state.prices, [symbol]: newPrice }
      const priceDir = { ...state.priceDir, [symbol]: newPrice >= prevPrice ? 'up' : 'down' }

      // Merge closed trades into broker
      const broker = { ...action.broker }

      // Toast for new signal
      let toasts = state.toasts
      if (signal) {
        const toast = { id: Date.now(), symbol, side: signal }
        toasts = [...toasts.slice(-4), toast]
        setTimeout(() => {}, 4000) // CSS animates it out
      }

      return {
        ...state,
        broker,
        candles: { ...state.candles, [symbol]: nextCandles },
        prices,
        priceDir,
        botCycle: state.botCycle + 1,
        toasts,
      }
    }

    case 'DISMISS_TOAST':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) }

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
  const candlesRef = useRef(state.candles)
  candlesRef.current = state.candles

  // ── Load historical replay chart points (committed artifact)
  const historicalPoints = useMemo(() => {
    try { return buildOfflineReplay() } catch { return [] }
  }, [])

  // ── Bot tick simulation
  const tickSymbolRef = useRef(0)
  useEffect(() => {
    if (!state.botRunning) return

    const interval = setInterval(() => {
      const coin   = COINS[tickSymbolRef.current % COINS.length]
      tickSymbolRef.current++
      const { symbol }  = coin
      const candleList   = candlesRef.current[symbol] ?? []
      if (candleList.length < 2) return

      // Generate next synthetic 1-min candle
      const config = SYMBOL_SEED[symbol]
      const last   = candleList.at(-1)
      const seed   = (Math.sin(Date.now()) * 0x7FFFFFFF) | 0
      const rng    = () => {
        let x = seed + tickSymbolRef.current * 1664525 + 1013904223
        x = (x ^ (x >>> 13)); x = (x ^ (x << 17)); x = (x ^ (x >>> 5))
        return ((x >>> 0) / 0xFFFFFFFF)
      }
      const change  = (rng() - 0.5) * 2 * config.volatility
      const openP   = last.close
      const closeP  = openP * (1 + change)
      const highP   = Math.max(openP, closeP) * (1 + rng() * config.volatility * 0.3)
      const lowP    = Math.min(openP, closeP) * (1 - rng() * config.volatility * 0.3)
      const nowMs   = Date.now()

      const candle  = { time: nowMs, open: openP, high: highP, low: lowP, close: closeP }
      const newCandles = [...candleList, candle].slice(-150)

      // Check signal
      const signal = generateSignal(newCandles)

      // Run paper broker
      const broker = { ...brokerRef.current }
      broker.positions = [...broker.positions]
      broker.trades    = [...broker.trades]
      broker.orders    = [...broker.orders]

      // Execute signal if any open positions for this symbol < 1
      const hasOpenForSymbol = broker.positions.some((p) => p.symbol === symbol)
      if (signal && !hasOpenForSymbol && !broker.breaker) {
        executePaperTrade(broker, symbol, signal, closeP, new Date(nowMs).toISOString())
      }

      // Tick all positions for this symbol
      const closed = tickPositions(broker, symbol, closeP, new Date(nowMs).toISOString())

      dispatch({
        type: 'BOT_TICK',
        symbol,
        candle,
        newPrice: closeP,
        signal,
        broker,
        closedTrades: closed,
      })
    }, BOT_TICK_MS)

    return () => clearInterval(interval)
  }, [state.botRunning])

  // ── Dismiss old toasts
  useEffect(() => {
    if (state.toasts.length === 0) return
    const timer = setTimeout(() => {
      dispatch({ type: 'DISMISS_TOAST', id: state.toasts[0].id })
    }, 4500)
    return () => clearTimeout(timer)
  }, [state.toasts])

  const activeCoin = COINS.find((c) => c.symbol === state.activeCoin) ?? COINS[0]
  const currentPrice = state.prices[state.activeCoin]
    ?? SYMBOL_SEED[state.activeCoin].price
  const priceDir = state.priceDir[state.activeCoin] ?? 'up'
  const broker   = state.broker

  // Build SVG chart path for active coin
  const activeCandles = state.candles[state.activeCoin] ?? []

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="app-shell">
      {/* Safety Banner */}
      <SafetyBanner />

      {/* Top Header */}
      <Header
        coins={COINS}
        activeCoin={state.activeCoin}
        prices={state.prices}
        priceDirs={state.priceDir}
        currentPrice={currentPrice}
        priceDir={priceDir}
        onCoinChange={(symbol) => dispatch({ type: 'SET_COIN', coin: symbol })}
        botRunning={state.botRunning}
      />

      {/* Main Trading Layout */}
      <div className="trading-layout">

        {/* LEFT: Market Info + Account */}
        <LeftPanel
          broker={broker}
          strategies={evidence.strategies}
          coins={COINS}
          prices={state.prices}
          priceDirs={state.priceDir}
          activeCoin={state.activeCoin}
          onCoinChange={(symbol) => dispatch({ type: 'SET_COIN', coin: symbol })}
        />

        {/* CENTER: Chart + Trade Log */}
        <CenterPanel
          historicalPoints={historicalPoints}
          activeCandles={activeCandles}
          activeCoin={activeCoin}
          currentPrice={currentPrice}
          botRunning={state.botRunning}
          botCycle={state.botCycle}
          broker={broker}
          tradeTab={state.tradeTab}
          onTabChange={(tab) => dispatch({ type: 'SET_TRADE_TAB', tab })}
        />

        {/* RIGHT: Bot Control + Positions */}
        <RightPanel
          botRunning={state.botRunning}
          broker={broker}
          strategy={state.strategy}
          onStrategyChange={(s) => dispatch({ type: 'SET_STRATEGY', strategy: s })}
          onStart={() => dispatch({ type: 'BOT_START' })}
          onStop={() => dispatch({ type: 'BOT_STOP' })}
          evidenceControls={evidence.controls}
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
            <span>{toast.symbol} {toast.side === 'LONG' ? 'LONG' : 'SHORT'} — Tín hiệu EMA Cross</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── SafetyBanner ────────────────────────────────────────────────────────────

function SafetyBanner() {
  return (
    <div className="paper-safety-bar" role="alert" aria-live="polite">
      <span className="pill">PAPER</span>
      <span>Không có lệnh thật · Không kết nối sàn · Mọi số liệu là mô phỏng hoặc dữ liệu lịch sử công khai</span>
      <span className="pill">RESEARCH</span>
    </div>
  )
}

// ─── Header ──────────────────────────────────────────────────────────────────

function Header({ coins, activeCoin, prices, priceDirs, currentPrice, priceDir, onCoinChange, botRunning }) {
  const fmt = (sym) => {
    const p = prices[sym] ?? SYMBOL_SEED[sym].price
    return p
  }

  return (
    <header className="exchange-header" role="banner">
      {/* Logo */}
      <a className="header-logo" href="#" aria-label="Quill3H Paper Research">
        <div className="header-logo-mark" aria-hidden="true">Q</div>
        <div>
          <div className="header-logo-text">Quill3H</div>
          <div className="header-logo-sub">Futures Research</div>
        </div>
      </a>

      {/* Coin Switcher */}
      <nav className="coin-switcher" aria-label="Chọn cặp giao dịch">
        {coins.map((coin) => (
          <button
            key={coin.symbol}
            className={`coin-tab ${activeCoin === coin.symbol ? 'active' : ''}`}
            onClick={() => onCoinChange(coin.symbol)}
            type="button"
            aria-pressed={activeCoin === coin.symbol}
          >
            <span className="coin-dot" style={{ background: coin.color }} aria-hidden="true" />
            {coin.display}
          </button>
        ))}
      </nav>

      {/* Ticker */}
      <div className="header-ticker" aria-live="polite" aria-atomic="false">
        <span
          className={`ticker-price mono ${priceDir}`}
          aria-label={`Giá hiện tại ${money(currentPrice, SYMBOL_SEED[coins.find(c=>c.symbol===activeCoin)?.symbol || 'BTCUSDT'].precision)}`}
        >
          {money(currentPrice, SYMBOL_SEED[coins.find(c=>c.symbol===activeCoin)?.symbol || 'BTCUSDT']?.precision ?? 2)}
        </span>
        <div className="ticker-stat" aria-label="Chế độ">
          <span className="ticker-stat-label">Chế độ</span>
          <span className="ticker-stat-value" style={{ color: '#F0B90B' }}>PAPER SIM</span>
        </div>
        <div className="ticker-stat">
          <span className="ticker-stat-label">Nguồn dữ liệu</span>
          <span className="ticker-stat-value">Dữ liệu lịch sử công khai</span>
        </div>
        <div className="ticker-stat">
          <span className="ticker-stat-label">Bot</span>
          <span className="ticker-stat-value" style={{ color: botRunning ? '#0ECB81' : '#848E9C' }}>
            {botRunning ? '● Đang chạy' : '○ Đã dừng'}
          </span>
        </div>
        {coins.filter(c => c.symbol !== activeCoin).map((coin) => (
          <div className="ticker-stat" key={coin.symbol}>
            <span className="ticker-stat-label">{coin.name}</span>
            <span className="ticker-stat-value mono">{money(fmt(coin.symbol), SYMBOL_SEED[coin.symbol].precision)}</span>
          </div>
        ))}
      </div>

      <div className="header-right">
        <span className="header-badge">PAPER ONLY</span>
      </div>
    </header>
  )
}

// ─── Left Panel ──────────────────────────────────────────────────────────────

function LeftPanel({ broker, strategies, coins, prices, priceDirs, activeCoin, onCoinChange }) {
  const pnlColor = (v) => v > 0 ? 'pos' : v < 0 ? 'neg' : ''

  return (
    <aside className="market-info-panel" aria-label="Thông tin thị trường và tài khoản">
      {/* Symbol list */}
      <div className="panel-title">Cặp giao dịch</div>
      <div className="symbol-list" role="list">
        {coins.map((coin) => {
          const p    = prices[coin.symbol] ?? SYMBOL_SEED[coin.symbol].price
          const dir  = priceDirs[coin.symbol] ?? 'up'
          return (
            <div
              key={coin.symbol}
              className={`symbol-row ${activeCoin === coin.symbol ? 'active' : ''}`}
              onClick={() => onCoinChange(coin.symbol)}
              role="listitem"
              aria-label={`${coin.display} giá ${money(p, SYMBOL_SEED[coin.symbol].precision)}`}
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onCoinChange(coin.symbol)}
            >
              <div>
                <div className="sym-name">{coin.display}</div>
                <div className="sym-sub">USD-M PERP · PAPER</div>
              </div>
              <div className={`sym-price mono ${dir}`}>
                {money(p, SYMBOL_SEED[coin.symbol].precision)}
              </div>
            </div>
          )
        })}
      </div>

      {/* Strategies */}
      <div className="panel-title" style={{ marginTop: '1px' }}>Chiến lược lịch sử</div>
      <div className="strategy-list" role="list">
        {strategies.map((s) => (
          <div className="strategy-item" key={s.id} role="listitem">
            <div>
              <div className="strategy-name">{s.nameVi || s.name}</div>
              <div className="strategy-timeframe">{s.timeframe} · {s.stateVi}</div>
            </div>
            <div className={`strategy-pnl mono ${pnlColor(s.rawPnl)}`}>
              {s.rawPnl > 0 ? '+' : ''}{money(s.rawPnl)}
            </div>
          </div>
        ))}
      </div>

      {/* Account */}
      <div className="account-panel" aria-label="Tài khoản mô phỏng">
        <div className="account-title">Tài khoản PAPER</div>
        <div className="account-row">
          <span className="account-key">Equity</span>
          <span className={`account-value mono ${broker.equity >= INITIAL_EQUITY ? 'green' : 'red'}`}>
            {money(broker.equity)} USDT
          </span>
        </div>
        <div className="account-row">
          <span className="account-key">Wallet</span>
          <span className="account-value mono">{money(broker.wallet)} USDT</span>
        </div>
        <div className="account-row">
          <span className="account-key">Khả dụng</span>
          <span className="account-value mono">{money(broker.available)} USDT</span>
        </div>
        <div className="account-row">
          <span className="account-key">Lãi/lỗ chưa chốt</span>
          <span className={`account-value mono ${broker.unrealized >= 0 ? 'green' : 'red'}`}>
            {broker.unrealized >= 0 ? '+' : ''}{money(broker.unrealized)} USDT
          </span>
        </div>
        <div className="account-row">
          <span className="account-key">Circuit breaker</span>
          <span className={`account-value ${broker.breaker ? 'red' : 'green'}`}>
            {broker.breaker ? 'ĐÃ KHÓA' : 'Bình thường'}
          </span>
        </div>
      </div>
    </aside>
  )
}

// ─── Center Panel ─────────────────────────────────────────────────────────────

function CenterPanel({
  historicalPoints, activeCandles, activeCoin, currentPrice,
  botRunning, botCycle, broker, tradeTab, onTabChange,
}) {
  const chartRef = useRef(null)

  // Build SVG paths
  const chartPaths = useMemo(() => {
    // Historical equity path (from committed artifact)
    const histPath = historicalPoints.length >= 2
      ? toPolyline(historicalPoints, 800, 240)
      : ''

    // Live price path (from bot simulation candles)
    const liveCloses = activeCandles.map((c) => ({ equity: c.close }))
    const livePath = liveCloses.length >= 2
      ? toPolyline(liveCloses, 800, 240)
      : ''

    // Separate fill area (close polygon for gradient)
    let fillPath = ''
    if (liveCloses.length >= 2) {
      const pts = toPolyline(liveCloses, 800, 240).split(' ')
      fillPath = `M ${pts[0]} L ${pts.join(' L ')} L 800,240 L 0,240 Z`
    }

    return { histPath, livePath, fillPath }
  }, [historicalPoints, activeCandles, botCycle])

  const allTrades  = broker.trades.slice().reverse()
  const openPos    = broker.positions

  return (
    <main className="center-panel" aria-label="Biểu đồ và nhật ký giao dịch">
      {/* Toolbar */}
      <div className="chart-toolbar" role="toolbar" aria-label="Tùy chọn biểu đồ">
        <button type="button" className="toolbar-btn active">Equity</button>
        <button type="button" className="toolbar-btn">Giá</button>
        <div className="toolbar-divider" aria-hidden="true" />
        <button type="button" className="toolbar-btn">1m</button>
        <button type="button" className="toolbar-btn">5m</button>
        <button type="button" className="toolbar-btn">15m</button>
        <button type="button" className="toolbar-btn">1h</button>
        <div className="toolbar-divider" aria-hidden="true" />
        <span className="toolbar-btn" style={{ color: '#F0B90B', cursor: 'default' }}>
          📊 Dữ liệu lịch sử công khai 2024 · EMA 9/21
        </span>
        <div className="toolbar-spacer" />
        <span style={{ fontSize: '11px', color: '#848E9C' }}>
          {activeCandles.length > 0
            ? `${activeCandles.length} nến mô phỏng`
            : 'Chờ bot khởi động'}
        </span>
      </div>

      {/* Chart Area */}
      <div className="chart-area" ref={chartRef} aria-label="Biểu đồ equity và giá mô phỏng">
        <svg
          className="svg-chart-container"
          viewBox="0 0 800 260"
          preserveAspectRatio="none"
          role="img"
          aria-label={`Biểu đồ equity ${activeCoin.display}`}
        >
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#0ECB81" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#0ECB81" stopOpacity="0.02" />
            </linearGradient>
            <linearGradient id="histGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#F0B90B" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#F0B90B" stopOpacity="0.01" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0.25, 0.5, 0.75].map((f) => (
            <line
              key={f}
              x1="0" y1={260 * f}
              x2="800" y2={260 * f}
              className="chart-grid-line"
            />
          ))}
          {[0.2, 0.4, 0.6, 0.8].map((f) => (
            <line
              key={f}
              x1={800 * f} y1="0"
              x2={800 * f} y2="260"
              className="chart-grid-line"
            />
          ))}

          {/* Historical equity (artifact) */}
          {chartPaths.histPath && (
            <>
              <polyline points={chartPaths.histPath} className="chart-price-line" />
            </>
          )}

          {/* Live simulated price fill */}
          {chartPaths.fillPath && (
            <path d={chartPaths.fillPath} className="chart-equity-area" />
          )}

          {/* Live simulated price line */}
          {chartPaths.livePath && (
            <polyline points={chartPaths.livePath} className="chart-equity-line" />
          )}

          {/* No data placeholder */}
          {!botRunning && activeCandles.length === 0 && (
            <text
              x="400" y="130"
              textAnchor="middle"
              fill="#474D57"
              fontSize="14"
              fontFamily="inherit"
            >
              Nhấn &quot;Khởi động Bot&quot; để bắt đầu mô phỏng
            </text>
          )}
        </svg>

        {/* Chart Labels */}
        <div className="chart-overlay" aria-hidden="true">
          {chartPaths.histPath && (
            <div className="chart-label">
              <span className="chart-label-dot" style={{ background: '#F0B90B' }} />
              Equity lịch sử (Artifact G0 · 2024)
            </div>
          )}
          {chartPaths.livePath && (
            <div className="chart-label">
              <span className="chart-label-dot" style={{ background: '#0ECB81' }} />
              Giá mô phỏng {activeCoin.name} (PAPER)
            </div>
          )}
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
              <strong>Bot đang mô phỏng</strong> · Tick #{botCycle} ·{' '}
              {broker.positions.length} vị thế mở ·{' '}
              {broker.trades.length} lệnh hoàn tất
            </>
          ) : (
            <>Bot <strong>đã dừng</strong> · Nhấn &quot;Khởi động Bot&quot; để bắt đầu mô phỏng PAPER</>
          )}
        </span>
        <span style={{ marginLeft: 'auto', color: '#474D57', fontFamily: 'var(--font-mono)' }}>
          {evidence.mode} · Không có lệnh sàn thật
        </span>
      </div>

      {/* Trade Log */}
      <div className="trade-log">
        <div className="trade-log-tabs" role="tablist">
          {[
            { id: 'closed', label: `Lệnh đã đóng (${broker.trades.length})` },
            { id: 'open',   label: `Vị thế mở (${broker.positions.length})` },
            { id: 'orders', label: `Lệnh gần đây (${broker.orders.length})` },
            { id: 'audit',  label: 'Nguồn dữ liệu' },
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
          {tradeTab === 'closed' && (
            allTrades.length === 0
              ? <div className="trade-log-empty">Chưa có lệnh hoàn tất. Bot cần chạy để tạo lệnh mô phỏng.</div>
              : (
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
                      <th>Lý do</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allTrades.map((t) => (
                      <tr key={t.id}>
                        <td className="mono">{t.exitTime?.slice(11, 19) ?? '—'}</td>
                        <td>{t.symbol}</td>
                        <td className={t.side === 'LONG' ? 'buy' : 'sell'}>{t.side}</td>
                        <td className="mono">{money(t.entryPrice, SYMBOL_SEED[t.symbol]?.precision ?? 2)}</td>
                        <td className="mono">{money(t.exitPrice, SYMBOL_SEED[t.symbol]?.precision ?? 2)}</td>
                        <td className="mono">{money(t.feeUsd)}</td>
                        <td className={`mono ${t.netPnl >= 0 ? 'pos' : 'neg'}`}>
                          {t.netPnl >= 0 ? '+' : ''}{money(t.netPnl)}
                        </td>
                        <td style={{ color: '#848E9C' }}>{t.closeReason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
          )}

          {tradeTab === 'open' && (
            broker.positions.length === 0
              ? <div className="trade-log-empty">Không có vị thế mở.</div>
              : (
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
                        <td className={p.side === 'LONG' ? 'buy' : 'sell'}>{p.side}</td>
                        <td className="mono">{p.quantity.toFixed(4)}</td>
                        <td className="mono">{money(p.entryPrice, SYMBOL_SEED[p.symbol]?.precision ?? 2)}</td>
                        <td className="mono">{money(p.stopLoss, SYMBOL_SEED[p.symbol]?.precision ?? 2)}</td>
                        <td>{p.leverage}×</td>
                        <td className={`mono ${(p.unrealizedPnl ?? 0) >= 0 ? 'pos' : 'neg'}`}>
                          {(p.unrealizedPnl ?? 0) >= 0 ? '+' : ''}{money(p.unrealizedPnl ?? 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
          )}

          {tradeTab === 'orders' && (
            broker.orders.length === 0
              ? <div className="trade-log-empty">Chưa có lệnh nào.</div>
              : (
                <table aria-label="Lệnh gần đây">
                  <thead>
                    <tr><th>Mã</th><th>Hướng</th><th>Giá</th><th>Trạng thái</th></tr>
                  </thead>
                  <tbody>
                    {[...broker.orders].reverse().slice(0, 50).map((o) => (
                      <tr key={o.id}>
                        <td>{o.symbol}</td>
                        <td className={o.side === 'LONG' ? 'buy' : 'sell'}>{o.side}</td>
                        <td className="mono">{money(o.price, SYMBOL_SEED[o.symbol]?.precision ?? 2)}</td>
                        <td style={{ color: '#0ECB81' }}>{o.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
          )}

          {tradeTab === 'audit' && (
            <div style={{ padding: '12px 14px' }}>
              <div style={{ fontSize: '11px', color: '#848E9C', marginBottom: '8px' }}>
                Nguồn dữ liệu đã xác minh · Cam kết Git
              </div>
              <table aria-label="Nguồn dữ liệu">
                <thead>
                  <tr><th>Tập dữ liệu</th><th>Loại</th><th>Trạng thái xác minh</th></tr>
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
                    <td>Giá mô phỏng bot (ETH/BTC/SOL)</td>
                    <td>Minh họa · Trình duyệt</td>
                    <td style={{ color: '#F0B90B' }}>ILLUSTRATIVE · Không phải backtest</td>
                  </tr>
                  <tr>
                    <td>Dữ liệu Funding G2</td>
                    <td>Chẩn đoán · {evidence.fundingCoverage.status}</td>
                    <td style={{ color: '#F6465D' }}>FAIL_CLOSED · Xem tài liệu G2</td>
                  </tr>
                </tbody>
              </table>
              <div style={{ marginTop: '10px', fontSize: '10px', color: '#474D57', lineHeight: '1.7' }}>
                Kết quả mô phỏng bot không phải backtest và không chứng minh khả năng sinh lời.
                Dữ liệu lịch sử từ Binance Futures public (2024). Không có lệnh sàn thật hoặc testnet.
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}

// ─── Right Panel ─────────────────────────────────────────────────────────────

function RightPanel({ botRunning, broker, strategy, onStrategyChange, onStart, onStop, evidenceControls }) {
  const pnlTotal = broker.trades.reduce((sum, t) => sum + (t.netPnl ?? 0), 0)

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
            ⚠ Circuit breaker đã kích hoạt: 3 lệnh thua liên tiếp. Khởi động lại bot để reset.
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
              title={`${s.label} · Khung ${s.timeframe}`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Open Positions */}
      <div className="positions-section" aria-label="Vị thế đang mở">
        <div className="panel-title">Vị thế đang mở ({broker.positions.length})</div>
        {broker.positions.length === 0 ? (
          <div style={{ padding: '20px 14px', color: '#474D57', fontSize: '12px' }}>
            Chưa có vị thế. Bot sẽ tạo lệnh khi phát hiện tín hiệu EMA Cross.
          </div>
        ) : (
          broker.positions.map((pos) => (
            <div
              key={pos.id}
              className={`position-card ${pos.side === 'LONG' ? 'long' : 'short'}`}
              aria-label={`Vị thế ${pos.side} ${pos.symbol}`}
            >
              <div className="position-header">
                <span className="position-sym">{pos.symbol}</span>
                <span className={`position-side ${pos.side === 'LONG' ? 'long' : 'short'}`}>
                  {pos.side}
                </span>
              </div>
              <div className="position-grid">
                <div>
                  <div className="position-stat-key">Giá vào</div>
                  <div className="position-stat-val mono">{money(pos.entryPrice, SYMBOL_SEED[pos.symbol]?.precision ?? 2)}</div>
                </div>
                <div>
                  <div className="position-stat-key">Đòn bẩy</div>
                  <div className="position-stat-val">{pos.leverage}×</div>
                </div>
                <div>
                  <div className="position-stat-key">Stop-loss</div>
                  <div className="position-stat-val mono">{money(pos.stopLoss, SYMBOL_SEED[pos.symbol]?.precision ?? 2)}</div>
                </div>
                <div>
                  <div className="position-stat-key">Số lượng</div>
                  <div className="position-stat-val mono">{pos.quantity.toFixed(4)}</div>
                </div>
              </div>
              <div className="position-pnl">
                <span>PnL chưa chốt</span>
                <strong className={(pos.unrealizedPnl ?? 0) >= 0 ? 'pos' : 'neg'}>
                  {(pos.unrealizedPnl ?? 0) >= 0 ? '+' : ''}{money(pos.unrealizedPnl ?? 0)} USDT
                </strong>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Risk Summary */}
      <div className="risk-audit-section" aria-label="Tóm tắt rủi ro">
        <div className="account-title">Tóm tắt phiên</div>
        <div className="risk-row">
          <span className="risk-key">Tổng PnL</span>
          <span className={`risk-val mono ${pnlTotal >= 0 ? 'green' : 'red'}`}>
            {pnlTotal >= 0 ? '+' : ''}{money(pnlTotal)} USDT
          </span>
        </div>
        <div className="risk-row">
          <span className="risk-key">Số lệnh đóng</span>
          <span className="risk-val">{broker.trades.length}</span>
        </div>
        <div className="risk-row">
          <span className="risk-key">Thua liên tiếp</span>
          <span className={`risk-val ${broker.breakerConsecutiveLosses >= 2 ? 'red' : 'green'}`}>
            {broker.breakerConsecutiveLosses}/3
          </span>
        </div>
        <div className="risk-row">
          <span className="risk-key">Đòn bẩy tối đa</span>
          <span className="risk-val yellow">5× (giới hạn cứng)</span>
        </div>
        <div className="risk-note">
          Lệnh do PaperBroker mô phỏng. Phí taker 0.05%, stop-loss 3%, không có lệnh sàn thật hoặc testnet.
          Không phải bằng chứng sinh lời.
        </div>
      </div>
    </aside>
  )
}
