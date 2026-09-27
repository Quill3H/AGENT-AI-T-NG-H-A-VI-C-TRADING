import publicManifest from './public_dataset_manifest.json'
import foldReport from './walk_forward.report.json'
import artifactAudit from './artifact_audit.json'

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
  historicalWindow: {
    start: publicManifest.datasets['1m'].start,
    end: publicManifest.datasets['1m'].end,
    cutoff: publicManifest.datasets['1m'].end,
    rows: publicManifest.datasets['1m'].rows,
    gaps: publicManifest.datasets['1m'].gaps,
    datasetHash: publicManifest.datasets['1m'].sha256,
    sourceUrl: `${historicalSource}public_dataset_manifest.json`,
  },
  replay: {
    sourceUrl: `${replaySource}equity_curve.csv`,
    reportUrl: `${replaySource}summary.json`,
    codeCommit: '2c9a4d0985fc9eafd29386482793425c26d47835',
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
  },
  strategies: foldReport.report.aggregate.map((row) => ({
    name: strategyNames[row.strategy],
    sample: '2024 public fold',
    trades: row.strategy === 'funding_arbitrage' ? `${row.sample_count} basket` : String(row.sample_count),
    result: `${row.total_net_pnl.toFixed(4)} USDT`,
    state: row.sample_count ? 'Historical sample' : 'No entry',
    level: 'author',
  })),
  strategySourceUrl: `${historicalSource}walk_forward.report.json`,
  controls: [
    { label: 'Maximum leverage', value: '5× cap', tone: 'neutral' },
    { label: 'Directional stop-loss', value: 'Required', tone: 'good' },
    { label: 'Funding provenance', value: 'Fail-closed', tone: 'warn' },
    { label: 'Exchange credentials', value: 'None', tone: 'good' },
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
  },
}
