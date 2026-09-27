import { useMemo, useState } from 'react'
import { evidence } from './data/evidence'
import { buildOfflineReplay, toPolyline } from './lib/replay'

function Status({ children, tone = 'neutral' }) {
  return <span className={`status status--${tone}`}>{children}</span>
}

function Header() {
  return (
    <header className="header">
      <div className="brand-block">
        <div className="mark" aria-hidden="true">Q</div>
        <div>
          <p className="product">Paper Research Console</p>
          <p className="mode">{evidence.mode} — NO LIVE ORDERS</p>
        </div>
      </div>
      <dl className="header-meta">
        <div><dt>2024 fold source</dt><dd>{evidence.source}</dd></div>
        <div><dt>2024 fold cutoff</dt><dd>{evidence.historicalWindow.cutoff}</dd></div>
        <div><dt>Evidence</dt><dd>{evidence.evidenceLevel}</dd></div>
      </dl>
    </header>
  )
}

function ReplayChart({ points }) {
  const line = useMemo(() => toPolyline(points), [points])
  return (
    <div className="chart-wrap">
      <svg className="chart" viewBox="0 0 680 230" role="img" aria-label="Archived synthetic PaperBroker equity chart">
        <defs>
          <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1687d9" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#1687d9" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 57.5, 115, 172.5, 230].map((y) => <line key={y} x1="0" y1={y} x2="680" y2={y} className="grid-line" />)}
        <polygon points={`0,230 ${line} 680,230`} fill="url(#chartFill)" />
        <polyline points={line} className="equity-line" />
      </svg>
      <div className="axis"><span>{points[0].timestamp}</span><span>Committed broker snapshots</span><span>{points.at(-1).timestamp}</span></div>
    </div>
  )
}

function FundingCoverage() {
  const readyPct = (evidence.fundingCoverage.exactReady / evidence.fundingCoverage.expected) * 100
  return (
    <section className="section funding" aria-labelledby="funding-title">
      <div className="section-heading">
        <div><p className="section-index">02</p><h2 id="funding-title">Funding coverage</h2></div>
        <Status tone="blocked">{evidence.fundingCoverage.status}</Status>
      </div>
      <div className="coverage-summary">
        <strong>{evidence.fundingCoverage.expected} expected boundaries</strong>
        <span>{evidence.fundingCoverage.start} → {evidence.fundingCoverage.end}</span>
      </div>
      <div className="coverage-bar" aria-label={`${evidence.fundingCoverage.exactReady} exact-ready and ${evidence.fundingCoverage.delayed} delayed or unready`}>
        <div className="coverage-ready" style={{ width: `${readyPct}%` }} />
        <div className="coverage-delayed" style={{ width: `${100 - readyPct}%` }} />
      </div>
      <div className="coverage-legend">
        <span><i className="dot dot--good" />{evidence.fundingCoverage.exactReady} exact-ready ({Math.round(readyPct)}%)</span>
        <span><i className="dot dot--warn" />{evidence.fundingCoverage.delayed} delayed 1–{evidence.fundingCoverage.maxDelayMs} ms / unready</span>
      </div>
      <p className="note">Delayed funding is never rounded backward. The seven-day basket replay stops before mutation when readiness is false.</p>
      <p className="note"><a href={evidence.fundingCoverage.sourceUrl}>G2 author diagnostic</a> · separate 2026 sample, not the 2024 fold below.</p>
    </section>
  )
}

function StrategyTable() {
  return (
    <section className="section" aria-labelledby="strategy-title">
      <div className="section-heading"><div><p className="section-index">03</p><h2 id="strategy-title">Strategy evidence</h2></div><Status>Independent review pending</Status></div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Strategy</th><th>Sample</th><th>Completed</th><th>Net result</th><th>State</th></tr></thead>
          <tbody>{evidence.strategies.map((row) => (
            <tr key={row.name}>
              <td><strong>{row.name}</strong></td><td>{row.sample}</td><td className="mono">{row.trades}</td><td className="mono">{row.result}</td>
              <td><Status tone={row.level === 'blocked' ? 'blocked' : 'neutral'}>{row.state}</Status></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="note"><a href={evidence.strategySourceUrl}>2024 walk-forward report</a> · four independent accounts, not a shared portfolio. Zero trades and one negative sample do not establish profitability.</p>
    </section>
  )
}

function AuditRail() {
  return (
    <aside className="rail" aria-label="Risk, accounting and artifact status">
      <section>
        <p className="section-index">04</p><h2>Risk & accounting</h2>
        <div className="control-list">{evidence.controls.map((control) => (
          <div className="control-row" key={control.label}><span>{control.label}</span><Status tone={control.tone}>{control.value}</Status></div>
        ))}</div>
        <p className="note">UI is read-only. No exchange client, wallet, API key, order endpoint or webhook is included.</p>
      </section>
      <section className="rail-section">
        <p className="section-index">05</p><h2>Artifact integrity</h2>
        <dl className="artifact-grid">
          <div><dt>JSON checks</dt><dd>{evidence.artifactAudit.json}</dd></div>
          <div><dt>SQLite reports</dt><dd>{evidence.artifactAudit.sqliteReports}</dd></div>
          <div><dt>PNG checks</dt><dd>{evidence.artifactAudit.png}</dd></div>
          <div><dt>Datasets</dt><dd>{evidence.artifactAudit.datasets}</dd></div>
        </dl>
        <div className="path-check"><span>Absolute paths found</span><strong>{evidence.artifactAudit.absolutePathsFound}</strong></div>
        <p className="hash">Evidence code: {evidence.artifactAudit.codeCommit}</p>
        <p className="note"><a href={evidence.artifactAudit.sourceUrl}>Source audit JSON</a> · {evidence.artifactAudit.level}</p>
      </section>
    </aside>
  )
}

export function App() {
  const idlePoints = useMemo(() => buildOfflineReplay(), [])
  const [runState, setRunState] = useState('idle')
  const finalEquity = idlePoints.at(-1).equity

  function runReplay() {
    setRunState('complete')
  }

  return (
    <div className="app-shell">
      <Header />
      <div className="notice"><strong>Read-only preview.</strong> Archived and synthetic evidence only. Not financial advice; no exchange connection or order submission.</div>
      <main className="layout">
        <div className="primary">
          <section className="section replay" aria-labelledby="replay-title">
            <div className="section-heading">
              <div><p className="section-index">01</p><h1 id="replay-title">Offline artifact viewer</h1></div>
              <Status tone="good">Archived synthetic broker run</Status>
            </div>
            <div className="replay-grid">
              <ReplayChart points={idlePoints} />
              <div className="replay-actions">
                <p className="eyeline">Archived artifact inspection</p>
                <p className="replay-copy">Displays {idlePoints.length} UTC equity snapshots from a committed synthetic PaperBroker run. The browser does not execute the engine or query a market API. <a href={evidence.replay.sourceUrl}>Equity CSV</a> · <a href={evidence.replay.reportUrl}>Accounting report</a> · code {evidence.replay.codeCommit.slice(0, 12)}.</p>
                <button type="button" onClick={runReplay} disabled={runState === 'complete'}>
                  {runState === 'complete' ? 'Replay inspected' : 'Inspect archived replay'}
                </button>
                <div className="result" aria-live="polite">
                  {runState === 'complete' ? (
                    <><strong>{idlePoints.length} / {idlePoints.length} artifact snapshots displayed</strong><span>End equity: {finalEquity.toLocaleString('en-US', { minimumFractionDigits: 2 })} synthetic USDT</span><span>No economic claim · no orders sent</span></>
                  ) : <span>Ready. No process is running.</span>}
                </div>
              </div>
            </div>
          </section>
          <FundingCoverage />
          <StrategyTable />
        </div>
        <AuditRail />
      </main>
      <footer>
        <span>Quill3H paper-bot research preview</span>
        <span><a href={evidence.historicalWindow.sourceUrl}>Historical dataset manifest</a>: {evidence.historicalWindow.rows.toLocaleString()} rows · {evidence.historicalWindow.gaps} gaps</span>
        <span className="mono">SHA-256 {evidence.historicalWindow.datasetHash.slice(0, 16)}…</span>
      </footer>
    </div>
  )
}
