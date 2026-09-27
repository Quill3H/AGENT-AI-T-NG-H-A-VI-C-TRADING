import publicManifest from './public_dataset_manifest.json'
import foldReport from './walk_forward.report.json'
import artifactAudit from './artifact_audit.json'
import { DATA_CATEGORIES, BACKEND_SAMPLE_CONTRACT } from './backend_contract'

const repo = 'https://github.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/blob/'
// Documentation evidence was committed after its code-under-test SHA.
// Link to the verified base commit containing all referenced artifacts.
const evidenceSnapshot = `${repo}fe1c1330d913e78239db575ff8433cf069fe1b01/crypto-paper-agent/`
const historicalSource = `${evidenceSnapshot}docs/reviews/evidence/stage-06-11-repair/`
const replaySource = `${evidenceSnapshot}docs/reviews/evidence/g0-2c9a4d0/replay/LONG/`

const strategyNames = {
  trend_following: 'Trend following',
  breakout_retest: 'Breakout & retest',
  smc_liquidity_sweep: 'SMC liquidity sweep',
  funding_arbitrage: 'Funding arbitrage',
}

export const evidence = {
  mode: 'PAPER / RESEARCH',
  source: publicManifest.datasets['1m'].source,
  evidenceLevel: foldReport.report.status,
  backendContract: BACKEND_SAMPLE_CONTRACT,
  dataCategories: DATA_CATEGORIES,
  historicalWindow: {
    start: publicManifest.datasets['1m'].start,
    end: publicManifest.datasets['1m'].end,
    cutoff: publicManifest.datasets['1m'].end,
    rows: publicManifest.datasets['1m'].rows,
    gaps: publicManifest.datasets['1m'].gaps,
    datasetHash: publicManifest.datasets['1m'].sha256,
    sourceUrl: `${historicalSource}public_dataset_manifest.json`,
    category: DATA_CATEGORIES.HISTORICAL,
  },
  replay: {
    sourceUrl: `${replaySource}equity_curve.csv`,
    reportUrl: `${replaySource}summary.json`,
    codeCommit: '2c9a4d0985fc9eafd29386482793425c26d47835',
    category: DATA_CATEGORIES.HISTORICAL,
    initialEquity: 10000.0,
    finalEquity: 10449.2125,
  },
  // G2 has a narrative diagnostic but no checked-in machine-readable
  // funding-coverage artifact. Keep this separately attributed, not merged
  // with the 2024 fold report or the synthetic chart.
  fundingCoverage: {
    start: '2026-08-20T00:00:00Z',
    end: '2026-08-26T23:59:00Z',
    expected: 21,
    exactReady: 11,
    delayed: 10,
    maxDelayMs: 6,
    status: 'FAIL_CLOSED',
    sourceUrl: `${evidenceSnapshot}docs/reviews/G2_BINANCE_PUBLIC_DATA_DIAGNOSTIC.md`,
    category: DATA_CATEGORIES.DIAGNOSTIC,
  },
  strategies: foldReport.report.aggregate.map((row) => {
    const meta = BACKEND_SAMPLE_CONTRACT.strategy_descriptions[row.strategy] || {}
    return {
      id: row.strategy,
      name: strategyNames[row.strategy],
      nameVi: meta.nameVi || strategyNames[row.strategy],
      conceptVi: meta.conceptVi || 'Chiến lược phân tích kỹ thuật hợp đồng tương lai.',
      timeframe: meta.timeframe || '15m',
      riskTier: meta.riskTier || 'Normal',
      sample: '2024 public fold',
      trades: row.strategy === 'funding_arbitrage' ? `${row.sample_count} basket` : String(row.sample_count),
      result: `${row.total_net_pnl.toFixed(4)} USDT`,
      rawPnl: row.total_net_pnl,
      state: row.sample_count ? 'Historical sample' : 'No entry',
      stateVi: row.sample_count ? 'Mẫu lịch sử đã chạy' : 'Không có lệnh (Điều kiện chưa thỏa)',
      level: 'author',
      category: DATA_CATEGORIES.HISTORICAL,
    }
  }),
  strategySourceUrl: `${historicalSource}walk_forward.report.json`,
  controls: [
    {
      label: 'Maximum leverage',
      labelVi: 'Đòn bẩy tối đa',
      value: '5× cap',
      tone: 'neutral',
      descVi: 'Khống chế mức đòn bẩy tối đa 5x, bảo vệ tài khoản khỏi thanh lý cưỡng bức.',
      category: DATA_CATEGORIES.ILLUSTRATION,
    },
    {
      label: 'Directional stop-loss',
      labelVi: 'Cắt lỗ bắt buộc (SL)',
      value: 'Required',
      tone: 'good',
      descVi: '100% các lệnh mua/bán theo xu hướng bắt buộc phải có lệnh cắt lỗ bảo hiểm.',
      category: DATA_CATEGORIES.ILLUSTRATION,
    },
    {
      label: 'Funding provenance',
      labelVi: 'Dữ liệu phí Funding',
      value: 'Fail-closed',
      tone: 'warn',
      descVi: 'Nếu nến funding từ sàn bị trễ hoặc thiếu dữ liệu, hệ thống tự động ngắt lệnh.',
      category: DATA_CATEGORIES.DIAGNOSTIC,
    },
    {
      label: 'Exchange credentials',
      labelVi: 'Kết nối tài khoản thật',
      value: 'None',
      tone: 'good',
      descVi: 'Mã nguồn không lưu API keys hay Private Key; rủi ro tài sản thật = 0%.',
      category: DATA_CATEGORIES.ILLUSTRATION,
    },
  ],
  artifactAudit: {
    json: artifactAudit.checks.json,
    sqliteReports: artifactAudit.checks.sqlite_reports,
    png: artifactAudit.checks.png,
    datasets: artifactAudit.checks.datasets,
    absolutePathsFound: artifactAudit.absolute_paths_found,
    codeCommit: artifactAudit.code_commit_sha,
    level: artifactAudit.status,
    sourceUrl: `${historicalSource}artifact_audit.json`,
    category: DATA_CATEGORIES.HISTORICAL,
  },
}
