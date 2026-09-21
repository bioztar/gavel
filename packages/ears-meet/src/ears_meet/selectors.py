"""Every Google Meet selector, in one place.

Google changes Meet's DOM without notice; obfuscated class names rotate every few
weeks, `aria-label`s and `data-*` attributes last months to years. Each selector below
is a *list of candidates* tried in order — the first one that matches wins — and every
candidate says what it matched and when that was last seen working. When Meet breaks,
this file is the fix, and `browser.self_check()` names the entry that stopped matching
rather than letting the bot sit in a call emitting no speaking events.

Verification key, per candidate:
  `seen YYYY-MM`       — matched in a live call by THIS package in that month. None yet:
                         the package has not been run against a real Meet. The first
                         live run (scripts/live_check.py, /api/selfcheck) promotes entries.
  `documented YYYY-MM` — a stable public hook (aria-label, data-* attribute, visible
                         text) as shown by Meet's UI and by open-source Meet bots as of
                         that month; expected to match, not yet confirmed from here.
  `unverified`         — a rotating obfuscated class or a guess; likely to need fixing.

Nothing in this file is ever a credential, a URL with a token, or a name from a call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Selector:
    """A named DOM target with ordered fallbacks."""

    name: str
    candidates: tuple[str, ...]
    # Whether `self_check` must find it in an active call. `optional` entries (captions,
    # the People panel) may legitimately be absent; a missing one is a warning, not a stop.
    required: bool = True
    where: Literal["lobby", "call", "any"] = "call"
    note: str = ""


# --- the lobby / pre-join screen --------------------------------------------------------

# Guest join: the name box shown to a browser that is not signed in. A signed-in profile
# never sees it, so it is optional.
LOBBY_NAME_INPUT = Selector(
    "lobby.name_input",
    (
        'input[aria-label="Your name"]',  # documented 2025-09 (guest lobby)
        'input[placeholder="Your name"]',  # unverified fallback
    ),
    required=False,
    where="lobby",
)

# The big blue button. Text differs by whether the account may enter on its own.
LOBBY_JOIN_BUTTON = Selector(
    "lobby.join_button",
    (
        'button:has-text("Join now")',  # documented 2025-09
        'button:has-text("Ask to join")',  # documented 2025-09 (host must admit)
        'button:has-text("Join anyway")',  # unverified — "others may see/hear" warning
        '[role="button"]:has-text("Join now")',  # unverified fallback
    ),
    where="lobby",
)

# Microphone / camera toggles carry `data-is-muted` in both the lobby and the call.
MIC_TOGGLE = Selector(
    "mic_toggle",
    (
        '[role="button"][aria-label*="microphone" i][data-is-muted]',  # documented 2025-09
        'button[aria-label*="microphone" i]',  # unverified fallback (no state attr)
    ),
    where="any",
    note="data-is-muted='true' means muted; we click until it reads 'false'.",
)
CAMERA_TOGGLE = Selector(
    "camera_toggle",
    (
        '[role="button"][aria-label*="camera" i][data-is-muted]',  # documented 2025-09
        'button[aria-label*="camera" i]',  # unverified fallback
    ),
    required=False,
    where="any",
    note="The bot has no face; the camera is turned off in the lobby.",
)

# Meet shows one of these while a request to join is pending, or when it is refused.
LOBBY_WAITING_TEXT = Selector(
    "lobby.waiting",
    (
        'text="Asking to be let in..."',  # documented 2025-09
        'text="Asking to be let in"',  # unverified variant without ellipsis
        ':text("Someone will let you in soon")',  # unverified
    ),
    required=False,
    where="lobby",
)
LOBBY_DENIED_TEXT = Selector(
    "lobby.denied",
    (
        ':text("You can\'t join this video call")',  # unverified
        ':text("Your request to join was denied")',  # unverified
        ':text("No one responded to your request")',  # unverified (timeout)
    ),
    required=False,
    where="lobby",
)

# Google sign-in form — only for the password fallback (settings.has_password_login).
SIGNIN_EMAIL = Selector(
    "signin.email",
    ('input[type="email"]',),  # documented 2025-09 (accounts.google.com)
    required=False,
    where="any",
)
SIGNIN_PASSWORD = Selector(
    "signin.password",
    ('input[type="password"]',),  # documented 2025-09
    required=False,
    where="any",
)
SIGNIN_NEXT = Selector(
    "signin.next",
    ('button:has-text("Next")', "#identifierNext", "#passwordNext"),  # documented 2025-09
    required=False,
    where="any",
)
# The avatar button top-right of meet.google.com when a Google account is signed in.
# Only scripts/login.py looks for it, to confirm the profile it just made is usable.
ACCOUNT_MENU = Selector(
    "signin.account_menu",
    (
        'a[aria-label^="Google Account:"]',  # documented 2025-09 (meet.google.com landing page)
        'a[href^="https://accounts.google.com/SignOutOptions"]',  # documented 2025-09 fallback
    ),
    required=False,
    where="any",
)


# --- in the call ------------------------------------------------------------------------

# One element per participant on stage. `data-participant-id` is the stable per-call
# identity Meet gives each person (a `spaces/…/devices/…` path); it is what goes into the
# contract's `discordId`. The self tile also carries `data-self-name`.
PARTICIPANT_TILE = Selector(
    "call.participant_tile",
    (
        "[data-participant-id]",  # documented 2025-09 — also the observer's root filter
    ),
    note="Everything per-person hangs off this element.",
)

# The display name inside a tile. Meet's classes rotate; the name is the one text node
# that is not inside a button, so the observer also has a structural fallback
# (observer.js `nameOf`), and `data-self-name` for the bot's own tile.
PARTICIPANT_NAME = Selector(
    "call.participant_name",
    (
        "[data-self-name]",  # documented 2025-09 — the bot's own tile only
        "span.notranslate",  # documented 2025-09 — every tile's name span; class `notranslate` is
        # Google's translate opt-out, not an obfuscated one, so it has been stable for years
        "div.zWGUib",  # unverified — rotating class as of 2025-09
        "[data-tooltip]",  # unverified fallback
    ),
)

# The speaking indicator: three animated bars in each tile that light up while that
# person's audio is above Meet's own VAD threshold. Its container's class list changes
# as speech starts and stops, which is what the MutationObserver watches. Because the
# obfuscated classes rotate, the observer decides "is speaking" by two independent
# signals — any running CSS animation on the indicator, OR one of the classes below —
# and the poll fallback re-reads both every 100 ms.
SPEAKING_INDICATOR = Selector(
    "call.speaking_indicator",
    (
        "div.IisKdb",  # unverified — the indicator container as of 2025-09
        '[data-participant-id] [class*="speaking" i]',  # unverified fallback
        "[data-participant-id] div[jscontroller][jsaction] > div > div:only-child",  # unverified
    ),
    note="The most important selector in the package. If self_check cannot find it "
    "on a tile that is speaking, no speaking.start/end will be emitted: stop.",
)
# Class names Meet has used on the indicator container while speaking / silent. Observed
# in open-source Meet bots in 2025; unverified from this package. Order is irrelevant.
SPEAKING_CLASSES: tuple[str, ...] = ("Oaajhc", "HX2H7", "wEsLMd", "OgVli")
SILENT_CLASSES: tuple[str, ...] = ("gjg47c",)

# A muted participant shows a crossed-out mic in the tile — useful only to suppress
# false speaking positives; not required.
TILE_MUTED_ICON = Selector(
    "call.tile_muted_icon",
    ('[data-participant-id] [data-is-muted="true"]',),  # unverified
    required=False,
)

# Bottom bar controls.
LEAVE_BUTTON = Selector(
    "call.leave_button",
    (
        'button[aria-label="Leave call"]',  # documented 2025-09
        'button[aria-label*="Leave" i]',  # unverified fallback
    ),
)
CAPTIONS_BUTTON = Selector(
    "call.captions_button",
    (
        'button[aria-label*="captions" i]',  # documented 2025-09 — "Turn on captions (c)"
        '[role="button"][aria-label*="captions" i]',  # unverified fallback
    ),
    required=False,
    note="aria-label flips between 'Turn on captions' and 'Turn off captions'.",
)
PRESENT_BUTTON = Selector(
    "call.present_button",
    (
        'button[aria-label="Present now"]',  # documented 2025-09
        'button[aria-label*="Present" i]',  # unverified fallback
        'button[aria-label*="Share screen" i]',  # unverified — newer wording
    ),
    required=False,
    note="Stage sharing is an enhancement; missing here means 'join without presenting'.",
)
PRESENT_TAB_MENU_ITEM = Selector(
    "call.present_tab_item",
    (
        '[role="menuitem"]:has-text("A tab")',  # documented 2025-09
        '[role="menuitem"]:has-text("Chrome tab")',  # unverified — older wording
        'li:has-text("A tab")',  # unverified fallback
    ),
    required=False,
)
STOP_PRESENTING_BUTTON = Selector(
    "call.stop_presenting",
    (
        'button[aria-label*="Stop presenting" i]',  # unverified — never presented in a check yet
        'button:has-text("Stop presenting")',  # unverified fallback
    ),
    required=False,
)

# The People side panel: participant list with a count in the button's badge. The list
# also carries `data-participant-id`, so join/leave can be read from it while tiles are
# paged out of the grid (Meet shows at most ~49 tiles).
PEOPLE_BUTTON = Selector(
    "call.people_button",
    (
        'button[aria-label*="People" i]',  # documented 2025-09 — "Show everyone" / "People"
        'button[aria-label*="Show everyone" i]',  # unverified variant
    ),
    required=False,
)
PEOPLE_LIST_ITEM = Selector(
    "call.people_list_item",
    (
        '[role="list"] [role="listitem"][data-participant-id]',  # unverified
        '[role="list"] [role="listitem"][aria-label]',  # unverified — aria-label is the name
    ),
    required=False,
)

# Live captions. The region keeps the last few lines: each line is a speaker name block
# followed by a text block that Meet edits in place as recognition settles.
CAPTIONS_REGION = Selector(
    "call.captions_region",
    (
        'div[role="region"][aria-label="Captions"]',  # documented 2025-09
        'div[role="region"][aria-label*="caption" i]',  # unverified fallback
        ".a4cQT",  # unverified — rotating class as of 2025-09
    ),
    required=False,
    note="Only present after captions are turned on; self_check tests it then.",
)
# Within the region, one line's speaker name and text. Classes rotate; observer.js also
# falls back to "first text node is the name, the rest is text" per line.
CAPTION_SPEAKER = Selector(
    "call.caption_speaker",
    ("div.NWpY1d", 'div[class*="speaker" i]'),  # unverified
    required=False,
)
CAPTION_TEXT = Selector(
    "call.caption_text",
    ("div.ygicle", "div.VbkSUe", 'div[class*="caption" i] span'),  # unverified
    required=False,
)

# "You're the only one here" / "Return to home screen" — the call has ended under us.
CALL_ENDED_TEXT = Selector(
    "call.ended",
    (
        ':text("You\'ve been removed from the meeting")',  # unverified
        ':text("Return to home screen")',  # documented 2025-09 — the post-call page
        ':text("The meeting has ended")',  # unverified
    ),
    required=False,
    where="any",
)


ALL: tuple[Selector, ...] = (
    LOBBY_NAME_INPUT,
    LOBBY_JOIN_BUTTON,
    MIC_TOGGLE,
    CAMERA_TOGGLE,
    LOBBY_WAITING_TEXT,
    LOBBY_DENIED_TEXT,
    SIGNIN_EMAIL,
    SIGNIN_PASSWORD,
    SIGNIN_NEXT,
    ACCOUNT_MENU,
    PARTICIPANT_TILE,
    PARTICIPANT_NAME,
    SPEAKING_INDICATOR,
    TILE_MUTED_ICON,
    LEAVE_BUTTON,
    CAPTIONS_BUTTON,
    PRESENT_BUTTON,
    PRESENT_TAB_MENU_ITEM,
    STOP_PRESENTING_BUTTON,
    PEOPLE_BUTTON,
    PEOPLE_LIST_ITEM,
    CAPTIONS_REGION,
    CAPTION_SPEAKER,
    CAPTION_TEXT,
    CALL_ENDED_TEXT,
)

# What self_check insists on once the bot is in the call. Tiles and the indicator are the
# floor policy's eyes; the leave button proves we are in a call at all.
IN_CALL_REQUIRED: tuple[Selector, ...] = (PARTICIPANT_TILE, SPEAKING_INDICATOR, LEAVE_BUTTON)


@dataclass
class SelfCheckResult:
    matched: dict[str, str] = field(default_factory=dict)  # selector name → candidate used
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing_required

    def message(self) -> str:
        if self.ok:
            return f"all {len(self.matched)} selectors matched"
        return (
            "Meet DOM changed — selectors missing: "
            + ", ".join(self.missing_required)
            + " (fix packages/ears-meet/src/ears_meet/selectors.py)"
        )


def observer_config() -> dict[str, object]:
    """What observer.js needs: the in-call selectors as plain lists."""
    return {
        "tile": list(PARTICIPANT_TILE.candidates),
        "name": list(PARTICIPANT_NAME.candidates),
        "indicator": list(SPEAKING_INDICATOR.candidates),
        "speakingClasses": list(SPEAKING_CLASSES),
        "silentClasses": list(SILENT_CLASSES),
        "mutedIcon": list(TILE_MUTED_ICON.candidates),
        "peopleItem": list(PEOPLE_LIST_ITEM.candidates),
        "captionsRegion": list(CAPTIONS_REGION.candidates),
        "captionSpeaker": list(CAPTION_SPEAKER.candidates),
        "captionText": list(CAPTION_TEXT.candidates),
    }
