const DEMO_DELTAS = [0, 18, -7, 12, -24, 9, 15, -5, -13, 7, 4, -10]

export function buildOfflineReplay(initialEquity = 10000) {
  let equity = initialEquity
  return DEMO_DELTAS.map((delta, index) => {
    equity += delta
    return { step: index + 1, equity }
  })
}

export function toPolyline(points, width = 680, height = 230) {
  const values = points.map((point) => point.equity)
  const min = Math.min(...values) - 8
  const max = Math.max(...values) + 8
  return points.map((point, index) => {
    const x = (index / (points.length - 1)) * width
    const y = height - ((point.equity - min) / (max - min)) * height
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}
