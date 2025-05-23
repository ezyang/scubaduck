from __future__ import annotations

import json
from typing import Any, cast

from scubaduck import server


def test_group_by_table() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
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


def test_table_avg_with_timestamp() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "table",
        "order_by": "user",
        "limit": 100,
        "columns": ["user", "timestamp", "value"],
        "group_by": ["user"],
        "aggregate": "Avg",
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

    ts = parser.parse(rows[0][2]).replace(tzinfo=None)
    assert ts == parser.parse("2024-01-01 12:00:00")


def test_timeseries_basic() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
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
    payload: dict[str, Any] = {
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


def test_timeseries_count_no_columns() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "granularity": "1 day",
        "columns": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    rows = data["rows"]
    assert len(rows) == 2
    assert rows[0][1] == 2
    assert rows[1][1] == 2
    assert len(rows[0]) == 3


def test_timeseries_limit_applies_to_series() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
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


def test_timeseries_sparse_limit_filtering() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "limit": 2,
        "group_by": ["user"],
        "columns": ["value"],
        "x_axis": "timestamp",
        "granularity": "1 day",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 3
    users = {r[1] for r in data["rows"]}
    assert users == {"alice", "bob"}


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
    assert rv.status_code == 200


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
        "aggregate": "Avg",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    rows = data["rows"]
    assert all(r[3] == r[2] * 2 for r in rows)


def test_reserved_word_column() -> None:
    app = server.create_app("TEST")
    client = app.test_client()
    payload = {
        "table": "extra",
        "columns": ["ts", "desc"],
        "order_by": "ts",
        "time_column": "",
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert len(data["rows"]) == 2
    assert data["rows"][0][1] == "x"


def test_table_count_group_by_extra() -> None:
    app = server.create_app("TEST")
    client = app.test_client()
    payload = {
        "table": "extra",
        "graph_type": "table",
        "time_column": "",
        "group_by": ["num"],
        "aggregate": "Count",
        "columns": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    rows = sorted(data["rows"])
    assert rows == [[1, 1], [2, 1]]
    assert all(len(r) == 2 for r in rows)


def test_order_by_samples_table() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "table",
        "order_by": "Samples",
        "order_dir": "DESC",
        "limit": 10,
        "columns": [],
        "group_by": ["user"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert 'ORDER BY "Hits" DESC' in data["sql"]


def test_order_by_samples_timeseries() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "timeseries",
        "order_by": "Samples",
        "order_dir": "DESC",
        "x_axis": "timestamp",
        "granularity": "1 day",
        "columns": [],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert 'ORDER BY "Hits" DESC' in data["sql"]


def test_order_by_samples_case_insensitive() -> None:
    app = server.app
    client = app.test_client()
    payload: dict[str, Any] = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "table",
        "order_by": "samples",
        "order_dir": "DESC",
        "limit": 10,
        "columns": [],
        "group_by": ["user"],
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert 'ORDER BY "Hits" DESC' in data["sql"]


def test_show_hits_client_side() -> None:
    app = server.app
    client = app.test_client()
    payload = {
        "table": "events",
        "start": "2024-01-01 00:00:00",
        "end": "2024-01-03 00:00:00",
        "graph_type": "table",
        "columns": ["value"],
        "group_by": ["user"],
        "aggregate": "Sum",
        "show_hits": False,
    }
    rv = client.post(
        "/api/query", data=json.dumps(payload), content_type="application/json"
    )
    data = rv.get_json()
    assert rv.status_code == 200
    assert "count(*) AS Hits" in data["sql"]
