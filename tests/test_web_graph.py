from __future__ import annotations

from typing import Any

from tests.web_utils import select_value


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
