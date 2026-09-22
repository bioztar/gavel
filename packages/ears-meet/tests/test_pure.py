"""Roster, caption mining, attribution, agenda binding — the pure pieces."""

from __future__ import annotations

from ears_meet.agenda import agenda_for
from ears_meet.attribution import UNATTRIBUTED, Attributor
from ears_meet.captions import CaptionMiner
from ears_meet.frames import Participant
from ears_meet.roster import Roster, Tile

T = 1_700_000_000.0

# --- roster ----------------------------------------------------------------------------


def test_roster_maps_meet_ids_onto_discord_id_and_drops_the_bot() -> None:
    r = Roster("Karen (gavel)")
    changed, joined, left = r.update(
        [
            Tile("spaces/x/devices/1", "Vitaly"),
            Tile("spaces/x/devices/2", "Ana"),
            Tile("spaces/x/devices/9", "Karen (gavel)", self=True),
        ]
    )
    assert changed and joined == ["spaces/x/devices/1", "spaces/x/devices/2"] and left == []
    assert [p.model_dump(by_alias=True) for p in r.participants()] == [
        {"discordId": "spaces/x/devices/1", "name": "Vitaly"},
        {"discordId": "spaces/x/devices/2", "name": "Ana"},
    ]
    assert r.is_self("spaces/x/devices/9") and not r.is_self("spaces/x/devices/1")


def test_roster_reports_join_and_leave_and_unchanged() -> None:
    r = Roster("bot")
    r.update([Tile("1", "A")])
    assert r.update([Tile("1", "A")]) == (False, [], [])
    changed, joined, left = r.update([Tile("2", "B")])
    assert changed and joined == ["2"] and left == ["1"]
    assert r.update([Tile("2", "B renamed")])[0]  # a rename is a change


def test_roster_keeps_an_unnamed_tile_until_the_name_arrives() -> None:
    r = Roster("bot")
    r.update([Tile("1", "")])
    assert r.get("1") is not None and r.get("1").name == "1"  # type: ignore[union-attr]
    changed, joined, _ = r.update([Tile("1", "Ana")])
    assert changed and joined == []


def test_roster_by_name_exact_then_loose() -> None:
    r = Roster("bot")
    r.update([Tile("1", "Ana Lima"), Tile("2", "Marc")])
    assert r.by_name("ana lima").discord_id == "1"  # type: ignore[union-attr]
    assert r.by_name("Ana").discord_id == "1"  # type: ignore[union-attr]
    assert r.by_name("Marc (Guest)").discord_id == "2"  # type: ignore[union-attr]
    assert r.by_name("Zed") is None and r.by_name("") is None


# --- captions --------------------------------------------------------------------------


def test_captions_emit_deltas_then_a_final_after_settle() -> None:
    m = CaptionMiner(settle_ms=300)
    (first,) = m.observe(1, "Ana", "Hello", T)
    assert not first.final and first.text == "Hello" and first.seq == 0
    (second,) = m.observe(1, "Ana", "Hello there everyone", T + 0.2)
    assert not second.final and second.text == "there everyone" and second.seq == 1
    assert m.tick(T + 0.4) == []
    (final,) = m.tick(T + 0.6)
    assert final.final and final.text == "Hello there everyone" and final.seq == 2
    assert final.utterance_id == first.utterance_id
    assert final.started_at == T and final.ended_at == T + 0.2
    assert m.tick(T + 9) == []


def test_captions_reattribution_finalizes_the_old_line() -> None:
    m = CaptionMiner(settle_ms=300)
    m.observe(1, "Ana", "I think", T)
    out = m.observe(1, "Marc", "I think so too", T + 0.1)
    assert [c.final for c in out] == [True, False]
    assert out[0].speaker == "Ana" and out[1].speaker == "Marc"
    assert out[0].utterance_id != out[1].utterance_id


def test_captions_rewrite_resends_whole_line_and_forget_finalizes() -> None:
    m = CaptionMiner(settle_ms=300)
    m.observe(1, "Ana", "We shipped it", T)
    (delta,) = m.observe(1, "Ana", "We skipped it", T + 0.1)
    assert delta.text == "We skipped it"
    (final,) = m.forget(1)
    assert final.final and final.text == "We skipped it"
    assert m.forget(1) == [] and m.observe(2, "Ana", "   ", T) == []


# --- attribution -----------------------------------------------------------------------


def test_attribution_by_largest_overlap_then_last_speaker_then_unattributed() -> None:
    a = Attributor()
    assert a.attribute(T, T + 1) == UNATTRIBUTED
    a.speaking_start("a", T)
    a.speaking_end("a", T + 5)
    a.speaking_start("b", T + 4)
    a.speaking_end("b", T + 10)
    assert a.attribute(T + 1, T + 3) == "a"
    assert a.attribute(T + 4.5, T + 8) == "b"
    assert a.attribute(T + 3, T + 7) == "b"  # a: 2 s of it, b: 3 s
    assert a.attribute(T + 12, T + 13) == "b"  # nobody speaking: whoever spoke last
    a.speaking_start("c", T + 20)  # still open
    assert a.attribute(T + 21, T + 22) == "c"


def test_attribution_ignores_duplicate_starts_and_prunes() -> None:
    a = Attributor(keep_s=10)
    a.speaking_start("a", T)
    a.speaking_start("a", T + 1)
    a.speaking_end("a", T + 2)
    a.speaking_start("b", T + 30)
    a.speaking_end("b", T + 31)
    assert a.attribute(T + 40, T + 41) == "b"
    assert a.attribute(T, T + 2) == UNATTRIBUTED  # a's interval was pruned; b came later


# --- agenda ----------------------------------------------------------------------------

SAVED = {
    "sessionId": "x",
    "purpose": "Decide",
    "attendees": [
        {"discordId": "100000000000000001", "name": "Vitaly", "role": "host"},
        {"discordId": "100000000000000002", "name": "Ana", "role": "attendee"},
    ],
    "topics": [
        {
            "id": "t1",
            "title": "A",
            "owner": "100000000000000002",
            "mustHear": ["100000000000000001"],
        }
    ],
}


def test_agenda_rebinds_attendees_by_name_to_meet_ids() -> None:
    people = [Participant(discord_id="m2", name="Ana"), Participant(discord_id="m3", name="Marc")]
    out = agenda_for(SAVED, "s1", people)
    assert out is not None and out["sessionId"] == "s1"
    assert out["attendees"] == [
        {"discordId": "100000000000000001", "name": "Vitaly", "role": "host"},  # not here yet
        {"discordId": "m2", "name": "Ana", "role": "attendee"},
        {"discordId": "m3", "name": "Marc", "role": "attendee"},
    ]
    assert out["topics"][0]["owner"] == "m2"
    assert out["topics"][0]["mustHear"] == ["100000000000000001"]
    assert SAVED["topics"][0]["owner"] == "100000000000000002"  # the saved copy is untouched


def test_agenda_without_attendees_takes_the_room_and_first_is_host() -> None:
    saved = {"purpose": "p", "attendees": [], "topics": []}
    out = agenda_for(
        saved, "s", [Participant(discord_id="a", name="A"), Participant(discord_id="b", name="B")]
    )
    assert out is not None and out["attendees"] == [
        {"discordId": "a", "name": "A", "role": "host"},
        {"discordId": "b", "name": "B", "role": "attendee"},
    ]
    assert agenda_for(None, "s", []) is None
