from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, OrderedDict

import duckdb
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

# Initialize DuckDB in-memory and load sample data
con = duckdb.connect()
con.execute(
    "CREATE TABLE IF NOT EXISTS events AS SELECT * FROM read_csv_auto('scubaduck/sample.csv')"
)

# Column type lookup
_columns_info = {
    r[1]: r[2] for r in con.execute("PRAGMA table_info(events)").fetchall()
}

# Simple LRU cache for sample value queries
_sample_cache: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
_CACHE_LIMIT = 100


def _is_string_column(col: str) -> bool:
    typ = _columns_info.get(col, "").upper()
    for part in ("INT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC", "FLOAT"):
        if part in typ:
            return False
    return True


@dataclass
class Filter:
    column: str
    op: str
    value: str | int | float | list[str] | None


@dataclass
class QueryParams:
    start: str | None = None
    end: str | None = None
    order_by: str | None = None
    order_dir: str = "ASC"
    limit: int | None = None
    columns: list[str] = field(default_factory=lambda: [])
    filters: list[Filter] = field(default_factory=lambda: [])
    derived_columns: dict[str, str] = field(default_factory=lambda: {})


@app.route("/")
def index() -> Any:
    assert app.static_folder is not None
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/columns")
def columns() -> Any:
    rows = con.execute("PRAGMA table_info(events)").fetchall()
    return jsonify([{"name": r[1], "type": r[2]} for r in rows])


@app.route("/api/samples")
def sample_values() -> Any:
    column = request.args.get("column")
    query = request.args.get("q", "")
    if not column or not _is_string_column(column):
        return jsonify([])
    key = (column, query)
    if key in _sample_cache:
        _sample_cache.move_to_end(key)
        return jsonify(_sample_cache[key])
    sql = f"SELECT DISTINCT {column} FROM events WHERE {column} ILIKE ? ORDER BY 1 LIMIT 20"
    rows = con.execute(sql, [f"%{query}%"]).fetchall()
    values = [r[0] for r in rows]
    _sample_cache[key] = values
    if len(_sample_cache) > _CACHE_LIMIT:
        _sample_cache.popitem(last=False)
    return jsonify(values)


def build_query(params: QueryParams) -> str:
    select_parts = [*params.columns]
    for name, expr in params.derived_columns.items():
        select_parts.append(f"{expr} AS {name}")
    select_clause = ", ".join(select_parts) if select_parts else "*"
    query = f"SELECT {select_clause} FROM events"
    where_parts: list[str] = []
    if params.start:
        where_parts.append(f"timestamp >= '{params.start}'")
    if params.end:
        where_parts.append(f"timestamp <= '{params.end}'")
    for f in params.filters:
        if f.value is None:
            continue
        if isinstance(f.value, list):
            if not f.value:
                continue
            if f.op == "=":
                vals = " OR ".join(f"{f.column} = '{v}'" for v in f.value)
                where_parts.append(f"({vals})")
                continue
        val = f"'{f.value}'" if isinstance(f.value, str) else str(f.value)
        where_parts.append(f"{f.column} {f.op} {val}")
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
    if params.order_by:
        query += f" ORDER BY {params.order_by} {params.order_dir}"
    if params.limit is not None:
        query += f" LIMIT {params.limit}"
    return query


@app.route("/api/query", methods=["POST"])
def query() -> Any:
    payload = request.get_json(force=True)
    params = QueryParams(
        start=payload.get("start"),
        end=payload.get("end"),
        order_by=payload.get("order_by"),
        order_dir=payload.get("order_dir", "ASC"),
        limit=payload.get("limit"),
        columns=payload.get("columns", []),
        derived_columns=payload.get("derived_columns", {}),
    )
    for f in payload.get("filters", []):
        params.filters.append(Filter(f["column"], f["op"], f.get("value")))
    sql = build_query(params)
    rows = con.execute(sql).fetchall()
    return jsonify({"sql": sql, "rows": rows})


if __name__ == "__main__":
    app.run(debug=True)
