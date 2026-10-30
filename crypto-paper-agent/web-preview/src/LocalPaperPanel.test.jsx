import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LocalPaperPanel } from './LocalPaperPanel'

const state = {
  api_version: 3, mode: 'PAPER_RESEARCH', status: 'IDLE', backend_busy: false,
  operator_intent: null, execution_mode: null, account_as_of_utc: null,
  account: { equity_usd: null, wallet_usd: null, available_margin_usd: null },
  recovery: { required: false, reconciled: false },
  risk_gate: { admission_open: false, reason: 'not initialized' },
  current_prices: { BTCUSDT: { price: null, valid: false } },
  funding_model: { kind: 'FIXED_SIMULATED' },
  research: { historical_verified: false, automatic_promotion_connected: false,
    promotion_block_reason: 'FIXED_SIMULATED_FUNDING_IS_DIAGNOSTIC_ONLY' },
  open_positions: [], trades: [], pending_orders: [],
}
const chart = { symbol: 'BTCUSDT', interval: '1m', source_time_utc: '2026-10-30T00:01:00+00:00',
  candles: [{ time_utc: '2026-10-30T00:00:00+00:00', open: 100, high: 102, low: 99, close: 101 }] }
const response = (data, ok = true) => ({ ok, json: async () => structuredClone(data) })

afterEach(() => vi.unstubAllGlobals())

function mockRead(payload = state, candles = chart) {
  const fetcher = vi.fn(async (url) => response(url.startsWith('/api/chart') ? candles : payload))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

describe('opt-in local PAPER runtime', () => {
  it('does no market/API request or implicit start when the preview mounts', () => {
    const fetcher = mockRead()
    render(<LocalPaperPanel />)
    expect(fetcher).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Connect local PAPER view' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Start PAPER' })).not.toBeInTheDocument()
  })

  it('reads v3 state and closed candles with their source time without inventing account values', async () => {
    const fetcher = mockRead()
    render(<LocalPaperPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Connect local PAPER view' }))
    await screen.findByText('IDLE')
    expect(fetcher).toHaveBeenCalledWith('/api/state', expect.objectContaining({ method: 'GET' }))
    expect(fetcher).toHaveBeenCalledWith('/api/chart?symbol=BTCUSDT&interval=1m', expect.objectContaining({ method: 'GET' }))
    expect(fetcher.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true)
    expect(screen.getByText(/Chart source UTC: 2026-10-30T00:01/)).toBeInTheDocument()
    expect(within(screen.getByLabelText('PAPER account')).getAllByText('Unknown')).toHaveLength(3)
    expect(screen.getByText('FIXED_SIMULATED')).toBeInTheDocument()
    expect(screen.getByText(/Historical evidence: NOT_VERIFIED/)).toBeInTheDocument()
    expect(screen.getByText(/Automatic promotion: blocked/)).toBeInTheDocument()
    expect(screen.getByText(/No current public price/)).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Closed BTCUSDT 1m candles' })).toHaveTextContent('101.00')
  })

  it('does not claim a requested operation succeeded before a confirmed backend response', async () => {
    const fetcher = mockRead()
    render(<LocalPaperPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Connect local PAPER view' }))
    await screen.findByText('IDLE')
    let complete
    fetcher.mockImplementationOnce(() => new Promise((resolve) => { complete = resolve }))
    fireEvent.click(screen.getByRole('button', { name: 'Start PAPER' }))
    expect(screen.getByText('IDLE')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start PAPER' })).toBeDisabled()
    complete(response({ ...state, status: 'WAITING_SYNC', operator_intent: 'RUNNING' }))
    await screen.findByText('WAITING_SYNC')
    expect(fetcher).toHaveBeenLastCalledWith('/api/start', expect.objectContaining({ method: 'POST' }))
    expect(screen.getByText(/Operator intent: RUNNING/)).toBeInTheDocument()
  })

  it('fails closed on provisional or malformed candles from the closed-only endpoint', async () => {
    mockRead(state, { ...chart, candles: [{ ...chart.candles[0], provisional: true }] })
    render(<LocalPaperPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Connect local PAPER view' }))
    await screen.findByRole('alert')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start PAPER' })).toBeEnabled()
    expect(screen.getByText('IDLE')).toBeInTheDocument()
  })

  it.each(['Pause', 'Resume', 'Stop'])('can request durable %s while the backend writer is busy', async (action) => {
    const fetcher = mockRead({ ...state, status: 'SCANNING', operator_intent: 'RUNNING', backend_busy: true })
    render(<LocalPaperPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Connect local PAPER view' }))
    await screen.findByText('SCANNING')
    expect(screen.getByRole('button', { name: 'Start PAPER' })).toBeDisabled()
    const button = screen.getByRole('button', { name: `${action} PAPER` })
    expect(button).toBeEnabled()
    const next = { ...state, status: 'SCANNING', backend_busy: true, operator_intent: 'RUNNING',
      operation: { name: action.toLowerCase(), status: 'PENDING' } }
    fetcher.mockResolvedValueOnce(response(next))
    fireEvent.click(button)
    await screen.findByText(`Operation: ${action.toLowerCase()} · PENDING`)
    expect(fetcher).toHaveBeenLastCalledWith(`/api/${action.toLowerCase()}`, expect.objectContaining({ method: 'POST' }))
    expect(screen.getByText('SCANNING')).toBeInTheDocument()
    expect(within(screen.getByLabelText('PAPER account')).getAllByText('Unknown')).toHaveLength(3)
  })

  it('keeps account controls usable when the independent public chart fails', async () => {
    const fetcher = mockRead({ ...state, status: 'SCANNING', operator_intent: 'RUNNING' })
    fetcher.mockImplementation(async (url) => url.startsWith('/api/chart')
      ? response({ error: 'public chart unavailable' }, false)
      : response({ ...state, status: 'SCANNING', operator_intent: 'RUNNING' }))
    render(<LocalPaperPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Connect local PAPER view' }))
    await screen.findByText(/public chart unavailable/)
    expect(screen.getByText('SCANNING')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pause PAPER' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Stop PAPER' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Stop PAPER' }))
    await waitFor(() => expect(fetcher).toHaveBeenLastCalledWith('/api/stop', expect.objectContaining({ method: 'POST' })))
  })

  it('publishes account state and accepts Stop without waiting for a hanging chart request', async () => {
    const fetcher = vi.fn(async (url) => url.startsWith('/api/chart')
      ? new Promise(() => {})
      : response({ ...state, status: url === '/api/stop' ? 'STOPPING' : 'SCANNING', operator_intent: 'RUNNING' }))
    vi.stubGlobal('fetch', fetcher)
    render(<LocalPaperPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Connect local PAPER view' }))
    await screen.findByText('SCANNING')
    expect(screen.getByRole('button', { name: 'Stop PAPER' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Stop PAPER' }))
    await screen.findByText('STOPPING')
    expect(fetcher).toHaveBeenLastCalledWith('/api/stop', expect.objectContaining({ method: 'POST' }))
    expect(screen.getByText('Loading public chart…')).toBeInTheDocument()
  })

  it('retains the last confirmed state but disables actions after a failed operation', async () => {
    const fetcher = mockRead({ ...state, status: 'SCANNING', operator_intent: 'RUNNING' })
    render(<LocalPaperPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Connect local PAPER view' }))
    await screen.findByText('SCANNING')
    fetcher.mockResolvedValueOnce(response({ error: 'reconciliation unavailable' }, false))
    fireEvent.click(screen.getByRole('button', { name: 'Pause PAPER' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('reconciliation unavailable'))
    expect(screen.getByText('SCANNING')).toBeInTheDocument()
    expect(screen.getByText(/Last confirmed snapshot; refresh required/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop PAPER' })).toBeDisabled()
  })
})
