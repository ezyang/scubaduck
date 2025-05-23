from __future__ import annotations

from typing import Any

from tests.web_utils import run_query, select_value


def test_range_filters(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="2024-01-02 00:00:00",
        end="2024-01-02 04:00:00",
        order_by="user",
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
        order_by="user",
        limit=2,
    )
    assert len(data["rows"]) == 2


def test_time_column_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#time_column option", state="attached")
    options = page.locator("#time_column option").all_inner_texts()
    assert "(none)" in options
    assert "timestamp" in options
    assert "value" in options
    assert page.input_value("#time_column") == "timestamp"


def test_time_column_none_hides_range(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#time_column option", state="attached")
    select_value(page, "#time_column", "")
    assert page.is_hidden("#start")
    assert page.is_hidden("#end")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    assert len(data["rows"]) == 4
    assert "start" not in data and "end" not in data


def test_time_unit_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#time_unit", state="attached")
    opts = page.locator("#time_unit option").all_inner_texts()
    assert "ms" in opts
    assert page.input_value("#time_unit") == "s"


def test_time_unit_hidden_when_no_time_column(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#time_column option", state="attached")
    select_value(page, "#time_column", "")
    assert page.is_hidden("#time_unit")


def test_table_selector_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#table option", state="attached")
    disp = page.query_selector("#table + .dropdown-display")
    assert disp
    assert (
        page.evaluate("getComputedStyle(document.querySelector('#table')).display")
        == "none"
    )
    assert page.query_selector("#table + .dropdown-display + .dropdown-menu input")


def test_dropdown_scroll_to_selected(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#table option", state="attached")
    page.evaluate(
        "() => { const sel=document.getElementById('table'); for(let i=0;i<30;i++){const o=document.createElement('option'); o.value='t'+i; o.textContent='Table '+i; sel.appendChild(o);} setSelectValue(sel,'t25'); }"
    )
    page.click("#table + .dropdown-display")
    page.wait_for_selector("#table + .dropdown-display + .dropdown-menu div.selected")
    scroll_top = page.evaluate(
        "document.querySelector('#table + .dropdown-display + .dropdown-menu').scrollTop"
    )
    assert scroll_top > 0


def test_x_axis_default_entry(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    page.wait_for_selector("#x_axis option", state="attached")
    options = page.locator("#x_axis option").all_inner_texts()
    assert "(default)" in options
    assert page.input_value("#x_axis") == ""


def test_simple_filter(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    filter_el = page.query_selector("#filters .filter:last-child")
    assert filter_el
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": filter_el, "val": "user"},
    )
    val_input = filter_el.query_selector(".f-val")
    val_input.click()
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    assert len(data["rows"]) == 2
    assert all(row[3] == "alice" for row in data["rows"])


def test_default_filter_and_layout(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    count = page.evaluate("document.querySelectorAll('#filters .filter').length")
    assert count == 1
    last_is_button = page.evaluate(
        "document.querySelector('#filters').lastElementChild.id === 'add_filter'"
    )
    assert last_is_button
    position = page.evaluate(
        "getComputedStyle(document.querySelector('#filters .filter button.remove')).position"
    )
    assert position == "static"


def test_filter_remove_alignment(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    diff = page.evaluate(
        "() => { const r=document.querySelector('#filters .filter-row').getBoundingClientRect(); const x=document.querySelector('#filters .filter-row button.remove').getBoundingClientRect(); return Math.abs(r.right - x.right); }"
    )
    assert diff <= 1


def test_header_and_tabs(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")

    header = page.text_content("#header")
    assert "sample.csv" in header
    assert "events" in header

    assert page.is_visible("#settings")
    assert page.is_hidden("#columns")
    page.click("text=Columns")
    assert page.is_visible("#columns")
    cols = [c.strip() for c in page.locator("#column_groups li").all_inner_texts()]
    assert "timestamp" in cols
    assert "event" in cols
    page.click("text=View Settings")
    assert page.is_visible("#settings")

    btn_color = page.evaluate(
        "getComputedStyle(document.querySelector('#dive')).backgroundColor"
    )
    assert "rgb(0, 128, 0)" == btn_color

    sidebar_overflow = page.evaluate(
        "getComputedStyle(document.querySelector('#sidebar')).overflowY"
    )
    view_overflow = page.evaluate(
        "getComputedStyle(document.querySelector('#view')).overflowY"
    )
    assert sidebar_overflow == "auto"
    assert view_overflow == "auto"


def test_help_and_alignment(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    titles = page.evaluate(
        "Array.from(document.querySelectorAll('#settings .help')).map(e => e.title)"
    )
    assert any("start/end of the time range" in t for t in titles)

    text_align = page.evaluate(
        "getComputedStyle(document.querySelector('#settings label')).textAlign"
    )
    assert text_align == "right"


def test_relative_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    btn = page.query_selector('[data-target="start-select"]')
    assert btn
    btn.click()
    page.click("#start-select div:text('-3 hours')")
    assert page.input_value("#start") == "-3 hours"


def test_end_dropdown_now(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click('[data-target="end-select"]')
    page.click("#end-select div:text('now')")
    assert page.input_value("#end") == "now"


def test_invalid_time_error_shown(page: Any, server_url: str) -> None:
    data = run_query(
        page,
        server_url,
        start="nonsense",
        end="now",
        order_by="user",
    )
    assert "error" in data
    msg = page.text_content("#view")
    assert "nonsense" in msg


def test_url_query_persistence(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.wait_for_function("window.lastResults !== undefined")
    page.fill("#start", "2024-01-01 00:00:00")
    page.fill("#end", "2024-01-02 00:00:00")
    page.fill("#limit", "1")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    first_url = page.url
    first_rows = page.evaluate("window.lastResults.rows.length")

    page.fill("#limit", "2")
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    second_url = page.url
    second_rows = page.evaluate("window.lastResults.rows.length")
    assert second_rows != first_rows
    assert first_url != second_url

    page.go_back()
    page.wait_for_function("window.lastResults !== undefined")
    assert page.url == first_url
    assert page.evaluate("window.lastResults.rows.length") == first_rows


def test_load_from_url(page: Any, server_url: str) -> None:
    url = (
        f"{server_url}?start=2024-01-01%2000:00:00&end=2024-01-02%2000:00:00"
        "&order_by=timestamp&limit=2"
    )
    page.goto(url)
    page.wait_for_selector("#order_by option", state="attached")
    page.wait_for_function("window.lastResults !== undefined")
    assert page.input_value("#start") == "2024-01-01 00:00:00"
    assert page.input_value("#end") == "2024-01-02 00:00:00"
    assert page.input_value("#limit") == "2"
    assert page.evaluate("window.lastResults.rows.length") == 2
