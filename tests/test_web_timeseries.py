from __future__ import annotations

from typing import Any

from tests.web_utils import select_value
from collections.abc import Iterator
import threading
import pytest
from werkzeug.serving import make_server
from scubaduck.server import create_app


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


def test_timeseries_default_query(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    assert "error" not in data
    assert page.is_visible("#chart")
    page.click("text=Columns")
    assert not page.is_checked("#column_groups input[value='timestamp']")


def test_timeseries_single_bucket(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-01 00:00:00")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    path = page.get_attribute("#chart path", "d")
    assert path is not None and "NaN" not in path


def test_timeseries_fill_options(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-02 03:00:00")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    select_value(page, "#granularity", "1 hour")

    select_value(page, "#fill", "0")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    path_zero = page.get_attribute("#chart path", "d")
    assert path_zero is not None and path_zero.count("L") > 20

    select_value(page, "#fill", "connect")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    path_conn = page.get_attribute("#chart path", "d")
    assert path_conn is not None and path_conn.count("M") == 1

    select_value(page, "#fill", "blank")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    path_blank = page.get_attribute("#chart path", "d")
    assert path_blank is not None and path_blank.count("M") > 1


def test_timeseries_hover_highlight(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart path", state="attached")
    path_el = page.query_selector("#chart path")
    assert path_el
    page.evaluate(
        "el => el.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}))",
        path_el,
    )
    width = page.evaluate(
        "getComputedStyle(document.querySelector('#chart path')).strokeWidth"
    )
    assert "2.5" in width
    color = page.evaluate(
        "getComputedStyle(document.querySelector('#legend .legend-item')).backgroundColor"
    )
    assert "221, 221, 221" in color


def test_timeseries_crosshair(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart path", state="attached")
    page.eval_on_selector(
        "#chart",
        "el => { const r = el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('mousemove', {clientX: r.left + r.width/2, clientY: r.top + r.height/2, bubbles: true})); }",
    )
    line_display = page.evaluate(
        "document.getElementById('crosshair_line').style.display"
    )
    assert line_display != "none"
    count = page.eval_on_selector_all("#crosshair_dots circle", "els => els.length")
    assert count > 0
    page.eval_on_selector(
        "#chart",
        "el => el.dispatchEvent(new MouseEvent('mouseleave', {bubbles: true}))",
    )
    line_display = page.evaluate(
        "document.getElementById('crosshair_line').style.display"
    )
    assert line_display == "none"


def test_timeseries_crosshair_freeze(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart path", state="attached")
    page.eval_on_selector(
        "#chart",
        "el => { const r = el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('mousemove', {clientX: r.left + r.width/2, clientY: r.top + r.height/2, bubbles: true})); }",
    )
    page.eval_on_selector(
        "#chart",
        "el => { const r = el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('click', {clientX: r.left + r.width/2, clientY: r.top + r.height/2, bubbles: true})); }",
    )
    line_display = page.evaluate(
        "document.getElementById('crosshair_line').style.display"
    )
    assert line_display != "none"
    pos1 = page.evaluate("document.getElementById('crosshair_line').getAttribute('x1')")
    page.eval_on_selector(
        "#chart",
        "el => { const r = el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('mousemove', {clientX: r.left + r.width/4, clientY: r.top + r.height/2, bubbles: true})); }",
    )
    pos2 = page.evaluate("document.getElementById('crosshair_line').getAttribute('x1')")
    assert pos1 == pos2
    page.eval_on_selector(
        "#chart",
        "el => el.dispatchEvent(new MouseEvent('mouseleave', {bubbles: true}))",
    )
    line_display = page.evaluate(
        "document.getElementById('crosshair_line').style.display"
    )
    assert line_display != "none"
    page.eval_on_selector(
        "#chart",
        "el => { const r = el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('click', {clientX: r.left + r.width/2, clientY: r.top + r.height/2, bubbles: true})); }",
    )
    line_display = page.evaluate(
        "document.getElementById('crosshair_line').style.display"
    )
    assert line_display == "none"


def test_timeseries_auto_timezone(browser: Any, server_url: str) -> None:
    context = browser.new_context(timezone_id="America/New_York")
    page = context.new_page()
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    path = page.get_attribute("#chart path", "d")
    context.close()
    assert path is not None
    coords = [float(p.split(" ")[1]) for p in path.replace("M", "L").split("L")[1:]]
    assert max(coords) > min(coords)


def test_timeseries_multi_series(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=Add Derived")
    expr = page.query_selector("#derived_list .derived textarea")
    assert expr
    name_inp = page.query_selector("#derived_list .derived .d-name")
    assert name_inp
    name_inp.fill("value_2")
    expr.fill("value * 2")
    page.click("text=View Settings")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-03 00:00:00")
    select_value(page, "#granularity", "1 hour")
    select_value(page, "#aggregate", "Avg")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    count = page.eval_on_selector_all("#chart path", "els => els.length")
    assert count == 2


def test_timeseries_resize(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart path", state="attached")

    def chart_info() -> dict[str, float]:
        return page.evaluate(
            "() => {const p=document.querySelector('#chart path'); const nums=p.getAttribute('d').match(/[-0-9.]+/g).map(parseFloat); return {width: parseFloat(document.getElementById('chart').getAttribute('width')), last: nums[nums.length-2]};}"
        )

    before = chart_info()
    legend_width = page.evaluate(
        "parseFloat(getComputedStyle(document.getElementById('legend')).width)"
    )
    assert page.evaluate(
        "() => document.getElementById('legend').getBoundingClientRect().right <= document.getElementById('chart').getBoundingClientRect().left"
    )
    page.evaluate("document.getElementById('sidebar').style.width='200px'")
    page.wait_for_function(
        "width => document.getElementById('chart').getAttribute('width') != width",
        arg=before["width"],
    )
    after = chart_info()
    legend_width_after = page.evaluate(
        "parseFloat(getComputedStyle(document.getElementById('legend')).width)"
    )
    assert after["width"] > before["width"]
    assert after["last"] > before["last"]
    assert legend_width_after == legend_width


def test_timeseries_no_overflow(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    overflow = page.evaluate(
        "var v=document.getElementById('view'); v.scrollWidth > v.clientWidth"
    )
    assert not overflow


def test_timeseries_axis_ticks(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart text.tick-label", state="attached")
    count = page.eval_on_selector_all("#chart text.tick-label", "els => els.length")
    assert count > 2


def test_timeseries_y_axis_labels(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart text.y-tick-label", state="attached")
    count = page.eval_on_selector_all("#chart text.y-tick-label", "els => els.length")
    grid_count = page.eval_on_selector_all("#chart line.grid", "els => els.length")
    assert count > 0 and count == grid_count


def test_timeseries_interval_offset(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-03 12:00:00")
    select_value(page, "#granularity", "1 hour")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart text.tick-label", state="attached")
    labels = page.eval_on_selector_all(
        "#chart text.tick-label", "els => els.map(e => e.textContent)"
    )
    assert labels
    assert all(lbl != "00:00" for lbl in labels)
    times = [lbl for lbl in labels if ":" in lbl]
    assert times
    for t in times:
        h = int(t.split(":")[0])
        assert h % 4 == 0


def test_timeseries_legend_values(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.evaluate("g => { groupBy.chips = g; groupBy.renderChips(); }", ["user"])
    select_value(page, "#aggregate", "Avg")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    headers = page.evaluate(
        "() => Array.from(document.querySelectorAll('#legend .legend-header')).map(e => e.textContent)"
    )
    assert any(h.startswith("alice") for h in headers)
    page.wait_for_selector("#chart path", state="attached")
    page.eval_on_selector(
        "#chart",
        "el => { const r=el.getBoundingClientRect(); el.dispatchEvent(new MouseEvent('mousemove', {clientX:r.left+r.width/2, clientY:r.top+r.height/2, bubbles:true})); }",
    )
    value = page.evaluate("document.querySelector('#legend .legend-value').textContent")
    assert value != ""


def test_timeseries_group_links(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-02 03:00:00")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    assert page.text_content("#legend .drill-links h4") == "Group by"
    page.click("#legend .drill-links a:text('user')")
    page.wait_for_function("window.lastResults !== undefined")
    chips = page.evaluate("groupBy.chips")
    assert chips == ["user"]
    assert page.text_content("#legend .drill-links h4") == "Drill up"
    assert page.is_visible("#legend .drill-links a:text('Aggregate')")


def test_timeseries_rotated_day_labels_padding(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.check("#column_groups input[value='value']")
    page.click("text=View Settings")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-16 00:00:00")
    select_value(page, "#granularity", "1 day")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart text.tick-label", state="attached")
    assert page.eval_on_selector_all(
        "#chart text.tick-label.rotated", "els => els.length"
    )
    overflow = page.eval_on_selector(
        "#chart",
        "el => {const r=el.getBoundingClientRect(); return Array.from(el.querySelectorAll('text.tick-label')).some(t => t.getBoundingClientRect().bottom > r.bottom);}",
    )
    assert not overflow


def test_timeseries_count_no_columns_numeric_time(
    page: Any, test_dataset_server_url: str
) -> None:
    page.goto(test_dataset_server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.click("text=Columns")
    page.click("#columns_none")
    page.click("text=View Settings")
    select_value(page, "#time_column", "ts")
    select_value(page, "#time_unit", "s")
    select_value(page, "#aggregate", "Count")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    page.wait_for_selector("#chart path", state="attached")
    series_count = page.eval_on_selector_all("#chart path", "els => els.length")
    assert series_count == 1
