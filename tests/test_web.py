from __future__ import annotations

from typing import Any


def run_query(
    page: Any,
    url: str,
    *,
    start: str | None = None,
    end: str | None = None,
    order_by: str | None = None,
    order_dir: str | None = "ASC",
    limit: int | None = None,
) -> dict[str, Any]:
    page.goto(url)
    page.wait_for_selector("#order_by option", state="attached")
    page.wait_for_selector("#order_dir", state="attached")
    if start is not None:
        page.fill("#start", start)
    if end is not None:
        page.fill("#end", end)
    if order_by is not None:
        page.select_option("#order_by", order_by)
    if order_dir is not None and order_dir == "DESC":
        page.click("#order_dir")
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
    assert position == "absolute"


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
    cols = page.locator("#column_list li").all_inner_texts()
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


def test_table_sorting(page: Any, server_url: str) -> None:
    run_query(
        page,
        server_url,
        start="2024-01-01 00:00:00",
        end="2024-01-03 00:00:00",
        order_by="timestamp",
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


def test_relative_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    btn = page.query_selector('[data-target="start-select"]')
    assert btn
    btn.click()
    page.select_option("#start-select", "-3 hours")
    assert page.input_value("#start") == "-3 hours"


def test_plain_text_not_used(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    filt = page.query_selector("#filters .filter")
    assert filt
    filt.query_selector(".f-col").select_option("user")
    input_el = filt.query_selector(".f-val")
    input_el.click()
    page.keyboard.type("alice")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    data = page.evaluate("window.lastResults")
    assert len(data["rows"]) == 4


def test_dropdown_and_arrow_select(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    filt = page.query_selector("#filters .filter")
    assert filt
    filt.query_selector(".f-col").select_option("user")
    input_el = filt.query_selector(".f-val")
    input_el.click()
    page.keyboard.type("a")
    page.wait_for_selector(".dropdown div")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    values = page.evaluate(
        "Array.from(document.querySelectorAll('.chip')).map(c => c.dataset.value)"
    )
    assert values == ["a"]


def test_copy_and_paste(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    filt = page.query_selector("#filters .filter")
    assert filt
    filt.query_selector(".f-col").select_option("user")
    input_el = filt.query_selector(".f-val")
    input_el.click()
    for name in ["alice", "bob"]:
        page.keyboard.type(name)
        page.keyboard.press("Enter")
    page.evaluate("navigator.clipboard.writeText = t => { window.copied = t }")
    filt.query_selector(".copy-icon").click()
    copied = page.evaluate("window.copied")
    assert copied == "alice,bob"
    page.locator(".chip .close").nth(1).click()
    page.locator(".chip .close").nth(0).click()
    page.evaluate(
        "args => {const el = document.querySelector(args.sel); const dt = new DataTransfer(); dt.setData('text/plain', args.text); el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt}));}",
        {"sel": ".f-val", "text": "alice,charlie"},
    )
    values = page.evaluate(
        "Array.from(document.querySelectorAll('.chip')).map(c => c.dataset.value)"
    )
    assert values == ["alice", "charlie"]


def test_shift_paste(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    filt = page.query_selector("#filters .filter")
    assert filt
    filt.query_selector(".f-col").select_option("user")
    input_el = filt.query_selector(".f-val")
    input_el.click()
    page.evaluate(
        "args => {const el = document.querySelector(args.sel); const dt = new DataTransfer(); dt.setData('text/plain', args.text); const ev = new ClipboardEvent('paste', {clipboardData: dt}); Object.defineProperty(ev, 'shiftKey', {value: true}); el.dispatchEvent(ev);}",
        {"sel": ".f-val", "text": "x,y"},
    )
    values = page.evaluate(
        "Array.from(document.querySelectorAll('.chip')).map(c => c.dataset.value)"
    )
    assert values == ["x,y"]


def test_numeric_no_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    filt = page.query_selector("#filters .filter")
    assert filt
    filt.query_selector(".f-col").select_option("value")
    input_el = filt.query_selector(".f-val")
    input_el.click()
    page.keyboard.type("1")
    assert page.query_selector(".dropdown div") is None
