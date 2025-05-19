from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import duckdb
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

# Initialize DuckDB in-memory and load sample data
con = duckdb.connect()
con.execute(
    "CREATE TABLE IF NOT EXISTS events AS SELECT * FROM read_csv_auto('scubaduck/sample.csv')"
)

# Cache column info and autocomplete results in memory
COLUMN_INFO = con.execute("PRAGMA table_info(events)").fetchall()
COLUMNS = [r[1] for r in COLUMN_INFO]
autocomplete_cache: Dict[Tuple[str, str], List[str]] = {}


@dataclass
class Filter:
    column: str
    op: str
    value: Any


@dataclass
class QueryParams:
    start: str | None = None
    end: str | None = None
    order_by: str | None = None
    order_dir: str = "ASC"
    limit: int | None = None
    columns: List[str] = field(default_factory=list)
    filters: List[Filter] = field(default_factory=list)
    derived_columns: Dict[str, str] = field(default_factory=dict)


@app.route("/")
def index() -> Any:
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/columns")
def columns() -> Any:
    return jsonify([{"name": r[1], "type": r[2]} for r in COLUMN_INFO])


def get_autocomplete(column: str, prefix: str) -> List[str]:
    key = (column, prefix)
    if key in autocomplete_cache:
        return autocomplete_cache[key]
    if column not in COLUMNS:
        return []
    sql = (
        f"SELECT DISTINCT {column} FROM events WHERE CAST({column} AS TEXT) LIKE ? "
        f"ORDER BY {column} LIMIT 10"
    )
    rows = con.execute(sql, [f"{prefix}%"]).fetchall()
    values = [r[0] for r in rows]
    autocomplete_cache[key] = values
    return values


@app.route("/api/autocomplete")
def autocomplete() -> Any:
    column = request.args.get("column", "")
    prefix = request.args.get("prefix", "")
    return jsonify(get_autocomplete(column, prefix))


def build_query(params: QueryParams) -> str:
    select_parts = [*params.columns]
    for name, expr in params.derived_columns.items():
        select_parts.append(f"{expr} AS {name}")
    select_clause = ", ".join(select_parts) if select_parts else "*"
    query = f"SELECT {select_clause} FROM events"
    where_parts = []
    if params.start:
        where_parts.append(f"timestamp >= '{params.start}'")
    if params.end:
        where_parts.append(f"timestamp <= '{params.end}'")
    for f in params.filters:
        if f.op == "=" and isinstance(f.value, list):
            vals = " OR ".join(f"{f.column} = '{v}'" for v in f.value)
            where_parts.append(f"({vals})")
        else:
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
