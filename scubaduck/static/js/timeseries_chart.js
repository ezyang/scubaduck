function showTimeSeries(data) {
  function parseTs(s) {
    if (s.match(/GMT/) || s.endsWith('Z') || /\+\d{2}:?\d{2}$/.test(s)) {
      return new Date(s).getTime();
    }
    return new Date(s + 'Z').getTime();
  }
  const view = document.getElementById('view');
  if (data.rows.length === 0) {
    view.innerHTML = '<p id="empty-message">Empty data provided to table</p>';
    return;
  }
  const height = 400;
  view.innerHTML =
    '<div id="ts-container"><div id="legend"></div><div id="chart-wrapper"><svg id="chart" height="' +
    height +
    '"></svg></div></div>';
  const legend = document.getElementById('legend');
  const chartWrapper = document.getElementById('chart-wrapper');
  const width = chartWrapper.clientWidth || 600;
  const svg = document.getElementById('chart');
  svg.setAttribute('width', width);
  const groups = groupBy.chips || [];
  const hasHits = document.getElementById('show_hits').checked ? 1 : 0;
  const fill = document.getElementById('fill').value;
  const bucketMs = (data.bucket_size || 3600) * 1000;
  const start = data.start ? parseTs(data.start) : null;
  const end = data.end ? parseTs(data.end) : null;
  const series = {};
  data.rows.forEach(r => {
    const ts = parseTs(r[0]);
    const key = groups.map((_, i) => r[1 + i]).join(':') || 'all';
    const val = Number(r[1 + groups.length + hasHits]);
    if (!series[key]) series[key] = {};
    series[key][ts] = val;
  });

  const buckets = [];
  let minX = start !== null ? start : Infinity;
  let maxX = end !== null ? end : -Infinity;
  if (start !== null && end !== null) {
    for (let t = start; t <= end; t += bucketMs) {
      buckets.push(t);
    }
  } else {
    Object.keys(series).forEach(k => {
      const s = series[k];
      Object.keys(s).forEach(t => {
        const n = Number(t);
        if (n < minX) minX = n;
        if (n > maxX) maxX = n;
      });
    });
    for (let t = minX; t <= maxX; t += bucketMs) {
      buckets.push(t);
    }
  }

  let minY = Infinity,
    maxY = -Infinity;
  Object.keys(series).forEach(key => {
    const vals = series[key];
    buckets.forEach(b => {
      const v = vals[b];
      const val = v === undefined && fill === '0' ? 0 : v;
      if (val === undefined) return;
      if (val < minY) minY = val;
      if (val > maxY) maxY = val;
    });
  });
  if (fill === '0') {
    if (minY > 0) minY = 0;
    if (maxY < 0) maxY = 0;
  }

  const colors = [
    '#1f77b4',
    '#ff7f0e',
    '#2ca02c',
    '#d62728',
    '#9467bd',
    '#8c564b',
    '#e377c2'
  ];
  let colorIndex = 0;
  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;
  const xScale = x => ((x - minX) / xRange) * (width - 60) + 50;
  const yScale = y => height - 30 - ((y - minY) / yRange) * (height - 60);

  Object.keys(series).forEach(key => {
    const vals = series[key];
    const color = colors[colorIndex++ % colors.length];
    let path = '';
    let drawing = false;
    buckets.forEach(b => {
      const v = vals[b];
      if (v === undefined) {
        if (fill === '0') {
          const x = xScale(b);
          const y = yScale(0);
          path += (drawing ? 'L' : 'M') + x + ' ' + y + ' ';
          drawing = true;
        } else if (fill === 'blank') {
          drawing = false;
        }
        // connect: do nothing
      } else {
        const x = xScale(b);
        const y = yScale(v);
        path += (drawing ? 'L' : 'M') + x + ' ' + y + ' ';
        drawing = true;
      }
    });
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    el.setAttribute('d', path.trim());
    el.setAttribute('fill', 'none');
    el.setAttribute('stroke', color);
    el.setAttribute('stroke-width', '1');
    svg.appendChild(el);
    const item = document.createElement('div');
    item.textContent = key;
    item.style.color = color;
    item.className = 'legend-item';
    legend.appendChild(item);

    function highlight(on) {
      el.setAttribute('stroke-width', on ? '3' : '1');
      item.classList.toggle('highlight', on);
    }

    el.addEventListener('mouseenter', () => highlight(true));
    el.addEventListener('mouseleave', () => highlight(false));
    item.addEventListener('mouseenter', () => highlight(true));
    item.addEventListener('mouseleave', () => highlight(false));
  });
}
