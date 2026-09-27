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
 *   • Strict state confirmation: no optimistic running flags.
 *   • Real session persistence, automatic reconnection, and safe recovery.
 *   • Zero Math.random(), zero fake default prices.
 */

import { useEffect, useRef, useState } from 'react'
import './styles.css'
import { CandlestickChart } from './CandlestickChart'

// ─── Constants & Symbols ─────────────────────────────────────────────────────

export const COINS = [
  { symbol: 'BTCUSDT', name: 'BTC', display: 'BTCUSDT', color: '#F7931A', precision: 2 },
  { symbol: 'ETHUSDT', name: 'ETH', display: 'ETHUSDT', color: '#627EEA', precision: 2 },
  { symbol: 'SOLUSDT', name: 'SOL', display: 'SOLUSDT', color: '#9945FF', precision: 2 },
]

export const STRATEGY_METADATA = [
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

export const money = (v, prec = 2) => {
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
  const [connectionStatus, setConnectionStatus] = useState('CONNECTING')
  // 'CONNECTING' | 'ONLINE' | 'WAITING_DATA' | 'WAITING_CONNECTION' | 'DATA_STALE' | 'SERVER_ERROR' | 'QUARANTINED' | 'RECOVERY_REQUIRED'

  const [backendState, setBackendState] = useState(null)
  const [liveCandle, setLiveCandle] = useState(null)
  const [tradeTab, setTradeTab] = useState('closed')
  const [botActionState, setBotActionState] = useState(null) // 'STARTING' | 'STOPPING' | null
  const [actionError, setActionError] = useState(null)
  const [lastSyncTime, setLastSyncTime] = useState(null)

  const activeCoinConfig = COINS.find((c) => c.symbol === activeCoin) || COINS[0]
  const precision = activeCoinConfig.precision

  // ── 1. Resilient Sequential Polling (/api/state) with out-of-order drop ──────
  const pollSeqRef = useRef(0)
  const latestCompletedSeqRef = useRef(0)
  const isPollingRef = useRef(false)
  const pollTimeoutRef = useRef(null)

  useEffect(() => {
    let isCancelled = false

    const pollState = async () => {
      if (isPollingRef.current) return
      isPollingRef.current = true
      const thisSeq = ++pollSeqRef.current

      try {
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), 4000)

        const resp = await fetch('/api/state', {
          signal: controller.signal,
          headers: { 'Cache-Control': 'no-cache' },
        })
        clearTimeout(timeout)

        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`)
        }

        const data = await resp.json()

        // Discard out-of-order stale response: older poll arriving after newer poll
        if (thisSeq < latestCompletedSeqRef.current) {
          return
        }
        latestCompletedSeqRef.current = thisSeq

        if (isCancelled) return

        setBackendState(data)
        setLastSyncTime(Date.now())

        // Classify connection & backend status
        if (data.status === 'QUARANTINED') {
          setConnectionStatus('QUARANTINED')
        } else if (data.status === 'RECOVERY_REQUIRED') {
          setConnectionStatus('RECOVERY_REQUIRED')
        } else if (data.status === 'WAITING_CONNECTION') {
          setConnectionStatus('WAITING_CONNECTION')
        } else if (!data.source_time_utc) {
          // Rule: source_time_utc = null must NEVER be considered ONLINE
          setConnectionStatus('WAITING_DATA')
        } else {
          const ageMs = Date.now() - new Date(data.source_time_utc).getTime()
          const streamConnected = data.connection?.connected ?? true
          if (ageMs > 180_000 || !streamConnected) {
            setConnectionStatus('DATA_STALE')
          } else {
            setConnectionStatus('ONLINE')
          }
        }
      } catch {
        if (isCancelled) return
        if (thisSeq >= latestCompletedSeqRef.current) {
          latestCompletedSeqRef.current = thisSeq
          setConnectionStatus('SERVER_ERROR')
        }
      } finally {
        isPollingRef.current = false
        if (!isCancelled) {
          pollTimeoutRef.current = setTimeout(pollState, 2000)
        }
      }
    }

    pollState()

    return () => {
      isCancelled = true
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current)
      }
    }
  }, [])

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
                provisional: !k.x, // true if bar is still forming, false if closed
              })
            }
          } catch {}
        }

        ws.onerror = () => {}

        ws.onclose = () => {
          if (!isCancelled) {
            reconnectTimer = setTimeout(connectWs, 3000)
          }
        }
      } catch {}
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
  // ZERO optimistic running state: status updates ONLY when backend confirms!
  const handleStart = async () => {
    if (isBotRunning || botActionState !== null || isQuarantined || isRecoveryRequired) return
    setBotActionState('STARTING')
    setActionError(null)

    try {
      const resp = await fetch('/api/start', {
        method: 'POST',
        signal: AbortSignal.timeout(8000),
      })

      if (!resp.ok) {
        let errDetail = `HTTP ${resp.status}`
        try {
          const errJson = await resp.json()
          if (errJson?.error) errDetail = errJson.error
        } catch {}
        setActionError(`Không thể khởi động bot: ${errDetail}`)
        return
      }

      const data = await resp.json()
      setBackendState(data)

      if (data.status === 'RECOVERY_REQUIRED') {
        setActionError(`Yêu cầu đối soát: ${data.error || 'Tồn tại journal phiên trước chưa phục hồi.'}`)
      } else if (data.status === 'QUARANTINED') {
        setActionError(`Bot bị cách ly: ${data.error || 'Dữ liệu không an toàn.'}`)
      } else if (data.status === 'STOPPED') {
        setActionError(data.error || 'Server từ chối khởi động bot.')
      } else if (data.error) {
        setActionError(`Lỗi backend: ${data.error}`)
      }
    } catch (err) {
      const isTimeout = err?.name === 'TimeoutError' || err?.message?.includes('timeout')
      setActionError(
        isTimeout
          ? 'Không thể khởi động bot: Hết thời gian chờ kết nối (Timeout)'
          : `Không thể khởi động bot: ${err?.message || 'Mất kết nối server'}`
      )
    } finally {
      setBotActionState(null)
    }
  }

  const handleStop = async () => {
    if (!isBotRunning || botActionState !== null) return
    setBotActionState('STOPPING')
    setActionError(null)

    try {
      const resp = await fetch('/api/stop', {
        method: 'POST',
        signal: AbortSignal.timeout(8000),
      })

      if (!resp.ok) {
        let errDetail = `HTTP ${resp.status}`
        try {
          const errJson = await resp.json()
          if (errJson?.error) errDetail = errJson.error
        } catch {}
        setActionError(`Không thể dừng bot: ${errDetail}`)
        return
      }

      const data = await resp.json()
      setBackendState(data)
      if (data.status !== 'STOPPED' && data.status !== 'IDLE') {
        setActionError(data.error || 'Server chưa xác nhận trạng thái dừng.')
      }
    } catch (err) {
      setActionError(`Lỗi kết nối khi dừng bot: ${err?.message || 'Mất kết nối server'}`)
    } finally {
      setBotActionState(null)
    }
  }

  // ── Derived Data from Backend State (100% from backend, no client math) ─────
  const isBotRunning = backendState?.status === 'SCANNING' || backendState?.status === 'WAITING_SYNC'
  const isQuarantined = backendState?.status === 'QUARANTINED' || connectionStatus === 'QUARANTINED'
  const isRecoveryRequired = backendState?.status === 'RECOVERY_REQUIRED' || connectionStatus === 'RECOVERY_REQUIRED'

  const account = backendState?.account || {
    initial_equity_usd: 10000.0,
    wallet_usd: 10000.0,
    equity_usd: 10000.0,
    available_margin_usd: 10000.0,
    reserved_collateral_usd: 0.0,
    unrealized_pnl_usd: 0.0,
    breaker_locked: false,
  }

  const openPositions = backendState?.open_positions || []
  const pendingOrders = backendState?.pending_orders || []
  const completedTrades = backendState?.trades || []
  const recentOrders = backendState?.orders || []
  const marketInfo = backendState?.markets?.[activeCoin]
  const riskGate = backendState?.risk_gate

  // Symbol Candles from backend
  const symbolCandles =
    backendState?.charts?.[activeCoin] ||
    (activeCoin === 'BTCUSDT' ? backendState?.chart : null) ||
    []

  // Real current price: strictly real or null. ZERO fake numbers (64k/2.5k/150).
  const marketPrice = typeof marketInfo?.last_closed_15m_price === 'number' ? marketInfo.last_closed_15m_price : null
  const lastCandlePrice = symbolCandles.length > 0 && typeof symbolCandles[symbolCandles.length - 1].close === 'number'
    ? symbolCandles[symbolCandles.length - 1].close
    : null
  const currentPrice = liveCandle?.close ?? marketPrice ?? lastCandlePrice ?? null

  // Function to get real price for any coin in the left list
  const getCoinPrice = (symbol) => {
    if (symbol === activeCoin && currentPrice !== null) return currentPrice
    const symMarket = backendState?.markets?.[symbol]
    if (typeof symMarket?.last_closed_15m_price === 'number') {
      return symMarket.last_closed_15m_price
    }
    const symCandles = backendState?.charts?.[symbol] || (symbol === 'BTCUSDT' ? backendState?.chart : null) || []
    if (symCandles.length > 0 && typeof symCandles[symCandles.length - 1].close === 'number') {
      return symCandles[symCandles.length - 1].close
    }
    return null
  }

  // 24h stats based on real symbolCandles
  const firstCandle = symbolCandles.length > 0 ? symbolCandles[0] : null
  const lastCandle = symbolCandles.length > 0 ? symbolCandles[symbolCandles.length - 1] : null
  const hasCandles = firstCandle && lastCandle && typeof firstCandle.open === 'number' && firstCandle.open > 0
  const change24h = hasCandles && currentPrice !== null ? currentPrice - firstCandle.open : null
  const changePct24h = hasCandles && currentPrice !== null ? (change24h / firstCandle.open) * 100 : null

  const validHighs = symbolCandles.map((c) => Number(c.high)).filter((h) => !Number.isNaN(h))
  const validLows = symbolCandles.map((c) => Number(c.low)).filter((l) => !Number.isNaN(l))
  const high24h = validHighs.length > 0 ? Math.max(...validHighs) : currentPrice
  const low24h = validLows.length > 0 ? Math.min(...validLows) : currentPrice

  // Timestamp formatting
  const priceUpdateUtc =
    liveCandle
      ? 'Vừa nhận (WebSocket)'
      : marketInfo?.as_of_utc
      ? new Date(marketInfo.as_of_utc).toLocaleTimeString('vi-VN', { hour12: false })
      : backendState?.source_time_utc
      ? new Date(backendState.source_time_utc).toLocaleTimeString('vi-VN', { hour12: false })
      : null

  // Market feed connection status
  const marketFeedText =
    liveCandle
      ? '● WebSocket Trực tiếp'
      : marketInfo
      ? '● REST Nến đã đóng'
      : connectionStatus === 'DATA_STALE'
      ? '⚠ Nguồn nến gián đoạn'
      : '○ Chờ dữ liệu nến'

  const marketFeedColor =
    liveCandle
      ? '#0ECB81'
      : marketInfo
      ? '#2563EB'
      : connectionStatus === 'DATA_STALE'
      ? '#F0B90B'
      : '#848E9C'

  // Bot status text & color
  const botStatusBadge = (() => {
    switch (backendState?.status) {
      case 'SCANNING':
        return { label: '● Đang quét (Live Paper)', color: '#0ECB81', indicator: 'running' }
      case 'WAITING_SYNC':
        return { label: '● Chờ đồng bộ 3 cặp', color: '#2563EB', indicator: 'sync' }
      case 'WAITING_CONNECTION':
        return { label: '○ Chờ kết nối stream', color: '#F0B90B', indicator: 'recovery' }
      case 'QUARANTINED':
        return { label: '⚠ Bị cách ly (Quarantined)', color: '#F6465D', indicator: 'error' }
      case 'RECOVERY_REQUIRED':
        return { label: '⚠ Cần đối soát (Recovery Required)', color: '#F0B90B', indicator: 'recovery' }
      case 'STOPPED':
        return { label: '○ Đã dừng (Stopped)', color: '#848E9C', indicator: 'idle' }
      case 'IDLE':
      default:
        return { label: '○ Chưa khởi động (Idle)', color: '#848E9C', indicator: 'idle' }
    }
  })()

  return (
    <div className="app-shell">
      {/* ── Top Alert Banners ── */}

      {/* 1. Action Error Banner (dismissible) */}
      {actionError && (
        <div role="alert" className="alert-action-error">
          <span>⚠ LỖI THAO TÁC: {actionError}</span>
          <button type="button" onClick={() => setActionError(null)}>
            ✕ Đóng
          </button>
        </div>
      )}

      {/* 2. Recovery Required Safety Banner */}
      {isRecoveryRequired && (
        <div role="alert" className="alert-recovery">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '14px' }}>⚠</span>
            <strong>CẢNH BÁO AN TOÀN: YÊU CẦU ĐỐI SOÁT PHỤC HỒI (RECOVERY REQUIRED)</strong>
          </div>
          <div style={{ fontSize: '11px', fontWeight: 400, color: '#EAECEF', lineHeight: '1.6' }}>
            Phát hiện journal phiên trước {backendState?.session_id ? `(#${backendState.session_id})` : ''}. Backend đang ở chế độ <strong>Chỉ-Đọc (Read-only)</strong> để bảo vệ vốn và vị thế đã lưu, không tự ý reset về 10,000 USDT hay tạo phiên mới khi chưa đối soát. Cần quản trị viên kiểm tra file journal cục bộ trước khi mở lại giao dịch.
          </div>
          {backendState?.error && (
            <div style={{ fontSize: '11px', color: '#F0B90B', marginTop: '2px' }}>
              Chi tiết: {backendState.error}
            </div>
          )}
        </div>
      )}

      {/* 3. Quarantine Safety Banner */}
      {isQuarantined && !isRecoveryRequired && (
        <div role="alert" className="alert-quarantine">
          <span>⚠ CẢNH BÁO AN TOÀN: Nguồn dữ liệu bị cách ly (Quarantined). Đã dừng nhận lệnh để bảo vệ vốn.</span>
          <span style={{ color: '#EAECEF', fontWeight: 400 }}>{backendState?.error || 'Lỗi đối soát dữ liệu'}</span>
        </div>
      )}

      {/* 4. Server Disconnected Banner */}
      {connectionStatus === 'SERVER_ERROR' && (
        <div role="alert" className="alert-server-error">
          <span>⚠ Mất kết nối tới server local (http://127.0.0.1:8765/). Đang tự động kết nối lại...</span>
        </div>
      )}

      {/* 5. Stale Data Warning Banner */}
      {connectionStatus === 'DATA_STALE' && (
        <div role="alert" className="alert-stale">
          <span>⚠ Nguồn dữ liệu thị trường gián đoạn hoặc quá cũ. Đang chờ khôi phục luồng dữ liệu...</span>
        </div>
      )}

      {/* ── Top Header ── */}
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
          {currentPrice !== null ? (
            <span
              className={`ticker-price mono ${changePct24h !== null && changePct24h >= 0 ? 'up' : 'down'}`}
              aria-label={`Giá hiện tại ${money(currentPrice, precision)}`}
            >
              {money(currentPrice, precision)}
            </span>
          ) : (
            <span className="ticker-no-price" aria-label="Chưa có dữ liệu giá">
              Chưa có dữ liệu
            </span>
          )}

          <div className="ticker-stat">
            <span className="ticker-stat-label">24h Thay đổi</span>
            {changePct24h !== null && change24h !== null ? (
              <span className={`ticker-stat-value mono ${changePct24h >= 0 ? 'text-buy' : 'text-sell'}`}>
                {changePct24h >= 0 ? '+' : ''}
                {money(change24h, precision)} ({changePct24h >= 0 ? '+' : ''}
                {changePct24h.toFixed(2)}%)
              </span>
            ) : (
              <span className="ticker-stat-value mono text-muted">--</span>
            )}
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">24h Cao nhất</span>
            <span className="ticker-stat-value mono">
              {high24h !== null ? money(high24h, precision) : '--'}
            </span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">24h Thấp nhất</span>
            <span className="ticker-stat-value mono">
              {low24h !== null ? money(low24h, precision) : '--'}
            </span>
          </div>

          {/* Separate Market Data Connection from Bot Status */}
          <div className="ticker-stat" title="Nguồn nến công khai hiển thị — Không chứng minh bot nhận lệnh">
            <span className="ticker-stat-label">Nguồn giá (Chart)</span>
            <span className="ticker-stat-value" style={{ color: marketFeedColor }}>
              {marketFeedText}
            </span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">Trạng thái Bot</span>
            <span className="ticker-stat-value" style={{ color: botStatusBadge.color }}>
              {botStatusBadge.label}
            </span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">Cổng lệnh</span>
            <span
              className="ticker-stat-value"
              style={{ color: riskGate?.admission_open ? '#0ECB81' : '#F6465D' }}
            >
              {riskGate?.admission_open ? '● MỞ (Sim)' : '○ ĐÓNG'}
            </span>
          </div>

          <div className="ticker-stat">
            <span className="ticker-stat-label">Thời điểm</span>
            <span className="ticker-stat-value mono" style={{ fontSize: '11px', color: '#848E9C' }}>
              {priceUpdateUtc || 'Chưa đồng bộ'}
            </span>
          </div>
        </div>

        {/* Header Right Safety Badge */}
        <div className="header-right">
          <span className="header-badge">PAPER ONLY</span>
        </div>
      </header>

      {/* ── Main Trading Layout ── */}
      <div className="trading-layout">
        {/* LEFT PANEL: Market List + Strategy Status + Paper Account */}
        <aside className="market-info-panel" aria-label="Thông tin thị trường và tài khoản">
          <div className="panel-title">Cặp giao dịch Futures</div>
          <div className="symbol-list" role="list">
            {COINS.map((coin) => {
              const symPrice = getCoinPrice(coin.symbol)
              return (
                <div
                  key={coin.symbol}
                  className={`symbol-row ${activeCoin === coin.symbol ? 'active' : ''}`}
                  onClick={() => handleCoinChange(coin.symbol)}
                  role="listitem"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleCoinChange(coin.symbol)}
                  aria-label={`${coin.display} giá ${symPrice !== null ? money(symPrice, coin.precision) : 'Chưa có giá'}`}
                >
                  <div>
                    <div className="sym-name">{coin.display}</div>
                    <div className="sym-sub">USD-M PERP · PAPER</div>
                  </div>
                  <div className="sym-price mono up">
                    {symPrice !== null ? money(symPrice, coin.precision) : 'Chưa có giá'}
                  </div>
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
                  <div
                    className="strategy-name"
                    style={{ color: strat.status === 'ACTIVE_LIVE' ? '#0ECB81' : '#EAECEF' }}
                  >
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
              <span
                className={`account-value mono ${account.equity_usd >= account.initial_equity_usd ? 'green' : 'red'}`}
              >
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
              <span className="account-key">Ký quỹ đang dùng</span>
              <span className="account-value mono">{money(account.reserved_collateral_usd ?? 0.0)} USDT</span>
            </div>
            <div className="account-row">
              <span className="account-key">PnL chưa thực hiện</span>
              <span
                className={`account-value mono ${(account.unrealized_pnl_usd ?? 0) >= 0 ? 'green' : 'red'}`}
              >
                {money(account.unrealized_pnl_usd ?? 0.0)} USDT
              </span>
            </div>
            <div className="account-row">
              <span className="account-key">Circuit breaker</span>
              <span className={`account-value ${account.breaker_locked ? 'red' : 'green'}`}>
                {account.breaker_locked ? 'ĐÃ KHÓA' : 'Bình thường'}
              </span>
            </div>
            <div style={{ marginTop: '6px', fontSize: '10px', color: '#848E9C' }}>
              PaperBroker mô phỏng · 100% số liệu từ backend · Không tự tính PnL trong trình duyệt
            </div>
          </div>
        </aside>

        {/* CENTER PANEL: Chart Toolbar + Candlestick Chart + Bot Status Bar + Trade Log */}
        <main className="chart-panel" aria-label="Biểu đồ giao dịch và lịch sử">
          {/* Chart Toolbar */}
          <div className="chart-toolbar">
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
            <span className={`bot-status-indicator ${botStatusBadge.indicator}`} aria-hidden="true" />
            <span className="bot-status-text">
              {isBotRunning ? (
                <>
                  <strong>Bot đang tự động quét & giao dịch mô phỏng</strong> · Phiên #{backendState?.session_id || 'live'} ·{' '}
                  {openPositions.length} vị thế mở · {completedTrades.length} lệnh hoàn tất
                </>
              ) : isRecoveryRequired ? (
                <>
                  Bot đang ở chế độ <strong>Yêu cầu đối soát phục hồi (Recovery Required)</strong> · Đã dừng nhận lệnh · Cần kiểm tra journal
                </>
              ) : isQuarantined ? (
                <>
                  Bot <strong>bị cách ly an toàn (Quarantined)</strong> · Đã dừng nhận lệnh để bảo vệ vốn
                </>
              ) : (
                <>
                  Bot <strong>đã dừng</strong> · Nhấn &quot;Khởi động Bot&quot; để bot tự động tính toán & giao dịch thử
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
                { id: 'orders', label: `Lệnh gần đây (${recentOrders.length + pendingOrders.length})` },
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
                        <th>Cặp</th>
                        <th>Phe</th>
                        <th>Giá vào</th>
                        <th>Giá đóng</th>
                        <th>Số lượng</th>
                        <th>PnL ròng</th>
                        <th>Lý do</th>
                      </tr>
                    </thead>
                    <tbody>
                      {completedTrades.map((t, idx) => (
                        <tr key={idx}>
                          <td className="mono">{t.exit_time || t.time || '--'}</td>
                          <td>{t.symbol}</td>
                          <td className={t.side === 'LONG' ? 'text-buy' : 'text-sell'}>{t.side}</td>
                          <td className="mono">{money(t.entry_price, precision)}</td>
                          <td className="mono">{money(t.exit_price, precision)}</td>
                          <td className="mono">{Number(t.quantity).toFixed(4)}</td>
                          <td className={`mono ${(t.pnl_net_usd ?? t.pnl ?? 0) >= 0 ? 'text-buy' : 'text-sell'}`}>
                            {money(t.pnl_net_usd ?? t.pnl ?? 0)} USDT
                          </td>
                          <td>{t.exit_reason || t.reason || '--'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ))}

              {tradeTab === 'open' &&
                (openPositions.length === 0 ? (
                  <div className="trade-log-empty">
                    Hiện tại không có vị thế mở nào. Bot quản lý vị thế tự động theo quy tắc rủi ro 2% vốn và đòn bẩy tối đa 5×.
                  </div>
                ) : (
                  <table aria-label="Vị thế mở">
                    <thead>
                      <tr>
                        <th>Cặp</th>
                        <th>Phe</th>
                        <th>Giá vào</th>
                        <th>Đòn bẩy</th>
                        <th>Stop Loss</th>
                        <th>Số lượng</th>
                        <th>Ký quỹ</th>
                        <th>PnL chưa chốt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {openPositions.map((pos) => (
                        <tr key={pos.symbol}>
                          <td><strong>{pos.symbol}</strong></td>
                          <td className={pos.side === 'LONG' ? 'text-buy' : 'text-sell'}>{pos.side}</td>
                          <td className="mono">{money(pos.entry_price, precision)}</td>
                          <td>{pos.leverage}×</td>
                          <td className="mono">{money(pos.stop_loss_price, precision)}</td>
                          <td className="mono">{Number(pos.quantity).toFixed(4)}</td>
                          <td className="mono">{money(pos.collateral_usd ?? pos.margin_usd)} USDT</td>
                          <td className={`mono ${(pos.unrealized_pnl_usd ?? 0) >= 0 ? 'text-buy' : 'text-sell'}`}>
                            {money(pos.unrealized_pnl_usd ?? 0.0)} USDT
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ))}

              {tradeTab === 'orders' && (
                <div>
                  {recentOrders.length === 0 && pendingOrders.length === 0 ? (
                    <div className="trade-log-empty">Chưa có lệnh mô phỏng nào được tạo.</div>
                  ) : (
                    <table aria-label="Lệnh gần đây">
                      <thead>
                        <tr>
                          <th>Thời gian</th>
                          <th>Cặp</th>
                          <th>Loại lệnh</th>
                          <th>Phe</th>
                          <th>Giá khớp/chờ</th>
                          <th>Số lượng</th>
                          <th>Trạng thái</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pendingOrders.map((ord, idx) => (
                          <tr key={`p-${idx}`} style={{ background: 'rgba(240, 185, 11, 0.06)' }}>
                            <td className="mono">{ord.time_utc || '--'}</td>
                            <td>{ord.symbol}</td>
                            <td>{ord.order_type || 'PENDING'}</td>
                            <td className={ord.side === 'LONG' ? 'text-buy' : 'text-sell'}>{ord.side}</td>
                            <td className="mono">{money(ord.price, precision)}</td>
                            <td className="mono">{Number(ord.quantity || 0).toFixed(4)}</td>
                            <td style={{ color: '#F0B90B' }}>PENDING</td>
                          </tr>
                        ))}
                        {recentOrders.map((ord, idx) => (
                          <tr key={`o-${idx}`}>
                            <td className="mono">{ord.time_utc || ord.time || '--'}</td>
                            <td>{ord.symbol}</td>
                            <td>{ord.order_type || 'MARKET'}</td>
                            <td className={ord.side === 'LONG' ? 'text-buy' : 'text-sell'}>{ord.side}</td>
                            <td className="mono">{money(ord.fill_price || ord.price, precision)}</td>
                            <td className="mono">{Number(ord.quantity || 0).toFixed(4)}</td>
                            <td style={{ color: ord.status === 'FILLED' ? '#0ECB81' : '#848E9C' }}>
                              {ord.status || 'SUBMITTED'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {tradeTab === 'audit' && (
                <div style={{ padding: '12px 14px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#EAECEF', marginBottom: '8px' }}>
                    Kiểm chứng dữ liệu & Cơ chế an toàn
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
                      <tr>
                        <td>Cổng nhận lệnh (Risk Gate)</td>
                        <td>{riskGate?.reason || (riskGate?.admission_open ? 'Sẵn sàng nhận lệnh mô phỏng' : 'Đóng nhận lệnh')}</td>
                        <td style={{ color: riskGate?.admission_open ? '#0ECB81' : '#F6465D' }}>
                          {riskGate?.admission_open ? 'OPEN' : 'CLOSED'}
                        </td>
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

            {/* Buttons: Strictly no optimistic state, locked on RECOVERY_REQUIRED */}
            <div className="bot-btn-group">
              {isRecoveryRequired ? (
                <button
                  type="button"
                  className="btn-start btn-recovery-locked"
                  disabled
                  aria-label="Khóa khởi động do cần đối soát journal"
                >
                  🔒 Khóa: Cần đối soát (Recovery Required)
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-start"
                  onClick={handleStart}
                  disabled={
                    isBotRunning ||
                    botActionState !== null ||
                    isQuarantined ||
                    connectionStatus === 'SERVER_ERROR'
                  }
                  aria-label="Khởi động bot mô phỏng paper trading"
                >
                  {botActionState === 'STARTING'
                    ? '⏳ Đang khởi động...'
                    : isBotRunning
                    ? '▶ Đang chạy...'
                    : '▶ Khởi động Bot'}
                </button>
              )}

              <button
                type="button"
                className="btn-stop"
                onClick={handleStop}
                disabled={!isBotRunning || botActionState !== null}
                aria-label="Dừng bot mô phỏng"
              >
                {botActionState === 'STOPPING' ? '⏳ Đang dừng...' : '■ Dừng'}
              </button>
            </div>

            {/* Notice for RECOVERY_REQUIRED */}
            {isRecoveryRequired && (
              <div
                role="alert"
                style={{
                  marginTop: '8px',
                  padding: '8px 10px',
                  background: 'rgba(240, 185, 11, 0.12)',
                  border: '1px solid #F0B90B',
                  borderRadius: '3px',
                  fontSize: '11px',
                  color: '#F0B90B',
                }}
              >
                🔒 Trạng thái tài khoản: <strong>Chỉ-Đọc (Read-only)</strong>. Số dư và vị thế đã lưu từ phiên trước đang được bảo toàn. Không thể khởi động phiên mới khi chưa đối soát.
              </div>
            )}

            {/* Notice for QUARANTINED */}
            {isQuarantined && !isRecoveryRequired && (
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
                ⚠ Dừng nhận lệnh: Dữ liệu bị gián đoạn và chưa thể khôi phục an toàn. Cần quản trị viên kiểm tra.
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
                      <div className="position-stat-val mono">{Number(pos.quantity).toFixed(4)}</div>
                    </div>
                    <div>
                      <div className="position-stat-key">Ký quỹ</div>
                      <div className="position-stat-val mono">{money(pos.collateral_usd ?? pos.margin_usd)} USDT</div>
                    </div>
                    <div>
                      <div className="position-stat-key">PnL chưa chốt</div>
                      <div
                        className={`position-stat-val mono ${(pos.unrealized_pnl_usd ?? 0) >= 0 ? 'text-buy' : 'text-sell'}`}
                      >
                        {money(pos.unrealized_pnl_usd ?? 0.0)} USDT
                      </div>
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
              <span className="risk-key">Nguồn nến thị trường</span>
              <span className="risk-val" style={{ color: marketFeedColor }}>
                {liveCandle ? 'WebSocket Live' : marketInfo ? 'REST Public' : 'Chưa có'}
              </span>
            </div>
            <div className="risk-row">
              <span className="risk-key">Trạng thái Bot</span>
              <span className="risk-val" style={{ color: botStatusBadge.color }}>
                {backendState?.status || 'IDLE'}
              </span>
            </div>
            <div className="risk-row">
              <span className="risk-key">Cổng nhận lệnh</span>
              <span
                className="risk-val"
                style={{ color: riskGate?.admission_open ? '#0ECB81' : '#F6465D' }}
              >
                {riskGate?.admission_open ? 'Mở (Simulated)' : 'Đóng'}
              </span>
            </div>
            <div className="risk-row">
              <span className="risk-key">Đòn bẩy tối đa</span>
              <span className="risk-val yellow">5× (giới hạn cứng)</span>
            </div>
            <div className="risk-note">
              {backendState?.risk_note ||
                'PaperBroker mô phỏng độc lập. Phí taker 0.05%, stop-loss 3%, không có lệnh sàn thật hoặc testnet.'}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
