from __future__ import annotations

import json

from scubaduck import server


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


def test_order_by_ignored_when_not_selected() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "order_by": "value",
        "columns": ["timestamp"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert "ORDER BY" not in data["sql"]
