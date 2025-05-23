from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Tuple, cast

import re
from datetime import datetime, timedelta, timezone

import time
from pathlib import Path
import os
import traceback
import math

import duckdb
from dateutil import parser as dtparser
from dateutil.relativedelta import relativedelta
from flask import Flask, jsonify, request, send_from_directory


def _quote(ident: str) -> str:
    """Return identifier quoted for SQL."""
    return f'"{ident.replace('"', '""')}"'


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
    x_axis: str | None = None
    granularity: str = "Auto"
    fill: str = "0"
    table: str = "events"
    time_column: str | None = "timestamp"
    time_unit: str = "s"


def _load_database(path: Path) -> duckdb.DuckDBPyConnection:
    if not path.exists():
        raise FileNotFoundError(path)

    ext = path.suffix.lower()
    if ext == ".csv":
        con = duckdb.connect()
        con.execute(
            f"CREATE TABLE events AS SELECT * FROM read_csv_auto('{path.as_posix()}')"
        )
    elif ext in {".parquet", ".parq"}:
        con = duckdb.connect()
        con.execute(
            f"CREATE TABLE events AS SELECT * FROM read_parquet('{path.as_posix()}')"
        )
    elif ext in {".db", ".sqlite"}:
        con = duckdb.connect()
        con.execute("LOAD sqlite")
        con.execute(f"ATTACH '{path.as_posix()}' AS db (TYPE SQLITE)")
        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        for t in tables:
            con.execute(f'CREATE VIEW "{t}" AS SELECT * FROM db."{t}"')
    else:
        con = duckdb.connect(path)
    return con


def _create_test_database() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection with a small multi-table dataset."""
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, ts INTEGER, val REAL, name TEXT, flag BOOLEAN)"
    )
    con.execute("INSERT INTO events VALUES (1, 1704067200, 1.5, 'alice', 1)")
    con.execute("INSERT INTO events VALUES (2, 1704070800, 2.0, 'bob', 0)")
    con.execute('CREATE TABLE extra (ts INTEGER, "desc" TEXT, num INTEGER)')
    con.execute("INSERT INTO extra VALUES (1704067200, 'x', 1)")
    con.execute("INSERT INTO extra VALUES (1704070800, 'y', 2)")
    return con


_REL_RE = re.compile(
    r"([+-]?\d+(?:\.\d*)?)\s*(hour|hours|day|days|week|weeks|fortnight|fortnights|month|months|year|years)",
    re.IGNORECASE,
)


def parse_time(val: str | None) -> str | None:
    """Parse an absolute or relative time string into ``YYYY-MM-DD HH:MM:SS``."""
    if val is None or val == "":
        return None
    s = val.strip()
    if s.lower() == "now":
        dt = datetime.now(timezone.utc)
        return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

    m = _REL_RE.fullmatch(s)
    if m:
        qty = float(m.group(1))
        unit = m.group(2).lower()
        now = datetime.now(timezone.utc)
        dt: datetime
        if unit.startswith("hour"):
            dt = now + timedelta(hours=qty)
        elif unit.startswith("day"):
            dt = now + timedelta(days=qty)
        elif unit.startswith("week"):
            dt = now + timedelta(weeks=qty)
        elif unit.startswith("fortnight"):
            dt = now + timedelta(weeks=2 * qty)
        elif unit.startswith("month"):
            if qty.is_integer():
                dt = now + relativedelta(months=int(qty))
            else:
                dt = now + timedelta(days=30 * qty)
        elif unit.startswith("year"):
            if qty.is_integer():
                dt = now + relativedelta(years=int(qty))
            else:
                dt = now + timedelta(days=365 * qty)
        else:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported unit: {unit}")
        return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

    dt = dtparser.parse(s)
    return dt.replace(microsecond=0, tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _numeric_to_datetime(value: int | float, unit: str) -> datetime:
    """Convert a numeric timestamp ``value`` with unit ``unit`` to ``datetime``.

    Heuristically fall back to seconds when the converted value is before 1990
    but the seconds interpretation is in a reasonable range.  This handles
    integer columns stored in seconds even when ``unit`` is mistakenly set to a
    finer granularity.
    """

    divisor = {
        "s": 1,
        "ms": 1000,
        "us": 1_000_000,
        "ns": 1_000_000_000,
    }.get(unit, 1)

    dt = datetime.fromtimestamp(int(value) / divisor, tz=timezone.utc)
    if unit != "s" and dt.year < 1990:
        alt = datetime.fromtimestamp(int(value), tz=timezone.utc)
        if alt.year >= 1990:
            dt = alt
    return dt


def _suggest_time_unit(value: int | float, given: str) -> str | None:
    """Return a plausible time unit for ``value`` not equal to ``given``."""

    for unit in ("s", "ms", "us", "ns"):
        if unit == given:
            continue
        try:
            dt = _numeric_to_datetime(value, unit)
        except Exception:
            continue
        if 1990 <= dt.year <= 2500:
            return unit
    return None


def _granularity_seconds(granularity: str, start: str | None, end: str | None) -> int:
    gran = granularity.lower()
    mapping = {
        "1 second": 1,
        "5 seconds": 5,
        "10 seconds": 10,
        "30 seconds": 30,
        "1 minute": 60,
        "4 minutes": 240,
        "5 minutes": 300,
        "10 minutes": 600,
        "15 minutes": 900,
        "30 minutes": 1800,
        "1 hour": 3600,
        "3 hours": 10800,
        "6 hours": 21600,
        "1 day": 86400,
        "1 week": 604800,
        "30 days": 2592000,
    }
    if gran in mapping:
        return mapping[gran]
    if gran in {"auto", "fine"} and start and end:
        try:
            s = dtparser.parse(start)
            e = dtparser.parse(end)
        except Exception:
            return 3600
        total = max((e - s).total_seconds(), 1)
        buckets = 100 if gran == "auto" else 500
        return max(int(total // buckets), 1)
    return 3600


def _time_expr(col: str, column_types: Dict[str, str] | None, unit: str) -> str:
    """Return SQL expression for column interpreted as timestamp."""
    qcol = _quote(col)
    if column_types is None:
        return qcol
    ctype = column_types.get(col, "").upper()
    if not any(t in ctype for t in ["TIMESTAMP", "DATE", "TIME"]):
        if any(
            t in ctype
            for t in [
                "INT",
                "DECIMAL",
                "REAL",
                "DOUBLE",
                "FLOAT",
                "NUMERIC",
                "HUGEINT",
            ]
        ):
            if unit == "ns":
                # Use nanosecond helper unless column cannot represent such large values
                if "INT" in ctype and "BIGINT" not in ctype and "HUGEINT" not in ctype:
                    unit = "s"
                else:
                    expr = f"CAST({qcol} AS BIGINT)"
                    return f"make_timestamp_ns({expr})"

            if (
                unit != "s"
                and "INT" in ctype
                and "BIGINT" not in ctype
                and "HUGEINT" not in ctype
            ):
                # 32-bit integers cannot store sub-second precision for modern dates
                unit = "s"

            multiplier = {
                "s": 1_000_000,
                "ms": 1_000,
                "us": 1,
            }.get(unit, 1_000_000)
            base = f"CAST({qcol} AS BIGINT)"
            expr = f"CAST({base} * {multiplier} AS BIGINT)" if multiplier != 1 else base
            return f"make_timestamp({expr})"
    return qcol


def build_query(params: QueryParams, column_types: Dict[str, str] | None = None) -> str:
    select_parts: list[str] = []
    group_cols = params.group_by[:]
    selected_for_order = set(params.columns) | set(params.derived_columns.keys())
    if params.graph_type == "timeseries":
        sec = _granularity_seconds(params.granularity, params.start, params.end)
        x_axis = params.x_axis or params.time_column
        if x_axis is None:
            raise ValueError("x_axis required for timeseries")
        xexpr = _time_expr(x_axis, column_types, params.time_unit)
        if params.start:
            bucket_expr = (
                f"TIMESTAMP '{params.start}' + INTERVAL '{sec} second' * "
                f"CAST(floor((epoch({xexpr}) - epoch(TIMESTAMP '{params.start}'))/{sec}) AS BIGINT)"
            )
        else:
            bucket_expr = (
                f"TIMESTAMP 'epoch' + INTERVAL '{sec} second' * "
                f"CAST(floor(epoch({xexpr})/{sec}) AS BIGINT)"
            )
        select_parts.append(f"{bucket_expr} AS bucket")
        group_cols = ["bucket"] + group_cols
        selected_for_order.add("bucket")
    has_agg = bool(group_cols) or params.aggregate is not None
    if has_agg:
        select_cols = (
            group_cols[1:] if params.graph_type == "timeseries" else group_cols
        )
        select_parts.extend(_quote(c) for c in select_cols)
        agg = (params.aggregate or "count").lower()
        selected_for_order.update(group_cols)

        def agg_expr(col: str) -> str:
            expr = _quote(col)
            ctype = column_types.get(col, "").upper() if column_types else ""
            if "BOOL" in ctype:
                expr = f"CAST({_quote(col)} AS BIGINT)"
            if agg.startswith("p"):
                quant = float(agg[1:]) / 100
                return f"quantile({expr}, {quant})"
            if agg == "count distinct":
                return f"count(DISTINCT {expr})"
            if agg == "avg" and column_types is not None:
                if "TIMESTAMP" in ctype or "DATE" in ctype or "TIME" in ctype:
                    return (
                        "TIMESTAMP 'epoch' + INTERVAL '1 second' * "
                        f"CAST(avg(epoch({_quote(col)})) AS BIGINT)"
                    )
            return f"{agg}({expr})"

        if agg == "count":
            if params.graph_type != "table":
                select_parts.append("count(*) AS Count")
                selected_for_order.add("Count")
        else:
            for col in params.columns:
                if col in group_cols:
                    continue
                select_parts.append(f"{agg_expr(col)} AS {_quote(col)}")
                selected_for_order.add(col)
        select_parts.insert(len(group_cols), "count(*) AS Hits")
        selected_for_order.add("Hits")
    else:
        select_parts.extend(_quote(c) for c in params.columns)
        selected_for_order.update(params.columns)

    order_by = params.order_by
    if order_by and str(order_by).strip().lower() == "samples":
        order_by = "Hits"
    order_by = order_by if order_by in selected_for_order else None

    if has_agg and params.derived_columns:
        inner_params = replace(
            params,
            derived_columns={},
            order_by=None,
            limit=None,
        )
        inner_sql = build_query(inner_params, column_types)
        outer_select = ["t.*"] + [
            f"{expr} AS {name}" for name, expr in params.derived_columns.items()
        ]
        indented_inner = "\n".join("    " + line for line in inner_sql.splitlines())
        lines = [
            f"SELECT {', '.join(outer_select)}",
            "FROM (",
            indented_inner,
            ") t",
        ]
        if order_by:
            lines.append(f"ORDER BY {_quote(order_by)} {params.order_dir}")
        elif params.graph_type == "timeseries":
            lines.append("ORDER BY bucket")
        if params.limit is not None:
            lines.append(f"LIMIT {params.limit}")
        return "\n".join(lines)

    for name, expr in params.derived_columns.items():
        select_parts.append(f"{expr} AS {name}")
        selected_for_order.add(name)
    select_clause = ", ".join(select_parts) if select_parts else "*"
    lines = [f"SELECT {select_clause}", f'FROM "{params.table}"']
    where_parts: list[str] = []
    if params.time_column:
        time_expr = _time_expr(params.time_column, column_types, params.time_unit)
    else:
        time_expr = None
    if time_expr and params.start:
        where_parts.append(f"{time_expr} >= '{params.start}'")
    if time_expr and params.end:
        where_parts.append(f"{time_expr} <= '{params.end}'")
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
                    qcol = _quote(f.column)
                    vals = " OR ".join(f"{qcol} = '{v}'" for v in f.value)
                    where_parts.append(f"({vals})")
                    continue
            val = f"'{f.value}'" if isinstance(f.value, str) else str(f.value)

        qcol = _quote(f.column)
        if op == "contains":
            where_parts.append(f"{qcol} ILIKE '%' || {val} || '%'")
        elif op == "!contains":
            where_parts.append(f"{qcol} NOT ILIKE '%' || {val} || '%'")
        elif op == "empty":
            where_parts.append(f"{qcol} = {val}")
        elif op == "!empty":
            where_parts.append(f"{qcol} != {val}")
        else:
            where_parts.append(f"{qcol} {op} {val}")
    if where_parts:
        lines.append("WHERE " + " AND ".join(where_parts))
    if group_cols:
        lines.append("GROUP BY " + ", ".join(_quote(c) for c in group_cols))
    if order_by:
        lines.append(f"ORDER BY {_quote(order_by)} {params.order_dir}")
    elif params.graph_type == "timeseries":
        lines.append("ORDER BY bucket")
    if params.limit is not None:
        lines.append(f"LIMIT {params.limit}")
    return "\n".join(lines)


def create_app(db_file: str | Path | None = None) -> Flask:
    app = Flask(__name__, static_folder="static")
    if db_file is None:
        env_db = os.environ.get("SCUBADUCK_DB")
        if env_db:
            db_file = env_db
    if isinstance(db_file, str) and db_file.upper() == "TEST":
        con = _create_test_database()
    else:
        db_path = Path(db_file or Path(__file__).with_name("sample.csv")).resolve()
        con = _load_database(db_path)
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    if not tables:
        raise ValueError("No tables found in database")
    default_table = tables[0]
    columns_cache: Dict[str, Dict[str, str]] = {}

    def get_columns(table: str) -> Dict[str, str]:
        if table not in columns_cache:
            rows = con.execute(f'PRAGMA table_info("{table}")').fetchall()
            if not rows:
                raise ValueError(f"Unknown table: {table}")
            columns_cache[table] = {r[1]: r[2] for r in rows}
        return columns_cache[table]

    sample_cache: Dict[Tuple[str, str, str], Tuple[List[str], float]] = {}
    CACHE_TTL = 60.0
    CACHE_LIMIT = 200

    @app.route("/")
    def index() -> Any:  # pyright: ignore[reportUnusedFunction]
        assert app.static_folder is not None
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/js/<path:filename>")
    def js(filename: str) -> Any:  # pyright: ignore[reportUnusedFunction]
        assert app.static_folder is not None
        folder = Path(app.static_folder) / "js"
        return send_from_directory(folder, filename)

    @app.route("/api/tables")
    def tables_endpoint() -> Any:  # pyright: ignore[reportUnusedFunction]
        return jsonify(tables)

    @app.route("/api/columns")
    def columns() -> Any:  # pyright: ignore[reportUnusedFunction]
        table = request.args.get("table", default_table)
        rows = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        return jsonify([{"name": r[1], "type": r[2]} for r in rows])

    def _cache_get(key: Tuple[str, str, str]) -> List[str] | None:
        item = sample_cache.get(key)
        if item is None:
            return None
        vals, ts = item
        if time.time() - ts > CACHE_TTL:
            del sample_cache[key]
            return None
        sample_cache[key] = (vals, time.time())
        return vals

    def _cache_set(key: Tuple[str, str, str], vals: List[str]) -> None:
        sample_cache[key] = (vals, time.time())
        if len(sample_cache) > CACHE_LIMIT:
            oldest = min(sample_cache.items(), key=lambda kv: kv[1][1])[0]
            del sample_cache[oldest]

    @app.route("/api/samples")
    def sample_values() -> Any:  # pyright: ignore[reportUnusedFunction]
        table = request.args.get("table", default_table)
        column = request.args.get("column")
        substr = request.args.get("q", "")
        column_types = get_columns(table)
        if not column or column not in column_types:
            return jsonify([])
        ctype = column_types[column].upper()
        if "CHAR" not in ctype and "STRING" not in ctype and "VARCHAR" not in ctype:
            return jsonify([])
        key = (table, column, substr)
        cached = _cache_get(key)
        if cached is not None:
            return jsonify(cached)
        qcol = _quote(column)
        rows = con.execute(
            f"SELECT DISTINCT {qcol} FROM \"{table}\" WHERE CAST({qcol} AS VARCHAR) ILIKE '%' || ? || '%' LIMIT 20",
            [substr],
        ).fetchall()
        values = [r[0] for r in rows]
        _cache_set(key, values)
        return jsonify(values)

    @app.route("/api/query", methods=["POST"])
    def query() -> Any:  # pyright: ignore[reportUnusedFunction]
        payload = request.get_json(force=True)
        try:
            start = parse_time(payload.get("start"))
            end = parse_time(payload.get("end"))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

        params = QueryParams(
            start=start,
            end=end,
            order_by=payload.get("order_by"),
            order_dir=payload.get("order_dir", "ASC"),
            limit=payload.get("limit"),
            columns=payload.get("columns", []),
            derived_columns=payload.get("derived_columns", {}),
            graph_type=payload.get("graph_type", "samples"),
            group_by=payload.get("group_by", []),
            aggregate=payload.get("aggregate"),
            show_hits=payload.get("show_hits", False),
            x_axis=payload.get("x_axis"),
            granularity=payload.get("granularity", "Auto"),
            fill=payload.get("fill", "0"),
            table=payload.get("table", default_table),
            time_column=payload.get("time_column", "timestamp"),
            time_unit=payload.get("time_unit", "s"),
        )
        if params.order_by and params.order_by.strip().lower() == "samples":
            params.order_by = "Hits"
        for f in payload.get("filters", []):
            params.filters.append(Filter(f["column"], f["op"], f.get("value")))

        if params.table not in tables:
            return jsonify({"error": "Invalid table"}), 400

        column_types = get_columns(params.table)

        if params.time_column and params.time_column not in column_types:
            return jsonify({"error": "Invalid time_column"}), 400

        if params.time_unit not in {"s", "ms", "us", "ns"}:
            return jsonify({"error": "Invalid time_unit"}), 400

        if params.graph_type not in {"table", "timeseries"} and (
            params.group_by or params.aggregate or params.show_hits
        ):
            return (
                jsonify(
                    {
                        "error": "group_by, aggregate and show_hits are only valid for table or timeseries view"
                    }
                ),
                400,
            )

        valid_cols = set(column_types.keys())
        valid_cols.update(params.derived_columns.keys())
        valid_cols.add("Hits")
        if params.graph_type == "timeseries":
            if params.x_axis is None:
                params.x_axis = params.time_column
            if params.x_axis is None or params.x_axis not in valid_cols:
                return jsonify({"error": "Invalid x_axis"}), 400
            ctype = column_types.get(params.x_axis, "").upper()
            is_time = any(t in ctype for t in ["TIMESTAMP", "DATE", "TIME"])
            is_numeric = any(
                t in ctype
                for t in [
                    "INT",
                    "DECIMAL",
                    "REAL",
                    "DOUBLE",
                    "FLOAT",
                    "NUMERIC",
                    "HUGEINT",
                ]
            )
            if not (is_time or is_numeric):
                return jsonify({"error": "x_axis must be a time column"}), 400
        for col in params.columns:
            if col not in valid_cols:
                return jsonify({"error": f"Unknown column: {col}"}), 400
        for col in params.group_by:
            if col not in valid_cols:
                return jsonify({"error": f"Unknown column: {col}"}), 400
        if params.order_by and params.order_by not in valid_cols:
            return jsonify({"error": f"Unknown column: {params.order_by}"}), 400

        if params.group_by or params.graph_type == "timeseries":
            agg = (params.aggregate or "count").lower()
            if agg.startswith("p") or agg == "sum":
                need_numeric = True
                allow_time = False
            elif agg == "avg" or agg in {"min", "max"}:
                need_numeric = False
                allow_time = True
            else:
                need_numeric = False
                allow_time = False
            if need_numeric or allow_time:
                for c in params.columns:
                    if c in params.group_by or c == params.x_axis:
                        continue
                    if c not in column_types:
                        continue
                    ctype = column_types.get(c, "").upper()
                    is_numeric = "BOOL" in ctype or any(
                        t in ctype
                        for t in [
                            "INT",
                            "DECIMAL",
                            "REAL",
                            "DOUBLE",
                            "FLOAT",
                            "NUMERIC",
                            "HUGEINT",
                        ]
                    )
                    is_time = "TIMESTAMP" in ctype or "DATE" in ctype or "TIME" in ctype
                    if need_numeric and not is_numeric:
                        return (
                            jsonify(
                                {
                                    "error": f"Aggregate {agg} cannot be applied to column {c}",
                                }
                            ),
                            400,
                        )
                    if allow_time and not (is_numeric or is_time):
                        return (
                            jsonify(
                                {
                                    "error": f"Aggregate {agg} cannot be applied to column {c}",
                                }
                            ),
                            400,
                        )
        if (params.start is None or params.end is None) and (
            params.x_axis or params.time_column
        ):
            axis = params.x_axis or params.time_column
            assert axis is not None
            row = cast(
                tuple[datetime | None, datetime | None],
                con.execute(
                    f'SELECT min({_quote(axis)}), max({_quote(axis)}) FROM "{params.table}"'
                ).fetchall()[0],
            )
            mn, mx = row
            if isinstance(mn, (int, float)):
                try:
                    mn = _numeric_to_datetime(mn, params.time_unit)
                except Exception:
                    suggestion = _suggest_time_unit(mn, params.time_unit)
                    msg = f"Invalid time value {mn} for column {axis} with time_unit {params.time_unit}"
                    if suggestion:
                        msg += f"; maybe try time_unit {suggestion}"
                    return jsonify({"error": msg}), 400
            if isinstance(mx, (int, float)):
                try:
                    mx = _numeric_to_datetime(mx, params.time_unit)
                except Exception:
                    suggestion = _suggest_time_unit(mx, params.time_unit)
                    msg = f"Invalid time value {mx} for column {axis} with time_unit {params.time_unit}"
                    if suggestion:
                        msg += f"; maybe try time_unit {suggestion}"
                    return jsonify({"error": msg}), 400
            if params.start is None and mn is not None:
                params.start = (
                    mn.strftime("%Y-%m-%d %H:%M:%S") if not isinstance(mn, str) else mn
                )
            if params.end is None and mx is not None:
                params.end = (
                    mx.strftime("%Y-%m-%d %H:%M:%S") if not isinstance(mx, str) else mx
                )

        bucket_size: int | None = None
        series_limit = params.limit
        if params.graph_type == "timeseries":
            bucket_size = _granularity_seconds(
                params.granularity,
                params.start if isinstance(params.start, str) else None,
                params.end if isinstance(params.end, str) else None,
            )
            if (
                params.limit is not None
                and params.start is not None
                and params.end is not None
            ):
                try:
                    start_dt = dtparser.parse(params.start)
                    end_dt = dtparser.parse(params.end)
                    buckets = math.ceil(
                        (end_dt - start_dt).total_seconds() / bucket_size
                    )
                    if buckets > 1:
                        params.limit *= buckets
                except Exception:
                    pass

        sql = build_query(params, column_types)
        try:
            rows = con.execute(sql).fetchall()
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"Query failed:\n{sql}\n{tb}")
            return (
                jsonify({"sql": sql, "error": str(exc), "traceback": tb}),
                400,
            )

        def _serialize(value: Any) -> Any:
            if isinstance(value, bytes):
                return repr(value)
            return value

        rows = [[_serialize(v) for v in r] for r in rows]

        if (
            params.graph_type == "timeseries"
            and params.group_by
            and series_limit is not None
        ):
            key_slice = slice(1, 1 + len(params.group_by))
            kept: set[tuple[Any, ...]] = set()
            filtered: list[list[Any]] = []
            for row in rows:
                key = tuple(row[key_slice])
                if key not in kept:
                    if len(kept) >= series_limit:
                        continue
                    kept.add(key)
                filtered.append(row)
            rows = filtered

        result: Dict[str, Any] = {"sql": sql, "rows": rows}
        if params.start is not None:
            result["start"] = str(params.start)
        if params.end is not None:
            result["end"] = str(params.end)
        if bucket_size is not None:
            result["bucket_size"] = bucket_size
        return jsonify(result)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
