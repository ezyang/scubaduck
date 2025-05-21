function showTimeSeries(data) {
  const view = document.getElementById('view');
  if (data.rows.length === 0) {
    view.innerHTML = '<p id="empty-message">Empty data provided to table</p>';
    return;
  }
  const width = 600;
  const height = 400;
  view.innerHTML =
    '<div id="legend"></div><svg id="chart" width="' +
    width +
    '" height="' +
    height +
    '"></svg>';
  const svg = document.getElementById('chart');
  const legend = document.getElementById('legend');
  const groups = groupBy.chips || [];
  const hasHits = document.getElementById('show_hits').checked ? 1 : 0;
  const series = {};
  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  data.rows.forEach(r => {
    const ts = new Date(r[0]).getTime();
    const key = groups.map((_, i) => r[1 + i]).join(':') || 'all';
    const val = Number(r[1 + groups.length + hasHits]);
    if (!series[key]) series[key] = [];
    series[key].push({ x: ts, y: val });
    if (ts < minX) minX = ts;
    if (ts > maxX) maxX = ts;
    if (val < minY) minY = val;
    if (val > maxY) maxY = val;
  });
  const colors = [
    '#1f77b4',
    '#ff7f0e',
    '#2ca02c',
    '#d62728',
    '#9467bd',
    '#8c564b',
    '#e377c2',
  ];
  let colorIndex = 0;
  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;
  const xScale = x => ((x - minX) / xRange) * (width - 60) + 50;
  const yScale = y => height - 30 - ((y - minY) / yRange) * (height - 60);
  Object.keys(series).forEach(key => {
    const pts = series[key];
    const color = colors[colorIndex++ % colors.length];
    const path = pts
      .map((p, i) => (i === 0 ? 'M' : 'L') + xScale(p.x) + ' ' + yScale(p.y))
      .join(' ');
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    el.setAttribute('d', path);
    el.setAttribute('fill', 'none');
    el.setAttribute('stroke', color);
    svg.appendChild(el);
    const item = document.createElement('div');
    item.textContent = key;
    item.style.color = color;
    legend.appendChild(item);
  });
}
