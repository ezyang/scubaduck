from __future__ import annotations

import json
from pathlib import Path


import pytest

from scubaduck import server


def test_integer_time_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "events.csv"
    csv_file.write_text("created,event\n1704067200,login\n1704070800,logout\n")
    app = server.create_app(csv_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-01 01:00:00",
        "order_by": "created",
        "columns": ["created", "event"],
        "time_column": "created",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 2


def test_integer_time_unit_ms(tmp_path: Path) -> None:
    csv_file = tmp_path / "events.csv"
    csv_file.write_text("created,event\n1704067200000,login\n1704070800000,logout\n")
    app = server.create_app(csv_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-01 01:00:00",
        "order_by": "created",
        "columns": ["created", "event"],
        "time_column": "created",
        "time_unit": "ms",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 2


def test_timeseries_default_xaxis_uses_time_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "events.csv"
    csv_file.write_text("created,event\n1704067200000,login\n1704070800000,logout\n")
    app = server.create_app(csv_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-01 01:00:00",
        "graph_type": "timeseries",
        "granularity": "1 hour",
        "columns": ["event"],
        "aggregate": "Count",
        "time_column": "created",
        "time_unit": "ms",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 2


def test_integer_time_unit_us_default_start_end(tmp_path: Path) -> None:
    csv_file = tmp_path / "events.csv"
    csv_file.write_text(
        "created,event\n1704067200000000,login\n1704070800000000,logout\n"
    )
    app = server.create_app(csv_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "order_by": "created",
        "columns": ["created", "event"],
        "time_column": "created",
        "time_unit": "us",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["start"] == "2024-01-01 00:00:00"
    assert data["end"] == "2024-01-01 01:00:00"
    assert len(data["rows"]) == 2


def test_sqlite_integer_time_unit_us(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "events.sqlite"
    import sqlite3

    conn = sqlite3.connect(sqlite_file)
    conn.execute("CREATE TABLE visits (visit_time INTEGER, event TEXT)")
    big_ts = 13384551652000000
    conn.execute("INSERT INTO visits VALUES (?, ?)", (big_ts, "foo"))
    conn.commit()
    conn.close()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    app = server.create_app(sqlite_file)
    client = app.test_client()
    payload = {
        "table": "visits",
        "start": "2394-02-20 00:00:00",
        "end": "2394-02-21 00:00:00",
        "order_by": "visit_time",
        "columns": ["visit_time", "event"],
        "time_column": "visit_time",
        "time_unit": "us",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 1


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


def test_relative_month_year(monkeypatch: pytest.MonkeyPatch) -> None:
    app = server.app
    client = app.test_client()

    from datetime import datetime

    fixed_now = datetime(2024, 1, 2, 0, 0, 0)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    monkeypatch.setattr(server, "datetime", FixedDateTime)

    payload = {
        "table": "events",
        "start": "-1 year",
        "end": "-1 month",
        "order_by": "timestamp",
        "limit": 10,
        "columns": ["timestamp"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["start"] == "2023-01-02 00:00:00"
    assert data["end"] == "2023-12-02 00:00:00"


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


def test_time_column_none_no_time_filter() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "columns": ["timestamp", "event"],
        "time_column": "",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert "start" not in data and "end" not in data
    assert len(data["rows"]) == 4


def test_test_dataset_int32_time_s() -> None:
    app = server.create_app("TEST")
    client = app.test_client()
    payload = {
        "table": "events",
        "time_column": "ts",
        "time_unit": "s",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["start"] == "2024-01-01 00:00:00"
    assert data["end"] == "2024-01-01 01:00:00"
    assert len(data["rows"]) == 2


def test_test_dataset_int32_time_us() -> None:
    app = server.create_app("TEST")
    client = app.test_client()
    payload = {
        "table": "events",
        "time_column": "ts",
        "time_unit": "us",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert data["start"] == "2024-01-01 00:00:00"
    assert data["end"] == "2024-01-01 01:00:00"
    assert len(data["rows"]) == 2
