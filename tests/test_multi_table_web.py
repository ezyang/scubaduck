import threading
from collections.abc import Iterator
from typing import Any

import pytest
from werkzeug.serving import make_server

from scubaduck.server import create_app
from tests.web_utils import select_value


@pytest.fixture()
def multi_table_server_url() -> Iterator[str]:
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


def test_table_param_updates_on_dive(page: Any, multi_table_server_url: str) -> None:
    page.goto(multi_table_server_url + "?table=events")
    page.wait_for_selector("#table option", state="attached")
    select_value(page, "#table", "extra")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    table_param = page.evaluate(
        "new URLSearchParams(window.location.search).get('table')"
    )
    assert table_param == "extra"


def test_table_dropdown_persists_on_refresh(
    page: Any, multi_table_server_url: str
) -> None:
    page.goto(multi_table_server_url + "?table=events")
    page.wait_for_selector("#table option", state="attached")
    select_value(page, "#table", "extra")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.reload()
    page.wait_for_selector("#table option", state="attached")
    assert page.input_value("#table") == "extra"
    disp = page.text_content("#table + .dropdown-display")
    assert disp is not None and disp.strip() == "extra"


def test_table_switch_resets_view_settings(
    page: Any, multi_table_server_url: str
) -> None:
    page.goto(multi_table_server_url + "?table=events")
    page.wait_for_selector("#table option", state="attached")
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")
    page.uncheck("#column_groups input:first-of-type")
    page.click("text=View Settings")
    select_value(page, "#graph_type", "table")
    page.fill("#limit", "50")
    page.evaluate("g => { groupBy.chips = ['name']; groupBy.renderChips(); }")
    select_value(page, "#table", "extra")
    page.wait_for_function("document.querySelector('#table').value === 'extra'")
    assert page.input_value("#graph_type") == "samples"
    assert page.input_value("#limit") == "100"
    chips = page.evaluate("groupBy.chips.length")
    assert chips == 0
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")
    count = page.evaluate(
        "document.querySelectorAll('#column_groups input:checked').length"
    )
    assert count == 3
