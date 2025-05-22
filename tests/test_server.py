from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import duckdb
from scubaduck import server
import pytest


def test_basic_query() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-02 00:00:00",
        "order_by": "timestamp",
        "order_dir": "ASC",
        "limit": 10,
        "columns": ["timestamp", "event", "value", "user"],
        "filters": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert data
    rows = data["rows"]
    # We expect first three rows (until 2024-01-02 00:00:00)
    assert len(rows) == 3
    assert rows[0][1] == "login"
    assert rows[1][1] == "logout"


def test_js_served() -> None:
    app = server.app
    client = app.test_client()
    rv = client.get("/js/chip_input.js")
    assert rv.status_code == 200
    assert b"initChipInput" in rv.data


def test_filter_multi_token() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-02 03:00:00",
        "order_by": "timestamp",
        "limit": 10,
        "columns": ["timestamp", "event", "value", "user"],
        "filters": [{"column": "user", "op": "=", "value": ["alice", "charlie"]}],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert data
    rows = data["rows"]
    # Should only return rows for alice and charlie
    assert len(rows) == 3
    assert rows[0][3] == "alice"
    assert rows[-1][3] == "charlie"


def test_empty_filter_is_noop() -> None:
    app = server.app
    client = app.test_client()
    base_payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "limit": 100,
        "columns": ["timestamp", "event", "value", "user"],
    }
    no_filter = {**base_payload, "filters": []}
    empty_filter = {
        **base_payload,
        "filters": [{"column": "user", "op": "=", "value": None}],
    }

    rv1 = client.post(
        "/api/query", data=json.dumps(no_filter), content_type="application/json"
    )
    rv2 = client.post(
        "/api/query", data=json.dumps(empty_filter), content_type="application/json"
    )
    rows1 = rv1.get_json()["rows"]
    rows2 = rv2.get_json()["rows"]
    assert rows1 == rows2


def test_select_columns() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "order_by": "timestamp",
        "limit": 10,
        "columns": ["timestamp", "user"],
        "filters": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert data
    rows = data["rows"]
    assert len(rows[0]) == 2
    assert rows[0][1] == "alice"


def test_string_filter_ops() -> None:
    app = server.app
    client = app.test_client()
    base = {
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "order_by": "timestamp",
        "limit": 100,
        "columns": ["timestamp", "event", "value", "user"],
    }

    contains = {
        **base,
        "filters": [{"column": "user", "op": "contains", "value": "ali"}],
    }
    rv = client.post(
        "/api/query", data=json.dumps(contains), content_type="application/json"
    )
    rows = rv.get_json()["rows"]
    assert all("ali" in r[3] for r in rows)

    regex = {
        **base,
        "filters": [{"column": "user", "op": "~", "value": "^a.*"}],
    }
    rv = client.post(
        "/api/query", data=json.dumps(regex), content_type="application/json"
    )
    rows = rv.get_json()["rows"]
    assert all(r[3].startswith("a") for r in rows)
    assert len(rows) == 2

    not_empty = {**base, "filters": [{"column": "user", "op": "!empty"}]}
    rv = client.post(
        "/api/query", data=json.dumps(not_empty), content_type="application/json"
    )
    assert len(rv.get_json()["rows"]) == 4


def _make_payload() -> dict[str, object]:
    return {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-02 00:00:00",
        "order_by": "timestamp",
        "order_dir": "ASC",
        "limit": 10,
        "columns": ["timestamp", "event", "value", "user"],
        "filters": [],
    }


def test_database_types(tmp_path: Path) -> None:
    csv_file = tmp_path / "events.csv"
    csv_file.write_text(Path("scubaduck/sample.csv").read_text())

    sqlite_file = tmp_path / "events.sqlite"
    import sqlite3

    conn = sqlite3.connect(sqlite_file)
    conn.execute(
        "CREATE TABLE events (timestamp TEXT, event TEXT, value INTEGER, user TEXT)"
    )
    with open(csv_file) as f:
        next(f)
        for line in f:
            ts, ev, val, user = line.strip().split(",")
            conn.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?)", (ts, ev, int(val), user)
            )
    conn.commit()
    conn.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    duckdb_file = tmp_path / "events.duckdb"
    con = duckdb.connect(duckdb_file)
    con.execute(
        f"CREATE TABLE events AS SELECT * FROM read_csv_auto('{csv_file.as_posix()}')"
    )
    con.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    for db in (csv_file, sqlite_file, duckdb_file):
        app = server.create_app(db)
        client = app.test_client()
        payload = _make_payload()
        rv = client.post(
            "/api/query", data=json.dumps(payload), content_type="application/json"
        )
        rows = rv.get_json()["rows"]
        assert len(rows) == 3


def test_sqlite_longvarchar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sqlite_file = tmp_path / "events.sqlite"
    import sqlite3

    conn = sqlite3.connect(sqlite_file)
    conn.execute(
        "CREATE TABLE events (timestamp TEXT, url LONGVARCHAR, title VARCHAR(10))"
    )
    conn.execute(
        "INSERT INTO events VALUES ('2024-01-01 00:00:00', 'https://a.com', 'Home')"
    )
    conn.commit()
    conn.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    from typing import Any

    real_connect = duckdb.connect

    def failing_connect(*args: Any, **kwargs: Any) -> Any:
        real = real_connect(*args, **kwargs)

        class Wrapper:
            def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
                self.con = con
                self._failed = False

            def execute(self, sql: str, *a: Any, **kw: Any):
                if not self._failed and sql == "LOAD sqlite":
                    self._failed = True
                    raise RuntimeError("fail")
                return self.con.execute(sql, *a, **kw)

            def __getattr__(self, name: str) -> object:
                return getattr(self.con, name)

        return Wrapper(real)

    monkeypatch.setattr(server.duckdb, "connect", failing_connect)

    app = server.create_app(sqlite_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-01 01:00:00",
        "order_by": "timestamp",
        "columns": ["timestamp", "url", "title"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["rows"][0][1] == "https://a.com"


def test_sqlite_bigint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sqlite_file = tmp_path / "big.sqlite"
    import sqlite3

    conn = sqlite3.connect(sqlite_file)
    conn.execute("CREATE TABLE events (timestamp TEXT, value INTEGER)")
    big_value = 13385262862605259
    conn.execute(
        "INSERT INTO events VALUES ('2024-01-01 00:00:00', ?)",
        (big_value,),
    )
    conn.commit()
    conn.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    from typing import Any

    real_connect = duckdb.connect

    def failing_connect(*args: Any, **kwargs: Any) -> Any:
        real = real_connect(*args, **kwargs)

        class Wrapper:
            def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
                self.con = con
                self._failed = False

            def execute(self, sql: str, *a: Any, **kw: Any):
                if not self._failed and sql == "LOAD sqlite":
                    self._failed = True
                    raise RuntimeError("fail")
                return self.con.execute(sql, *a, **kw)

            def __getattr__(self, name: str) -> object:
                return getattr(self.con, name)

        return Wrapper(real)

    monkeypatch.setattr(server.duckdb, "connect", failing_connect)

    app = server.create_app(sqlite_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "order_by": "timestamp",
        "columns": ["timestamp", "value"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["rows"][0][1] == big_value


def test_envvar_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    csv_file = tmp_path / "custom.csv"
    csv_file.write_text("timestamp,event,value,user\n2024-01-01 00:00:00,login,5,bob\n")
    monkeypatch.setenv("SCUBADUCK_DB", str(csv_file))
    app = server.create_app()
    client = app.test_client()
    payload = _make_payload()
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    rows = rv.get_json()["rows"]
    assert len(rows) == 1


def test_envvar_db_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite"
    monkeypatch.setenv("SCUBADUCK_DB", str(missing))
    with pytest.raises(FileNotFoundError):
        server.create_app()


def test_group_by_table() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "table",
        "order_by": "user",
        "limit": 10,
        "columns": ["value"],
        "group_by": ["user"],
        "aggregate": "Sum",
        "show_hits": True,
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    rows = rv.get_json()["rows"]
    assert rows[0][0] == "alice"
    assert rows[0][1] == 2
    assert rows[0][2] == 40


def test_relative_time_query(monkeypatch: pytest.MonkeyPatch) -> None:
    app = server.app
    client = app.test_client()

    from datetime import datetime

    fixed_now = datetime(2024, 1, 2, 4, 0, 0)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    monkeypatch.setattr(server, "datetime", FixedDateTime)

    payload = {
        "table": "events",
        "start": "-1 hour",
        "end": "now",
        "order_by": "timestamp",
        "limit": 100,
        "columns": ["timestamp", "event", "value", "user"],
        "filters": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 1
    assert data["rows"][0][3] == "charlie"


def test_invalid_time_error() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "nonsense",
        "end": "now",
        "order_by": "timestamp",
        "limit": 10,
        "columns": ["timestamp"],
        "filters": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 400
    assert "error" in data


def test_query_error_returns_sql_and_traceback() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "columns": ["event"],
        "group_by": ["user"],
        "aggregate": "avg",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 400
    assert "error" in data


def test_table_unknown_column_error() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "table",
        "order_by": "timestamp",
        "limit": 100,
        "columns": ["user", "Hits", "value"],
        "group_by": ["user"],
        "aggregate": "Count",
        "show_hits": True,
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 400
    assert "Unknown column" in data["error"]


def test_samples_view_rejects_group_by() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "graph_type": "samples",
        "group_by": ["user"],
        "columns": ["timestamp"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 400
    assert "only valid" in data["error"]


def test_table_avg_with_timestamp() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "table",
        "order_by": "user",
        "limit": 100,
        "columns": ["user", "timestamp", "value"],
        "group_by": ["user"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert "error" not in data
    rows = data["rows"]
    assert rows[0][0] == "alice"
    from dateutil import parser

    ts = parser.parse(rows[0][1]).replace(tzinfo=None)
    assert ts == parser.parse("2024-01-01 12:00:00")


def test_timeseries_basic() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "limit": 100,
        "group_by": ["user"],
        "aggregate": "Count",
        "columns": ["value"],
        "x_axis": "timestamp",
        "granularity": "1 day",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 4


def test_timeseries_orders_by_xaxis() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "limit": 100,
        "columns": ["value"],
        "x_axis": "timestamp",
        "granularity": "1 day",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    rows = data["rows"]
    from dateutil import parser

    timestamps = [parser.parse(r[0]).replace(tzinfo=None) for r in rows]
    assert timestamps == sorted(timestamps)


def test_timeseries_limit_applies_to_series() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "limit": 1,
        "order_by": "user",
        "group_by": ["user"],
        "aggregate": "Count",
        "columns": ["value"],
        "x_axis": "timestamp",
        "granularity": "1 day",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 2
    assert all(r[1] == "alice" for r in data["rows"])


def test_timeseries_auto_and_fine_buckets() -> None:
    app = server.app
    client = app.test_client()

    def run(gran: str) -> None:
        payload = {
            "start": "2024-01-01 00:00:00",
            "end": "2024-01-02 03:00:00",
            "graph_type": "timeseries",
            "columns": ["value"],
            "x_axis": "timestamp",
            "granularity": gran,
        }
        rv = client.post(
            "/api/query", data=json.dumps(payload), content_type="application/json"
        )
        data = rv.get_json()
        assert rv.status_code == 200
        from dateutil import parser

        start = parser.parse(cast(str, payload["start"])).replace(tzinfo=None)
        buckets = [
            parser.parse(cast(str, r[0])).replace(tzinfo=None) for r in data["rows"]
        ]
        assert buckets[0] == start
        if len(buckets) > 1:
            step = (buckets[1] - buckets[0]).total_seconds()
            assert step % data["bucket_size"] == 0
        assert any(r[1] != 0 for r in data["rows"])

    run("Auto")
    run("Fine")


def test_timeseries_string_column_error() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "limit": 7,
        "columns": ["timestamp", "event", "value", "user"],
        "x_axis": "timestamp",
        "granularity": "1 hour",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 400
    assert "Aggregate" in data["error"]


def test_derived_column_basic() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "limit": 10,
        "columns": ["timestamp"],
        "derived_columns": {"val2": "value * 2"},
        "filters": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["rows"][0][1] == 20


def test_timeseries_derived_column() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "granularity": "1 hour",
        "limit": 7,
        "columns": ["value"],
        "derived_columns": {"derived_1": "value * 2"},
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    rows = data["rows"]
    assert all(r[2] == r[1] * 2 for r in rows)


def test_default_start_end_returned() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "order_by": "timestamp",
        "limit": 5,
        "columns": ["timestamp"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["start"] == "2024-01-01 00:00:00"
    assert data["end"] == "2024-01-02 03:00:00"
