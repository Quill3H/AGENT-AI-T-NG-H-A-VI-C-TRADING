import { useEffect, useRef, useState } from 'react'
import { CandlestickSeries, createChart } from 'lightweight-charts'

const money = (value) => Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function MarketChart({ bars }) {
  const container = useRef(null)

  useEffect(() => {
    if (!container.current || !bars.length || typeof ResizeObserver === 'undefined') return undefined
    const chart = createChart(container.current, {
      width: container.current.clientWidth,
      height: 330,
      layout: { background: { color: '#ffffff' }, textColor: '#64748b' },
      grid: { vertLines: { color: '#edf1f5' }, horzLines: { color: '#edf1f5' } },
      rightPriceScale: { borderColor: '#e2e8f0' },
      timeScale: { borderColor: '#e2e8f0', timeVisible: true, secondsVisible: false },
    })
    chart.addSeries(CandlestickSeries, {
      upColor: '#0b9f76', downColor: '#dc5960',
      borderUpColor: '#0b9f76', borderDownColor: '#dc5960',
      wickUpColor: '#0b9f76', wickDownColor: '#dc5960',
    }).setData(bars.map((bar) => ({
      time: Math.floor(Date.parse(bar.time_utc) / 1000),
      open: bar.open, high: bar.high, low: bar.low, close: bar.close,
    })))
    chart.timeScale().fitContent()
    const observer = new ResizeObserver(() => chart.applyOptions({ width: container.current?.clientWidth || 300 }))
    observer.observe(container.current)
    return () => { observer.disconnect(); chart.remove() }
  }, [bars])

  return <div className="market-chart" ref={container} role="img" aria-label="Biểu đồ nến BTCUSDT từ dữ liệu Binance Futures công khai" />
}

async function request(path, method = 'GET') {
  const response = await fetch(path, { method, cache: 'no-store' })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.error || `Local service returned ${response.status}`)
  return payload
}

export function LocalPaperPanel() {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    request('/api/start', 'POST')
      .then((result) => { if (active) setState(result) })
      .catch((cause) => { if (active) setError(cause.message) })
    const interval = window.setInterval(() => {
      request('/api/state')
        .then((result) => { if (active) { setState(result); setError(null) } })
        .catch((cause) => { if (active) setError(cause.message) })
    }, 5000)
    return () => { active = false; window.clearInterval(interval) }
  }, [])

  async function stop() {
    setBusy(true)
    try {
      setState(await request('/api/stop', 'POST'))
      setError(null)
    } catch (cause) {
      setError(cause.message)
    } finally {
      setBusy(false)
    }
  }

  const bars = state?.chart || []
  const last = bars.at(-1)
  const scanning = ['SCANNING', 'WAITING_SYNC'].includes(state?.status)

  return (
    <section id="paper" className="paper-terminal" aria-labelledby="paper-title">
      <div className="paper-terminal-head">
        <div>
          <div className="paper-market-title"><span className="paper-symbol">BTCUSDT</span><span className="paper-perp">USD-M PERP · PUBLIC DATA</span></div>
          <h2 id="paper-title">Phiên quan sát & giao dịch mô phỏng</h2>
          <p>Trend Following cố định · tín hiệu 4h, khớp giả định tại nến 15m kế tiếp</p>
        </div>
        <div className="paper-terminal-actions">
          <span className={`paper-runtime ${state?.status === 'QUARANTINED' ? 'paper-runtime--error' : ''}`}>
            {state?.status === 'WAITING_SYNC' ? 'Đang chờ đồng bộ 3 mã' : scanning ? 'Đang quét BTC · ETH · SOL' : state?.status === 'STOPPED' ? 'Đã dừng phiên' : state?.status === 'QUARANTINED' ? 'Nguồn dữ liệu bị cách ly' : 'Đang kết nối local'}
          </span>
          {scanning && <button type="button" className="paper-stop" onClick={stop} disabled={busy}>Dừng mô phỏng</button>}
        </div>
      </div>

      {error && <p className="paper-error" role="alert">Không thể lấy dữ liệu: {error}</p>}
      {state?.error && <p className="paper-error" role="alert">Phiên dừng nhận lệnh: {state.error}</p>}

      <div className="paper-terminal-grid">
        <div className="paper-price-panel">
          <div className="paper-price-top">
            <div><strong>{last ? money(last.close) : '—'}</strong><span>USDT · {last?.provisional ? 'Nến 1m đang hình thành (không dùng làm tín hiệu)' : 'Nến 1m đã đóng'}</span></div>
            <span className="paper-source">Binance Futures public · 1m</span>
          </div>
          {bars.length ? <MarketChart bars={bars} /> : <div className="paper-chart-empty">Chờ dữ liệu BTC thực tế</div>}
          <div className="paper-chart-foot"><span>Giờ nguồn UTC: {state?.source_time_utc || '—'}</span><span>Nhận lúc UTC: {state?.received_at_utc || '—'}</span></div>
        </div>
        <aside className="paper-account" aria-label="Tài khoản mô phỏng">
          <h3>Tài khoản PAPER</h3>
          <dl>
            <div><dt>Equity</dt><dd>{state ? money(state.account.equity_usd) : '—'} USDT</dd></div>
            <div><dt>Wallet</dt><dd>{state ? money(state.account.wallet_usd) : '—'} USDT</dd></div>
            <div><dt>Margin khả dụng</dt><dd>{state ? money(state.account.available_margin_usd) : '—'} USDT</dd></div>
            <div><dt>Circuit breaker</dt><dd>{state?.account.breaker_locked ? 'ĐÃ KHÓA' : state ? 'Chưa khóa' : '—'}</dd></div>
          </dl>
          <div className="paper-watch">
            <h3>Đang theo dõi</h3>
            {['BTCUSDT', 'ETHUSDT', 'SOLUSDT'].map((symbol) => (
              <div className="paper-watch-row" key={symbol}>
                <span>{symbol}<small>15m closed</small></span>
                <strong>{state?.markets?.[symbol] ? money(state.markets[symbol].last_closed_15m_price) : '—'}</strong>
              </div>
            ))}
          </div>
          <p className="paper-account-note">Lệnh, phí, trượt giá và stop-loss do PaperBroker mô phỏng. Không có lệnh sàn thật hoặc testnet.</p>
        </aside>
      </div>

      <div className="paper-terminal-ledger">
        <div className="paper-ledger-head"><h3>Nhật ký giao dịch mô phỏng</h3><span>Phiên {state?.session_id || 'chưa khởi tạo'} · {state?.completed_trades ?? 0} hoàn tất</span></div>
        {state?.trades?.length ? (
          <div className="table-scroll"><table><thead><tr><th>Thời điểm đóng UTC</th><th>Mã</th><th>Hướng</th><th>Giá vào</th><th>Giá ra</th><th>Phí</th><th>Funding</th><th>Net PnL</th></tr></thead><tbody>
            {state.trades.map((trade) => <tr key={trade.id}><td>{trade.exit_time_utc}</td><td>{trade.symbol}</td><td>{trade.side}</td><td>{money(trade.entry_price)}</td><td>{money(trade.exit_price)}</td><td>{money(trade.fee_usd)}</td><td>{money(trade.funding_usd)}</td><td className={trade.net_pnl_usd < 0 ? 'paper-negative' : 'paper-positive'}>{money(trade.net_pnl_usd)}</td></tr>)}
          </tbody></table></div>
        ) : <p className="paper-empty">Chưa có lệnh hoàn tất</p>}
        <h4 className="paper-subhead">Vị thế đang mở</h4>
        {state?.open_positions?.length ? (
          <div className="table-scroll"><table><thead><tr><th>Mã</th><th>Hướng</th><th>Số lượng</th><th>Giá vào</th><th>Stop-loss</th><th>Thanh lý ước tính</th><th>Đòn bẩy</th></tr></thead><tbody>
            {state.open_positions.map((position) => <tr key={position.symbol}><td>{position.symbol}</td><td>{position.side}</td><td>{position.quantity}</td><td>{money(position.entry_price)}</td><td>{money(position.stop_loss_price)}</td><td>{money(position.liquidation_price)}</td><td>{position.leverage}×</td></tr>)}
          </tbody></table></div>
        ) : <p className="paper-empty">Không có vị thế đang mở</p>}
        {!!state?.orders?.length && <><h4 className="paper-subhead">Lệnh gần đây</h4><div className="table-scroll"><table><thead><tr><th>Mã</th><th>Hướng</th><th>Trạng thái</th><th>Lý do từ chối</th></tr></thead><tbody>
          {state.orders.map((order) => <tr key={order.id}><td>{order.symbol}</td><td>{order.side}</td><td>{order.status}</td><td>{order.rejection_reasons.join('; ') || '—'}</td></tr>)}
        </tbody></table></div></>}
        <div className="paper-ledger-meta"><span>Vị thế mở: {state?.open_positions.length ?? 0}</span><span>Đã xử lý nến 15m: {state?.last_processed_open_utc || 'chưa có nến mới sau khi mở trang'}</span><span>Config SHA-256: {state?.config_sha256?.slice(0, 16) || '—'}</span></div>
        <p className="paper-fidelity">{state?.risk_note || 'ETH/SOL dùng giả định maintenance margin bảo thủ, chưa xác minh theo tier hiện hành của sàn.'} Đây là quan sát tiến tới, không phải backtest hay bằng chứng sinh lời.</p>
      </div>
    </section>
  )
}
