from __future__ import annotations

from typing import Any


def run_query(page: Any, url: str, *, start: str | None = None, end: str | None = None,
              order_by: str | None = None, order_dir: str | None = "ASC", limit: int | None = None) -> dict[str, Any]:
    page.goto(url)
    page.wait_for_selector("#order_by option", state="attached")
    if start is not None:
        page.fill("#start", start)
    if end is not None:
        page.fill("#end", end)
    if order_by is not None:
        page.select_option("#order_by", order_by)
    if order_dir is not None:
        page.select_option("#order_dir", order_dir)
    if limit is not None:
        page.fill("#limit", str(limit))
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    return page.evaluate("window.lastResults")


def test_range_filters(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-02 00:00:00",
        end="2024-01-02 04:00:00",
        order_by="timestamp",
        limit=100,
    )
    assert len(data["rows"]) == 2
    from dateutil import parser

    timestamps = [parser.parse(row[0]).replace(tzinfo=None) for row in data["rows"]]
    assert timestamps == [
        parser.parse("2024-01-02 00:00:00"),
        parser.parse("2024-01-02 03:00:00"),
    ]


def test_order_by(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="value",
        order_dir="DESC",
        limit=100,
    )
    values = [row[2] for row in data["rows"]]
    assert values == sorted(values, reverse=True)


def test_limit(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="timestamp",
        limit=2,
    )
    assert len(data["rows"]) == 2

