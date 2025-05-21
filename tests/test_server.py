from __future__ import annotations

import json
from pathlib import Path

import duckdb
from scubaduck import server
import pytest


def test_basic_query() -> None:
    app = server.app
    client = app.test_client()
    payload = {
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


def test_filter_multi_token() -> None:
    app = server.app
    client = app.test_client()
    payload = {
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
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "order_by": "timestamp",
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


def test_group_by_table() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
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
