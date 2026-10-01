import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, it, expect, vi } from 'vitest'
import { App } from './App'

afterEach(() => vi.unstubAllGlobals())

function feed(state) {
  vi.stubGlobal('WebSocket', class { close() {} })
  vi.stubGlobal('fetch', vi.fn(async (url) => ({ ok: true, status: url === '/api/stop' ? 202 : 200,
    json: async () => url.startsWith('/api/chart') ? { candles: [] } :
      url === '/api/stop' ? { ...state, status: 'STOPPING', operator_intent: 'STOPPING',
        operation: { id: 'control-7', name: 'stop', status: 'PENDING' } } : state })))
}

it('renders actual recipe, fixed funding, replay and total allocations without treating stale price as current', async () => {
  feed({ api_version: 3, status: 'SCANNING', operator_intent: 'RUNNING', execution_mode: 'REPLAY',
    strategy: 'breakout_retest', recipe: { strategy_id: 'breakout_retest' }, trial_id: 'trial-0002',
    funding_model: { kind: 'FIXED_SIMULATED', rate: .0001, display_hours: [7,15,23] },
    trials: { total_capital_injected_usd: 20000, trials: [{ trial_id: 'trial-0001', status: 'FAILED', final_equity_usd: 4900 },
      { trial_id: 'trial-0002', status: 'ACTIVE', current_equity_usd: 10000, target_reached: false }] },
    replay: { remaining_batches: 30 }, risk_gate: { admission_open: false },
    current_prices: { BTCUSDT: { price: null, valid: false } },
    markets: { BTCUSDT: { last_closed_15m_price: 99123, as_of_utc: new Date().toISOString() } },
    source_time_utc: new Date().toISOString() })
  render(<App />)
  await waitFor(() => expect(screen.getByText('trial-0002')).toBeInTheDocument())
  expect(screen.getByText('20,000.00 USDT')).toBeInTheDocument()
  expect(screen.getByText(/0.01%.*07.*15.*23/)).toBeInTheDocument()
  expect(screen.getByText(/REPLAY.*30/)).toBeInTheDocument()
  expect(screen.queryByText(/99,123/)).not.toBeInTheDocument()
  expect(screen.getByText(/trial-0001.*FAILED.*4,900/)).toBeInTheDocument()
})

it('accepts asynchronous stop without declaring the account flat or reporting a refusal', async () => {
  feed({ api_version: 3, status: 'SCANNING', operator_intent: 'RUNNING',
    strategy: 'trend_following', source_time_utc: new Date().toISOString(), risk_gate: { admission_open: false } })
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Dừng bot mô phỏng' })).not.toBeDisabled())
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Dừng bot mô phỏng' })))
  expect(screen.queryByText(/Server chưa xác nhận/)).not.toBeInTheDocument()
  expect(screen.getByText(/STOPPING.*đối soát/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Dừng bot mô phỏng' })).toBeDisabled()
})
