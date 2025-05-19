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


def test_simple_filter(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    filter_el = page.query_selector("#filters .filter:last-child")
    assert filter_el
    filter_el.query_selector(".f-col").select_option("user")
    val_input = filter_el.query_selector(".f-val")
    val_input.click()
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    assert len(data["rows"]) == 2
    assert all(row[3] == "alice" for row in data["rows"])


def test_local_sorting(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="timestamp",
        limit=100,
    )
    # Initial unsorted table matches server results
    cell_values = page.eval_on_selector_all(
        "#results td:nth-child(1)", "els => els.map(e => e.textContent)"
    )
    assert cell_values == [row[0] for row in data["rows"]]

    header_selector = "#results th:nth-child(3)"
    header = page.query_selector(header_selector)
    assert header and header.text_content() == "value"

    # Click to sort descending
    header.click()
    page.wait_for_timeout(100)
    header = page.query_selector(header_selector)
    assert header.text_content().endswith("\u2193")
    values = page.eval_on_selector_all(
        "#results td:nth-child(3)", "els => els.map(e => parseInt(e.textContent))"
    )
    assert values == sorted(values, reverse=True)

    # Click to sort ascending
    header.click()
    page.wait_for_timeout(100)
    header = page.query_selector(header_selector)
    assert header.text_content().endswith("\u2191")
    values = page.eval_on_selector_all(
        "#results td:nth-child(3)", "els => els.map(e => parseInt(e.textContent))"
    )
    assert values == sorted(values)

    # Click again to remove sorting
    header.click()
    page.wait_for_timeout(100)
    header = page.query_selector(header_selector)
    assert header.text_content() == "value"
    cell_values = page.eval_on_selector_all(
        "#results td:nth-child(1)", "els => els.map(e => e.textContent)"
    )
    assert cell_values == [row[0] for row in data["rows"]]

