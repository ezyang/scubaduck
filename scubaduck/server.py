from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import time
from pathlib import Path
import sqlite3

import duckdb
from flask import Flask, jsonify, request, send_from_directory


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
    graph_type: str = "samples"
    group_by: list[str] = field(default_factory=lambda: [])
    aggregate: str | None = None
    show_hits: bool = False


def _load_database(path: Path) -> duckdb.DuckDBPyConnection:
    ext = path.suffix.lower()
    if ext == ".csv":
        con = duckdb.connect()
        con.execute(
            f"CREATE TABLE events AS SELECT * FROM read_csv_auto('{path.as_posix()}')"
        )
    elif ext in {".db", ".sqlite"}:
        con = duckdb.connect()
        sconn = sqlite3.connect(path)
        info = sconn.execute("PRAGMA table_info(events)").fetchall()
        col_defs = ", ".join(f"{r[1]} {r[2]}" for r in info)
        con.execute(f"CREATE TABLE events ({col_defs})")
        placeholders = ",".join("?" for _ in info)
        for row in sconn.execute("SELECT * FROM events"):
            con.execute(f"INSERT INTO events VALUES ({placeholders})", row)
        sconn.close()
    else:
        con = duckdb.connect(path)
    return con


def build_query(params: QueryParams) -> str:
    select_parts: list[str] = []
    if params.group_by:
        select_parts.extend(params.group_by)
        agg = (params.aggregate or "avg").lower()

        def agg_expr(col: str) -> str:
            if agg.startswith("p"):
                quant = float(agg[1:]) / 100
                return f"quantile({col}, {quant})"
            if agg == "count distinct":
                return f"count(DISTINCT {col})"
            return f"{agg}({col})"

        for col in params.columns:
            if col in params.group_by:
                continue
            select_parts.append(f"{agg_expr(col)} AS {col}")
        if params.show_hits:
            select_parts.insert(len(params.group_by), "count(*) AS Hits")
    else:
        select_parts.extend(params.columns)
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
        op = f.op
        if op in {"empty", "!empty"}:
            val = "''"
        else:
            if f.value is None:
                continue
            if isinstance(f.value, list):
                if not f.value:
                    continue
                if op == "=":
                    vals = " OR ".join(f"{f.column} = '{v}'" for v in f.value)
                    where_parts.append(f"({vals})")
                    continue
            val = f"'{f.value}'" if isinstance(f.value, str) else str(f.value)

        if op == "contains":
            where_parts.append(f"{f.column} ILIKE '%' || {val} || '%'")
        elif op == "!contains":
            where_parts.append(f"{f.column} NOT ILIKE '%' || {val} || '%'")
        elif op == "empty":
            where_parts.append(f"{f.column} = {val}")
        elif op == "!empty":
            where_parts.append(f"{f.column} != {val}")
        else:
            where_parts.append(f"{f.column} {op} {val}")
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
    if params.group_by:
        query += " GROUP BY " + ", ".join(params.group_by)
    if params.order_by:
        query += f" ORDER BY {params.order_by} {params.order_dir}"
    if params.limit is not None:
        query += f" LIMIT {params.limit}"
    return query


def create_app(db_file: str | Path | None = None) -> Flask:
    app = Flask(__name__, static_folder="static")
    db_path = Path(db_file or Path(__file__).with_name("sample.csv")).resolve()
    con = _load_database(db_path)
    column_types: Dict[str, str] = {
        r[1]: r[2] for r in con.execute("PRAGMA table_info(events)").fetchall()
    }

    sample_cache: Dict[Tuple[str, str], Tuple[List[str], float]] = {}
    CACHE_TTL = 60.0
    CACHE_LIMIT = 200

    @app.route("/")
    def index() -> Any:  # pyright: ignore[reportUnusedFunction]
        assert app.static_folder is not None
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/api/columns")
    def columns() -> Any:  # pyright: ignore[reportUnusedFunction]
        rows = con.execute("PRAGMA table_info(events)").fetchall()
        return jsonify([{"name": r[1], "type": r[2]} for r in rows])

    def _cache_get(key: Tuple[str, str]) -> List[str] | None:
        item = sample_cache.get(key)
        if item is None:
            return None
        vals, ts = item
        if time.time() - ts > CACHE_TTL:
            del sample_cache[key]
            return None
        sample_cache[key] = (vals, time.time())
        return vals

    def _cache_set(key: Tuple[str, str], vals: List[str]) -> None:
        sample_cache[key] = (vals, time.time())
        if len(sample_cache) > CACHE_LIMIT:
            oldest = min(sample_cache.items(), key=lambda kv: kv[1][1])[0]
            del sample_cache[oldest]

    @app.route("/api/samples")
    def sample_values() -> Any:  # pyright: ignore[reportUnusedFunction]
        column = request.args.get("column")
        substr = request.args.get("q", "")
        if not column or column not in column_types:
            return jsonify([])
        ctype = column_types[column].upper()
        if "CHAR" not in ctype and "STRING" not in ctype and "VARCHAR" not in ctype:
            return jsonify([])
        key = (column, substr)
        cached = _cache_get(key)
        if cached is not None:
            return jsonify(cached)
        rows = con.execute(
            f"SELECT DISTINCT {column} FROM events WHERE CAST({column} AS VARCHAR) ILIKE '%' || ? || '%' LIMIT 20",
            [substr],
        ).fetchall()
        values = [r[0] for r in rows]
        _cache_set(key, values)
        return jsonify(values)

    @app.route("/api/query", methods=["POST"])
    def query() -> Any:  # pyright: ignore[reportUnusedFunction]
        payload = request.get_json(force=True)
        params = QueryParams(
            start=payload.get("start"),
            end=payload.get("end"),
            order_by=payload.get("order_by"),
            order_dir=payload.get("order_dir", "ASC"),
            limit=payload.get("limit"),
            columns=payload.get("columns", []),
            derived_columns=payload.get("derived_columns", {}),
            graph_type=payload.get("graph_type", "samples"),
            group_by=payload.get("group_by", []),
            aggregate=payload.get("aggregate"),
            show_hits=payload.get("show_hits", False),
        )
        for f in payload.get("filters", []):
            params.filters.append(Filter(f["column"], f["op"], f.get("value")))
        sql = build_query(params)
        rows = con.execute(sql).fetchall()
        return jsonify({"sql": sql, "rows": rows})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
