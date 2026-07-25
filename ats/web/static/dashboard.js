(() => {
  const svg = document.getElementById("equity-chart");
  const rows = window.ATS_EQUITY || [];
  if (!svg || rows.length < 2) {
    if (svg) svg.innerHTML = '<text x="20" y="40" fill="#8ca4b8">暂无净值数据</text>';
    return;
  }
  const width = 760, height = 280, pad = 28;
  const values = rows.flatMap(r => [r.strategy_equity, r.benchmark_equity]);
  const min = Math.min(...values), max = Math.max(...values);
  const span = Math.max(max - min, 0.01);
  const x = i => pad + i * (width - 2 * pad) / (rows.length - 1);
  const y = v => height - pad - (v - min) * (height - 2 * pad) / span;
  const path = key => rows.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`).join(" ");
  svg.innerHTML = `
    <line x1="${pad}" y1="${height-pad}" x2="${width-pad}" y2="${height-pad}" stroke="#243746"/>
    <path d="${path("benchmark_equity")}" fill="none" stroke="#7aa7ff" stroke-width="2" opacity=".8"/>
    <path d="${path("strategy_equity")}" fill="none" stroke="#59d8b5" stroke-width="3"/>
    <text x="${pad}" y="18" fill="#8ca4b8" font-size="11">${max.toFixed(2)}</text>
    <text x="${pad}" y="${height-7}" fill="#8ca4b8" font-size="11">${min.toFixed(2)}</text>`;
})();
