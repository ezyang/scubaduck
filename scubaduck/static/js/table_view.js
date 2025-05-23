// Logic for rendering the table based views.  Extracted from index.html so that
// the inline script only handles wiring up the UI.

let originalRows = [];
let sortState = { index: null, dir: null };

function renderTable(rows) {
  const table = document.getElementById("results");
  table.innerHTML = "";
  if (rows.length === 0) return;
  let hitsIndex = selectedColumns.indexOf("Hits");
  let totalHits = 0;
  if (hitsIndex !== -1) {
    totalHits = rows.reduce((s, r) => s + Number(r[hitsIndex]), 0);
  }
  const header = document.createElement("tr");
  selectedColumns.forEach((col, i) => {
    const th = document.createElement("th");
    let label = col;
    if (
      displayType === "table" &&
      col !== "Hits" &&
      !(groupBy.chips || []).includes(col)
    ) {
      const agg = document.getElementById("aggregate").value.toLowerCase();
      label += ` (${agg})`;
    }
    th.textContent = label;
    th.dataset.index = i;
    th.addEventListener("click", handleSort);
    if (sortState.index === i) {
      th.classList.add("sorted");
      th.textContent = label + (sortState.dir === "desc" ? " \u25BC" : " \u25B2");
    }
    th.style.textAlign = "left";
    header.appendChild(th);
  });
  table.appendChild(header);
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.addEventListener("click", () => {
      const wasSelected = tr.classList.contains("selected");
      document
        .querySelectorAll("#results tr.selected")
        .forEach((el) => el.classList.remove("selected"));
      if (!wasSelected) {
        tr.classList.add("selected");
      }
    });
    row.forEach((v, i) => {
      const col = selectedColumns[i];
      const td = document.createElement("td");
      if (isTimeColumn(col)) {
        let d;
        const t = (columnTypes[col] || "").toUpperCase();
        if (t.includes("TIMESTAMP") || t.includes("DATE") || t.includes("TIME")) {
          d = new Date(v);
        } else {
          const unit = document.getElementById("time_unit").value;
          const factors = { s: 1000, ms: 1, us: 0.001, ns: 0.000001 };
          d = new Date(Number(v) * (factors[unit] || 1000));
        }
        td.textContent = d.toLocaleString("en-US", {
          weekday: "short",
          month: "short",
          day: "numeric",
          year: "numeric",
          hour: "numeric",
          minute: "numeric",
          second: "numeric",
          hour12: true,
          timeZoneName: "short",
        });
        td.classList.add("date");
      } else {
        if (col === "Hits") {
          const pct = totalHits ? ((v / totalHits) * 100).toFixed(1) : "0";
          td.textContent = `${formatNumber(v)} (${pct}%)`;
        } else {
          td.textContent = isStringColumn(col) ? v : formatNumber(v);
        }
      }
      if (!isStringColumn(col) && !isTimeColumn(col)) {
        td.classList.add("numeric");
      }
      td.style.textAlign = isStringColumn(col) ? "left" : "right";
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  // ensure table does not overflow unless necessary
  const view = document.getElementById("view");
  if (table.scrollWidth <= view.clientWidth) {
    table.style.width = "100%";
  }
}

function handleSort(e) {
  const idx = parseInt(e.target.dataset.index, 10);
  if (sortState.index !== idx) {
    sortState.index = idx;
    sortState.dir = "asc";
  } else if (sortState.dir === "asc") {
    sortState.dir = "desc";
  } else if (sortState.dir === "desc") {
    sortState.index = null;
    sortState.dir = null;
  } else {
    sortState.dir = "asc";
  }
  let rows = originalRows.slice();
  if (sortState.index !== null) {
    rows.sort((a, b) => {
      const va = a[sortState.index];
      const vb = b[sortState.index];
      if (va === vb) return 0;
      if (sortState.dir === "desc") return va < vb ? 1 : -1;
      return va > vb ? 1 : -1;
    });
  }
  renderTable(rows);
}

function showResults(data) {
  window.lastResults = data;
  const hideHits =
    (graphTypeSel.value === "table" || graphTypeSel.value === "timeseries") &&
    !document.getElementById("show_hits").checked;
  if (hideHits && data.rows.length) {
    const groupCount =
      (graphTypeSel.value === "timeseries" ? 1 : 0) +
      ((groupBy.chips || []).length || 0);
    data.rows.forEach((r) => r.splice(groupCount, 1));
  }
  const view = document.getElementById("view");
  if (graphTypeSel.value === "timeseries") {
    showTimeSeries(data);
  } else {
    if (data.rows.length === 0) {
      view.innerHTML =
        '<p id="empty-message">Empty data provided to table</p><table id="results"></table>';
    } else {
      view.innerHTML = '<table id="results"></table>';
    }
    originalRows = data.rows.slice();
    sortState = { index: null, dir: null };
    renderTable(originalRows);
  }
  const sqlEl = document.createElement("pre");
  sqlEl.id = "sql_query";
  sqlEl.style.whiteSpace = "pre-wrap";
  sqlEl.style.marginTop = "10px";
  sqlEl.textContent = data.sql;
  view.appendChild(sqlEl);
  document.getElementById("query_info").textContent = `Your query took about ${lastQueryTime} ms`;
}

function showError(err) {
  window.lastResults = err;
  const view = document.getElementById("view");
  let msg = "";
  if (typeof err === "string") {
    msg = err;
  } else if (err) {
    msg = err.error || "Error";
    if (err.sql) {
      msg += "\nSQL: " + err.sql;
    }
    if (err.traceback) {
      msg += "\n" + err.traceback;
    }
  }
  view.innerHTML = `<pre id="error-message">${msg}</pre>`;
  document.getElementById("query_info").textContent = "";
}

