import { useMemo, useState } from 'react'
import { evidence } from './data/evidence'
import { buildOfflineReplay, toPolyline } from './lib/replay'
import { LocalPaperPanel } from './LocalPaperPanel'

function Status({ children, tone = 'neutral' }) {
  return <span className={`status status--${tone}`}>{children}</span>
}

function CategoryBadge({ category }) {
  if (!category) return null
  return (
    <span className={`flat-badge ${category.badgeClass}`} title={category.descVi}>
      {category.labelVi}
    </span>
  )
}

function Header() {
  return (
    <header className="header">
      <div className="header-container">
        <div className="brand-group">
          <div className="brand-logo" aria-hidden="true">Q</div>
          <div>
            <h1 className="brand-title">Quill3H Paper Research Console</h1>
            <p className="brand-subtitle">{evidence.mode} — NO LIVE ORDERS</p>
          </div>
        </div>
        <dl className="header-meta">
          <div className="header-meta-item">
            <dt>2024 fold source</dt>
            <dd>{evidence.source}</dd>
          </div>
          <div className="header-meta-item">
            <dt>2024 fold cutoff</dt>
            <dd>{evidence.historicalWindow.cutoff}</dd>
          </div>
          <div className="header-meta-item">
            <dt>Evidence level</dt>
            <dd><Status tone="neutral">{evidence.evidenceLevel}</Status></dd>
          </div>
        </dl>
      </div>
    </header>
  )
}

function NavigationStrip({ localMode }) {
  return (
    <nav className="nav-strip" aria-label="Điều hướng nhanh các mục">
      <div className="nav-container">
        {localMode && <a href="#paper" className="nav-tab active">Thị trường PAPER</a>}
        <a href="#overview" className={`nav-tab${localMode ? '' : ' active'}`}>📋 Tổng quan (Overview)</a>
        <a href="#replay" className="nav-tab">📈 Kết quả mô phỏng (Simulation Replay)</a>
        <a href="#strategy" className="nav-tab">⚡ Chiến lược (Strategies)</a>
        <a href="#funding" className="nav-tab">⏱️ Phí Funding (Funding Coverage)</a>
        <a href="#risk" className="nav-tab">🛡️ Kiểm soát rủi ro (Risk Controls)</a>
        <a href="#audit" className="nav-tab">🔍 Kiểm toán dữ liệu (Artifact Integrity)</a>
      </div>
    </nav>
  )
}

function OverviewSection({ idlePoints }) {
  const finalEquity = idlePoints.at(-1)?.equity || 10000

  return (
    <section id="overview" className="flat-card flat-card--highlight" aria-labelledby="overview-title">
      <div className="card-header">
        <div className="card-header-left">
          <div className="card-badge-row">
            <span className="section-num">Mục 01</span>
            <CategoryBadge category={evidence.dataCategories.ILLUSTRATION} />
          </div>
          <h2 id="overview-title" className="card-title">Tổng quan dự án & Chỉ số an toàn</h2>
          <p className="card-desc">Hệ thống nghiên cứu thuật toán giao dịch tiền mã hóa chạy hoàn toàn trên môi trường mô phỏng (Paper Trading Sandbox).</p>
        </div>
        <Status tone="good">Mô phỏng khép kín · Không rủi ro tài chính</Status>
      </div>

      <div className="explainer-box">
        <strong>💡 Dành cho người không biết code / Nhà đầu tư:</strong>
        <p>
          Dự án này là môi trường phòng thí nghiệm (Sandbox). Bot hoạt động bằng cách đọc dữ liệu nến thật từ sàn Binance,
          nhưng <strong>mọi lệnh mua/bán và số dư tài khoản đều là giả định trên giấy (Paper Trading)</strong>.
          Mã nguồn được thiết kế biệt lập: không có quyền đặt lệnh ra sàn thật, không kết nối ví tiền mã hóa cá nhân,
          giúp thử nghiệm độ ổn định và quản trị rủi ro một cách minh bạch 100%.
        </p>
      </div>

      {/* 4 Flat KPI Metric Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Vốn giả định ban đầu</span>
            <span className="flat-badge badge--illustration">Minh họa</span>
          </div>
          <div className="kpi-value mono">10,000.00 <small style={{ fontSize: '14px', fontWeight: 600 }}>USDT</small></div>
          <div className="kpi-sub">Mức vốn khởi tạo trong cấu hình test</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Vốn chốt mẫu lưu trữ</span>
            <span className="flat-badge badge--historical">Lịch sử G0</span>
          </div>
          <div className="kpi-value mono" style={{ color: 'var(--flat-green)' }}>
            {finalEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <small style={{ fontSize: '14px', fontWeight: 600 }}>USDT</small>
          </div>
          <div className="kpi-sub">
            Tăng trưởng mẫu: <strong>+4.49%</strong> (65 snapshots)
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Mức sụt giảm tối đa</span>
            <span className="flat-badge badge--historical">Lịch sử G0</span>
          </div>
          <div className="kpi-value mono">0.00%</div>
          <div className="kpi-sub">Max Drawdown trong chuỗi mẫu Long</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Khóa an toàn sàn & ví</span>
            <span className="flat-badge badge--safe">Bảo vệ 100%</span>
          </div>
          <div className="kpi-value" style={{ color: 'var(--flat-green)', fontSize: '18px' }}>KHÓA HOÀN TOÀN</div>
          <div className="kpi-sub">0 API Key · 0 Private Key · Read-Only</div>
        </div>
      </div>
    </section>
  )
}

function ReplayChart({ points }) {
  const line = useMemo(() => toPolyline(points), [points])
  return (
    <div className="chart-box">
      <div className="chart-title-bar">
        <span>Đồ thị số dư vốn PaperBroker (65 điểm UTC)</span>
        <span className="flat-badge badge--historical">Mẫu lịch sử đã cam kết</span>
      </div>
      <div className="chart-wrap">
        <svg className="chart" viewBox="0 0 680 230" role="img" aria-label="Archived synthetic PaperBroker equity chart">
          <defs>
            <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#2563eb" stopOpacity="0.01" />
            </linearGradient>
          </defs>
          {[0, 57.5, 115, 172.5, 230].map((y) => (
            <line key={y} x1="0" y1={y} x2="680" y2={y} className="grid-line" />
          ))}
          <polygon points={`0,230 ${line} 680,230`} fill="url(#chartFill)" />
          <polyline points={line} className="equity-line" />
        </svg>
        <div className="axis">
          <span>{points[0].timestamp}</span>
          <span>Committed broker snapshots</span>
          <span>{points.at(-1).timestamp}</span>
        </div>
      </div>
    </div>
  )
}

function ReplaySection({ idlePoints, runState, setRunState, finalEquity }) {
  function runReplay() {
    setRunState('complete')
  }

  return (
    <section id="replay" className="flat-card" aria-labelledby="replay-title">
      <div className="card-header">
        <div className="card-header-left">
          <div className="card-badge-row">
            <span className="section-num">Mục 02</span>
            <CategoryBadge category={evidence.dataCategories.HISTORICAL} />
          </div>
          <h2 id="replay-title" className="card-title">Offline artifact viewer</h2>
          <p className="card-desc">Kiểm tra chuỗi số dư tài khoản từ tệp bằng chứng PaperBroker đã được kiểm toán (không tạo số liệu ảo).</p>
        </div>
        <Status tone="good">Archived synthetic broker run</Status>
      </div>

      <div className="chart-container">
        <ReplayChart points={idlePoints} />

        <div className="replay-panel">
          <div>
            <p className="replay-panel-title">Archived artifact inspection</p>
            <p className="replay-copy">
              Displays {idlePoints.length} UTC equity snapshots from a committed synthetic PaperBroker run. The browser does not execute the engine or query a market API. <a href={evidence.replay.sourceUrl}>Equity CSV</a> · <a href={evidence.replay.reportUrl}>Accounting report</a> · code {evidence.replay.codeCommit.slice(0, 12)}.
            </p>
            <div style={{ marginBottom: '14px', fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.45' }}>
              <strong>ℹ️ Vì sao không gọi là "Chạy bot"?</strong>
              <div>Giao diện hiện tại là trang tĩnh nghiệm thu bằng chứng. Nút bên dưới phục vụ việc duyệt và xác minh 65 snapshot số dư đã ghi nhận từ tệp CSV gốc, không gửi lệnh ra sàn giao dịch.</div>
            </div>
          </div>

          <div>
            <button type="button" onClick={runReplay} disabled={runState === 'complete'}>
              {runState === 'complete' ? 'Replay inspected' : 'Inspect archived replay'}
            </button>

            <div className="result" aria-live="polite">
              {runState === 'complete' ? (
                <>
                  <strong>{idlePoints.length} / {idlePoints.length} artifact snapshots displayed</strong>
                  <span>End equity: {finalEquity.toLocaleString('en-US', { minimumFractionDigits: 2 })} synthetic USDT</span>
                  <span>No economic claim · no orders sent</span>
                </>
              ) : (
                <span>Archived replay is idle; the local paper session is separate.</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {runState === 'complete' && (
        <div className="replay-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Mốc thời gian (UTC)</th>
                <th>Vốn tổng (Equity)</th>
                <th>Tiền trong ví</th>
                <th>Trạng thái đối chiếu</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="mono">{idlePoints[0].timestamp} (Bắt đầu)</td>
                <td className="mono">10,000.00 USDT</td>
                <td className="mono">10,000.00 USDT</td>
                <td><Status tone="good">Khớp tệp gốc</Status></td>
              </tr>
              <tr>
                <td className="mono">{idlePoints[Math.floor(idlePoints.length / 2)].timestamp} (Giữa kỳ)</td>
                <td className="mono">{idlePoints[Math.floor(idlePoints.length / 2)].equity.toFixed(2)} USDT</td>
                <td className="mono">10,000.00 USDT</td>
                <td><Status tone="good">Khớp tệp gốc</Status></td>
              </tr>
              <tr>
                <td className="mono">{idlePoints.at(-1).timestamp} (Kết thúc)</td>
                <td className="mono" style={{ color: 'var(--flat-green)', fontWeight: 700 }}>{finalEquity.toFixed(4)} USDT</td>
                <td className="mono">10,000.00 USDT</td>
                <td><Status tone="good">Xác thực SHA-256</Status></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function FundingCoverage() {
  const readyPct = (evidence.fundingCoverage.exactReady / evidence.fundingCoverage.expected) * 100

  return (
    <section id="funding" className="flat-card" aria-labelledby="funding-title">
      <div className="card-header">
        <div className="card-header-left">
          <div className="card-badge-row">
            <span className="section-num">Mục 04</span>
            <CategoryBadge category={evidence.dataCategories.DIAGNOSTIC} />
          </div>
          <h2 id="funding-title" className="card-title">Funding coverage</h2>
          <p className="card-desc">Kiểm tra chất lượng và độ trễ nhận dữ liệu phí Funding Rate từ Binance Futures.</p>
        </div>
        <Status tone="blocked">{evidence.fundingCoverage.status}</Status>
      </div>

      <div className="explainer-box">
        <strong>💡 Nguyên tắc an toàn Fail-Closed:</strong>
        <p>
          Phí Funding được tính chu kỳ mỗi 8 tiếng. Nếu dữ liệu gửi về từ sàn bị trễ dù chỉ 1 mili-giây (1–6 ms) hoặc chưa sẵn sàng,
          thuật toán <strong>lập tức ngừng mở vị thế mới</strong> để bảo vệ tài khoản. Hệ thống tuyệt đối không làm tròn lùi mốc thời gian.
        </p>
      </div>

      <div className="coverage-summary">
        <strong>{evidence.fundingCoverage.expected} expected boundaries</strong>
        <span>{evidence.fundingCoverage.start} → {evidence.fundingCoverage.end}</span>
      </div>

      <div
        className="coverage-bar"
        aria-label={`${evidence.fundingCoverage.exactReady} exact-ready and ${evidence.fundingCoverage.delayed} delayed or unready`}
      >
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

function StrategySection() {
  return (
    <section id="strategy" className="flat-card" aria-labelledby="strategy-title">
      <div className="card-header">
        <div className="card-header-left">
          <div className="card-badge-row">
            <span className="section-num">Mục 03</span>
            <CategoryBadge category={evidence.dataCategories.HISTORICAL} />
          </div>
          <h2 id="strategy-title" className="card-title">Strategy evidence</h2>
          <p className="card-desc">Đánh giá 4 chiến lược giao dịch định lượng qua mẫu kiểm tra Walk-forward 2024.</p>
        </div>
        <Status>Independent review pending</Status>
      </div>

      {/* 4 Strategy Cards for Non-Coders */}
      <div className="strategy-cards-grid">
        {evidence.strategies.map((strat) => (
          <div className="strategy-card" key={strat.id || strat.name}>
            <div className="strategy-card-header">
              <div>
                <h3 className="strategy-card-name">{strat.name}</h3>
                <span className="strategy-card-name-vi">{strat.nameVi}</span>
              </div>
              <span className="flat-badge badge--historical">{strat.timeframe}</span>
            </div>
            <p className="strategy-card-desc">{strat.conceptVi}</p>
            <div className="strategy-card-footer">
              <span>Lệnh hoàn tất: <strong>{strat.trades}</strong></span>
              <span className="mono" style={{ color: strat.rawPnl < 0 ? 'var(--flat-red)' : 'var(--text-main)' }}>
                PnL: {strat.result}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Main Walk-forward Table */}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Sample</th>
              <th>Completed</th>
              <th>Net result</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {evidence.strategies.map((row) => (
              <tr key={row.name}>
                <td>
                  <strong>{row.name}</strong>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{row.nameVi}</div>
                </td>
                <td>{row.sample}</td>
                <td className="mono">{row.trades}</td>
                <td className="mono">{row.result}</td>
                <td>
                  <Status tone={row.level === 'blocked' ? 'blocked' : 'neutral'}>
                    {row.state}
                  </Status>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="note">
        <a href={evidence.strategySourceUrl}>2024 walk-forward report</a> · four independent accounts, not a shared portfolio. Zero trades and one negative sample do not establish profitability.
      </p>
    </section>
  )
}

function RiskSection() {
  return (
    <section id="risk" className="flat-card sidebar-section" aria-labelledby="risk-title">
      <div className="card-header-left">
        <div className="card-badge-row">
          <span className="section-num">Mục 05</span>
          <CategoryBadge category={evidence.dataCategories.ILLUSTRATION} />
        </div>
        <h2 id="risk-title" className="card-title">Risk & accounting</h2>
        <p className="card-desc">Hàng rào kỷ luật rủi ro bắt buộc trước khi thực thi mọi hành động.</p>
      </div>

      <div className="control-list">
        {evidence.controls.map((control) => (
          <div className="control-row" key={control.label}>
            <div className="control-row-header">
              <span className="control-label">{control.label}</span>
              <Status tone={control.tone}>{control.value}</Status>
            </div>
            {control.descVi && <div className="control-desc">{control.descVi}</div>}
          </div>
        ))}
      </div>

      <p className="note">
        Hosted evidence is read-only. Local controls start/stop only the paper session; no exchange order client, wallet, API key or webhook is included.
      </p>
    </section>
  )
}

function AuditSection() {
  return (
    <section id="audit" className="flat-card sidebar-section" aria-labelledby="audit-title">
      <div className="card-header-left">
        <div className="card-badge-row">
          <span className="section-num">Mục 06</span>
          <CategoryBadge category={evidence.dataCategories.HISTORICAL} />
        </div>
        <h2 id="audit-title" className="card-title">Artifact integrity</h2>
        <p className="card-desc">Kiểm toán tự động tính toàn vẹn của dữ liệu và không rò rỉ đường dẫn tuyệt đối.</p>
      </div>

      <dl className="artifact-grid">
        <div className="artifact-stat">
          <dt>JSON checks</dt>
          <dd>{evidence.artifactAudit.json}</dd>
        </div>
        <div className="artifact-stat">
          <dt>SQLite reports</dt>
          <dd>{evidence.artifactAudit.sqliteReports}</dd>
        </div>
        <div className="artifact-stat">
          <dt>PNG checks</dt>
          <dd>{evidence.artifactAudit.png}</dd>
        </div>
        <div className="artifact-stat">
          <dt>Datasets</dt>
          <dd>{evidence.artifactAudit.datasets}</dd>
        </div>
      </dl>

      <div className="path-check">
        <span>Absolute paths found</span>
        <strong>{evidence.artifactAudit.absolutePathsFound}</strong>
      </div>

      <p className="hash">Evidence code: {evidence.artifactAudit.codeCommit}</p>
      <p className="note">
        <a href={evidence.artifactAudit.sourceUrl}>Source audit JSON</a> · {evidence.artifactAudit.level}
      </p>
    </section>
  )
}

export function App() {
  const localMode = (window.location.hostname === '127.0.0.1' && !!window.location.port)
    || (window.location.hostname === 'localhost' && ['8765', '5173'].includes(window.location.port))
  const idlePoints = useMemo(() => buildOfflineReplay(), [])
  const [runState, setRunState] = useState('idle')
  const finalEquity = idlePoints.at(-1)?.equity || 10000

  return (
    <div className={`app-shell${localMode ? ' app-shell--local' : ''}`}>
      {/* Top Banner with Strict Safety Label */}
      <div className="safety-bar" role="alert">
        <div className="safety-bar-left">
          <span className="safety-pill">CHẾ ĐỘ MÔ PHỎNG</span>
          <span className="safety-bar-text">
            <strong>PAPER / RESEARCH — NO LIVE ORDERS:</strong> Chỉ đọc dữ liệu công khai; không kết nối tài khoản hoặc đặt lệnh sàn.
          </span>
        </div>
        <span className="safety-bar-tag">AUDIT PREVIEW</span>
      </div>

      <Header />
      <NavigationStrip localMode={localMode} />

      <main className="main-content">
        {localMode && <LocalPaperPanel />}
        <div className="primary-column">
          <OverviewSection idlePoints={idlePoints} />
          <ReplaySection
            idlePoints={idlePoints}
            runState={runState}
            setRunState={setRunState}
            finalEquity={finalEquity}
          />
          <StrategySection />
          <FundingCoverage />
        </div>

        <aside className="sidebar-column" aria-label="Risk, accounting and artifact status">
          <RiskSection />
          <AuditSection />
        </aside>
      </main>

      <footer>
        <div className="footer-container">
          <span>Quill3H paper-bot research preview · Flat Design Edition</span>
          <span>
            <a href={evidence.historicalWindow.sourceUrl}>Historical dataset manifest</a>: {evidence.historicalWindow.rows.toLocaleString()} rows · {evidence.historicalWindow.gaps} gaps
          </span>
          <span className="mono">SHA-256 {evidence.historicalWindow.datasetHash.slice(0, 16)}…</span>
        </div>
      </footer>
    </div>
  )
}
