import { useEffect, useRef, useState } from 'react'

const amount = (value) => typeof value === 'number' && Number.isFinite(value)
  ? value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Unknown'

async function request(path, method = 'GET') {
  const response = await fetch(path, { method, cache: 'no-store' })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.error || 'Local PAPER service unavailable')
  return payload
}

function checkedState(payload) {
  if (payload?.api_version !== 3 || payload.mode !== 'PAPER_RESEARCH'
      || !payload.account || !payload.risk_gate || !payload.recovery) {
    throw new Error('Unsupported local PAPER state contract')
  }
  return payload
}

function checkedChart(payload) {
  const source = Date.parse(payload?.source_time_utc)
  if (payload?.symbol !== 'BTCUSDT' || payload.interval !== '1m'
      || !Number.isFinite(source) || !Array.isArray(payload.candles)
      || payload.candles.some((bar, index, bars) => bar.provisional === true
        || !Number.isFinite(Date.parse(bar.time_utc)) || Date.parse(bar.time_utc) + 60000 > source
        || (index > 0 && Date.parse(bar.time_utc) <= Date.parse(bars[index - 1].time_utc))
        || !['open', 'high', 'low', 'close'].every((key) => typeof bar[key] === 'number' && Number.isFinite(bar[key]) && bar[key] > 0)
        || bar.high < Math.max(bar.open, bar.close) || bar.low > Math.min(bar.open, bar.close))) {
    throw new Error('Invalid closed-only chart contract')
  }
  return payload
}

export function LocalPaperPanel() {
  const [state, setState] = useState(null)
  const [chart, setChart] = useState(null)
  const [error, setError] = useState(null)
  const [chartError, setChartError] = useState(null)
  const [chartLoading, setChartLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState(false)
  const pending = useRef(false)
  const chartPending = useRef(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  async function refreshChart() {
    if (chartPending.current) return
    chartPending.current = true
    setChartLoading(true)
    try {
      const candles = checkedChart(await request('/api/chart?symbol=BTCUSDT&interval=1m'))
      if (mounted.current) { setChart(candles); setChartError(null) }
    } catch (cause) {
      if (mounted.current) setChartError(cause.message)
    } finally {
      chartPending.current = false
      if (mounted.current) setChartLoading(false)
    }
  }

  async function refresh(action) {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    try {
      if (action) {
        const confirmed = checkedState(await request(`/api/${action}`, 'POST'))
        if (mounted.current) { setState(confirmed); setError(null) }
      } else {
        // Chart transport must never hold up account state or operator controls.
        void refreshChart()
        const next = checkedState(await request('/api/state'))
        if (mounted.current) {
          setState(next); setConnected(true); setError(null)
        }
      }
    } catch (cause) {
      if (mounted.current) setError(cause.message)
    } finally {
      pending.current = false
      if (mounted.current) setBusy(false)
    }
  }

  useEffect(() => {
    if (!connected) return undefined
    const timer = window.setInterval(() => refresh(), 5000)
    return () => window.clearInterval(timer)
  }, [connected])

  const blocked = busy || !!error
  const current = state?.current_prices?.BTCUSDT
  const publicPrice = current?.valid === true && typeof current.price === 'number' && Number.isFinite(current.price)

  return <section className="section local-paper" aria-labelledby="local-paper-title">
    <div className="section-heading"><h2 id="local-paper-title">Local PAPER session</h2>
      <button type="button" disabled={busy} onClick={() => refresh()}>{connected ? 'Refresh local PAPER view' : 'Connect local PAPER view'}</button>
    </div>
    <p className="note">Connect reads the local backend and public chart only. Start, pause, resume and stop require explicit actions. No exchange orders. Simulated fills and funding do not establish profitability.</p>
    {error && <p role="alert">{error}{state && ' — Last confirmed snapshot; refresh required.'}</p>}
    {state && <>
      <p role="status">{state.status}</p>
      <p>Operator intent: {state.operator_intent || 'Unknown'} · Execution mode: {state.execution_mode || 'Unknown'}</p>
      {state.operation && <p>Operation: {state.operation.name} · {state.operation.status}{state.operation.error ? ` · ${state.operation.error}` : ''}</p>}
      <div className="local-paper-controls">
        <button type="button" disabled={blocked || state.backend_busy} onClick={() => refresh('start')}>Start PAPER</button>
        <button type="button" disabled={blocked} onClick={() => refresh('pause')}>Pause PAPER</button>
        <button type="button" disabled={blocked} onClick={() => refresh('resume')}>Resume PAPER</button>
        <button type="button" disabled={blocked} onClick={() => refresh('stop')}>Stop PAPER</button>
      </div>
      <dl className="local-paper-account" aria-label="PAPER account">
        <div><dt>Equity USDT</dt><dd>{amount(state.account.equity_usd)}</dd></div>
        <div><dt>Wallet USDT</dt><dd>{amount(state.account.wallet_usd)}</dd></div>
        <div><dt>Available margin USDT</dt><dd>{amount(state.account.available_margin_usd)}</dd></div>
      </dl>
      <p>Account valuation UTC: {state.account_as_of_utc || 'Unknown'} · Last reconciled closed 15m</p>
      <p>New-entry gate: {state.risk_gate.admission_open ? 'open' : 'closed'} · {state.risk_gate.reason || 'No reason reported'}</p>
      <p>Recovery: {state.recovery.required ? 'REQUIRED' : state.recovery.reconciled ? 'reconciled' : 'not reconciled'}</p>
      <p>Funding: <strong>{state.funding_model?.kind || 'Unknown'}</strong> · Historical evidence: {state.research?.historical_verified === true ? 'backend claim; independent review required' : 'NOT_VERIFIED'}</p>
      <p>Automatic promotion: {state.research?.automatic_promotion_connected === true ? 'backend-connected; independent review required' : 'blocked'} · {state.research?.promotion_block_reason || 'No evidence contract reported'}</p>
      <p>{publicPrice ? `Current public price (provisional; separate from account valuation): ${amount(current.price)}` : 'No current public price'}</p>
      <p>Open positions: {state.open_positions?.length ?? 'Unknown'} · Pending orders: {state.pending_orders?.length ?? 'Unknown'} · Recent realization records: {state.trades?.length ?? 'Unknown'}</p>
    </>}
    {chartLoading && <p>Loading public chart…</p>}
    {chartError && <p role="alert">Chart unavailable: {chartError}{chart && ' — Last confirmed candles; chart refresh required.'}</p>}
    {chart && <>
      <p>Chart source UTC: {chart.source_time_utc}</p>
      <div className="table-scroll"><table aria-label="Closed BTCUSDT 1m candles">
        <thead><tr><th>Open time UTC</th><th>Open</th><th>High</th><th>Low</th><th>Close</th></tr></thead>
        <tbody>{chart.candles.slice(-10).map((bar) => <tr key={bar.time_utc}><td>{bar.time_utc}</td>
          <td>{amount(bar.open)}</td><td>{amount(bar.high)}</td><td>{amount(bar.low)}</td><td>{amount(bar.close)}</td></tr>)}</tbody>
      </table></div>
    </>}
  </section>
}
