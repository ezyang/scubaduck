from __future__ import annotations

import json
from scubaduck import server


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


def test_subset_columns() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-02 00:00:00",
        "order_by": "timestamp",
        "limit": 10,
        "columns": ["timestamp", "event"],
        "filters": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    rows = rv.get_json()["rows"]
    assert rows
    # Only two columns requested
    assert len(rows[0]) == 2
