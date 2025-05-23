from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from scubaduck import server


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


def test_sqlite_longvarchar(tmp_path: Path) -> None:
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


def test_sqlite_bigint(tmp_path: Path) -> None:
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


def test_sqlite_bytes(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "bin.sqlite"
    import sqlite3

    conn = sqlite3.connect(sqlite_file)
    conn.execute("CREATE TABLE events (timestamp TEXT, data BLOB)")
    conn.execute(
        "INSERT INTO events VALUES ('2024-01-01 00:00:00', ?)",
        (b"\x00\xff",),
    )
    conn.commit()
    conn.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    app = server.create_app(sqlite_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "order_by": "timestamp",
        "columns": ["timestamp", "data"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["rows"] == [["2024-01-01 00:00:00", "b'\\x00\\xff'"]]


def test_sqlite_boolean_aggregation(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "bool.sqlite"
    import sqlite3

    conn = sqlite3.connect(sqlite_file)
    conn.execute("CREATE TABLE events (timestamp TEXT, flag BOOLEAN)")
    conn.execute("INSERT INTO events VALUES ('2024-01-01 00:00:00', 1)")
    conn.execute("INSERT INTO events VALUES ('2024-01-01 00:30:00', 0)")
    conn.commit()
    conn.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    app = server.create_app(sqlite_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-02 00:00:00",
        "graph_type": "table",
        "aggregate": "Avg",
        "columns": ["flag"],
        "show_hits": True,
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["rows"][0][0] == 2
    assert data["rows"][0][1] == 0.5


def test_sqlite_boolean_group_by(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "bool.sqlite"
    import sqlite3

    conn = sqlite3.connect(sqlite_file)
    conn.execute("CREATE TABLE events (id INTEGER, ts TEXT, flag BOOLEAN)")
    conn.execute("INSERT INTO events VALUES (1, '2024-01-01 00:00:00', 1)")
    conn.execute("INSERT INTO events VALUES (1, '2024-01-01 00:30:00', 0)")
    conn.execute("INSERT INTO events VALUES (2, '2024-01-01 01:00:00', 1)")
    conn.commit()
    conn.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    app = server.create_app(sqlite_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-02 00:00:00",
        "graph_type": "table",
        "time_column": "ts",
        "aggregate": "Avg",
        "group_by": ["id"],
        "columns": ["flag"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    rows = sorted(data["rows"])  # order can vary
    assert rows == [[1, 2, 0.5], [2, 1, 1.0]]


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


def test_envvar_parquet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    parquet_file = tmp_path / "events.parquet"
    con = duckdb.connect()
    csv_path = Path("scubaduck/sample.csv").resolve()
    con.execute(
        f"COPY (SELECT * FROM read_csv_auto('{csv_path.as_posix()}')) TO '{parquet_file.as_posix()}' (FORMAT PARQUET)"
    )
    con.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    monkeypatch.setenv("SCUBADUCK_DB", str(parquet_file))
    app = server.create_app()
    client = app.test_client()
    payload = _make_payload()
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    rows = rv.get_json()["rows"]
    assert len(rows) == 3


def test_envvar_db_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite"
    monkeypatch.setenv("SCUBADUCK_DB", str(missing))
    with pytest.raises(FileNotFoundError):
        server.create_app()
