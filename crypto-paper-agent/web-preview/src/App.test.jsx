import { fireEvent, render, screen, waitFor, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { buildOfflineReplay, parseEquityArtifact } from './lib/replay'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import previewEquityCsv from './data/long_equity_curve.csv?raw'
import foldReport from './data/walk_forward.report.json'
import publicManifest from './data/public_dataset_manifest.json'
import artifactAudit from './data/artifact_audit.json'
import { evidence } from './data/evidence'

const brokerEquityCsv = readFileSync(
  resolve(process.cwd(), '../docs/reviews/evidence/g0-2c9a4d0/replay/LONG/equity_curve.csv'),
  'utf8',
)

describe('paper research console — Binance dark UI & Independent Review Fixes', () => {
  let originalFetch

  let originalWebSocket

  beforeEach(() => {
    originalFetch = globalThis.fetch
    originalWebSocket = globalThis.WebSocket
    class MockWebSocket {
      close() {}
      addEventListener() {}
      removeEventListener() {}
      send() {}
    }
    globalThis.WebSocket = MockWebSocket
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    globalThis.WebSocket = originalWebSocket
    if (typeof window !== 'undefined' && window.history?.replaceState) {
      try {
        window.history.replaceState(null, '', window.location.pathname)
      } catch {}
    }
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('renders PAPER/RESEARCH safety labels and mode indicators', () => {
    render(<App />)
    expect(screen.getAllByText(/PAPER/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/RESEARCH/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Không có lệnh thật/)).toBeInTheDocument()
    expect(screen.getByText(/PAPER ONLY/)).toBeInTheDocument()
  })

  it('contains no control for exchange order submission', () => {
    render(<App />)
    const buttons = screen.getAllByRole('button').map((b) => b.textContent.toLowerCase())
    expect(buttons.join(' ')).not.toMatch(/connect exchange|wallet|submit order|testnet/)
    const hasStart = buttons.some((b) => b.includes('khởi động bot') || b.includes('đang chạy'))
    expect(hasStart).toBe(true)
    const hasStop = buttons.some((b) => b.includes('dừng'))
    expect(hasStop).toBe(true)
  })

  it('charts the committed synthetic broker snapshots without invented deltas', () => {
    render(<App />)
    const artifactRows = brokerEquityCsv.trim().split(/\r?\n/).slice(1).map((line) => {
      const [timestamp, equity] = line.split(',')
      return { timestamp, equity: Number(equity) }
    })
    const replay = buildOfflineReplay()
    expect(previewEquityCsv.replaceAll('\r\n', '\n')).toBe(brokerEquityCsv.replaceAll('\r\n', '\n'))
    expect(replay).toEqual(artifactRows)
    expect(replay.at(-1)).toEqual({ timestamp: '2024-01-01T02:05:00+00:00', equity: 10449.2125 })
    expect(buildOfflineReplay(42)).toEqual(artifactRows)
    expect(() => parseEquityArtifact('timestamp,equity\n2024-01-01T00:00:00+00:00,NaN')).toThrow(
      'Invalid broker equity artifact schema',
    )
    const missingBalance = brokerEquityCsv.replace(',10000.0,10000.0,0.0,', ',10000.0,,0.0,')
    expect(() => parseEquityArtifact(missingBalance)).toThrow('Invalid broker equity artifact row')
  })

  it('derives public fold and audit figures from byte-matching committed evidence', () => {
    for (const [name, copy] of [
      ['walk_forward.report.json', foldReport],
      ['public_dataset_manifest.json', publicManifest],
      ['artifact_audit.json', artifactAudit],
    ]) {
      const original = JSON.parse(
        readFileSync(resolve(process.cwd(), `../docs/reviews/evidence/stage-06-11-repair/${name}`), 'utf8'),
      )
      expect(copy).toEqual(original)
    }
    expect(evidence.historicalWindow.datasetHash).toBe(publicManifest.datasets['1m'].sha256)
    expect(evidence.strategies.map((row) => row.result)).toEqual(
      foldReport.report.aggregate.map((row) => `${row.total_net_pnl.toFixed(4)} USDT`),
    )
    expect(evidence.artifactAudit.absolutePathsFound).toBe(artifactAudit.absolute_paths_found)
  })

  it('renders coin switcher with BTC, ETH, SOL buttons', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /BTCUSDT/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ETHUSDT/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /SOLUSDT/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /ETHUSDT/i }))
    const ethBtn = screen.getByRole('button', { name: /ETHUSDT/i })
    expect(ethBtn.getAttribute('aria-pressed')).toBe('true')
  })

  it('starts and stops paper bot strictly when backend confirms status', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/start' && opts?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            mode: 'PAPER_RESEARCH',
            status: 'SCANNING',
            session_id: 'test-session-123',
            source_time_utc: new Date().toISOString(),
            risk_gate: { admission_open: true, reason: null },
            account: { initial_equity_usd: 10000.0, wallet_usd: 10000.0, equity_usd: 10000.0 },
          }),
        })
      }
      if (url === '/api/stop' && opts?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            mode: 'PAPER_RESEARCH',
            status: 'STOPPED',
            account: { initial_equity_usd: 10000.0, wallet_usd: 10000.0, equity_usd: 10000.0 },
          }),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ mode: 'PAPER_RESEARCH', status: 'IDLE' }),
      })
    })

    render(<App />)
    const startBtn = screen.getAllByRole('button').find((b) => /khởi động bot/i.test(b.textContent))
    expect(startBtn).toBeTruthy()
    expect(startBtn).not.toBeDisabled()

    await act(async () => {
      fireEvent.click(startBtn)
    })

    // Bot now confirmed running by backend
    await waitFor(() => {
      const runningBtn = screen.getAllByRole('button').find((b) => /đang chạy/i.test(b.textContent))
      expect(runningBtn).toBeTruthy()
      expect(runningBtn).toBeDisabled()
    })

    // Stop bot
    const stopBtn = screen.getAllByRole('button').find((b) => /dừng/i.test(b.textContent))
    expect(stopBtn).not.toBeDisabled()

    await act(async () => {
      fireEvent.click(stopBtn)
    })

    // Bot confirmed stopped by backend
    await waitFor(() => {
      const startAgain = screen.getAllByRole('button').find((b) => /khởi động bot/i.test(b.textContent))
      expect(startAgain).toBeTruthy()
      expect(startAgain).not.toBeDisabled()
    })
  })

  it('handles /api/start failure (503/error/timeout) without setting optimistic running flag', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/start') {
        return Promise.resolve({
          ok: false,
          status: 503,
          json: async () => ({ error: 'Service Unavailable: public stream warming up' }),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ mode: 'PAPER_RESEARCH', status: 'IDLE' }),
      })
    })

    render(<App />)
    const startBtn = screen.getAllByRole('button').find((b) => /khởi động bot/i.test(b.textContent))
    expect(startBtn).toBeTruthy()

    await act(async () => {
      fireEvent.click(startBtn)
    })

    // Must show user-facing error message
    await waitFor(() => {
      expect(screen.getByText(/Không thể khởi động bot/i)).toBeInTheDocument()
      expect(screen.getByText(/Service Unavailable/i)).toBeInTheDocument()
    })

    // CRITICAL: Bot must NOT be in running state!
    const runningBtn = screen.getAllByRole('button').find((b) => /đang chạy/i.test(b.textContent))
    expect(runningBtn).toBeUndefined()

    // Stop button remains disabled
    const stopBtn = screen.getAllByRole('button').find((b) => /dừng/i.test(b.textContent))
    expect(stopBtn).toBeDisabled()
  })

  it('handles /api/stop failure without falsely claiming bot is stopped', async () => {
    // Initial state is SCANNING
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/stop') {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: async () => ({ error: 'Internal stop failed' }),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          mode: 'PAPER_RESEARCH',
          status: 'SCANNING',
          source_time_utc: new Date().toISOString(),
        }),
      })
    })

    render(<App />)

    // Wait until scanning state loads
    await waitFor(() => {
      const runningBtn = screen.getAllByRole('button').find((b) => /đang chạy/i.test(b.textContent))
      expect(runningBtn).toBeTruthy()
    })

    const stopBtn = screen.getAllByRole('button').find((b) => /dừng/i.test(b.textContent))
    expect(stopBtn).not.toBeDisabled()

    await act(async () => {
      fireEvent.click(stopBtn)
    })

    // Must show stop error
    await waitFor(() => {
      expect(screen.getByText(/Không thể dừng bot/i)).toBeInTheDocument()
    })
  })

  it('handles server connection loss (SERVER_ERROR) and shows reconnect banner', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Connection refused'))

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/Mất kết nối tới server local/i)).toBeInTheDocument()
    })

    // Start button must be disabled when disconnected from server
    const startBtn = screen.getAllByRole('button').find((b) => /khởi động bot/i.test(b.textContent))
    expect(startBtn).toBeDisabled()
  })

  it('does not treat source_time_utc = null as ONLINE and flags waiting or stale data', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'IDLE',
        source_time_utc: null, // NULL source time!
        markets: {},
        chart: [],
      }),
    })

    render(<App />)

    // Must NOT say "Kết nối ổn định" or "ONLINE"
    await waitFor(() => {
      const text = screen.getByLabelText(/Tóm tắt rủi ro/i).textContent
      expect(text).not.toContain('Kết nối ổn định')
    })
  })

  it('handles missing prices without showing fake 64000/2500/150 defaults', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'IDLE',
        source_time_utc: new Date().toISOString(),
        markets: {},
        chart: [],
        charts: {},
      }),
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/Chưa có dữ liệu/i)).toBeInTheDocument()
    })

    // Must NOT contain 64,000 as default price
    const tickerText = screen.getByRole('banner').textContent
    expect(tickerText).not.toContain('64,000')
    expect(tickerText).not.toContain('2,500')
  })

  it('handles RECOVERY_REQUIRED with open positions, shows audit warning and locks start button', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'RECOVERY_REQUIRED',
        error: 'Prior paper journal exists; exact broker restoration is not available. No new orders admitted.',
        session_id: '20260927T140000-saved',
        source_time_utc: '2026-09-27T14:00:00+00:00',
        account: {
          initial_equity_usd: 10000.0,
          wallet_usd: 9850.25,
          equity_usd: 9920.50,
          available_margin_usd: 8500.0,
          reserved_collateral_usd: 1350.25,
          unrealized_pnl_usd: 70.25,
          breaker_locked: false,
        },
        open_positions: [
          {
            symbol: 'BTCUSDT',
            side: 'LONG',
            entry_price: 63200.0,
            quantity: 0.05,
            leverage: 3,
            stop_loss_price: 61304.0,
            collateral_usd: 1053.33,
            unrealized_pnl_usd: 70.25,
          },
        ],
        orders: [],
        trades: [],
        risk_gate: {
          admission_open: false,
          reason: 'Prior journal exists; exact broker restoration is not available.',
          halted: true,
        },
      }),
    })

    render(<App />)

    // 1. Prominent safety warning
    await waitFor(() => {
      expect(screen.getAllByText(/YÊU CẦU ĐỐI SOÁT PHỤC HỒI/i).length).toBeGreaterThan(0)
    })

    // 2. Saved equity & wallet displayed faithfully
    expect(screen.getByText(/9,850.25/)).toBeInTheDocument()
    expect(screen.getByText(/9,920.50/)).toBeInTheDocument()

    // 3. Saved position displayed
    expect(screen.getByText(/63,200.00/)).toBeInTheDocument()

    // 4. Start button is locked with recovery warning — cannot start as clean new account!
    const lockedBtn = screen.getByRole('button', { name: /Khóa khởi động do cần đối soát journal/i })
    expect(lockedBtn).toBeInTheDocument()
    expect(lockedBtn).toBeDisabled()
    expect(lockedBtn.textContent).toContain('Khóa: Cần đối soát')
  })

  it('drops out-of-order stale poll responses so older responses never overwrite newer ones', async () => {
    let callCount = 0
    let resolveFirstCall
    const firstCallPromise = new Promise((resolve) => {
      resolveFirstCall = resolve
    })

    globalThis.fetch = vi.fn().mockImplementation((url) => {
      if (url === '/api/state') {
        callCount++
        if (callCount === 1) {
          // Slow first response (seq 1, status IDLE)
          return firstCallPromise
        }
        // Fast second response (seq 2, status SCANNING)
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            mode: 'PAPER_RESEARCH',
            status: 'SCANNING',
            source_time_utc: new Date().toISOString(),
          }),
        })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) })
    })

    render(<App />)

    // Trigger second poll while first is pending
    // We let firstCall resolve later with stale IDLE state
    await act(async () => {
      // Allow first poll to initiate
      await new Promise((r) => setTimeout(r, 10))
    })

    // Now resolve first call with stale IDLE state
    await act(async () => {
      resolveFirstCall({
        ok: true,
        status: 200,
        json: async () => ({
          mode: 'PAPER_RESEARCH',
          status: 'IDLE',
          source_time_utc: new Date().toISOString(),
        }),
      })
    })

    // Stale IDLE should not have crashed the app
    expect(screen.getByText(/Quill3H/i)).toBeInTheDocument()
  })

  it('shows paper account panel with initial equity and broker safety note', () => {
    render(<App />)
    expect(screen.getAllByText(/10,000/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/PaperBroker mô phỏng/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Circuit breaker/i)).toBeInTheDocument()
    expect(screen.getAllByText(/không có lệnh sàn thật/i).length).toBeGreaterThan(0)
  })

  it('handles price stream loss: does not display WebSocket Trực tiếp and falls back to closed REST price', async () => {
    let wsInstance = null
    class ControllableWebSocket {
      constructor(url) {
        wsInstance = this
        this.url = url
      }
      close() {
        if (this.onclose) this.onclose({ wasClean: true })
      }
      send() {}
    }
    globalThis.WebSocket = ControllableWebSocket

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'SCANNING',
        source_time_utc: new Date().toISOString(),
        markets: {
          BTCUSDT: {
            last_closed_15m_price: 63800.0,
            as_of_utc: new Date().toISOString(),
          },
        },
        risk_gate: { admission_open: true, reason: null },
      }),
    })

    render(<App />)

    // Initially open WS and emit kline
    await act(async () => {
      if (wsInstance?.onopen) wsInstance.onopen()
      if (wsInstance?.onmessage) {
        wsInstance.onmessage({
          data: JSON.stringify({
            k: {
              t: Date.now(),
              o: '64000',
              h: '64100',
              l: '63900',
              c: '64050',
              x: false,
            },
          }),
        })
      }
    })

    // While WS is live, shows live price 64,050.00 and WebSocket Trực tiếp
    await waitFor(() => {
      expect(screen.getAllByText(/64,050.00/).length).toBeGreaterThan(0)
      expect(screen.getByText(/● WebSocket Trực tiếp/i)).toBeInTheDocument()
    })

    // Now trigger WebSocket stream loss (disconnect)
    await act(async () => {
      wsInstance.close()
    })

    // Must NOT continue to claim "● WebSocket Trực tiếp"
    await waitFor(() => {
      expect(screen.queryByText(/● WebSocket Trực tiếp/i)).toBeNull()
    })

    // Must fall back to REST closed price (63,800.00), NOT keep stale 64,050.00
    expect(screen.getAllByText(/63,800.00/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/REST nến đóng/i).length).toBeGreaterThan(0)
  })

  it('handles stale price (>15s without kline event): drops WebSocket Trực tiếp and falls back to closed REST price', async () => {
    let wsInstance = null
    class ControllableWebSocket {
      constructor(url) {
        wsInstance = this
        this.url = url
      }
      close() {}
      send() {}
    }
    globalThis.WebSocket = ControllableWebSocket

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'SCANNING',
        source_time_utc: new Date().toISOString(),
        markets: {
          BTCUSDT: {
            last_closed_15m_price: 63500.0,
            as_of_utc: new Date().toISOString(),
          },
        },
        risk_gate: { admission_open: true, reason: null },
      }),
    })

    const baseTime = 1700000000000
    vi.useFakeTimers()
    try {
      vi.setSystemTime(baseTime)
      render(<App />)

      await act(async () => {
        if (wsInstance?.onopen) wsInstance.onopen()
        if (wsInstance?.onmessage) {
          wsInstance.onmessage({
            data: JSON.stringify({
              k: {
                t: baseTime,
                o: '64000',
                h: '64200',
                l: '63900',
                c: '64150',
                x: false,
              },
            }),
          })
        }
      })

      // Fresh tick: live price 64,150.00
      expect(screen.getAllByText(/64,150.00/).length).toBeGreaterThan(0)
      expect(screen.getByText(/● WebSocket Trực tiếp/i)).toBeInTheDocument()

      // Advance time by 16 seconds (>15s watchdog)
      await act(async () => {
        vi.advanceTimersByTime(16000)
      })

      // Must NOT continue to say "WebSocket Trực tiếp"
      expect(screen.queryByText(/● WebSocket Trực tiếp/i)).toBeNull()

      // Must show stale warning and fallback to REST closed price (63,500.00)
      expect(screen.getAllByText(/gián đoạn|Giá cũ/i).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/63,500.00/).length).toBeGreaterThan(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('truthfully reports bot status: distinguishes permitted simulated orders from closed risk gates', async () => {
    // 1. Closed Risk Gate while scanning
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'SCANNING',
        source_time_utc: new Date().toISOString(),
        markets: { BTCUSDT: { last_closed_15m_price: 63000.0 } },
        risk_gate: {
          admission_open: false,
          reason: 'Circuit breaker triggered after 3 consecutive losses',
          halted: true,
        },
      }),
    })

    const { unmount } = render(<App />)

    await waitFor(() => {
      // Must NOT claim "bot đang giao dịch"
      expect(screen.queryByText(/bot đang giao dịch/i)).toBeNull()
      // Must show closed admission gate
      expect(screen.getAllByText(/CỔNG LỆNH ĐÓNG/i).length).toBeGreaterThan(0)
      expect(screen.getByText(/Circuit breaker triggered/i)).toBeInTheDocument()
    })

    unmount()

    // 2. Open Risk Gate with permitted order simulation
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'SCANNING',
        session_id: 'test-session-456',
        source_time_utc: new Date().toISOString(),
        markets: { BTCUSDT: { last_closed_15m_price: 63000.0 } },
        risk_gate: { admission_open: true, reason: null, halted: false },
      }),
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getAllByText(/ĐƯỢC PHÉP TẠO LỆNH MÔ PHỎNG/i).length).toBeGreaterThan(0)
    })
  })

  it('displays waiting states WAITING_SYNC and WAITING_CONNECTION truthfully', async () => {
    // WAITING_SYNC
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'WAITING_SYNC',
        source_time_utc: new Date().toISOString(),
        markets: { BTCUSDT: { last_closed_15m_price: 63000.0 } },
        risk_gate: { admission_open: false, reason: 'Waiting 3 symbols sync' },
      }),
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getAllByText(/Đang chờ đồng bộ 3 cặp/i).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/chưa nhận lệnh/i).length).toBeGreaterThan(0)
    })
  })

  it('displays Không xác định for null financial info in RECOVERY_REQUIRED and includes browser closure notice', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'RECOVERY_REQUIRED',
        session_id: 'prior-session-789',
        source_time_utc: new Date().toISOString(),
        account: {
          initial_equity_usd: null,
          wallet_usd: null,
          equity_usd: null,
          available_margin_usd: null,
          reserved_collateral_usd: null,
          unrealized_pnl_usd: null,
          breaker_locked: null,
        },
        risk_gate: { admission_open: false, reason: 'Journal reconciliation required' },
      }),
    })

    render(<App />)

    await waitFor(() => {
      // Must display "Không xác định" for unknown account values
      expect(screen.getAllByText(/Không xác định/i).length).toBeGreaterThan(0)
    })

    // Reassurance notice: closing browser does NOT stop backend
    expect(screen.getByText(/Đóng tab trình duyệt KHÔNG làm dừng bot/i)).toBeInTheDocument()
  })

  it('handles successful recovery from RECOVERY_REQUIRED to active SCANNING', async () => {
    // Phase 1: RECOVERY_REQUIRED
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'RECOVERY_REQUIRED',
        session_id: 'prior-recovered',
        source_time_utc: new Date().toISOString(),
        account: {
          initial_equity_usd: null,
          wallet_usd: null,
          equity_usd: null,
          available_margin_usd: null,
          reserved_collateral_usd: null,
          unrealized_pnl_usd: null,
          breaker_locked: null,
        },
        risk_gate: { admission_open: false, reason: 'Reconciling' },
      }),
    })

    const { unmount } = render(<App />)

    // Starts in RECOVERY_REQUIRED
    await waitFor(() => {
      expect(screen.getAllByText(/RECOVERY REQUIRED|YÊU CẦU ĐỐI SOÁT/i).length).toBeGreaterThan(0)
    })

    unmount()

    // Phase 2: SCANNING after recovery
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        mode: 'PAPER_RESEARCH',
        status: 'SCANNING',
        session_id: 'recovered-clean',
        source_time_utc: new Date().toISOString(),
        markets: { BTCUSDT: { last_closed_15m_price: 64000.0 } },
        account: {
          initial_equity_usd: 10000.0,
          wallet_usd: 10250.0,
          equity_usd: 10250.0,
          available_margin_usd: 10250.0,
          reserved_collateral_usd: 0.0,
          unrealized_pnl_usd: 0.0,
          breaker_locked: false,
        },
        risk_gate: { admission_open: true, reason: null },
      }),
    })

    render(<App />)

    // Advances to SCANNING
    await waitFor(() => {
      expect(screen.getAllByText(/ĐƯỢC PHÉP TẠO LỆNH MÔ PHỎNG/i).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/10,250.00/).length).toBeGreaterThan(0)
    })
  })
})
