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
  const height = 600;
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
  let valueCols = selectedColumns.slice(groups.length + hasHits);
  if (
    valueCols.length === 0 &&
    document.getElementById('aggregate').value.toLowerCase() === 'count'
  ) {
    valueCols = ['Count'];
  }
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
    selected: null,
    frozen: false
  };

  const intervals = [
    {unit: 'second', step: 1, ms: 1000},
    {unit: 'second', step: 2, ms: 2000},
    {unit: 'second', step: 5, ms: 5000},
    {unit: 'second', step: 10, ms: 10000},
    {unit: 'second', step: 15, ms: 15000},
    {unit: 'second', step: 30, ms: 30000},
    {unit: 'minute', step: 1, ms: 60000},
    {unit: 'minute', step: 2, ms: 120000},
    {unit: 'minute', step: 5, ms: 300000},
    {unit: 'minute', step: 10, ms: 600000},
    {unit: 'minute', step: 15, ms: 900000},
    {unit: 'minute', step: 30, ms: 1800000},
    {unit: 'hour', step: 1, ms: 3600000},
    {unit: 'hour', step: 2, ms: 7200000},
    {unit: 'hour', step: 3, ms: 10800000},
    {unit: 'hour', step: 4, ms: 14400000},
    {unit: 'hour', step: 6, ms: 21600000},
    {unit: 'hour', step: 12, ms: 43200000},
    {unit: 'day', step: 1, ms: 86400000},
    {unit: 'day', step: 2, ms: 172800000},
    {unit: 'week', step: 1, ms: 604800000},
    {unit: 'week', step: 2, ms: 1209600000},
    {unit: 'month', step: 1},
    {unit: 'month', step: 3},
    {unit: 'month', step: 6},
    {unit: 'year', step: 1},
    {unit: 'year', step: 2},
    {unit: 'year', step: 5},
    {unit: 'year', step: 10}
  ];

  function chooseInterval(start, end) {
    const span = end - start;
    function approxMs(i) {
      if (i.ms) return i.ms;
      if (i.unit === 'month') return i.step * 2629800000;
      if (i.unit === 'year') return i.step * 31557600000;
      return 1000;
    }
    let best = intervals[0];
    let bestScore = Infinity;
    intervals.forEach(i => {
      const count = span / approxMs(i);
      const score = Math.abs(count - 15);
      if (score < bestScore) {
        best = i;
        bestScore = score;
      }
    });
    return best;
  }

  function generateTicks(start, end, intv) {
    const ticks = [];
    if (intv.unit === 'month' || intv.unit === 'year') {
      let d = new Date(start);
      d.setUTCDate(1);
      if (intv.unit === 'year') d.setUTCMonth(0);
      let unitVal =
        intv.unit === 'month'
          ? d.getUTCFullYear() * 12 + d.getUTCMonth()
          : d.getUTCFullYear();
      unitVal = Math.ceil(unitVal / intv.step) * intv.step;
      while (true) {
        const year =
          intv.unit === 'month' ? Math.floor(unitVal / 12) : unitVal;
        const month = intv.unit === 'month' ? unitVal % 12 : 0;
        const t = Date.UTC(year, month, 1);
        if (t > end) break;
        if (t >= start) ticks.push(t);
        unitVal += intv.step;
      }
    } else {
      const step = intv.ms * intv.step;
      let t = Math.ceil(start / step) * step;
      if (intv.unit === 'week') {
        const d = new Date(t);
        const adj = (d.getUTCDay() + 6) % 7;
        t = d.getTime() - adj * 86400000;
        t = Math.ceil(t / step) * step;
      }
      if (t === start) t += step;
      for (; t <= end; t += step) ticks.push(t);
    }
    return ticks;
  }

  function labelUnit(intv) {
    if (intv.unit === 'year') return 'year';
    if (intv.unit === 'month') return 'month';
    if (intv.unit === 'day' || intv.unit === 'week') return 'day';
    if (intv.unit === 'hour') return 'hour';
    return 'minute';
  }

  function fmt(date, unit) {
    const pad = n => String(n).padStart(2, '0');
    const mon = date.toLocaleString('en-US', {month: 'short'});
    switch (unit) {
      case 'year':
        return String(date.getFullYear());
      case 'month':
        if (date.getMonth() === 0) return String(date.getFullYear());
        return `${mon} ${date.getFullYear()}`;
      case 'day':
        if (date.getDate() === 1) return `${mon} ${date.getFullYear()}`;
        return `${date.getDate()} ${mon}`;
      case 'hour':
        if (date.getHours() === 0 && date.getMinutes() === 0)
          return `${date.getDate()} ${mon}`;
        return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
      default:
        if (date.getMinutes() === 0 && date.getSeconds() === 0)
          return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
        return `${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
    }
  }

  function niceNum(range, round) {
    const exponent = Math.floor(Math.log10(range));
    const fraction = range / Math.pow(10, exponent);
    let niceFraction;
    if (round) {
      if (fraction < 1.5) niceFraction = 1;
      else if (fraction < 3) niceFraction = 2;
      else if (fraction < 7) niceFraction = 5;
      else niceFraction = 10;
    } else {
      if (fraction <= 1) niceFraction = 1;
      else if (fraction <= 2) niceFraction = 2;
      else if (fraction <= 5) niceFraction = 5;
      else niceFraction = 10;
    }
    return niceFraction * Math.pow(10, exponent);
  }

  function niceTicks(min, max, count) {
    const range = niceNum(max - min || 1, false);
    const step = niceNum(range / Math.max(count - 1, 1), true);
    const start = Math.floor(min / step) * step;
    const end = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = start; v <= end; v += step) ticks.push(v);
    return ticks;
  }

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
    const grid = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    svg.appendChild(grid);
    const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const yTicks = niceTicks(minY, maxY, 10);
    yTicks.forEach(v => {
      const y = yScale(v);
      const gLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      gLine.setAttribute('x1', xScale(minX));
      gLine.setAttribute('x2', xScale(maxX));
      gLine.setAttribute('y1', y);
      gLine.setAttribute('y2', y);
      gLine.setAttribute('class', 'grid');
      grid.appendChild(gLine);

      const tick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      tick.setAttribute('x1', xScale(minX));
      tick.setAttribute('x2', xScale(minX) - 5);
      tick.setAttribute('y1', y);
      tick.setAttribute('y2', y);
      tick.setAttribute('stroke', '#000');
      yAxis.appendChild(tick);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', xScale(minX) - 8);
      text.setAttribute('y', y + 3);
      text.setAttribute('text-anchor', 'end');
      text.setAttribute('class', 'y-tick-label');
      text.textContent = formatNumber(v);
      yAxis.appendChild(text);
    });
    const seriesEls = {};
    const agg = document.getElementById('aggregate').value.toLowerCase();
    const groups = {};
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
      el.setAttribute('stroke-width', '1.3');
      svg.appendChild(el);
      const idx = key.lastIndexOf(':');
      const groupKey = idx === -1 ? 'all' : key.slice(0, idx);
      const name = idx === -1 ? key : key.slice(idx + 1);
      let group = groups[groupKey];
      if (!group) {
        const gEl = document.createElement('div');
        gEl.className = 'legend-group';
        const header = document.createElement('div');
        header.className = 'legend-header';
        header.textContent =
          groupKey === 'all' ? agg : `${groupKey} ${agg}`;
        gEl.appendChild(header);
        const items = document.createElement('div');
        items.className = 'legend-items';
        gEl.appendChild(items);
        legend.appendChild(gEl);
        group = {items};
        groups[groupKey] = group;
      }
      const item = document.createElement('div');
      item.className = 'legend-item';
      const label = document.createElement('span');
      label.textContent = name;
      label.style.color = color;
      const valueSpan = document.createElement('span');
      valueSpan.className = 'legend-value';
      item.appendChild(label);
      item.appendChild(valueSpan);
      group.items.appendChild(item);

      function highlight(on) {
        el.setAttribute('stroke-width', on ? '2.5' : '1.3');
        item.classList.toggle('highlight', on);
      }

      el.addEventListener('mouseenter', () => highlight(true));
      el.addEventListener('mouseleave', () => highlight(false));
      item.addEventListener('mouseenter', () => highlight(true));
      item.addEventListener('mouseleave', () => highlight(false));
      seriesEls[key] = { path: el, item, highlight, color, valueEl: valueSpan };
    });
    currentChart.seriesEls = seriesEls;
    currentChart.xScale = xScale;
    currentChart.yScale = yScale;
    currentChart.bucketPixels = buckets.map(xScale);
    svg.appendChild(crosshairLine);
    svg.appendChild(crosshairDots);

    const intv = chooseInterval(minX, maxX);
    const ticks = generateTicks(minX, maxX, intv);
    const lu = labelUnit(intv);
    const rotate = ticks.length > 0 && (width - 60) / ticks.length < 60;
    const axis = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const axisLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    axisLine.setAttribute('x1', xScale(minX));
    axisLine.setAttribute('x2', xScale(maxX));
    axisLine.setAttribute('y1', height - 30);
    axisLine.setAttribute('y2', height - 30);
    axisLine.setAttribute('stroke', '#888');
    axis.appendChild(axisLine);
    ticks.forEach(t => {
      const x = xScale(t);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x);
      line.setAttribute('y1', height - 30);
      line.setAttribute('x2', x);
      line.setAttribute('y2', height - 25);
      line.setAttribute('stroke', '#888');
      axis.appendChild(line);
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      const labelY = rotate ? height - 25 : height - 10;
      text.setAttribute('x', x);
      text.setAttribute('y', labelY);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('class', 'tick-label' + (rotate ? ' rotated' : ''));
      if (rotate) text.setAttribute('transform', `rotate(-45 ${x} ${labelY})`);
      text.textContent = fmt(new Date(t), lu);
      axis.appendChild(text);
    });
    svg.appendChild(axis);
    svg.appendChild(yAxis);

    const helper = document.createElement('div');
    helper.className = 'drill-links';
    const heading = document.createElement('h4');
    helper.appendChild(heading);
    if ((groupBy.chips || []).length) {
      heading.textContent = 'Drill up';
      const link = document.createElement('a');
      link.href = '#';
      link.textContent = 'Aggregate';
      link.addEventListener('click', e => {
        e.preventDefault();
        groupBy.chips = [];
        groupBy.renderChips();
        dive();
      });
      helper.appendChild(link);
    } else {
      heading.textContent = 'Group by';
      (allColumns || []).forEach(col => {
        const link = document.createElement('a');
        link.href = '#';
        link.textContent = col;
        link.addEventListener('click', e => {
          e.preventDefault();
          groupBy.addChip(col);
          groupBy.renderChips();
          dive();
        });
        helper.appendChild(link);
      });
    }
    legend.appendChild(helper);
  }

  render();

  function hideCrosshair() {
    if (currentChart.frozen) return;
    crosshairLine.style.display = 'none';
    crosshairDots.style.display = 'none';
    crosshairDots.innerHTML = '';
    Object.values(currentChart.seriesEls).forEach(el => {
      el.valueEl.textContent = '';
    });
    if (currentChart.selected) {
      currentChart.seriesEls[currentChart.selected].highlight(false);
      currentChart.selected = null;
    }
  }

  function updateCrosshair(e) {
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
      if (v === undefined && currentChart.fill !== '0') {
        currentChart.seriesEls[key].valueEl.textContent = '';
        return;
      }
      if (v === undefined) v = 0;
      currentChart.seriesEls[key].valueEl.textContent = formatNumber(v);
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
  }

  svg.addEventListener('mouseleave', hideCrosshair);
  svg.addEventListener('mousemove', e => {
    if (currentChart.frozen) return;
    updateCrosshair(e);
  });

  svg.addEventListener('click', e => {
    if (currentChart.frozen) {
      currentChart.frozen = false;
      hideCrosshair();
    } else {
      updateCrosshair(e);
      currentChart.frozen = true;
    }
  });

  if (resizeObserver) resizeObserver.disconnect();
  resizeObserver = new ResizeObserver(render);
  resizeObserver.observe(svg.parentElement);
}
