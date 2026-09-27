import brokerEquityCsv from '../data/long_equity_curve.csv?raw'

// Snapshot of the checked-in G0 synthetic PaperBroker artifact. No browser-side
// PnL increments, strategy decisions, or simulated fills are invented here.
export function parseEquityArtifact(csv) {
  const lines = csv.trim().split(/\r?\n/)
  const expected = 'timestamp,equity,wallet_balance,unrealized_pnl,margin_used,available_balance,drawdown_usd,drawdown_pct'
  if (lines[0] !== expected || lines.length < 2) throw new Error('Invalid broker equity artifact schema')

  let previous = -Infinity
  return lines.slice(1).map((line) => {
    const fields = line.split(',')
    const timestamp = fields[0]
    const time = Date.parse(timestamp)
    const numericFields = fields.slice(1)
    const values = numericFields.map(Number)
    if (fields.length !== 8 || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$/.test(timestamp)
        || !Number.isFinite(time) || time <= previous
        || numericFields.some((value) => value.trim() === '')
        || values.some((value) => !Number.isFinite(value))) {
      throw new Error('Invalid broker equity artifact row')
    }
    previous = time
    return { timestamp, equity: values[0] }
  })
}

export function buildOfflineReplay() {
  return parseEquityArtifact(brokerEquityCsv)
}

export function toPolyline(points, width = 680, height = 230) {
  if (points.length < 2) throw new Error('At least two equity snapshots are required')
  const values = points.map((point) => point.equity)
  const min = Math.min(...values) - 8
  const max = Math.max(...values) + 8
  return points.map((point, index) => {
    const x = (index / (points.length - 1)) * width
    const y = height - ((point.equity - min) / (max - min)) * height
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}
