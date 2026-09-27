/**
 * App.jsx — Binance Futures-style Desktop Paper Trading Console
 *
 * PAPER / RESEARCH ONLY — NO LIVE ORDERS, NO EXCHANGE KEYS, NO TESTNET.
 *
 * Data Pipeline:
 *   • Real public Binance USD-M Futures data for BTC, ETH, and SOL.
 *   • Public WebSocket stream for real-time 1m candlestick chart.
 *   • Trend Following strategy (4h/15m) executing via backend Codex PaperBroker.
 *   • Connected to local endpoints: /api/state, /api/start, /api/stop.
 *   • Real session persistence, automatic reconnection, and safe recovery.
 *   • Zero Math.random().
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import './styles.css'
import { evidence } from './data/evidence'
import { CandlestickChart } from './CandlestickChart'

// ─── Constants & Symbols ─────────────────────────────────────────────────────

export const COINS = [
  { symbol: 'BTCUSDT', name: 'BTC', display: 'BTCUSDT', color: '#F7931A', precision: 2 },
  { symbol: 'ETHUSDT', name: 'ETH', display: 'ETHUSDT', color: '#627EEA', precision: 2 },
  { symbol: 'SOLUSDT', name: 'SOL', display: 'SOLUSDT', color: '#9945FF', precision: 2 },
]

const STRATEGY_METADATA = [
  {
    id: 'trend_following',
    nameVi: 'Bám theo xu hướng (Trend Following)',
    timeframe: '4h / 15m',
    status: 'ACTIVE_LIVE',
    statusLabel: '🟢 Đang chạy trực tiếp (Live paper)',
    desc: 'Chiến lược duy nhất hiện đang quét và vào lệnh trực tiếp trên dữ liệu mới.',
  },
  {
    id: 'breakout',
    nameVi: 'Phá vỡ cản & Kiểm tra lại (Breakout)',
    timeframe: '15m / 1m',
    status: 'DORMANT',
    statusLabel: '⚪ Chưa kích hoạt (Mẫu lịch sử)',
    desc: 'Không chạy trên luồng mới. Giữ nguyên theo hợp đồng kiến trúc.',
  },
  {
    id: 'smc',
    nameVi: 'Quét thanh khoản dòng tiền lớn (SMC)',
    timeframe: '15m',
    status: 'DORMANT',
    statusLabel: '⚪ Chưa kích hoạt (Mẫu lịch sử)',
    desc: 'Không chạy trên luồng mới. Giữ nguyên theo hợp đồng kiến trúc.',
  },
  {
    id: 'funding_arb',
    nameVi: 'Khai thác chênh lệch phí Funding',
    timeframe: '8h settlement',
    status: 'DORMANT',
    statusLabel: '⚪ Chưa kích hoạt (Mẫu lịch sử)',
    desc: 'Thiếu dữ liệu settlement tại mốc nến. Tạm khóa bảo vệ vốn.',
  },
]

const money = (v, prec = 2) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('en-US', {
    minimumFractionDigits: prec,
    maximumFractionDigits: prec,
  })
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

// ─── Main App Component ──────────────────────────────────────────────────────

export function App() {
  const [activeCoin, setActiveCoin] = useState(getInitialCoin())
  const [connectionStatus, setConnectionStatus] = useState('CONNECTING') // 'CONNECTING' | 'ONLINE' | 'DATA_STALE' | 'SERVER_ERROR' | 'QUARANTINED'
  const [backendState, setBackendState] = useState(null)
  const [liveCandle, setLiveCandle] = useState(null)
  const [tradeTab, setTradeTab] = useState('closed')
  const [actionPending, setActionPending] = useState(false)
  const [lastSyncTime, setLastSyncTime] = useState(null)

  const activeCoinConfig = COINS.find((c) => c.symbol === activeCoin) || COINS[0]
  const precision = activeCoinConfig.precision

  // ── 1. Fetch Backend State (/api/state) with non-blocking timeout ────────────
  const fetchState = useCallback(async () => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 3500)

    try {
      const resp = await fetch('/api/state', {
        signal: controller.signal,
        headers: { 'Cache-Control': 'no-cache' },
      })
      clearTimeout(timer)

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const data = await resp.json()
      setBackendState(data)
      setLastSyncTime(Date.now())

      if (data.status === 'QUARANTINED') {
        setConnectionStatus('QUARANTINED')
      } else {
        // Check staleness of data (if source time older than 5 minutes)
        if (data.source_time_utc) {
          const ageMs = Date.now() - new Date(data.source_time_utc).getTime()
          if (ageMs > 300_000) {
            setConnectionStatus('DATA_STALE')
          } else {
            setConnectionStatus('ONLINE')
          }
        } else {
          setConnectionStatus('ONLINE')
        }
      }
    } catch {
      clearTimeout(timer)
      setConnectionStatus((prev) => (prev === 'ONLINE' ? 'SERVER_ERROR' : prev))
    }
  }, [])

  // Poll state every 2 seconds
  useEffect(() => {
    fetchState()
    const interval = setInterval(fetchState, 2000)
    return () => clearInterval(interval)
  }, [fetchState])

  // ── 2. Real Public WebSocket Stream for Live 1m Kline Chart ─────────────────
  useEffect(() => {
    let ws = null
    let reconnectTimer = null
    let isCancelled = false

    const connectWs = () => {
      if (typeof WebSocket === 'undefined') return
      try {
        const streamUrl = `wss://fstream.binance.com/ws/${activeCoin.toLowerCase()}@kline_1m`
        ws = new WebSocket(streamUrl)

        ws.onmessage = (event) => {
          if (isCancelled) return
          try {
            const data = JSON.parse(event.data)
            if (data && data.k) {
              const k = data.k
              setLiveCandle({
                time: Math.floor(k.t / 1000),
                open: parseFloat(k.o),
                high: parseFloat(k.h),
                low: parseFloat(k.l),
                close: parseFloat(k.c),
                provisional: !k.x, // k.x is boolean: true if bar is closed, false if provisional
              })
            }
          } catch {
            // Silently ignore malformed packet
          }
        }

        ws.onerror = () => {
          // Fallback to backend polling if WebSocket drops
        }

        ws.onclose = () => {
          if (!isCancelled) {
            reconnectTimer = setTimeout(connectWs, 3000)
          }
        }
      } catch {
        // WebSocket not available in this environment; fallback
      }
    }

    connectWs()

    return () => {
      isCancelled = true
      clearTimeout(reconnectTimer)
      if (ws) {
        ws.onclose = null
        ws.close()
      }
    }
  }, [activeCoin])

  const [localRunning, setLocalRunning] = useState(false)

  // ── 3. Handle Coin Change ───────────────────────────────────────────────────
  const handleCoinChange = (newSymbol) => {
    setActiveCoin(newSymbol)
    setLiveCandle(null)
    if (typeof window !== 'undefined' && window.history?.replaceState) {
      const url = new URL(window.location.href)
      url.searchParams.set('coin', newSymbol)
      window.history.replaceState(null, '', url.toString())
    }
  }

  // ── 4. Bot Start / Stop Actions (/api/start, /api/stop) ─────────────────────
  const handleStart = async () => {
    setActionPending(true)
    setLocalRunning(true)
    try {
      const resp = await fetch('/api/start', { method: 'POST' })
      const data = await resp.json()
      setBackendState(data)
      setConnectionStatus(data.status === 'QUARANTINED' ? 'QUARANTINED' : 'ONLINE')
      if (data.status === 'QUARANTINED' || data.status === 'STOPPED') {
        setLocalRunning(false)
      }
    } catch {
      // In standalone UI mode or fetch error, remain running optimistically unless quarantined
    } finally {
      setActionPending(false)
    }
  }

  const handleStop = async () => {
    setActionPending(true)
    setLocalRunning(false)
    try {
      const resp = await fetch('/api/stop', { method: 'POST' })
      const data = await resp.json()
      setBackendState(data)
    } catch {
      // In standalone UI mode, stop was set locally
    } finally {
      setActionPending(false)
    }
  }

  // ── Derived Data from Backend State ─────────────────────────────────────────
  const isBotRunning =
    localRunning || backendState?.status === 'SCANNING' || backendState?.status === 'WAITING_SYNC'
  const isQuarantined = backendState?.status === 'QUARANTINED' || connectionStatus === 'QUARANTINED'

  const account = backendState?.account || {
    initial_equity_usd: 10000.0,
    wallet_usd: 10000.0,
    equity_usd: 10000.0,
    available_margin_usd: 10000.0,
    breaker_locked: false,
  }

  const openPositions = backendState?.open_positions || []
  const completedTrades = backendState?.trades || []
  const recentOrders = backendState?.orders || []
  const marketInfo = backendState?.markets?.[activeCoin]

  // Get symbol candles: check backendState.charts[activeCoin], then backendState.chart, then fallback
  const symbolCandles =
    backendState?.charts?.[activeCoin] ||
    (activeCoin === 'BTCUSDT' ? backendState?.chart : null) ||
    []

  // Best current price: from liveCandle close, or backend markets, or last candle close
  const currentPrice =
    liveCandle?.close ||
    marketInfo?.last_closed_15m_price ||
    (symbolCandles.length > 0 ? symbolCandles[symbolCandles.length - 1].close : null) ||
    (activeCoin === 'BTCUSDT' ? 64000 : activeCoin === 'ETHUSDT' ? 2500 : 150)

  // Calculate 24h stats based on symbolCandles if available
  const firstCandle = symbolCandles[0]
  const lastCandle = symbolCandles[symbolCandles.length - 1]
  const change24h = firstCandle && lastCandle ? lastCandle.close - firstCandle.open : 0
  const changePct24h = firstCandle && lastCandle && firstCandle.open > 0 ? (change24h / firstCandle.open) * 100 : 0
  const highs = symbolCandles.map((c) => c.high)
  const lows = symbolCandles.map((c) => c.low)
  const high24h = highs.length ? Math.max(...highs) : currentPrice
  const low24h = lows.length ? Math.min(...lows) : currentPrice

  return (
    <div className="app-shell">
      {/* Status Warning Alert Bar if disconnected or quarantined */}
      {isQuarantined && (
        <div
          role="alert"
          style={{
            background: 'rgba(246, 70, 93, 0.2)',
            borderBottom: '1px solid #F6465D',
            padding: '6px 16px',
            color: '#F6465D',
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            fontWeight: 600,
          }}
        >
          <span>⚠ CẢNH BÁO AN TOÀN: Nguồn dữ liệu bị cách ly (Quarantined). Đã dừng nhận lệnh để bảo vệ vốn.</span>
          <span style={{ color: '#EAECEF', fontWeight: 400 }}>{backendState?.error || 'Lỗi đối soát dữ liệu'}</span>
        </div>
      )}

      {connectionStatus === 'SERVER_ERROR' && (
        <div
          role="alert"
          style={{
            background: 'rgba(240, 185, 11, 0.15)',
            borderBottom: '1px solid #F0B90B',
            padding: '6px 16px',
            color: '#F0B90B',
            fontSize: '11px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
          }}
        >
          <span>⚠ Mất kết nối tới server local (http://127.0.0.1:8765/). Đang tự động kết nối lại...</span>
        </div>
      )}

      {/* Top Header */}
      <header className="exchange-header" role="banner">
        <a className="header-logo" href="#" aria-label="Quill3H Futures Paper Console">
          <div className="header-logo-mark" aria-hidden="true">
            Q
          </div>
          <div>
            <div className="header-logo-text">Quill3H</div>
            <div className="header-logo-sub">Futures Paper Trading</div>
          </div>
        </a>

        {/* Coin Switcher Tabs */}
        <nav className="coin-switcher" aria-label="Chọn cặp giao dịch">
          {COINS.map((coin) => (
            <button
              key={coin.symbol}
              className={`coin-tab ${activeCoin === coin.symbol ? 'active' : ''}`}
              onClick={() => handleCoinChange(coin.symbol)}
              type="button"
              aria-pressed={activeCoin === coin.symbol}
            >
              <span className="coin-dot" style={{ background: coin.color }} aria-hidden="true" />
              {coin.display}
            </button>
          ))}
        </nav>

        {/* Real-time Ticker */}
        <div className="header-ticker" aria-live="polite" aria-atomic="false">
          <span
            className={`ticker-price mono ${changePct24h >= 0 ? 'up' : 'down'}`}
            aria-label={`Giá hiện tại ${money(currentPrice, precision)}`}
          >
            {money(currentPrice, precision)}
          </span>

          <div className="ticker-stat">
            <span className="ticker-stat-label">24h Thay đổi</span>
            <span className={`ticker-stat-value mono ${changePct24h >= 0 ? 'text-buy' : 'text-sell'}`}>
              {changePct24h >= 0 ? '+' : ''}
              {money(change24h, precision)} ({changePct24h >= 0 ? '+' : ''}
              {changePct24h.toFixed(2)}%)
            </span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">24h Cao nhất</span>
            <span className="ticker-stat-value mono">{money(high24h, precision)}</span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">24h Thấp nhất</span>
            <span className="ticker-stat-value mono">{money(low24h, precision)}</span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">Chế độ</span>
            <span className="ticker-stat-value" style={{ color: '#F0B90B' }}>
              PAPER SIM
            </span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">Trạng thái Bot</span>
            <span
              className="ticker-stat-value"
              style={{ color: isBotRunning ? '#0ECB81' : isQuarantined ? '#F6465D' : '#848E9C' }}
            >
              {isBotRunning ? '● Đang chạy' : isQuarantined ? '⚠ Quarantined' : '○ Đã dừng'}
            </span>
          </div>
        </div>

        {/* Header Right Safety Badge */}
        <div className="header-right">
          <span className="header-badge">PAPER ONLY</span>
        </div>
      </header>

      {/* Main Trading Layout */}
      <div className="trading-layout">
        {/* LEFT PANEL: Market List + Strategy Status + Paper Account */}
        <aside className="market-info-panel" aria-label="Thông tin thị trường và tài khoản">
          <div className="panel-title">Cặp giao dịch Futures</div>
          <div className="symbol-list" role="list">
            {COINS.map((coin) => {
              const symMarket = backendState?.markets?.[coin.symbol]
              const symPrice =
                coin.symbol === activeCoin
                  ? currentPrice
                  : symMarket?.last_closed_15m_price || (coin.symbol === 'BTCUSDT' ? 64000 : coin.symbol === 'ETHUSDT' ? 2500 : 150)
              return (
                <div
                  key={coin.symbol}
                  className={`symbol-row ${activeCoin === coin.symbol ? 'active' : ''}`}
                  onClick={() => handleCoinChange(coin.symbol)}
                  role="listitem"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleCoinChange(coin.symbol)}
                  aria-label={`${coin.display} giá ${money(symPrice, coin.precision)}`}
                >
                  <div>
                    <div className="sym-name">{coin.display}</div>
                    <div className="sym-sub">USD-M PERP · PAPER</div>
                  </div>
                  <div className="sym-price mono up">{money(symPrice, coin.precision)}</div>
                </div>
              )
            })}
          </div>

          {/* Strategy Status Section */}
          <div className="panel-title" style={{ marginTop: '1px' }}>
            Chiến lược hệ thống
          </div>
          <div className="strategy-list" role="list">
            {STRATEGY_METADATA.map((strat) => (
              <div
                key={strat.id}
                className="strategy-item"
                role="listitem"
                style={{
                  opacity: strat.status === 'ACTIVE_LIVE' ? 1 : 0.65,
                  borderLeft: strat.status === 'ACTIVE_LIVE' ? '3px solid #0ECB81' : '3px solid transparent',
                }}
              >
                <div>
                  <div className="strategy-name" style={{ color: strat.status === 'ACTIVE_LIVE' ? '#0ECB81' : '#EAECEF' }}>
                    {strat.nameVi}
                  </div>
                  <div className="strategy-timeframe">
                    {strat.timeframe} · {strat.statusLabel}
                  </div>
                  <div style={{ fontSize: '10px', color: '#848E9C', marginTop: '2px' }}>
                    {strat.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Paper Account Summary */}
          <div className="account-panel" aria-label="Tài khoản mô phỏng">
            <div className="account-title">Tài khoản PAPER</div>
            <div className="account-row">
              <span className="account-key">Equity</span>
              <span className={`account-value mono ${account.equity_usd >= account.initial_equity_usd ? 'green' : 'red'}`}>
                {money(account.equity_usd)} USDT
              </span>
            </div>
            <div className="account-row">
              <span className="account-key">Wallet (Ví)</span>
              <span className="account-value mono">{money(account.wallet_usd)} USDT</span>
            </div>
            <div className="account-row">
              <span className="account-key">Khả dụng</span>
              <span className="account-value mono">{money(account.available_margin_usd)} USDT</span>
            </div>
            <div className="account-row">
              <span className="account-key">Circuit breaker</span>
              <span className={`account-value ${account.breaker_locked ? 'red' : 'green'}`}>
                {account.breaker_locked ? 'ĐÃ KHÓA' : 'Bình thường'}
              </span>
            </div>
            <div style={{ marginTop: '6px', fontSize: '10px', color: '#848E9C' }}>
              PaperBroker mô phỏng · Vốn được bảo toàn khi khởi động lại
            </div>
          </div>
        </aside>

        {/* CENTER PANEL: Candlestick Chart + Bot Status Bar + Trade Log Tabs */}
        <main className="center-panel" aria-label="Biểu đồ và nhật ký giao dịch">
          {/* Chart Toolbar */}
          <div className="chart-toolbar" role="toolbar" aria-label="Tùy chọn biểu đồ">
            <span className="toolbar-btn active">{activeCoin}</span>
            <div className="toolbar-divider" aria-hidden="true" />
            <span className="toolbar-btn" style={{ color: activeCoinConfig.color, fontWeight: 700 }}>
              ● {activeCoinConfig.name}
            </span>
            <div className="toolbar-divider" aria-hidden="true" />
            <span className="toolbar-btn active">1m</span>
            <span className="toolbar-btn">15m</span>
            <span className="toolbar-btn">4h</span>
            <div className="toolbar-divider" aria-hidden="true" />
            <span className="toolbar-btn" style={{ color: '#F0B90B', cursor: 'default' }}>
              📊 Binance Futures Public Stream · Trend Following (4h/15m)
            </span>
            <div className="toolbar-spacer" />
            <span style={{ fontSize: '11px', color: '#848E9C' }}>
              {liveCandle ? (
                liveCandle.provisional ? (
                  <span style={{ color: '#F0B90B' }}>● Nến 1m đang chạy (Provisional)</span>
                ) : (
                  <span style={{ color: '#0ECB81' }}>✔ Nến 1m đã đóng</span>
                )
              ) : (
                'Đang đồng bộ nến...'
              )}
            </span>
          </div>

          {/* Candlestick Chart Area */}
          <div className="chart-area" style={{ position: 'relative' }}>
            <CandlestickChart
              key={activeCoin}
              symbol={activeCoin}
              candles={symbolCandles}
              liveCandle={liveCandle}
              precision={precision}
            />

            {/* Overlay Info */}
            <div className="chart-overlay" aria-hidden="true">
              <div className="chart-label">
                <span className="chart-label-dot" style={{ background: activeCoinConfig.color }} />
                {activeCoin} Perpetual · Nến 1m công khai
              </div>
              <div className="chart-label">
                <span className="chart-label-dot" style={{ background: '#848E9C' }} />
                Quyết định trade: Chỉ dựa trên nến 15m/4h đã đóng hoàn toàn
              </div>
            </div>
          </div>

          {/* Bot Status Bar */}
          <div className="bot-status-bar" aria-live="polite">
            <span className={`bot-status-indicator ${isBotRunning ? 'running' : 'idle'}`} aria-hidden="true" />
            <span className="bot-status-text">
              {isBotRunning ? (
                <>
                  <strong>Bot đang tự động quét & giao dịch mô phỏng</strong> · Phiên #{backendState?.session_id || 'live'} ·{' '}
                  {openPositions.length} vị thế mở · {completedTrades.length} lệnh hoàn tất
                </>
              ) : (
                <>
                  Bot <strong>{isQuarantined ? 'bị cách ly an toàn' : 'đã dừng'}</strong> · Nhấn &quot;Khởi động Bot&quot; để bot tự động tính toán & giao dịch thử
                </>
              )}
            </span>
            <span style={{ marginLeft: 'auto', color: '#474D57', fontFamily: 'var(--font-mono)' }}>
              {backendState?.mode || 'PAPER_RESEARCH'} · Không có lệnh thật
            </span>
          </div>

          {/* Trade Log & Audit Tabs */}
          <div className="trade-log">
            <div className="trade-log-tabs" role="tablist">
              {[
                { id: 'closed', label: `Lệnh đã đóng (${completedTrades.length})` },
                { id: 'open', label: `Vị thế mở (${openPositions.length})` },
                { id: 'orders', label: `Lệnh gần đây (${recentOrders.length})` },
                { id: 'audit', label: 'Nguồn dữ liệu & Giới hạn' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  className={`trade-log-tab ${tradeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setTradeTab(tab.id)}
                  aria-selected={tradeTab === tab.id}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="trade-log-body" role="tabpanel">
              {tradeTab === 'closed' &&
                (completedTrades.length === 0 ? (
                  <div className="trade-log-empty">
                    Chưa có lệnh hoàn tất. Khi tín hiệu Trend Following xuất hiện và vị thế chạm SL/TP, lệnh đóng sẽ hiển thị ở đây.
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
                      {completedTrades.map((t) => (
                        <tr key={t.id || t.trade_id}>
                          <td className="mono">{t.exit_time_utc?.slice(11, 19) || '—'}</td>
                          <td>{t.symbol}</td>
                          <td className={t.side === 'LONG' ? 'buy' : 'sell'}>{t.side}</td>
                          <td className="mono">{money(t.entry_price, precision)}</td>
                          <td className="mono">{money(t.exit_price, precision)}</td>
                          <td className="mono">{money(t.fee_usd)}</td>
                          <td className={`mono ${t.net_pnl_usd >= 0 ? 'pos' : 'neg'}`}>
                            {t.net_pnl_usd >= 0 ? '+' : ''}
                            {money(t.net_pnl_usd)} USDT
                          </td>
                          <td style={{ color: '#848E9C' }}>{t.exit_reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ))}

              {tradeTab === 'open' &&
                (openPositions.length === 0 ? (
                  <div className="trade-log-empty">Không có vị thế đang mở. Bot tự động mở khi có tín hiệu Trend Following.</div>
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
                        <th>Giá thanh lý</th>
                      </tr>
                    </thead>
                    <tbody>
                      {openPositions.map((pos) => (
                        <tr key={pos.symbol}>
                          <td>{pos.symbol}</td>
                          <td className={pos.side === 'LONG' ? 'buy' : 'sell'}>{pos.side}</td>
                          <td className="mono">{pos.quantity.toFixed(4)}</td>
                          <td className="mono">{money(pos.entry_price, precision)}</td>
                          <td className="mono">{money(pos.stop_loss_price, precision)}</td>
                          <td>{pos.leverage}×</td>
                          <td className="mono">{money(pos.liquidation_price, precision)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ))}

              {tradeTab === 'orders' &&
                (recentOrders.length === 0 ? (
                  <div className="trade-log-empty">Chưa có lệnh nào được tạo.</div>
                ) : (
                  <table aria-label="Lệnh gần đây">
                    <thead>
                      <tr>
                        <th>Mã</th>
                        <th>Hướng</th>
                        <th>Trạng thái</th>
                        <th>Lý do từ chối (nếu có)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentOrders.map((o) => (
                        <tr key={o.id}>
                          <td>{o.symbol}</td>
                          <td className={o.side === 'LONG' ? 'buy' : 'sell'}>{o.side}</td>
                          <td style={{ color: o.status === 'FILLED' ? '#0ECB81' : '#F6465D' }}>{o.status}</td>
                          <td style={{ color: '#848E9C' }}>{o.rejection_reasons?.join(', ') || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ))}

              {tradeTab === 'audit' && (
                <div style={{ padding: '12px 14px' }}>
                  <div style={{ fontSize: '11px', color: '#848E9C', marginBottom: '8px' }}>
                    Nguồn dữ liệu & Cơ chế an toàn theo hợp đồng kiến trúc:
                  </div>
                  <table aria-label="Nguồn dữ liệu">
                    <thead>
                      <tr>
                        <th>Hạng mục</th>
                        <th>Mô tả</th>
                        <th>Trạng thái</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Dữ liệu nến vào lệnh</td>
                        <td>Binance USD-M REST /fapi/v1/klines (4h/15m)</td>
                        <td style={{ color: '#0ECB81' }}>ĐÃ ĐÓNG HOÀN TOÀN</td>
                      </tr>
                      <tr>
                        <td>Dữ liệu biểu đồ</td>
                        <td>Binance USD-M Public WebSocket (@kline_1m)</td>
                        <td style={{ color: '#0ECB81' }}>LIVE STREAM</td>
                      </tr>
                      <tr>
                        <td>Bảo toàn vốn qua restart</td>
                        <td>persistent_state.json tự động khôi phục số dư</td>
                        <td style={{ color: '#0ECB81' }}>PERSISTENT</td>
                      </tr>
                      <tr>
                        <td>Giới hạn rủi ro</td>
                        <td>Đòn bẩy tối đa 5×, Stop-loss 3%, Circuit Breaker 3 lệnh thua</td>
                        <td style={{ color: '#F0B90B' }}>STRICT RISK GATE</td>
                      </tr>
                    </tbody>
                  </table>
                  <div style={{ marginTop: '10px', fontSize: '10px', color: '#848E9C', lineHeight: '1.7' }}>
                    Tuyên bố an toàn: Mọi giao dịch thực hiện bởi PaperBroker cục bộ. Tuyệt đối không gửi lệnh lên sàn Binance, không sử dụng API key giao dịch, không dùng testnet. không có lệnh sàn thật hoặc testnet.
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>

        {/* RIGHT PANEL: Bot Controls + Open Positions + Risk */}
        <aside className="order-panel" aria-label="Điều khiển bot và vị thế">
          {/* Bot Control Section */}
          <div className="bot-control">
            <div className="bot-control-title">Bot Mô Phỏng · PAPER</div>
            <div className="bot-config-row">
              <span className="bot-config-key">Chiến lược</span>
              <span className="bot-config-value">Trend Following (4h/15m)</span>
            </div>
            <div className="bot-config-row">
              <span className="bot-config-key">Rủi ro/lệnh</span>
              <span className="bot-config-value">2% wallet</span>
            </div>
            <div className="bot-config-row">
              <span className="bot-config-key">Đòn bẩy tối đa</span>
              <span className="bot-config-value">5× (giới hạn cứng)</span>
            </div>
            <div className="bot-config-row">
              <span className="bot-config-key">Vốn ban đầu</span>
              <span className="bot-config-value mono">10,000 USDT</span>
            </div>
            <div className="bot-config-row">
              <span className="bot-config-key">Cặp theo dõi</span>
              <span className="bot-config-value">BTC · ETH · SOL</span>
            </div>

            {/* Buttons */}
            <div className="bot-btn-group">
              <button
                type="button"
                className="btn-start"
                onClick={handleStart}
                disabled={isBotRunning || isQuarantined}
                aria-label="Khởi động bot mô phỏng paper trading"
              >
                {isBotRunning ? '▶ Đang chạy...' : '▶ Khởi động Bot'}
              </button>
              <button
                type="button"
                className="btn-stop"
                onClick={handleStop}
                disabled={!isBotRunning}
                aria-label="Dừng bot mô phỏng"
              >
                ■ Dừng
              </button>
            </div>

            {isQuarantined && (
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
                ⚠ Dừng nhận lệnh: Phiên trước bị gián đoạn và chưa thể khôi phục an toàn. Cần quản trị viên kiểm tra.
              </div>
            )}
          </div>

          {/* Open Positions Cards */}
          <div className="positions-section" aria-label="Vị thế đang mở">
            <div className="panel-title">Vị thế đang mở ({openPositions.length})</div>
            {openPositions.length === 0 ? (
              <div style={{ padding: '20px 14px', color: '#474D57', fontSize: '12px' }}>
                Không có vị thế mở. Bot sẽ tự động tạo lệnh khi xuất hiện tín hiệu Trend Following hợp lệ.
              </div>
            ) : (
              openPositions.map((pos) => (
                <div
                  key={pos.symbol}
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
                      <div className="position-stat-val mono">{money(pos.entry_price, precision)}</div>
                    </div>
                    <div>
                      <div className="position-stat-key">Đòn bẩy</div>
                      <div className="position-stat-val">{pos.leverage}×</div>
                    </div>
                    <div>
                      <div className="position-stat-key">Stop-loss</div>
                      <div className="position-stat-val mono">{money(pos.stop_loss_price, precision)}</div>
                    </div>
                    <div>
                      <div className="position-stat-key">Số lượng</div>
                      <div className="position-stat-val mono">{pos.quantity.toFixed(4)}</div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Session Risk & Recovery Summary */}
          <div className="risk-audit-section" aria-label="Tóm tắt rủi ro">
            <div className="account-title">Tóm tắt phiên & An toàn</div>
            <div className="risk-row">
              <span className="risk-key">Lệnh đã đóng</span>
              <span className="risk-val">{completedTrades.length}</span>
            </div>
            <div className="risk-row">
              <span className="risk-key">Trạng thái kết nối</span>
              <span className={`risk-val ${connectionStatus === 'ONLINE' ? 'green' : 'yellow'}`}>
                {connectionStatus === 'ONLINE' ? 'Kết nối ổn định' : connectionStatus}
              </span>
            </div>
            <div className="risk-row">
              <span className="risk-key">Đòn bẩy tối đa</span>
              <span className="risk-val yellow">5× (giới hạn cứng)</span>
            </div>
            <div className="risk-note">
              PaperBroker mô phỏng độc lập. Phí taker 0.05%, stop-loss 3%, không có lệnh sàn thật hoặc testnet.
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
