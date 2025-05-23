import threading
from collections.abc import Iterator
from typing import Any

import pytest
from werkzeug.serving import make_server

from scubaduck.server import create_app
from tests.test_web import select_value


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
