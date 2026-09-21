"""Contract conformance: the brain must not be able to tell a Meet call from a Discord one.

For each Discord recording in packages/contract/fixtures we re-enact the *same meeting* in
a Google Meet as this package would have seen it — tiles appearing, speaking indicators
flipping, caption lines settling — drive that through the real composition root (browser
and PulseAudio faked, everything else real), and record the frames it puts on the wire.

Then both streams go through the brain's own replay harness (packages/brain/src/replay.ts,
stub LLM, fake clock) and the chair's decisions — every line it said and when, the talk
time it computed per person, what it parked — must be identical.

Two assertions per scenario:
  1. the frames this package emits today match the committed Meet recording in
     ./fixtures (volatile ids aside), so a change to the mapping is a visible diff;
  2. the brain reaches the same decisions from the Meet recording as from the Discord one.

The brain half needs `packages/brain/node_modules` (pnpm install there). Without it the
brain assertion is skipped with a message; the recording assertion always runs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from conftest import CONTRACT_FIXTURES, ROOT, T0, Clock, Harness, make_settings
from ears_meet.agenda import load_agenda

HERE = Path(__file__).resolve().parent
MEET_FIXTURES = HERE / "fixtures"
BRAIN = ROOT / "packages" / "brain"
AGENDA = CONTRACT_FIXTURES / "agenda.demo.json"

SCENARIOS = ["replay", "replay.offagenda"]

# Fields whose values are freshly minted on every run and carry no decision.
VOLATILE = {"sessionId", "utteranceId", "turnId", "previousTurnId"}
# Frame types the brain's parser ignores or that carry no decision; dropped from the
# recording comparison so the fixture stays about the contract, not about bookkeeping.
NOISE_TYPES = {"voice"}


def meet_id(discord_id: str) -> str:
    """Meet identifies a participant by a device id, not a snowflake."""
    return f"spaces/demo-room/devices/{int(discord_id) % 1000}"


def reenact(discord_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Play the Discord recording back as the DOM events a Meet tab would have produced,
    and return what ears-meet put on the wire."""
    ready = next(f for f in discord_frames if f["type"] == "ready")
    started = next((f for f in discord_frames if f["type"] == "session.started"), None)
    people = {p["discordId"]: p["name"] for p in ready["participants"]}
    tiles = [(meet_id(did), name) for did, name in people.items()]

    settings = make_settings(
        agenda_file=str(AGENDA),
        meeting_title=(started or {}).get("title") or "",
    )
    harness = Harness(settings, Clock(T0))
    harness.ears.saved_agenda = load_agenda(str(AGENDA))

    events = sorted(discord_frames, key=lambda f: f["atMs"])
    caption_keys: dict[str, int] = {}  # Discord utteranceId -> Meet caption line key
    for frame in events:
        harness.advance_to(T0 + frame["atMs"] / 1000)
        kind = frame["type"]
        if kind == "ready":
            harness.tiles(*tiles)
            harness.ears.on_joined("abc-defg-hij")
            harness.captions_visible(True)  # the bot turns Meet's captions on after joining
        elif kind == "speaking.start":
            harness.indicator(meet_id(frame["discordId"]), True)
        elif kind == "speaking.end":
            harness.indicator(meet_id(frame["discordId"]), False)
        elif kind == "transcript":
            # One Meet caption line per Discord utterance; interims are the line being edited.
            uid = frame.get("utteranceId") or f"anon-{len(caption_keys)}"
            key = caption_keys.setdefault(uid, len(caption_keys) + 1)
            harness.caption(key, people[frame["discordId"]], frame["text"])
        elif kind == "session.started":
            pass  # a Meet session starts at join, titled from settings (see above)
        else:  # pragma: no cover — a new fixture frame type needs a DOM equivalent here
            raise AssertionError(f"no Meet re-enactment for fixture frame {kind!r}")
    # Let every debounce, caption settle and turn gap run out.
    harness.advance(harness.settings.turn_gap_ms / 1000 + 2)
    return [f for f in harness.frames if f["type"] not in NOISE_TYPES]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dump_jsonl(frames: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(f, separators=(",", ":")) + "\n" for f in frames)


def stable(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for f in frames:
        g = {k: v for k, v in f.items() if k not in VOLATILE}
        if g.get("agenda"):
            g["agenda"] = {k: v for k, v in g["agenda"].items() if k not in VOLATILE}
        out.append(g)
    return out


# --- 1. the recording ---------------------------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_meet_recording_matches_the_committed_fixture(scenario: str) -> None:
    discord = load_jsonl(CONTRACT_FIXTURES / f"{scenario}.jsonl")
    frames = reenact(discord)
    fixture = MEET_FIXTURES / f"meet.{scenario}.jsonl"
    if not fixture.exists():  # first run: write it, then fail so it is looked at
        fixture.parent.mkdir(exist_ok=True)
        fixture.write_text(dump_jsonl(frames))
        pytest.fail(f"wrote new fixture {fixture}; review and commit it")
    assert stable(frames) == stable(load_jsonl(fixture)), (
        f"ears-meet's frames changed; if intended, delete {fixture} and re-run to re-record"
    )


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_meet_recording_carries_the_same_contract_events_as_discord(scenario: str) -> None:
    """Frame-for-frame: every speaking.start/end and every final transcript the Discord
    ears emitted, ears-meet emits for the same person at the same millisecond.

    Meet captions keep every word, so where Discord's STT sent an interim and then a
    differently-worded final, Meet also finalises the interim text. Those extra finals
    are allowed, but only if Discord had them as interims (same words, same time)."""
    discord = load_jsonl(CONTRACT_FIXTURES / f"{scenario}.jsonl")
    meet = load_jsonl(MEET_FIXTURES / f"meet.{scenario}.jsonl")
    t0 = next(f for f in meet if f["type"] == "ready")["atMs"]

    def events(
        frames: list[dict[str, Any]], *, final: bool | None, shift: int = 0
    ) -> set[tuple[Any, ...]]:
        return {
            (f["atMs"] - shift, f["type"], f["discordId"], f.get("text"))
            for f in frames
            if f["type"] in ("speaking.start", "speaking.end")
            or (
                f["type"] == "transcript" and (final is None or bool(f.get("final", True)) is final)
            )
        }

    for f in discord:
        if "discordId" in f:
            f["discordId"] = meet_id(f["discordId"])
    want_final = events(discord, final=True)
    want_interim = events(discord, final=False)
    got_final = events(meet, final=True, shift=t0)

    assert want_final <= got_final, sorted(want_final - got_final)
    assert got_final - want_final <= want_interim, sorted(got_final - want_final - want_interim)
    assert all("at" in f and "atMs" in f for f in meet)
    assert {f["type"] for f in meet} >= {
        "ready",
        "session.started",
        "speaking.start",
        "speaking.end",
        "transcript",
    }


# --- 2. the brain --------------------------------------------------------------------


def brain_available() -> str | None:
    if shutil.which("node") is None:
        return "node is not installed"
    if not (BRAIN / "node_modules" / ".bin" / "tsx").exists():
        return f"brain deps missing: run `pnpm install` in {BRAIN}"
    return None


def brain_decisions(recording: Path) -> str:
    """Run the brain's replay harness and return its decision record: what the chair said
    (with mm:ss offsets), per-person talk time, and what was parked."""
    proc = subprocess.run(
        [
            str(BRAIN / "node_modules" / ".bin" / "tsx"),
            "src/replay.ts",
            str(recording),
            "--stub-llm",
            "--quiet",
            "--agenda",
            str(AGENDA),
        ],
        cwd=BRAIN,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-4000:]
    out = proc.stdout
    start = out.index("— what the chair said —")
    end = out.index("— model usage —")
    return out[start:end].strip()


def normalise(decisions: str) -> str:
    # The stub LLM is deterministic and the templates name people, never ids; only the
    # trailing whitespace per line can differ between runs.
    return "\n".join(line.rstrip() for line in decisions.splitlines())


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_brain_makes_the_same_decisions_from_meet_as_from_discord(
    scenario: str, tmp_path: Path
) -> None:
    reason = brain_available()
    if reason:
        pytest.skip(reason)
    discord = CONTRACT_FIXTURES / f"{scenario}.jsonl"
    meet = MEET_FIXTURES / f"meet.{scenario}.jsonl"

    from_discord = normalise(brain_decisions(discord))
    from_meet = normalise(brain_decisions(meet))
    assert from_meet == from_discord

    # And the record is not trivially empty: the chair did chair.
    said = re.findall(r"^\d\d:\d\d\s+\w+", from_meet, flags=re.MULTILINE)
    assert len(said) >= 3, from_meet
    assert "— talk time (s) —" in from_meet
