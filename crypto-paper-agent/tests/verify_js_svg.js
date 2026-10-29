const series_1 = [{equity: 10000.0, dd_pct: 0.0}];
const series_2 = [
  {equity: 10000.0, dd_pct: 0.0},
  {equity: 10200.0, dd_pct: 0.0},
  {equity: 9800.0, dd_pct: 3.92}
];

function createSvgLineChart(series) {
  if (!series || series.length === 0) return '<div style="padding:20px;color:#94a3b8;">No data</div>';
  const w = 800, h = 300, pad = 40;
  const equities = series.map(s => s.equity);
  const minEq = Math.min(...equities);
  const maxEq = Math.max(...equities);
  const range = (maxEq - minEq) || 1;
  const pts = series.map((s, i) => {
    const x = pad + (i / (series.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((s.equity - minEq) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:100%;">
    <polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${pts}" />
  </svg>`;
}

function createSvgAreaChart(series) {
  if (!series || series.length === 0) return '';
  const w = 800, h = 200, pad = 30;
  const dds = series.map(s => s.dd_pct);
  const maxDd = Math.max(...dds) || 1;
  const pts = series.map((s, i) => {
    const x = pad + (i / (series.length - 1)) * (w - 2 * pad);
    const y = pad + (s.dd_pct / maxDd) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:100%;">
    <polygon fill="rgba(244,63,94,0.3)" stroke="#f43f5e" stroke-width="1.5" points="${pad},${pad} ${pts} ${w-pad},${pad}" />
  </svg>`;
}

console.log("=== TEST 1: series length = 1 ===");
const res1_line = createSvgLineChart(series_1);
console.log("Line Chart (1 pt):", res1_line);
const res1_area = createSvgAreaChart(series_1);
console.log("Area Chart (1 pt):", res1_area);

console.log("\n=== TEST 2: series length = 3 ===");
const res2_line = createSvgLineChart(series_2);
console.log("Line Chart (3 pts):", res2_line);
const res2_area = createSvgAreaChart(series_2);
console.log("Area Chart (3 pts):", res2_area);

console.log("\n=== TEST 3: series length = 0 ===");
const res0_line = createSvgLineChart([]);
console.log("Line Chart (0 pts):", res0_line);
const res0_area = createSvgAreaChart([]);
console.log("Area Chart (0 pts):", res0_area);
