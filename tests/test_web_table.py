from __future__ import annotations

from typing import Any

from collections.abc import Iterator
import threading

import pytest
from werkzeug.serving import make_server

from scubaduck.server import create_app
from tests.web_utils import run_query, select_value


@pytest.fixture()
def test_dataset_server_url() -> Iterator[str]:
    app = create_app("TEST")
    httpd = make_server("127.0.0.1", 0, app)
    port = httpd.server_port
    thread = threading.Thread(target=httpd.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        thread.join()


def test_table_sorting(page: Any, server_url: str) -> None:
    run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="user",
        order_dir="ASC",
        limit=100,
    )
    # header alignment
    align = page.evaluate(
        "getComputedStyle(document.querySelector('#results th')).textAlign"
    )
    assert align == "left"

    header = page.locator("#results th").nth(3)

    def values() -> list[str]:
        return page.locator("#results td:nth-child(4)").all_inner_texts()

    orig_rows = values()
    assert orig_rows == ["alice", "bob", "alice", "charlie"]

    first_sql = page.evaluate("window.lastResults.sql")

    header.click()
    assert values() == sorted(orig_rows)
    assert header.inner_text().endswith("▲")
    color = page.evaluate(
        "getComputedStyle(document.querySelector('#results th:nth-child(4)')).color"
    )
    assert "0, 0, 255" in color
    assert page.evaluate("window.lastResults.sql") == first_sql

    header.click()
    assert values() == sorted(orig_rows, reverse=True)
    assert header.inner_text().endswith("▼")

    header.click()
    assert values() == orig_rows
    assert header.inner_text() == "user"
    color = page.evaluate(
        "getComputedStyle(document.querySelector('#results th:nth-child(4)')).color"
    )
    assert "0, 0, 255" not in color


def test_table_avg_group_by(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="timestamp",
        group_by=["user"],
        aggregate="Avg",
    )
    assert "error" not in data
    assert len(data["rows"]) == 3


def test_table_enhancements(page: Any, server_url: str) -> None:
    run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="timestamp",
        limit=10,
    )
    border = page.evaluate(
        "getComputedStyle(document.querySelector('#results td')).borderStyle"
    )
    assert border == "solid"

    color1 = page.evaluate(
        "getComputedStyle(document.querySelector('#results tr:nth-child(2) td')).backgroundColor"
    )
    color2 = page.evaluate(
        "getComputedStyle(document.querySelector('#results tr:nth-child(3) td')).backgroundColor"
    )
    assert color1 != color2

    page.hover("#results tr:nth-child(2)")
    hover_color = page.evaluate(
        "getComputedStyle(document.querySelector('#results tr:nth-child(2) td')).backgroundColor"
    )
    assert hover_color != color1

    page.click("#results tr:nth-child(2)")
    selected_color = page.evaluate(
        "getComputedStyle(document.querySelector('#results tr:nth-child(2) td')).backgroundColor"
    )
    assert "189, 228, 255" in selected_color

    overflow = page.evaluate(
        "var v=document.getElementById('view'); v.scrollWidth > v.clientWidth"
    )
    assert not overflow


def test_table_single_selection(page: Any, server_url: str) -> None:
    run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="timestamp",
        limit=10,
    )
    page.click("#results tr:nth-child(2)")
    page.click("#results tr:nth-child(3)")
    count = page.evaluate("document.querySelectorAll('#results tr.selected').length")
    assert count == 1
    is_third = page.evaluate(
        "document.querySelector('#results tr:nth-child(3)').classList.contains('selected')"
    )
    assert is_third


def test_timestamp_rendering(page: Any, server_url: str) -> None:
    run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-02 00:00:00",
        order_by="timestamp",
        limit=1,
    )
    cell = page.text_content("#results td")
    assert cell != "Invalid Date"
    valid = page.evaluate("v => !isNaN(Date.parse(v))", cell)
    assert valid


def test_empty_data_message(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2025-01-01 00:00:00",
        end="2025-01-02 00:00:00",
        order_by="timestamp",
        limit=100,
    )
    assert data["rows"] == []
    msg = page.text_content("#view")
    assert "Empty data provided to table" in msg


def test_group_by_chip_from_url(page: Any, server_url: str) -> None:
    url = f"{server_url}?graph_type=table&group_by=user&order_by=user&limit=10"
    page.goto(url)
    page.wait_for_selector("#group_by_field .chip", state="attached")
    chips = page.evaluate(
        "Array.from(document.querySelectorAll('#group_by_field .chip')).map(c => c.firstChild.textContent)"
    )
    assert chips == ["user"]


def test_group_by_autocomplete(page: Any, server_url: str) -> None:
    page.goto(f"{server_url}?graph_type=table")
    page.wait_for_selector("#group_by_field", state="visible")
    inp = page.query_selector("#group_by_field .f-val")
    assert inp
    inp.click()
    page.keyboard.type("us")
    page.wait_for_selector("#group_by_field .chip-dropdown div")
    options = page.locator("#group_by_field .chip-dropdown div").all_inner_texts()
    assert "user" in options


def test_group_by_copy_icon(page: Any, server_url: str) -> None:
    page.goto(f"{server_url}?graph_type=table")
    page.wait_for_selector("#group_by_field", state="visible")
    icon = page.text_content("#group_by_field .chip-copy")
    assert icon == "⎘"


def test_group_by_input_no_border(page: Any, server_url: str) -> None:
    page.goto(f"{server_url}?graph_type=table")
    page.wait_for_selector("#group_by_field", state="visible")
    border = page.evaluate(
        "getComputedStyle(document.querySelector('#group_by_field .f-val')).borderStyle"
    )
    assert border == "none"


def test_table_group_by_query(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="user",
        limit=100,
        group_by=["user"],
        aggregate="Count",
    )
    assert "error" not in data
    assert len(data["rows"]) == 3


def test_table_avg_no_group_by(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        aggregate="Avg",
        order_by="timestamp",
    )
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row[0] == 4
    from dateutil import parser

    ts = parser.parse(row[1]).replace(tzinfo=None)
    assert ts == parser.parse("2024-01-01 13:00:00")
    assert row[2] == 25


def test_table_headers_show_aggregate(page: Any, server_url: str) -> None:
    run_query(
        page,
        server_url,
        aggregate="Avg",
        order_by="timestamp",
    )
    headers = page.locator("#results th").all_inner_texts()
    assert "Hits" in headers
    assert "timestamp (avg)" in headers
    assert "value (avg)" in headers


def test_format_number_function(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    vals = page.evaluate(
        "() => [formatNumber(815210), formatNumber(999.999), formatNumber(0.0004), formatNumber(0)]"
    )
    assert vals == ["815.21 K", "999.999", "0.000", "0"]


def test_numeric_cell_nowrap(page: Any, server_url: str) -> None:
    run_query(page, server_url, order_by="timestamp", limit=10)
    whitespace = page.evaluate(
        "getComputedStyle(document.querySelector('#results td:nth-child(3)')).whiteSpace"
    )
    assert whitespace == "nowrap"


def test_date_cell_nowrap(page: Any, server_url: str) -> None:
    run_query(page, server_url, order_by="timestamp", limit=10)
    whitespace = page.evaluate(
        "getComputedStyle(document.querySelector('#results td:nth-child(1)')).whiteSpace"
    )
    assert whitespace == "nowrap"


def test_derived_column_query(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    select_value(page, "#order_by", "timestamp")
    page.click("text=Columns")
    page.click("text=Add Derived")
    expr = page.query_selector("#derived_list .derived textarea")
    assert expr
    expr.fill("value * 2")
    page.click("text=View Settings")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-03 00:00:00")
    page.fill("#limit", "10")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    assert data["rows"][0][-1] == 20


def test_derived_column_remove(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Columns")
    page.click("text=Add Derived")
    assert page.query_selector("#derived_list .derived button.remove")
    page.click("#derived_list .derived button.remove")
    count = page.evaluate("document.querySelectorAll('#derived_list .derived').length")
    assert count == 0


def test_sql_query_display(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-02 00:00:00",
        order_by="timestamp",
        limit=10,
    )
    sql = data["sql"]
    displayed = page.text_content("#sql_query")
    assert displayed is not None
    assert displayed.strip() == sql


def test_table_count_no_columns(page: Any, test_dataset_server_url: str) -> None:
    page.goto(test_dataset_server_url)
    page.wait_for_selector("#order_by option", state="attached")
    select_value(page, "#graph_type", "table")
    page.click("text=Columns")
    page.click("#columns_all")
    page.click("text=View Settings")
    page.evaluate("groupBy.chips = ['id']; groupBy.renderChips();")
    select_value(page, "#aggregate", "Count")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    headers = page.locator("#results th").all_inner_texts()
    assert headers == ["id", "Hits"]
    col_count = page.locator("#results th").count()
    row_count = page.locator("#results tr").count()
    assert col_count == 2
    assert row_count == 3
    overflow = page.evaluate(
        "var v=document.getElementById('view'); v.scrollWidth > v.clientWidth"
    )
    assert not overflow
