from __future__ import annotations

from typing import Any

from tests.web_utils import select_value


def test_column_toggle_and_selection(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")

    count = page.evaluate(
        "document.querySelectorAll('#column_groups input:checked').length"
    )
    assert count == 4

    page.click("#columns_none")
    count = page.evaluate(
        "document.querySelectorAll('#column_groups input:checked').length"
    )
    assert count == 0
    page.click("#columns_all")
    count = page.evaluate(
        "document.querySelectorAll('#column_groups input:checked').length"
    )
    assert count == 4

    page.uncheck("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-02 00:00:00")
    select_value(page, "#order_by", "timestamp")
    page.fill("#limit", "10")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    assert len(data["rows"][0]) == 3
    headers = page.locator("#results th").all_inner_texts()
    assert "value" not in headers


def test_columns_links_alignment(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")
    tag = page.evaluate("document.getElementById('columns_all').tagName")
    assert tag == "A"
    align = page.evaluate(
        "getComputedStyle(document.querySelector('#column_actions')).textAlign"
    )
    assert align == "right"


def test_column_group_links(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Columns")
    page.wait_for_selector("#column_groups a", state="attached")
    tag = page.evaluate("document.querySelector('#column_groups .col-group a').tagName")
    assert tag == "A"


def test_column_group_links_float_right(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Columns")
    page.wait_for_selector("#column_groups .col-group .links", state="attached")
    float_val = page.evaluate(
        "getComputedStyle(document.querySelector('#column_groups .col-group .links')).float"
    )
    assert float_val == "right"


def test_columns_tab_selected_count(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    count_text = page.text_content("#columns_tab")
    assert count_text is not None and "(4)" in count_text
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")
    page.uncheck("#column_groups input[value='value']")
    count_text = page.text_content("#columns_tab")
    assert count_text is not None and "(3)" in count_text
