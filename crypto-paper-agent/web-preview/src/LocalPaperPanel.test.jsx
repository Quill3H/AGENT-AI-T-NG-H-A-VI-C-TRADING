import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LocalPaperPanel } from './LocalPaperPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('local prospective paper terminal', () => {
  it('starts the loopback paper session and shows an honest zero-trade ledger', async () => {
    const payload = {
      mode: 'PAPER_RESEARCH', status: 'SCANNING', error: null,
      session_id: 'session-1', symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
      venue: 'Binance USD-M perpetual public data', strategy: 'Trend Following 4h/15m fixed rules',
      source_time_utc: '2026-09-27T04:01:00+00:00', received_at_utc: '2026-09-27T04:01:01+00:00',
      last_processed_open_utc: null, config_sha256: 'abc123',
      chart: [{ time_utc: '2026-09-27T04:00:00+00:00', open: 100, high: 102, low: 99, close: 101, provisional: true }],
      markets: {
        BTCUSDT: { last_closed_15m_price: 101, as_of_utc: '2026-09-27T04:00:00+00:00' },
        ETHUSDT: { last_closed_15m_price: 2500, as_of_utc: '2026-09-27T04:00:00+00:00' },
        SOLUSDT: { last_closed_15m_price: 150, as_of_utc: '2026-09-27T04:00:00+00:00' },
      },
      account: { initial_equity_usd: 10000, wallet_usd: 10000, equity_usd: 10000, available_margin_usd: 10000, breaker_locked: false },
      open_positions: [], completed_trades: 0, trades: [], orders: [],
      risk_note: 'ETH/SOL simulated brackets',
    }
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => payload })
    vi.stubGlobal('fetch', fetcher)
    render(<LocalPaperPanel />)
    await waitFor(() => expect(screen.getByText('Đang quét BTC · ETH · SOL')).toBeInTheDocument())
    expect(fetcher).toHaveBeenCalledWith('/api/start', expect.objectContaining({ method: 'POST' }))
    expect(screen.getByText('Chưa có lệnh hoàn tất')).toBeInTheDocument()
    expect(screen.getByText(/Nến 1m đang hình thành/)).toBeInTheDocument()
    expect(screen.getByText(/2026-09-27T04:01:00/)).toBeInTheDocument()
    expect(screen.getByText('2,500.00')).toBeInTheDocument()
    expect(screen.queryByText(/lãi đảm bảo|bot sinh lời/)).not.toBeInTheDocument()
  })

  it('reports an unavailable local source without inventing a price or trade', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: 'market unavailable' }) }))
    render(<LocalPaperPanel />)
    await waitFor(() => expect(screen.getByText(/market unavailable/)).toBeInTheDocument())
    expect(screen.getByText('Chưa có lệnh hoàn tất')).toBeInTheDocument()
    expect(screen.queryByText('0.00 USDT PnL')).not.toBeInTheDocument()
  })
})
