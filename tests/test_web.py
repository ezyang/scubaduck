from typing import Any
from tests.web_utils import select_value


def test_order_by_implicit_column(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")
    page.uncheck("#column_groups input[value='timestamp']")
    page.click("text=View Settings")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-02 00:00:00")
    select_value(page, "#order_by", "timestamp")
    page.fill("#limit", "10")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    headers = page.locator("#results th").all_inner_texts()
    assert "timestamp" in headers
    assert len(data["rows"][0]) == 4
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")
    assert not page.is_checked("#column_groups input[value='timestamp']")
