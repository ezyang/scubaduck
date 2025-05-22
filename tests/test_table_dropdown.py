import sqlite3
import threading
from pathlib import Path
from collections.abc import Iterator
from typing import Any

import pytest
from werkzeug.serving import make_server

from scubaduck.server import create_app
from tests.test_web import select_value


@pytest.fixture()
def multi_table_server_url(tmp_path: Path) -> Iterator[str]:
    db_path = tmp_path / "complex.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, ts TEXT, val REAL, name TEXT, flag BOOLEAN)"
    )
    conn.execute(
        "INSERT INTO events VALUES (1, '2024-01-01 00:00:00', 1.5, 'alice', 1)"
    )
    conn.execute("INSERT INTO events VALUES (2, '2024-01-01 01:00:00', 2.0, 'bob', 0)")
    conn.execute("CREATE TABLE extra (ts TEXT, desc TEXT, num INTEGER)")
    conn.execute("INSERT INTO extra VALUES ('2024-01-01 00:00:00', 'x', 1)")
    conn.execute("INSERT INTO extra VALUES ('2024-01-01 01:00:00', 'y', 2)")
    conn.commit()
    conn.close()

    app = create_app(db_path)
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
