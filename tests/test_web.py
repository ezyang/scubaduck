from __future__ import annotations

from typing import Any


def select_value(page: Any, selector: str, value: str) -> None:
    page.evaluate(
        "arg => setSelectValue(arg.sel, arg.val)",
        {"sel": selector, "val": value},
    )


def run_query(
    page: Any,
    url: str,
    *,
    start: str | None = None,
    end: str | None = None,
    order_by: str | None = None,
    order_dir: str | None = "ASC",
    limit: int | None = None,
    group_by: list[str] | None = None,
    aggregate: str | None = None,
) -> dict[str, Any]:
    page.goto(url)
    page.wait_for_selector("#order_by option", state="attached")
    page.wait_for_selector("#order_dir", state="attached")
    page.wait_for_function("window.lastResults !== undefined")
    if start is not None:
        page.fill("#start", start)
    if end is not None:
        page.fill("#end", end)
    if order_by is not None:
        select_value(page, "#order_by", order_by)
    if order_dir is not None and order_dir == "DESC":
        page.click("#order_dir")
    if limit is not None:
        page.fill("#limit", str(limit))
    if group_by is not None:
        select_value(page, "#graph_type", "table")
        page.evaluate(
            "g => { groupBy.chips = g; groupBy.renderChips(); }",
            group_by,
        )
    if aggregate is not None:
        select_value(page, "#graph_type", "table")
        select_value(page, "#aggregate", aggregate)
    if page.input_value("#graph_type") != "samples":
        page.click("text=Columns")
        page.wait_for_selector("#column_groups input", state="attached")
        if not page.is_checked("#column_groups input[value='value']"):
            page.check("#column_groups input[value='value']")
        order_col = order_by or page.input_value("#order_by")
        if order_col and not page.is_checked(
            f"#column_groups input[value='{order_col}']"
        ):
            if page.query_selector(f"#column_groups input[value='{order_col}']"):
                page.check(f"#column_groups input[value='{order_col}']")
        page.click("text=View Settings")
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


def test_time_column_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#time_column option", state="attached")
    options = page.locator("#time_column option").all_inner_texts()
    assert "timestamp" in options
    assert "value" in options
    assert page.input_value("#time_column") == "timestamp"


def test_time_unit_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#time_unit", state="attached")
    opts = page.locator("#time_unit option").all_inner_texts()
    assert "ms" in opts
    assert page.input_value("#time_unit") == "s"


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


def test_graph_type_table_fields(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "table")
    assert page.is_visible("#group_by_field")
    assert page.is_visible("#aggregate_field")
    assert page.is_visible("#show_hits_field")
    page.click("text=Columns")
    assert not page.is_visible("text=Strings:")


def test_graph_type_timeseries_fields(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    select_value(page, "#graph_type", "timeseries")
    assert page.is_visible("#group_by_field")
    assert page.is_visible("#aggregate_field")
    assert page.is_visible("#x_axis_field")
    assert page.is_visible("#granularity_field")
    assert page.is_visible("#fill_field")


def test_limit_persists_per_chart_type(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    assert page.input_value("#limit") == "100"
    select_value(page, "#graph_type", "timeseries")
    assert page.input_value("#limit") == "7"
    select_value(page, "#graph_type", "samples")
    assert page.input_value("#limit") == "100"


def test_columns_persist_per_chart_type(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#graph_type", state="attached")
    page.click("text=Columns")
    page.wait_for_selector("#column_groups input", state="attached")
    page.uncheck("#column_groups input[value='value']")
    select_value(page, "#graph_type", "timeseries")
    count = page.evaluate(
        "document.querySelectorAll('#column_groups input:checked').length"
    )
    assert count == 0
    select_value(page, "#graph_type", "samples")
    count = page.evaluate(
        "document.querySelectorAll('#column_groups input:checked').length"
    )
    assert count == 3


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
    page.evaluate("window.lastResults = undefined")
    page.click("text=Dive")
    page.wait_for_function("window.lastResults !== undefined")
    count = page.eval_on_selector_all("#chart path", "els => els.length")
    assert count == 2


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
    assert align == "right"

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
        order_by="timestamp",
    )
    assert "error" in data
    msg = page.text_content("#view")
    assert "nonsense" in msg


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


def test_chip_dropdown_navigation(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown div")
    page.keyboard.type("ali")
    page.wait_for_selector("text=alice")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    chips = page.evaluate(
        "Array.from(document.querySelectorAll('#filters .filter:last-child .chip')).map(c => c.firstChild.textContent)"
    )
    assert chips == ["ali"]
    page.click("#filters .filter:last-child .chip .x")
    page.wait_for_selector(".chip", state="detached")


def test_chip_copy_and_paste(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.evaluate(
        "Object.defineProperty(navigator, 'clipboard', {value:{ _data: '', writeText(t){ this._data = t; }, readText(){ return Promise.resolve(this._data); } }})"
    )
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    inp.click()
    page.keyboard.type("bob")
    page.keyboard.press("Enter")
    f.query_selector(".chip-copy").click()
    assert page.evaluate("navigator.clipboard._data") == "alice,bob"
    page.evaluate(
        "var f=document.querySelector('#filters .filter:last-child'); f.chips=[]; f.querySelectorAll('.chip').forEach(c=>c.remove())"
    )
    page.wait_for_selector("#filters .chip", state="detached")
    inp.click()
    page.evaluate(
        "var dt=new DataTransfer(); dt.setData('text/plain','alice,bob'); var e=new ClipboardEvent('paste',{clipboardData:dt}); document.querySelector('#filters .filter:last-child .f-val').dispatchEvent(e);"
    )
    chips = page.evaluate(
        "Array.from(document.querySelectorAll('#filters .filter:last-child .chip')).map(c => c.firstChild.textContent)"
    )
    assert chips[:2] == ["alice", "bob"]
    page.evaluate(
        "var f=document.querySelector('#filters .filter:last-child'); f.chips=[]; f.querySelectorAll('.chip').forEach(c=>c.remove())"
    )
    page.wait_for_selector("#filters .chip", state="detached")
    inp.click()
    page.evaluate(
        "var dt=new DataTransfer(); dt.setData('text/plain','alice,bob'); var e=new ClipboardEvent('paste',{clipboardData:dt}); Object.defineProperty(e,'shiftKey',{value:true}); document.querySelector('#filters .filter:last-child .f-val').dispatchEvent(e);"
    )
    chips = page.evaluate(
        "Array.from(document.querySelectorAll('#filters .filter:last-child .chip')).map(c => c.firstChild.textContent)"
    )
    assert chips[-1] == "alice,bob"


def test_chip_dropdown_hides_on_outside_click(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown div")
    page.click("#header")
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown", state="hidden")


def test_chip_input_no_outline(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    inp = page.query_selector("#filters .filter:last-child .f-val")
    assert inp
    inp.click()
    outline = page.evaluate(
        "getComputedStyle(document.querySelector('#filters .filter:last-child .f-val')).outlineStyle"
    )
    assert outline == "none"


def test_chip_enter_keeps_focus(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown")
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    focused = page.evaluate(
        "document.activeElement === document.querySelector('#filters .filter:last-child .f-val')"
    )
    assert focused
    visible = page.evaluate(
        "getComputedStyle(document.querySelector('#filters .filter:last-child .chip-dropdown')).display"
    )
    assert visible == "none"


def test_chip_delete_keeps_focus(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown")
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    page.keyboard.type("b")
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown")
    f.query_selector(".chip .x").click()
    page.wait_for_selector("#filters .filter:last-child .chip", state="detached")
    focused = page.evaluate(
        "document.activeElement === document.querySelector('#filters .filter:last-child .f-val')"
    )
    assert focused
    visible = page.evaluate(
        "getComputedStyle(document.querySelector('#filters .filter:last-child .chip-dropdown')).display"
    )
    assert visible == "block"


def test_chip_click_blurs_input(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown")
    page.keyboard.type("ali")
    page.wait_for_selector(
        "#filters .filter:last-child .chip-dropdown div:text('alice')"
    )
    page.click("#filters .filter:last-child .chip-dropdown div:text('alice')")
    focused = page.evaluate(
        "document.activeElement === document.querySelector('#filters .filter:last-child .f-val')"
    )
    assert not focused
    visible = page.evaluate(
        "getComputedStyle(document.querySelector('#filters .filter:last-child .chip-dropdown')).display"
    )
    assert visible == "none"


def test_chip_dropdown_hides_on_column_click(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown div")
    f.query_selector(".f-col + .dropdown-display").click()
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown", state="hidden")


def test_chip_backspace_keeps_dropdown(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    page.keyboard.type("b")
    page.wait_for_selector("#filters .filter:last-child .chip-dropdown div")
    page.keyboard.press("Backspace")
    page.wait_for_function(
        "document.querySelector('#filters .filter:last-child .f-val').value === ''"
    )
    focused = page.evaluate(
        "document.activeElement === document.querySelector('#filters .filter:last-child .f-val')"
    )
    assert focused
    visible = page.evaluate(
        "getComputedStyle(document.querySelector('#filters .filter:last-child .chip-dropdown')).display"
    )
    assert visible == "block"


def test_chip_duplicate_toggles(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
    page.click("text=Add Filter")
    f = page.query_selector("#filters .filter:last-child")
    assert f
    page.evaluate(
        "arg => setSelectValue(arg.el.querySelector('.f-col'), arg.val)",
        {"el": f, "val": "user"},
    )
    inp = f.query_selector(".f-val")
    inp.click()
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    chips = page.evaluate(
        "Array.from(document.querySelectorAll('#filters .filter:last-child .chip')).map(c => c.firstChild.textContent)"
    )
    assert chips == ["alice"]
    inp.click()
    page.keyboard.type("alice")
    page.keyboard.press("Enter")
    chips = page.evaluate(
        "Array.from(document.querySelectorAll('#filters .filter:last-child .chip')).map(c => c.firstChild.textContent)"
    )
    assert chips == []


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
        order_by="timestamp",
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
    run_query(page, server_url, limit=10)
    whitespace = page.evaluate(
        "getComputedStyle(document.querySelector('#results td:nth-child(3)')).whiteSpace"
    )
    assert whitespace == "nowrap"


def test_derived_column_query(page: Any, server_url: str) -> None:
    page.goto(server_url)
    page.wait_for_selector("#order_by option", state="attached")
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
