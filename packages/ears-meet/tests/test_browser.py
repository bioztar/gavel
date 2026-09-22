"""The browser layer with Playwright's Page mocked: the self-check names what is missing,
the selector table is well-formed, observer.js is shipped and configured from it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conftest import make_settings
from ears_meet import selectors as sel
from ears_meet.browser import Browser, JoinError, PlaywrightError

SRC = Path(__file__).resolve().parents[1] / "src" / "ears_meet"


class FakeLocator:
    def __init__(self, page: FakePage, css: str) -> None:
        self.page = page
        self.css = css

    @property
    def first(self) -> FakeLocator:
        return self

    async def count(self) -> int:
        return 1 if self.css in self.page.present else 0

    async def wait_for(self, *, state: str, timeout: int) -> None:  # noqa: ASYNC109 — Playwright's signature
        if self.css not in self.page.present:
            raise PlaywrightError(f"{self.css}: not {state} after {timeout}ms")

    async def click(self) -> None:
        self.page.clicked.append(self.css)
        self.page.present |= self.page.reveals.get(self.css, set())


class FakeKeyboard:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    async def press(self, key: str) -> None:
        self.page.keys.append(key)


class FakePage:
    """Answers `locator(css)` from a set of CSS strings that 'exist'. Clicking one of the
    `reveals` keys adds its value to the set, the way a menu button reveals its items."""

    def __init__(
        self,
        present: set[str],
        snapshot: dict[str, Any] | None = None,
        reveals: dict[str, set[str]] | None = None,
    ) -> None:
        self.present = set(present)
        self._snapshot = snapshot or {}
        self.reveals = reveals or {}
        self.clicked: list[str] = []
        self.keys: list[str] = []
        self.keyboard = FakeKeyboard(self)

    def locator(self, css: str) -> FakeLocator:
        return FakeLocator(self, css)

    async def evaluate(self, _js: str) -> dict[str, Any]:
        return self._snapshot

    def is_closed(self) -> bool:
        return False


def browser_with(page: FakePage, **settings: Any) -> Browser:
    b = Browser(make_settings(**settings), on_event=lambda _e: None)
    b.page = page  # type: ignore[assignment]
    return b


PRESENT = sel.PRESENT_BUTTON.candidates[0]
TAB_ITEM = sel.PRESENT_TAB_MENU_ITEM.candidates[0]


def all_first_candidates(*selectors: sel.Selector) -> set[str]:
    return {s.candidates[0] for s in selectors}


@pytest.mark.asyncio
async def test_self_check_passes_when_the_required_selectors_are_present() -> None:
    page = FakePage(all_first_candidates(*sel.IN_CALL_REQUIRED))
    result = await browser_with(page).self_check()
    assert result.ok
    assert set(result.matched) == {s.name for s in sel.IN_CALL_REQUIRED}
    assert result.matched[sel.PARTICIPANT_TILE.name] == sel.PARTICIPANT_TILE.candidates[0]
    assert sel.CAPTIONS_REGION.name in result.missing_optional
    assert "matched" in result.message()


@pytest.mark.asyncio
async def test_self_check_names_the_selector_that_went_missing() -> None:
    page = FakePage(all_first_candidates(sel.PARTICIPANT_TILE, sel.LEAVE_BUTTON))
    result = await browser_with(page).self_check()
    assert not result.ok
    assert result.missing_required == [sel.SPEAKING_INDICATOR.name]
    msg = result.message()
    assert "Meet DOM changed" in msg and sel.SPEAKING_INDICATOR.name in msg
    assert "selectors.py" in msg


@pytest.mark.asyncio
async def test_self_check_uses_a_fallback_candidate() -> None:
    present = all_first_candidates(sel.PARTICIPANT_TILE, sel.LEAVE_BUTTON)
    present.add(sel.SPEAKING_INDICATOR.candidates[-1])
    result = await browser_with(FakePage(present)).self_check()
    assert result.ok
    assert result.matched[sel.SPEAKING_INDICATOR.name] == sel.SPEAKING_INDICATOR.candidates[-1]


@pytest.mark.asyncio
async def test_the_observer_can_vouch_for_the_indicator_it_found_per_tile() -> None:
    present = all_first_candidates(sel.PARTICIPANT_TILE, sel.LEAVE_BUTTON)
    result = await browser_with(FakePage(present, {"indicatorFound": True})).self_check()
    assert result.ok and result.matched[sel.SPEAKING_INDICATOR.name] == "observer"


@pytest.mark.asyncio
async def test_without_a_stage_the_present_menu_is_not_probed() -> None:
    page = FakePage(all_first_candidates(*sel.IN_CALL_REQUIRED) | {PRESENT})
    result = await browser_with(page).self_check()
    assert result.ok
    assert page.clicked == []
    assert sel.PRESENT_TAB_MENU_ITEM.name not in result.matched
    assert sel.PRESENT_TAB_MENU_ITEM.name not in result.missing_optional


@pytest.mark.asyncio
async def test_with_a_stage_the_tab_item_is_found_behind_the_present_menu() -> None:
    page = FakePage(
        all_first_candidates(*sel.IN_CALL_REQUIRED) | {PRESENT},
        reveals={PRESENT: {TAB_ITEM}},
    )
    result = await browser_with(page, stage_url="http://stage.local").self_check()
    assert result.ok
    assert result.matched[sel.PRESENT_TAB_MENU_ITEM.name] == TAB_ITEM
    assert page.clicked == [PRESENT]
    assert page.keys == ["Escape"], "the probe must close the menu it opened"


@pytest.mark.asyncio
async def test_with_a_stage_a_missing_tab_item_is_required_and_explains_why() -> None:
    page = FakePage(all_first_candidates(*sel.IN_CALL_REQUIRED) | {PRESENT})  # menu, no item
    result = await browser_with(page, stage_url="http://stage.local").self_check()
    assert not result.ok
    assert result.missing_required == [sel.PRESENT_TAB_MENU_ITEM.name]
    assert page.keys == ["Escape"]
    msg = result.message()
    assert sel.PRESENT_TAB_MENU_ITEM.name in msg
    assert "virtual display" in msg and "Entire screen" in msg


@pytest.mark.asyncio
async def test_with_a_stage_but_no_present_button_the_tab_item_is_still_required() -> None:
    page = FakePage(all_first_candidates(*sel.IN_CALL_REQUIRED))
    result = await browser_with(page, stage_url="http://stage.local").self_check()
    assert result.missing_required == [sel.PRESENT_TAB_MENU_ITEM.name]
    assert sel.PRESENT_BUTTON.name in result.missing_optional


@pytest.mark.asyncio
async def test_self_check_without_a_page_is_loud() -> None:
    b = Browser(make_settings(), on_event=lambda _e: None)
    with pytest.raises(JoinError, match="not launched"):
        await b.self_check()


def test_every_selector_is_named_documented_and_listed_once() -> None:
    names = [s.name for s in sel.ALL]
    assert len(names) == len(set(names))
    source = (SRC / "selectors.py").read_text().splitlines()
    for s in sel.ALL:
        assert s.candidates, s.name
        for css in s.candidates:
            lines = [ln for ln in source if repr(css) in ln or f'"{css}"' in ln]
            assert lines, f"{s.name}: candidate {css!r} not found verbatim in selectors.py"
            comment = lines[0].split("#", 1)[1] if "#" in lines[0] else ""
            assert any(k in comment for k in ("seen 20", "documented 20", "unverified")), (
                f"{s.name}: {css!r} needs a '# seen YYYY-MM' or '# unverified' comment"
            )
    module_selectors = {v for v in vars(sel).values() if isinstance(v, sel.Selector)}
    assert module_selectors == set(sel.ALL), "a Selector is defined but not in ALL"
    assert set(sel.IN_CALL_REQUIRED) <= set(sel.ALL)
    assert all(s.required and s.where != "lobby" for s in sel.IN_CALL_REQUIRED)
    assert sel.PRESENT_TAB_MENU_ITEM.required and sel.PRESENT_TAB_MENU_ITEM.note


def test_only_tab_capture_is_auto_selected() -> None:
    source = (SRC / "browser.py").read_text()
    assert "--auto-select-tab-capture-source-by-title=" in source
    assert 'f"--auto-select-desktop-capture-source' not in source, (
        "entire-screen capture cannot start on a virtual display; do not imply a fallback"
    )


def test_observer_js_is_shipped_and_configured_from_the_selector_module() -> None:
    js = (SRC / "observer.js").read_text()
    config = sel.observer_config()
    for key in ("tile", "name", "indicator", "speakingClasses", "captionsRegion"):
        assert config.get(key), key
        assert f"config.{key}" in js, key
    for kind in ("tiles", "indicator", "caption", "captions"):
        assert f'kind: "{kind}"' in js or f"kind: '{kind}'" in js, kind
    assert "MutationObserver" in js
