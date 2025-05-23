// Logic for View Settings, Columns, and URL handling extracted from index.html

const allColumns = [];
const baseColumns = [];
const columnTypes = {};
const stringColumns = [];
const baseStringColumns = [];
const integerColumns = [];
const baseIntegerColumns = [];
const timeColumns = [];
const baseTimeColumns = [];
const timeColumnOptions = [];
const baseTimeColumnOptions = [];
const derivedColumns = [];
let selectedColumns = [];
let displayType = 'samples';
let groupBy = {chips: [], addChip: () => {}, renderChips: () => {}};
let defaultTimeColumn = '';
const limitInput = document.getElementById('limit');
const defaultLimit = parseInt(limitInput.value, 10);
const limitValues = {
  samples: defaultLimit,
  table: defaultLimit,
  timeseries: 7
};
const columnValues = {
  samples: [],
  table: [],
  timeseries: []
};
limitInput.addEventListener('input', () => {
  limitValues[displayType] = parseInt(limitInput.value, 10);
  limitInput.dataset.setByUser = '1';
});

function initDropdown(select) {
  // Avoid creating duplicate wrappers if this dropdown was already initialised.
  if (select.dataset.dropdownInit) {
    const disp = select.parentElement?.querySelector('.dropdown-display');
    if (disp) {
      const opt = select.options[select.selectedIndex];
      disp.textContent = opt ? opt.textContent : '';
    }
    return;
  }
  select.dataset.dropdownInit = '1';

  const wrapper = document.createElement('div');
  wrapper.className = 'dropdown';
  if (select.classList.contains('f-col')) {
    wrapper.classList.add('f-col');
  }
  select.parentNode.insertBefore(wrapper, select);
  wrapper.appendChild(select);
  select.style.display = 'none';
  const disp = document.createElement('div');
  disp.className = 'dropdown-display';
  function updateDisplay() {
    const opt = select.options[select.selectedIndex];
    disp.textContent = opt ? opt.textContent : '';
  }
  updateDisplay();
  wrapper.appendChild(disp);
  const menu = document.createElement('div');
  menu.className = 'dropdown-menu';
  const search = document.createElement('input');
  search.placeholder = 'Search';
  menu.appendChild(search);
  const list = document.createElement('div');
  menu.appendChild(list);
  wrapper.appendChild(menu);

  function close() {
    menu.style.display = 'none';
  }

  function open() {
    renderOptions();
    menu.style.display = 'block';
    requestAnimationFrame(() => {
      const selected = list.querySelector('.selected');
      if (selected) {
        const offset = selected.offsetTop - search.offsetHeight - 4;
        menu.scrollTop = offset > 0 ? offset : 0;
      }
    });
    search.focus();
  }

  disp.addEventListener('click', () => {
    if (menu.style.display === 'block') {
      close();
    } else {
      open();
    }
  });

  document.addEventListener('click', e => {
    if (!wrapper.contains(e.target)) {
      close();
    }
  });

  function renderOptions() {
    const q = search.value.toLowerCase();
    list.innerHTML = '';
    Array.from(select.options).forEach(o => {
      if (!o.textContent.toLowerCase().includes(q)) return;
      const div = document.createElement('div');
      div.className = 'option';
      if (q) {
        const text = o.textContent;
        const idx = text.toLowerCase().indexOf(q);
        if (idx !== -1) {
          div.innerHTML =
            text.slice(0, idx) +
            '<u>' +
            text.slice(idx, idx + q.length) +
            '</u>' +
            text.slice(idx + q.length);
        } else {
          div.textContent = text;
        }
      } else {
        div.textContent = o.textContent;
      }
      if (o.value === select.value) div.classList.add('selected');
      div.addEventListener('mousedown', evt => {
        evt.preventDefault();
        select.value = o.value;
        select.dispatchEvent(new Event('change'));
        updateDisplay();
        close();
      });
      list.appendChild(div);
    });
  }

  search.addEventListener('input', renderOptions);
  select.addEventListener('change', updateDisplay);
}
let orderDir = 'ASC';
const orderDirBtn = document.getElementById('order_dir');
const graphTypeSel = document.getElementById('graph_type');
function updateOrderDirButton() {
  orderDirBtn.textContent = orderDir + (orderDir === 'ASC' ? ' \u25B2' : ' \u25BC');
}

function updateDisplayTypeUI() {
  const prevType = displayType;
  updateSelectedColumns(prevType);
  const newType = graphTypeSel.value;
  const showTable = newType === 'table';
  const showTS = newType === 'timeseries';
  document.getElementById('group_by_field').style.display = showTable || showTS ? 'flex' : 'none';
  document.getElementById('aggregate_field').style.display = showTable || showTS ? 'flex' : 'none';
  document.getElementById('show_hits_field').style.display = showTable ? 'flex' : 'none';
  document.getElementById('x_axis_field').style.display = showTS ? 'flex' : 'none';
  document.getElementById('granularity_field').style.display = showTS ? 'flex' : 'none';
  document.getElementById('fill_field').style.display = showTS ? 'flex' : 'none';
  document.querySelectorAll('#column_groups .col-group').forEach(g => {
    if (g.querySelector('.col-group-header').textContent.startsWith('Strings')) {
      g.style.display = showTable || showTS ? 'none' : '';
    }
  });
  limitValues[prevType] = parseInt(limitInput.value, 10);
  if (showTS && limitValues.timeseries === undefined) {
    limitValues.timeseries = 7;
  }
  limitInput.value = limitValues[newType];
  document.querySelectorAll('#column_groups input').forEach(cb => {
    cb.checked = columnValues[newType].includes(cb.value);
  });
  if (showTS) {
    document.querySelectorAll('#column_groups input').forEach(cb => {
      if (isTimeColumn(cb.value) || isStringColumn(cb.value)) {
        cb.checked = false;
      }
    });
    document.getElementById('order_by').value = '';
  }
  updateSelectedColumns(newType);
  displayType = newType;
}
function updateTimeFieldVisibility() {
  const show = document.getElementById('time_column').value !== '';
  document.getElementById('start').closest('.field').style.display = show
    ? 'flex'
    : 'none';
  document.getElementById('end').closest('.field').style.display = show
    ? 'flex'
    : 'none';
  document.getElementById('time_unit').style.display = show ? '' : 'none';
}
orderDirBtn.addEventListener('click', () => {
  orderDir = orderDir === 'ASC' ? 'DESC' : 'ASC';
  updateOrderDirButton();
});
updateOrderDirButton();
graphTypeSel.addEventListener('change', updateDisplayTypeUI);
document.getElementById('time_column').addEventListener('change', updateTimeFieldVisibility);
updateTimeFieldVisibility();

function loadColumns(table) {
  return fetch('/api/columns?table=' + encodeURIComponent(table)).then(r => r.json()).then(cols => {
    const orderSelect = document.getElementById('order_by');
    const xAxisSelect = document.getElementById('x_axis');
    const groupsEl = document.getElementById('column_groups');
    const timeColumnSelect = document.getElementById('time_column');
    orderSelect.innerHTML = '';
    const orderDef = document.createElement('option');
    orderDef.value = '';
    orderDef.textContent = '(default)';
    orderSelect.appendChild(orderDef);
    const samplesOpt = document.createElement('option');
    samplesOpt.value = 'Samples';
    samplesOpt.textContent = 'Samples';
    orderSelect.appendChild(samplesOpt);
    xAxisSelect.innerHTML = '';
    const defOpt = document.createElement('option');
    defOpt.value = '';
    defOpt.textContent = '(default)';
    xAxisSelect.appendChild(defOpt);
    timeColumnSelect.innerHTML = '';
    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.textContent = '(none)';
    timeColumnSelect.appendChild(noneOpt);
    groupsEl.innerHTML = '';
    allColumns.length = 0;
    stringColumns.length = 0;
    integerColumns.length = 0;
    timeColumns.length = 0;
    timeColumnOptions.length = 0;
    baseColumns.length = 0;
    baseStringColumns.length = 0;
    baseIntegerColumns.length = 0;
    baseTimeColumns.length = 0;
    baseTimeColumnOptions.length = 0;
    for (const k in columnTypes) delete columnTypes[k];
    const groups = {
      time: {name: 'Time', cols: [], ul: null},
      integer: {name: 'Integers', cols: [], ul: null},
      string: {name: 'Strings', cols: [], ul: null},
    };
    cols.forEach(c => {
      const t = c.type.toUpperCase();
      columnTypes[c.name] = c.type;
      allColumns.push(c.name);
      baseColumns.push(c.name);
      let g = 'string';
      const isNumeric = t.includes('INT') || t.includes('DECIMAL') || t.includes('NUMERIC') || t.includes('REAL') || t.includes('DOUBLE') || t.includes('FLOAT') || t.includes('HUGEINT');
      const isTimeType = t.includes('TIMESTAMP') || t.includes('DATE') || t.includes('TIME');
      if (isNumeric || isTimeType) {
        timeColumnOptions.push(c.name);
        baseTimeColumnOptions.push(c.name);
      }
      if (isTimeType) {
        g = 'time';
        timeColumns.push(c.name);
        baseTimeColumns.push(c.name);
      } else if (isNumeric) {
        g = 'integer';
      }
      if (g === 'string') {
        stringColumns.push(c.name);
        baseStringColumns.push(c.name);
      } else if (g === 'integer') {
        integerColumns.push(c.name);
        baseIntegerColumns.push(c.name);
      }
      groups[g].cols.push(c.name);
      if (g !== 'string') {
        const o = document.createElement('option');
        o.value = c.name;
        o.textContent = c.name;
        orderSelect.appendChild(o);
      }
    });
    timeColumns.forEach(name => {
      const o = document.createElement('option');
      o.value = name;
      o.textContent = name;
      xAxisSelect.appendChild(o);
    });
    timeColumnOptions.forEach(name => {
      const o = document.createElement('option');
      o.value = name;
      o.textContent = name;
      timeColumnSelect.appendChild(o);
    });
    xAxisSelect.value = '';
    defaultTimeColumn = guessTimeColumn(cols) || '';
    updateTimeFieldVisibility();
    Object.keys(groups).forEach(key => {
      const g = groups[key];
      const div = document.createElement('div');
      div.className = 'col-group';
      const header = document.createElement('div');
      header.className = 'col-group-header';
      header.appendChild(document.createTextNode(g.name + ': '));
      const links = document.createElement('span');
      links.className = 'links';
      const allBtn = document.createElement('a');
      allBtn.href = '#';
      allBtn.textContent = 'All';
      const noneBtn = document.createElement('a');
      noneBtn.href = '#';
      noneBtn.textContent = 'None';
      links.appendChild(allBtn);
      links.appendChild(noneBtn);
      header.appendChild(links);
      div.appendChild(header);
      const ul = document.createElement('ul');
      g.ul = ul;
      g.cols.forEach(name => {
        const li = document.createElement('li');
        const label = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = name;
        cb.checked = true;
        cb.addEventListener('change', updateSelectedColumns);
        label.appendChild(cb);
        label.appendChild(document.createTextNode(' ' + name));
        li.appendChild(label);
        ul.appendChild(li);
      });
      allBtn.addEventListener('click', e => {
        e.preventDefault();
        ul.querySelectorAll('input').forEach(cb => (cb.checked = true));
        updateSelectedColumns();
      });
      noneBtn.addEventListener('click', e => {
        e.preventDefault();
        ul.querySelectorAll('input').forEach(cb => (cb.checked = false));
        updateSelectedColumns();
      });
      div.appendChild(ul);
      groupsEl.appendChild(div);
    });
    document.getElementById('columns_all').addEventListener('click', e => {
      e.preventDefault();
      groupsEl.querySelectorAll('input').forEach(cb => (cb.checked = true));
      updateSelectedColumns();
    });
    document.getElementById('columns_none').addEventListener('click', e => {
      e.preventDefault();
      groupsEl.querySelectorAll('input').forEach(cb => (cb.checked = false));
      updateSelectedColumns();
    });
    updateSelectedColumns();
    columnValues.samples = allColumns.slice();
    columnValues.table = [];
    columnValues.timeseries = [];
    groupBy = document.getElementById('group_by').closest('.field');
    initChipInput(groupBy, typed =>
      allColumns.filter(c => c.toLowerCase().includes(typed.toLowerCase()))
    );
    initDropdown(orderSelect);
    initDropdown(document.getElementById('aggregate'));
  });
}

let columnsInitialized = false;
  fetch('/api/tables').then(r => r.json()).then(tables => {
    const tableSel = document.getElementById('table');
    tables.forEach(t => {
      const o = document.createElement('option');
      o.value = t;
      o.textContent = t;
      tableSel.appendChild(o);
    });
    initDropdown(tableSel);
    const measure = document.createElement('span');
    measure.style.visibility = 'hidden';
    measure.style.position = 'absolute';
    document.body.appendChild(measure);
    let maxWidth = 0;
    tables.forEach(t => {
      measure.textContent = t;
      const w = measure.getBoundingClientRect().width;
      if (w > maxWidth) maxWidth = w;
    });
    measure.remove();
    const disp = tableSel.parentElement.querySelector('.dropdown-display');
    if (disp) disp.style.minWidth = maxWidth + 30 + 'px';
    const table = parseSearch().table || tables[0];
    tableSel.value = table;
    tableSel.dispatchEvent(new Event('change'));
  loadColumns(table).then(() => {
    updateDisplayTypeUI();
    addFilter();
    initFromUrl();
    columnsInitialized = true;
  });
  tableSel.addEventListener('change', () => {
    loadColumns(tableSel.value).then(() => {
      if (columnsInitialized) {
        resetViewSettings();
        applyParams({table: tableSel.value});
      }
    });
  });
});

document.querySelectorAll('#tabs .tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#tabs .tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

document.querySelectorAll('.rel-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const dd = document.getElementById(btn.dataset.target);
    const show = dd.style.display === 'none' || dd.style.display === '';
    document.querySelectorAll('.rel-dropdown').forEach(d => (d.style.display = 'none'));
    dd.style.display = show ? 'block' : 'none';
  });
});
document.querySelectorAll('.rel-dropdown div').forEach(opt => {
  opt.addEventListener('click', () => {
    const box = opt.closest('.rel-box');
    const input = box.querySelector('input');
    input.value = opt.dataset.value || opt.textContent;
    opt.parentElement.style.display = 'none';
  });
});

document.addEventListener('click', e => {
  document.querySelectorAll('.rel-dropdown').forEach(dd => {
    if (!dd.parentElement.contains(e.target)) dd.style.display = 'none';
  });
});

function updateColumnsTabCount() {
  const baseCount = document.querySelectorAll('#column_groups input:checked').length;
  const derivedCount = document.querySelectorAll('#derived_list .derived .d-use:checked').length;
  const btn = document.getElementById('columns_tab');
  if (btn) btn.textContent = `Columns (${baseCount + derivedCount})`;
}

function updateSelectedColumns(type = graphTypeSel.value) {
  const base = allColumns.filter(name => {
    const cb = document.querySelector(`#column_groups input[value="${name}"]`);
    if (!cb || !cb.checked) return false;
    if (type === 'table' && isStringColumn(name)) return false;
    return true;
  });
  if (type === 'table' || type === 'timeseries') {
    selectedColumns = groupBy.chips.slice();
    if (document.getElementById('show_hits').checked) selectedColumns.push('Hits');
    const agg = document.getElementById('aggregate').value.toLowerCase();
    if (!(type === 'table' && agg === 'count')) {
      base.forEach(c => {
        if (!selectedColumns.includes(c)) selectedColumns.push(c);
      });
      derivedColumns.forEach(dc => {
        if (dc.include && !selectedColumns.includes(dc.name)) selectedColumns.push(dc.name);
      });
    }
  } else {
    selectedColumns = base.slice();
    derivedColumns.forEach(dc => {
      if (dc.include) selectedColumns.push(dc.name);
    });
  }
  columnValues[type] = selectedColumns.slice();
  const orderCol = document.getElementById('order_by').value;
  if (orderCol && !selectedColumns.includes(orderCol)) {
    selectedColumns.push(orderCol);
  }
  updateColumnsTabCount();
}

function isStringColumn(name) {
  const t = (columnTypes[name] || '').toUpperCase();
  return t.includes('CHAR') || t.includes('STRING') || t.includes('VARCHAR');
}

function isIntegerColumn(name) {
  const t = (columnTypes[name] || '').toUpperCase();
  return t.includes('INT');
}

function isTimeColumn(name) {
  const t = (columnTypes[name] || '').toUpperCase();
  if (t.includes('TIMESTAMP') || t.includes('DATE') || t.includes('TIME')) return true;
  const sel = document.getElementById('time_column').value;
  const xsel = document.getElementById('x_axis').value;
  if (name === sel || name === xsel) return true;
  return false;
}

function formatNumber(val) {
  if (typeof val !== 'number') val = Number(val);
  if (Number.isNaN(val)) return '';
  if (val === 0) return '0';
  const abs = Math.abs(val);
  if (abs > 999.999) {
    const units = [
      {n: 1e12, s: 'T'},
      {n: 1e9, s: 'B'},
      {n: 1e6, s: 'M'},
      {n: 1e3, s: 'K'},
    ];
    for (const u of units) {
      if (abs >= u.n) {
        return (val / u.n).toFixed(2) + ' ' + u.s;
      }
    }
  }
  if (abs < 0.0005) return '0.000';
  if (Number.isInteger(val)) return val.toString();
  return val.toFixed(3);
}


function addFilter() {
  const container = document.createElement('div');
  container.className = 'filter';
  container.innerHTML = `
    <div class="filter-row">
      <select class="f-col"></select>
      <select class="f-op"></select>
      <button type="button" class="remove" onclick="this.closest('.filter').remove()">✖</button>
    </div>
    <div class="chip-box">
      <div class="chip-input">
        <input class="f-val" type="text">
        <button type="button" class="chip-copy">&#x2398;</button>
      </div>
      <div class="chip-dropdown"></div>
    </div>
  `;
  const colSel = container.querySelector('.f-col');
  colSel.innerHTML = allColumns.map(c => `<option value="${c}">${c}</option>`).join('');
  initDropdown(colSel);

  function populateOps() {
    const opSel = container.querySelector('.f-op');
    const col = colSel.value;
    const ops = isStringColumn(col)
      ? [
          ['=', '='],
          ['!=', '!='],
          ['~', 'matches regex'],
          ['!~', 'not matches regex'],
          ['contains', 'contains'],
          ['!contains', 'not contains'],
          ['empty', 'empty'],
          ['!empty', 'not empty'],
          ['LIKE', 'like'],
        ]
      : [
          ['=', '='],
          ['!=', '!='],
          ['<', '<'],
          ['>', '>'],
        ];
    opSel.innerHTML = ops.map(o => `<option value="${o[0]}">${o[1]}</option>`).join('');
    updateInputVis();
  }

  function updateInputVis() {
    const op = container.querySelector('.f-op').value;
    const box = container.querySelector('.chip-box');
    box.style.display = op === 'empty' || op === '!empty' ? 'none' : 'block';
  }

  colSel.addEventListener('change', populateOps);
  container.querySelector('.f-op').addEventListener('change', updateInputVis);
  populateOps();
  document.getElementById('filter_list').appendChild(container);
  initChipInput(container, (typed, el) => {
    const colEl = el.querySelector('.f-col select') || el.querySelector('.f-col');
    if (!colEl) return [];
    const col = colEl.value;
    if (!isStringColumn(col)) return [];
    return fetch(`/api/samples?column=${encodeURIComponent(col)}&q=${encodeURIComponent(typed)}`)
      .then(r => r.json());
  });
}

function nextDerivedName() {
  let n = 1;
  while (true) {
    const name = `derived_${n}`;
    if (!derivedColumns.some(d => d.name === name) && !allColumns.includes(name)) return name;
    n++;
  }
}

function addDerived(data = {}) {
  const container = document.createElement('div');
  container.className = 'derived';
  container.innerHTML = `
    <div class="derived-row">
      <select class="d-type">
        <option value="aggregated">Aggregated</option>
        <option value="string">String</option>
        <option value="numeric">Numeric</option>
      </select>
      <input class="d-name" type="text">
      <button type="button" class="remove" onclick="removeDerived(this)">✖</button>
    </div>
    <label><input type="checkbox" class="d-use" checked> Include in Query</label>
    <textarea class="d-expr" rows="2"></textarea>
  `;
  document.getElementById('derived_list').appendChild(container);
  const obj = {
    type: data.type || 'string',
    name: data.name || nextDerivedName(),
    expr: data.expr || '',
    include: data.include !== undefined ? data.include : true,
    el: container
  };
  container.querySelector('.d-type').value = obj.type;
  container.querySelector('.d-name').value = obj.name;
  container.querySelector('.d-expr').value = obj.expr;
  container.querySelector('.d-use').checked = obj.include;
  ['change','input'].forEach(evt => {
    container.addEventListener(evt, refreshDerivedColumns);
  });
  derivedColumns.push(obj);
  refreshDerivedColumns();
}

function removeDerived(btn) {
  const el = btn.closest('.derived');
  const idx = derivedColumns.findIndex(d => d.el === el);
  if (idx !== -1) {
    derivedColumns.splice(idx, 1);
  }
  el.remove();
  refreshDerivedColumns();
}

function refreshDerivedColumns() {
  allColumns.splice(0, allColumns.length, ...baseColumns);
  stringColumns.splice(0, stringColumns.length, ...baseStringColumns);
  integerColumns.splice(0, integerColumns.length, ...baseIntegerColumns);
  timeColumns.splice(0, timeColumns.length, ...baseTimeColumns);
  timeColumnOptions.splice(0, timeColumnOptions.length, ...baseTimeColumnOptions);
  derivedColumns.forEach(d => {
    d.type = d.el.querySelector('.d-type').value;
    d.name = d.el.querySelector('.d-name').value;
    d.expr = d.el.querySelector('.d-expr').value;
    d.include = d.el.querySelector('.d-use').checked;
    allColumns.push(d.name);
    columnTypes[d.name] = d.type;
    if (d.type === 'string') {
      stringColumns.push(d.name);
    } else {
      integerColumns.push(d.name);
      timeColumnOptions.push(d.name);
    }
  });
  updateSelectedColumns();
}

let lastQueryTime = 0;
let queryStart = 0;

function dive(push=true) {
  const params = collectParams();
  if (push) {
    history.pushState(params, '', paramsToSearch(params));
  }
  const payload = Object.assign({}, params);
  const dcMap = {};
  (params.derived_columns || []).forEach(d => {
    if (d.include) dcMap[d.name] = d.expr;
  });
  payload.derived_columns = dcMap;
  const view = document.getElementById('view');
  view.innerHTML = '<p>Loading...</p>';
  window.lastResults = undefined;
  queryStart = performance.now();
  fetch('/api/query', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
    .then(async r => {
      const data = await r.json();
      if (!r.ok) throw data;
      return data;
    })
    .then(data => {
      lastQueryTime = Math.round(performance.now() - queryStart);
      showResults(data);
    })
    .catch(err => {
      showError(err);
    });
}

function collectParams() {
  updateSelectedColumns();
  const payload = {
    table: document.getElementById('table').value,
    time_column: document.getElementById('time_column').value,
    time_unit: document.getElementById('time_unit').value,
    start: document.getElementById('start').value,
    end: document.getElementById('end').value,
    order_by: document.getElementById('order_by').value,
    order_dir: orderDir,
    limit: parseInt(document.getElementById('limit').value, 10),
    columns: selectedColumns.filter(c =>
      c !== 'Hits' && !derivedColumns.some(dc => dc.name === c)
    ),
    samples_columns: columnValues.samples.slice(),
    table_columns: columnValues.table.slice(),
    timeseries_columns: columnValues.timeseries.slice(),
    graph_type: graphTypeSel.value,
    filters: Array.from(document.querySelectorAll('#filters .filter')).map(f => {
      const chips = f.chips || [];
      const op = f.querySelector('.f-op').value;
      let value = null;
      if (op !== 'empty' && op !== '!empty') {
        value = chips.length === 0 ? null : (chips.length === 1 ? chips[0] : chips);
      }
      const colSel = f.querySelector('.f-col select') || f.querySelector('.f-col');
      return {column: colSel.value, op, value};
    }),
    derived_columns: Array.from(document.querySelectorAll('#derived_list .derived')).map(d => ({
      type: d.querySelector('.d-type').value,
      name: d.querySelector('.d-name').value,
      expr: d.querySelector('.d-expr').value,
      include: d.querySelector('.d-use').checked,
    }))
  };
  if (graphTypeSel.value === 'table' || graphTypeSel.value === 'timeseries') {
    payload.group_by = groupBy.chips || [];
    payload.aggregate = document.getElementById('aggregate').value;
    payload.show_hits = document.getElementById('show_hits').checked;
  }
  if (graphTypeSel.value === 'timeseries') {
    const xval = document.getElementById('x_axis').value;
    if (xval) payload.x_axis = xval;
    payload.granularity = document.getElementById('granularity').value;
    payload.fill = document.getElementById('fill').value;
  }
  return payload;
}

function paramsToSearch(params) {
  const sp = new URLSearchParams();
  if (params.table) sp.set('table', params.table);
  if (params.time_column) sp.set('time_column', params.time_column);
  if (params.time_unit) sp.set('time_unit', params.time_unit);
  if (params.start) sp.set('start', params.start);
  if (params.end) sp.set('end', params.end);
  if (params.order_by) sp.set('order_by', params.order_by);
  if (params.order_dir) sp.set('order_dir', params.order_dir);
  if (params.limit !== null && params.limit !== undefined) sp.set('limit', params.limit);
  if (params.samples_columns && params.samples_columns.length) sp.set('samples_columns', params.samples_columns.join(','));
  if (params.table_columns && params.table_columns.length) sp.set('table_columns', params.table_columns.join(','));
  if (params.timeseries_columns && params.timeseries_columns.length) sp.set('timeseries_columns', params.timeseries_columns.join(','));
  if (params.filters && params.filters.length) sp.set('filters', JSON.stringify(params.filters));
  if (params.derived_columns && params.derived_columns.length) sp.set('derived_columns', JSON.stringify(params.derived_columns));
  if (params.graph_type) sp.set('graph_type', params.graph_type);
  if (params.graph_type === 'table' || params.graph_type === 'timeseries') {
    if (params.group_by && params.group_by.length) sp.set('group_by', params.group_by.join(','));
    if (params.aggregate) sp.set('aggregate', params.aggregate);
    if (params.show_hits) sp.set('show_hits', '1');
  }
  if (params.graph_type === 'timeseries') {
    if (params.x_axis) sp.set('x_axis', params.x_axis);
    if (params.granularity) sp.set('granularity', params.granularity);
    if (params.fill) sp.set('fill', params.fill);
  }
  const qs = sp.toString();
  return qs ? '?' + qs : '';
}

function applyParams(params) {
  if (params.table) document.getElementById('table').value = params.table;
  document.getElementById('time_column').value = params.time_column || defaultTimeColumn;
  updateTimeFieldVisibility();
  if (params.time_unit) document.getElementById('time_unit').value = params.time_unit;
  document.getElementById('start').value = params.start || '';
  document.getElementById('end').value = params.end || '';
  if (params.order_by) {
    document.getElementById('order_by').value = params.order_by;
  }
  orderDir = params.order_dir || 'ASC';
  updateOrderDirButton();
  if (params.limit !== undefined && params.limit !== null) {
    document.getElementById('limit').value = params.limit;
    limitValues[params.graph_type || 'samples'] = params.limit;
    limitInput.dataset.setByUser = '1';
  }
  graphTypeSel.value = params.graph_type || 'samples';
  updateDisplayTypeUI();
  limitInput.value = limitValues[graphTypeSel.value];
  if (params.x_axis) {
    document.getElementById('x_axis').value = params.x_axis;
  } else {
    document.getElementById('x_axis').value = '';
  }
  if (params.granularity) document.getElementById('granularity').value = params.granularity;
  if (params.fill) document.getElementById('fill').value = params.fill;
  if (params.group_by) {
    groupBy.chips.splice(0, groupBy.chips.length, ...params.group_by);
    groupBy.renderChips();
  }
  if (params.aggregate) document.getElementById('aggregate').value = params.aggregate;
  document.getElementById('show_hits').checked = params.show_hits ?? true;
  if (params.samples_columns) columnValues.samples = params.samples_columns;
  if (params.table_columns) columnValues.table = params.table_columns;
  if (params.timeseries_columns) columnValues.timeseries = params.timeseries_columns;
  document.querySelectorAll('#column_groups input').forEach(cb => {
    cb.checked = columnValues[graphTypeSel.value].includes(cb.value);
  });
  updateSelectedColumns(graphTypeSel.value);
  const dlist = document.getElementById('derived_list');
  dlist.innerHTML = '';
  derivedColumns.splice(0, derivedColumns.length);
  if (params.derived_columns && params.derived_columns.length) {
    params.derived_columns.forEach(dc => addDerived(dc));
  }
  refreshDerivedColumns();
  const list = document.getElementById('filter_list');
  list.innerHTML = '';
  if (params.filters && params.filters.length) {
    params.filters.forEach(f => {
      addFilter();
      const el = list.lastElementChild;
      const colSel = el.querySelector('.f-col select') || el.querySelector('.f-col');
      colSel.value = f.column;
      colSel.dispatchEvent(new Event('change'));
      el.querySelector('.f-op').value = f.op;
      el.querySelector('.f-op').dispatchEvent(new Event('change'));
      if (f.value !== null && f.op !== 'empty' && f.op !== '!empty') {
        const values = Array.isArray(f.value) ? f.value : [f.value];
        values.forEach(v => el.addChip(v));
        el.renderChips();
      }
    });
  } else {
    addFilter();
  }
}

function resetViewSettings() {
  orderDir = 'ASC';
  updateOrderDirButton();
  document.getElementById('order_by').value = '';
  document.getElementById('start').value = '';
  document.getElementById('end').value = '';
  document.getElementById('time_unit').value = 's';
  document.getElementById('granularity').value = 'Auto';
  document.getElementById('fill').value = '0';
  document.getElementById('aggregate').value = 'Count';
  document.getElementById('show_hits').checked = true;
  document.getElementById('x_axis').value = '';
  groupBy.chips.splice(0, groupBy.chips.length);
  groupBy.renderChips();
  const dlist = document.getElementById('derived_list');
  dlist.innerHTML = '';
  derivedColumns.splice(0, derivedColumns.length);
  refreshDerivedColumns();
  const flist = document.getElementById('filter_list');
  flist.innerHTML = '';
  addFilter();
  document.getElementById('graph_type').value = 'samples';
  limitValues.samples = defaultLimit;
  limitValues.table = defaultLimit;
  limitValues.timeseries = 7;
  limitInput.dataset.setByUser = '';
  updateDisplayTypeUI();
  document.querySelectorAll('#column_groups input').forEach(cb => {
    cb.checked = true;
  });
  updateSelectedColumns();
}

function parseSearch() {
  const sp = new URLSearchParams(window.location.search);
  const params = {};
  if (sp.has('table')) params.table = sp.get('table');
  if (sp.has('time_column')) params.time_column = sp.get('time_column');
  if (sp.has('time_unit')) params.time_unit = sp.get('time_unit');
  if (sp.has('start')) params.start = sp.get('start');
  if (sp.has('end')) params.end = sp.get('end');
  if (sp.has('order_by')) params.order_by = sp.get('order_by');
  if (sp.has('order_dir')) params.order_dir = sp.get('order_dir');
  if (sp.has('limit')) params.limit = parseInt(sp.get('limit'), 10);
  if (sp.has('samples_columns')) params.samples_columns = sp.get('samples_columns').split(',').filter(c => c);
  if (sp.has('table_columns')) params.table_columns = sp.get('table_columns').split(',').filter(c => c);
  if (sp.has('timeseries_columns')) params.timeseries_columns = sp.get('timeseries_columns').split(',').filter(c => c);
  if (sp.has('filters')) {
    try { params.filters = JSON.parse(sp.get('filters')); } catch(e) { params.filters = []; }
  }
  if (sp.has('graph_type')) params.graph_type = sp.get('graph_type');
  if (sp.has('group_by')) params.group_by = sp.get('group_by').split(',').filter(c => c);
  if (sp.has('aggregate')) params.aggregate = sp.get('aggregate');
  if (sp.has('show_hits')) params.show_hits = sp.get('show_hits') === '1';
  if (sp.has('x_axis')) params.x_axis = sp.get('x_axis');
  if (sp.has('granularity')) params.granularity = sp.get('granularity');
  if (sp.has('fill')) params.fill = sp.get('fill');
  if (sp.has('derived_columns')) {
    try { params.derived_columns = JSON.parse(sp.get('derived_columns')); } catch(e) { params.derived_columns = []; }
  }
  return params;
}

function initFromUrl() {
  const params = parseSearch();
  history.replaceState(params, '', paramsToSearch(params));
  applyParams(params);
  dive(false);
}

window.addEventListener('popstate', e => {
  const params = e.state || parseSearch();
  applyParams(params);
  dive(false);
});

function setSelectValue(selector, value) {
  const el = typeof selector === 'string' ? document.querySelector(selector) : selector;
  if (el) {
    const select = el.tagName === 'SELECT' ? el : el.querySelector('select');
    if (select) {
      select.value = value;
      select.dispatchEvent(new Event('change'));
    }
  }
}
