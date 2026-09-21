"""The browser layer with Playwright's Page mocked: the self-check names what is missing,
the selector table is well-formed, observer.js is shipped and configured from it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from conftest import make_settings
from ears_meet import selectors as sel
from ears_meet.browser import Browser, JoinError

SRC = Path(__file__).resolve().parents[1] / "src" / "ears_meet"


class FakeLocator:
    def __init__(self, n: int) -> None:
        self.n = n

    async def count(self) -> int:
        return self.n


class FakePage:
    """Answers `locator(css).count()` from a set of CSS strings that 'exist'."""

    def __init__(self, present: set[str], snapshot: dict[str, Any] | None = None) -> None:
        self.present = present
        self._snapshot = snapshot or {}

    def locator(self, css: str) -> FakeLocator:
        return FakeLocator(1 if css in self.present else 0)

    async def evaluate(self, _js: str) -> dict[str, Any]:
        return self._snapshot

    def is_closed(self) -> bool:
        return False


def browser_with(page: FakePage) -> Browser:
    b = Browser(make_settings(), on_event=lambda _e: None)
    b.page = page  # type: ignore[assignment]
    return b


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


def test_observer_js_is_shipped_and_configured_from_the_selector_module() -> None:
    js = (SRC / "observer.js").read_text()
    config = sel.observer_config()
    for key in ("tile", "name", "indicator", "speakingClasses", "captionsRegion"):
        assert config.get(key), key
        assert f"config.{key}" in js, key
    for kind in ("tiles", "indicator", "caption", "captions"):
        assert f'kind: "{kind}"' in js or f"kind: '{kind}'" in js, kind
    assert "MutationObserver" in js
