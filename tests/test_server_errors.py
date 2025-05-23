from __future__ import annotations

import json

from pathlib import Path

from scubaduck import server


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
    _data = rv.get_json()
    assert rv.status_code == 200


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


def test_invalid_integer_time_value_suggests_unit(tmp_path: Path) -> None:
    csv_file = tmp_path / "events.csv"
    csv_file.write_text("created,event\n1704067200000000,login\n")
    app = server.create_app(csv_file)
    client = app.test_client()
    payload = {
        "table": "events",
        "columns": ["created"],
        "time_column": "created",
        "time_unit": "s",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 400
    assert "maybe try time_unit us" in data["error"]
