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
