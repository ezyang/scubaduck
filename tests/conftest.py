from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from werkzeug.serving import make_server

from scubaduck.server import app


@pytest.fixture()
def server_url() -> Iterator[str]:
    httpd = make_server("127.0.0.1", 0, app)
    port = httpd.server_port
    thread = threading.Thread(target=httpd.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        thread.join()
