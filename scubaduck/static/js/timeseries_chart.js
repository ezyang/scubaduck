let resizeObserver = null;
let currentChart = null;

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
  const svg = document.getElementById('chart');
  const legend = document.getElementById('legend');
  const crosshairLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  crosshairLine.id = 'crosshair_line';
  crosshairLine.setAttribute('stroke', '#555');
  crosshairLine.style.display = 'none';

  const crosshairDots = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  crosshairDots.id = 'crosshair_dots';
  crosshairDots.style.display = 'none';
  const groups = groupBy.chips || [];
  const hasHits = document.getElementById('show_hits').checked ? 1 : 0;
  const fill = document.getElementById('fill').value;
  const bucketMs = (data.bucket_size || 3600) * 1000;
  const start = data.start ? parseTs(data.start) : null;
  const end = data.end ? parseTs(data.end) : null;
  const startIdx = 1 + groups.length + hasHits;
  const valueCols = selectedColumns.slice(groups.length + hasHits);
  const series = {};
  data.rows.forEach(r => {
    const ts = parseTs(r[0]);
    const groupKey = groups.map((_, i) => r[1 + i]).join(':') || 'all';
    valueCols.forEach((name, i) => {
      const val = Number(r[startIdx + i]);
      const key = groupKey === 'all' ? name : groupKey + ':' + name;
      if (!series[key]) series[key] = {};
      series[key][ts] = val;
    });
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

  currentChart = {
    svg,
    legend,
    series,
    buckets,
    minX,
    maxX,
    minY,
    maxY,
    fill,
    colors,
    height,
    crosshairLine,
    crosshairDots,
    seriesEls: {},
    bucketPixels: [],
    xScale: null,
    yScale: null,
    selected: null
  };

  function render() {
    const style = getComputedStyle(svg.parentElement);
    const width =
      svg.parentElement.clientWidth -
      parseFloat(style.paddingLeft) -
      parseFloat(style.paddingRight);
    svg.setAttribute('width', width);
    svg.innerHTML = '';
    legend.innerHTML = '';
    let colorIndex = 0;
    const xRange = maxX - minX || 1;
    const yRange = maxY - minY || 1;
    const xScale = x => ((x - minX) / xRange) * (width - 60) + 50;
    const yScale = y => height - 30 - ((y - minY) / yRange) * (height - 60);
    const seriesEls = {};
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
      seriesEls[key] = { path: el, item, highlight, color };
    });
    currentChart.seriesEls = seriesEls;
    currentChart.xScale = xScale;
    currentChart.yScale = yScale;
    currentChart.bucketPixels = buckets.map(xScale);
    svg.appendChild(crosshairLine);
    svg.appendChild(crosshairDots);
  }

  render();

  function hideCrosshair() {
    crosshairLine.style.display = 'none';
    crosshairDots.style.display = 'none';
    crosshairDots.innerHTML = '';
    if (currentChart.selected) {
      currentChart.seriesEls[currentChart.selected].highlight(false);
      currentChart.selected = null;
    }
  }

  svg.addEventListener('mouseleave', hideCrosshair);
  svg.addEventListener('mousemove', e => {
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const pixels = currentChart.bucketPixels;
    if (!pixels.length) return;
    let idx = 0;
    let dist = Math.abs(pixels[0] - x);
    for (let i = 1; i < pixels.length; i++) {
      const d = Math.abs(pixels[i] - x);
      if (d < dist) {
        dist = d;
        idx = i;
      }
    }
    const bucket = currentChart.buckets[idx];
    const xPix = pixels[idx];
    crosshairLine.setAttribute('x1', xPix);
    crosshairLine.setAttribute('x2', xPix);
    crosshairLine.setAttribute('y1', currentChart.yScale(currentChart.maxY));
    crosshairLine.setAttribute('y2', currentChart.yScale(currentChart.minY));
    crosshairLine.style.display = 'block';
    crosshairDots.style.display = 'block';
    crosshairDots.innerHTML = '';
    const options = [];
    Object.keys(currentChart.series).forEach(key => {
      const vals = currentChart.series[key];
      let v = vals[bucket];
      if (v === undefined && currentChart.fill !== '0') return;
      if (v === undefined) v = 0;
      const yPix = currentChart.yScale(v);
      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', xPix);
      dot.setAttribute('cy', yPix);
      dot.setAttribute('r', '3');
      dot.setAttribute('fill', currentChart.seriesEls[key].color);
      crosshairDots.appendChild(dot);
      options.push({ key, y: yPix });
    });
    if (options.length) {
      let best = options[0];
      let bestDist = Math.abs(best.y - y);
      for (let i = 1; i < options.length; i++) {
        const d = Math.abs(options[i].y - y);
        if (d < bestDist) {
          best = options[i];
          bestDist = d;
        }
      }
      if (currentChart.selected && currentChart.selected !== best.key) {
        currentChart.seriesEls[currentChart.selected].highlight(false);
      }
      currentChart.seriesEls[best.key].highlight(true);
      currentChart.selected = best.key;
    }
  });

  if (resizeObserver) resizeObserver.disconnect();
  resizeObserver = new ResizeObserver(render);
  resizeObserver.observe(svg.parentElement);
}
