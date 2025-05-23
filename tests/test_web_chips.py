from __future__ import annotations

from typing import Any


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
