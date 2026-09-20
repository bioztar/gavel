"""Console surface: meetings, sessions carrying the agenda, the say-box, /live."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from ears.app import Ears
from ears.bus import Bus
from ears.db.store import Store
from ears.frames import Participant
from ears.settings import Settings
from ears.tts import SlngTts, TtsResult
from ears.wire import create_api

AGENDA = {
    "purpose": "Pick a date",
    "attendees": [{"discordId": "1", "name": "Vitaly", "role": "host"}],
    "topics": [
        {"id": "t1", "title": "Status", "budgetSeconds": 90, "mustHear": ["1"]},
        {"id": "t2", "title": "Date", "budgetSeconds": 120},
    ],
}


class FakeTts:
    model = "fake"

    async def synthesize(self, text: str) -> TtsResult:
        return TtsResult(audio=b"ID3fake-mp3", content_type="audio/mpeg", latency_ms=7)


class FakeVoice:
    def __init__(self) -> None:
        self.played: list[bytes] = []

    def play(self, audio: bytes, done: Any, priority: bool = False) -> bool:
        self.played.append(audio)
        return True

    def stop_playback(self) -> None: ...


class FakeDiscordVoice(FakeVoice):
    def __init__(self) -> None:
        super().__init__()
        self.selected: str | None = None

    def discord_servers(self) -> dict[str, Any]:
        return {
            "connected": True,
            "servers": [
                {
                    "id": "10",
                    "name": "Demo server",
                    "selectedChannelId": self.selected,
                    "connectedChannelId": None,
                    "channels": [
                        {"id": "20", "name": "Meeting room", "participants": 0, "canPost": True}
                    ],
                    "textChannels": [{"id": "30", "name": "general", "canPost": False}],
                }
            ],
        }

    async def configure_channel(self, guild_id: str, channel_id: str | None) -> None:
        if guild_id != "10" or channel_id not in {None, "20"}:
            raise ValueError("not available")
        self.selected = channel_id


def make() -> tuple[Ears, TestClient, list[dict[str, Any]]]:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    ears = Ears(settings, Store(None), Bus(None, "t", 10), None, FakeTts())  # type: ignore[arg-type]
    sent: list[dict[str, Any]] = []
    ears.hub.broadcast = sent.append  # type: ignore[method-assign]
    return ears, TestClient(create_api(ears)), sent


def test_meeting_crud_and_session_carries_agenda() -> None:
    ears, client, sent = make()
    created = client.post(
        "/api/meetings", json={"title": "Sync", "context": "ctx", "agenda": AGENDA}
    )
    assert created.status_code == 200, created.text
    meeting = created.json()
    assert meeting["agenda"]["totalSeconds"] == 210  # defaulted to the sum of budgets
    assert meeting["agenda"]["policy"]["floorShareThreshold"] == 0.6

    updated = client.put(f"/api/meetings/{meeting['id']}", json={**meeting, "title": "Sync 2"})
    assert updated.json()["title"] == "Sync 2"
    assert [m["title"] for m in client.get("/api/meetings").json()] == ["Sync 2"]

    ears.participants = {
        "2": Participant(discord_id="2", name="Ana"),
        "3": Participant(discord_id="3", name="Marc"),
    }
    sid = client.post("/api/sessions", json={"meetingId": meeting["id"]}).json()["sessionId"]
    [started] = [f for f in sent if f["type"] == "session.started"]
    assert started["sessionId"] == sid
    assert started["title"] == "Sync 2" and started["context"] == "ctx"
    assert started["agenda"]["sessionId"] == sid
    # The saved roster is the invitation: Vitaly is expected and simply not here yet, and
    # whoever else is in the channel joins him. Nobody's `mustHear` is quietly dropped.
    assert started["agenda"]["attendees"] == [
        {"discordId": "1", "name": "Vitaly", "role": "host"},
        {"discordId": "2", "name": "Ana", "role": "attendee"},
        {"discordId": "3", "name": "Marc", "role": "attendee"},
    ]
    assert started["agenda"]["topics"][0]["mustHear"] == ["1"]
    ears.participants["4"] = Participant(discord_id="4", name="Jo")
    assert ears.hello()[-1]["agenda"]["attendees"] == started["agenda"]["attendees"]

    # A new session ends the previous one.
    client.post("/api/sessions", json={"meetingId": None})
    assert [f["type"] for f in sent if f["type"].startswith("session.")] == [
        "session.started",
        "session.ended",
        "session.started",
    ]
    client.post("/api/sessions/end")
    assert ears.session_id is None


# --- the roster an invitation carries -------------------------------------------------
# A calendar invite has names and emails, never snowflakes; `packages/calendar` falls back
# to the email as the `discordId`. Binding the two by name is what makes the person who
# joins the call the person who was invited, rather than a fourth stranger.

INVITED = {
    "purpose": "Pick a date",
    "attendees": [
        {"discordId": "vitaly@x.dev", "name": "Vitaly", "role": "host"},
        {"discordId": "artem@x.dev", "name": "Artem", "role": "attendee"},
    ],
    "topics": [
        {
            "id": "t1",
            "title": "Status",
            "budgetSeconds": 90,
            "owner": "artem@x.dev",
            "mustHear": ["artem@x.dev"],
        }
    ],
}


def test_an_invited_attendee_is_bound_to_the_speaker_with_their_name() -> None:
    ears, client, sent = make()
    meeting = client.post("/api/meetings", json={"title": "Sync", "agenda": INVITED}).json()
    ears.participants = {
        "777": Participant(discord_id="777", name="artemshambalev"),
        "888": Participant(discord_id="888", name="Priya"),
    }
    client.post("/api/sessions", json={"meetingId": meeting["id"]})
    agenda = [f for f in sent if f["type"] == "session.started"][-1]["agenda"]
    assert agenda["attendees"] == [
        # Expected, not here yet — the chair waits for him and the room page says so.
        {"discordId": "vitaly@x.dev", "name": "Vitaly", "role": "host"},
        {"discordId": "777", "name": "artemshambalev", "role": "attendee"},
        # In the channel, on nobody's invitation: still in the meeting.
        {"discordId": "888", "name": "Priya", "role": "attendee"},
    ]
    # The topic follows him to his Discord id, or the brain chases an owner it cannot see.
    assert agenda["topics"][0]["owner"] == "777"
    assert agenda["topics"][0]["mustHear"] == ["777"]


def test_one_speaker_answers_for_one_attendee() -> None:
    """Vitaly and Vitaly P cannot both be the one Vitaly who actually joined."""
    ears, client, sent = make()
    agenda = {
        **INVITED,
        "attendees": [
            {"discordId": "vp@x.dev", "name": "Vitaly P", "role": "attendee"},
            {"discordId": "v@x.dev", "name": "Vitaly", "role": "host"},
        ],
        "topics": [],
    }
    meeting = client.post("/api/meetings", json={"title": "Sync", "agenda": agenda}).json()
    ears.participants = {"777": Participant(discord_id="777", name="Vitaly")}
    client.post("/api/sessions", json={"meetingId": meeting["id"]})
    started = [f for f in sent if f["type"] == "session.started"][-1]
    assert started["agenda"]["attendees"] == [
        {"discordId": "vp@x.dev", "name": "Vitaly P", "role": "attendee"},
        {"discordId": "777", "name": "Vitaly", "role": "host"},
    ]


def test_a_meeting_with_no_saved_roster_is_still_whoever_is_in_the_channel() -> None:
    ears, client, sent = make()
    agenda = {**INVITED, "attendees": [], "topics": []}
    meeting = client.post("/api/meetings", json={"title": "Sync", "agenda": agenda}).json()
    ears.participants = {
        "2": Participant(discord_id="2", name="Ana"),
        "3": Participant(discord_id="3", name="Marc"),
    }
    client.post("/api/sessions", json={"meetingId": meeting["id"]})
    started = [f for f in sent if f["type"] == "session.started"][-1]
    assert started["agenda"]["attendees"] == [
        {"discordId": "2", "name": "Ana", "role": "host"},
        {"discordId": "3", "name": "Marc", "role": "attendee"},
    ]


def test_unknown_meeting_is_404_and_bad_id_422() -> None:
    _, client, _ = make()
    assert client.post("/api/sessions", json={"meetingId": "not-a-uuid"}).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post("/api/sessions", json={"meetingId": missing}).status_code == 404
    assert client.post("/api/meetings", json={"title": ""}).status_code == 422


def test_joining_voice_starts_a_session_brains_hear_about() -> None:
    ears, client, _ = make()
    ears.on_joined("g", "c1", [Participant(discord_id="1", name="Vitaly")])
    assert ears.session_id is not None
    with client.websocket_connect("/") as ws:
        types = [ws.receive_json()["type"] for _ in range(4)]
    # `voice` leads: a brain learns how to speak before what the meeting is.
    assert types == ["voice", "ready", "participants", "session.started"]


def test_say_goes_through_playback_and_is_visible_on_live() -> None:
    ears, client, _ = make()
    voice = FakeVoice()
    ears.voice = voice  # type: ignore[assignment]
    with client.websocket_connect("/live") as live:
        hello = live.receive_json()
        assert hello["type"] == "console.hello" and hello["status"]["tts"] == "fake"
        response = client.post("/api/say", json={"text": "Ana, go ahead."})
        assert response.status_code == 200 and response.json()["ttsMs"] == 7
        kinds = [live.receive_json()["kind"] for _ in range(4)]
    assert kinds == ["tts.request", "tts.result", "speak.queued", "speak.playing"]
    assert voice.played == [b"ID3fake-mp3"]


def test_console_page_is_served() -> None:
    _, client, _ = make()
    page = client.get("/console")
    assert page.status_code == 200 and "ears console" in page.text
    assert "What Karen understands" in page.text
    assert 'id="m-require-start"' in page.text
    assert 'id="m-timed"' in page.text
    assert "b-add-att" not in page.text and "b-import-voice" not in page.text
    assert client.get("/", follow_redirects=False).headers["location"] == "/console"


async def test_discord_servers_and_channel_selection() -> None:
    ears, client, _ = make()
    voice = FakeDiscordVoice()
    ears.voice = voice  # type: ignore[assignment]

    servers = client.get("/api/discord/servers").json()
    assert servers["servers"][0]["name"] == "Demo server"

    response = client.put("/api/discord/servers/10", json={"channelId": "20"})
    assert response.status_code == 200
    assert response.json()["servers"][0]["selectedChannelId"] == "20"
    assert await ears.store.discord_channels() == {"10": "20"}

    cleared = client.put("/api/discord/servers/10", json={"channelId": None})
    assert cleared.status_code == 200
    assert await ears.store.discord_channels() == {}


async def test_status_message_settings_per_server() -> None:
    ears, client, _ = make()
    ears.voice = FakeDiscordVoice()  # type: ignore[assignment]

    server = client.get("/api/discord/servers").json()["servers"][0]
    assert server["status"] == {"enabled": True, "channelId": None}  # default: the voice chat

    response = client.put(
        "/api/discord/servers/10/status", json={"enabled": True, "channelId": "30"}
    )
    assert response.json()["servers"][0]["status"] == {"enabled": True, "channelId": "30"}
    assert ears.status_config("10").channel_id == "30"
    assert (await ears.store.discord_status())["10"].channel_id == "30"

    client.put("/api/discord/servers/10/status", json={"enabled": False, "channelId": None})
    assert ears.status_config("10").enabled is False
    # Only this server's own text channels.
    assert client.put("/api/discord/servers/10/status", json={"channelId": "99"}).status_code == 404
    assert client.put("/api/discord/servers/11/status", json={}).status_code == 404


def test_brain_state_is_proxied_for_the_console(httpx_mock: HTTPXMock) -> None:
    _, client, _ = make()
    httpx_mock.add_response(
        url="http://127.0.0.1:8788/state",
        json={"chairName": "Karen", "phase": "gathering", "readyToStart": True},
    )
    response = client.get("/api/brain-state")
    assert response.status_code == 200
    assert response.json() == {"chairName": "Karen", "phase": "gathering", "readyToStart": True}


def test_brain_state_error_does_not_expose_upstream_details(httpx_mock: HTTPXMock) -> None:
    _, client, _ = make()
    httpx_mock.add_exception(
        httpx.ConnectError("private upstream URL and transport details"),
        url="http://127.0.0.1:8788/state",
    )

    response = client.get("/api/brain-state")

    # Recommended by Norma — fixed with GPT-5 via Codex
    assert response.status_code == 503
    assert response.json() == {"detail": "brain state unavailable"}


class RenamingVoice(FakeDiscordVoice):
    """Discord never tells the bot about a profile rename; a refresh re-reads it."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "Old Name"

    async def refresh_names(self) -> list[Participant]:
        return [Participant(discord_id="1", name=self.name)]


def test_refresh_names_re_announces_the_roster_and_a_new_session_uses_it() -> None:
    ears, client, sent = make()
    voice = RenamingVoice()
    ears.voice = voice  # type: ignore[assignment]
    ears.on_joined("10", "20", [Participant(discord_id="1", name="Old Name")])

    voice.name = "New Name"
    body = client.post("/api/discord/refresh-names")
    assert body.status_code == 200, body.text
    assert body.json() == {"participants": [{"discordId": "1", "name": "New Name"}]}
    assert ears.participants["1"].name == "New Name"
    assert [f for f in sent if f["type"] == "participants"][-1]["participants"] == [
        {"discordId": "1", "name": "New Name"}
    ]

    # Restarting the meeting hands the brain the name the person actually has now.
    meeting = client.post("/api/meetings", json={"title": "Sync", "agenda": AGENDA}).json()
    voice.name = "Newer Name"
    client.post("/api/sessions", json={"meetingId": meeting["id"]})
    started = [f for f in sent if f["type"] == "session.started"][-1]
    assert started["agenda"]["attendees"] == [
        {"discordId": "1", "name": "Newer Name", "role": "host"}
    ]


# --- the chair's voice ----------------------------------------------------------------
# One setting for two synthesizers: ears' say-box reads it per line, and the brain is
# told over the wire. Both apply it to their next line, not their next restart.


def test_voices_offers_the_known_list_and_what_is_selected() -> None:
    _, client, _ = make()
    body = client.get("/api/voices").json()
    assert body["voice"] == "aura-2-thalia-en"
    assert {"aura-2-thalia-en", "aura-2-hera-en", "aura-2-minerva-en", "aura-2-theia-en"} <= set(
        body["known"]
    )
    assert body["model"] == "deepgram/aura:2"


def test_the_pickers_type_your_own_row_cannot_be_read_as_a_voice_id() -> None:
    """The regression: that row was marked by a NUL sentinel in its `value`, and
    the HTML parser rewrites NUL to U+FFFD — so picking it saved "\ufffdcustom"
    as the voice instead of opening the field for a typed id."""
    console = (Path(__file__).parents[2] / "src/ears/console.html").read_text()
    assert "\u0000" not in console
    assert '<option value="" data-custom="1">' in console


def test_changing_the_voice_tells_every_brain_at_once() -> None:
    ears, client, sent = make()
    resp = client.put("/api/voice", json={"voice": "aura-2-luna-en"})

    assert resp.status_code == 200
    assert resp.json()["voice"] == "aura-2-luna-en"
    assert ears.tts_voice == "aura-2-luna-en"
    frames = [f for f in sent if f["type"] == "voice"]
    assert [f["voice"] for f in frames] == ["aura-2-luna-en"]


def test_the_say_box_uses_the_new_voice_on_the_very_next_line() -> None:
    """The regression this replaces: `SlngTts` snapshotted the voice at
    construction, so a change could not reach anything until a restart."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    ears = Ears(settings, Store(None), Bus(None, "t", 10), None, None)  # type: ignore[arg-type]
    tts = SlngTts(settings, httpx.AsyncClient(), voice=lambda: ears.tts_voice)

    assert tts._body("hi")["model"] == "aura-2-thalia-en"
    ears.tts_voice = "aura-2-orion-en"
    assert tts._body("hi")["model"] == "aura-2-orion-en"


def test_a_chosen_voice_is_offered_even_when_it_is_not_in_the_known_list() -> None:
    _, client, _ = make()
    client.put("/api/voice", json={"voice": "some-voice-shipped-yesterday"})
    body = client.get("/api/voices").json()
    assert body["voice"] == "some-voice-shipped-yesterday"
    assert body["known"][0] == "some-voice-shipped-yesterday"


def test_a_blank_voice_is_refused_and_changes_nothing() -> None:
    ears, client, sent = make()
    assert client.put("/api/voice", json={"voice": "   "}).status_code == 422
    assert ears.tts_voice == "aura-2-thalia-en"
    assert [f for f in sent if f["type"] == "voice"] == []


def test_a_brain_that_connects_is_told_the_current_voice() -> None:
    """A brain reconnecting mid-meeting would otherwise fall back to its own
    YAML and speak in the voice the operator already changed away from."""
    ears, client, _ = make()
    client.put("/api/voice", json={"voice": "aura-2-luna-en"})
    voice_frames = [f for f in ears.hello() if f["type"] == "voice"]
    assert [f["voice"] for f in voice_frames] == ["aura-2-luna-en"]


async def test_the_choice_outlives_the_process() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    store = Store(None)  # memory-backed here; the same code path writes app_settings
    ears = Ears(settings, store, Bus(None, "t", 10), None, FakeTts())  # type: ignore[arg-type]
    ears.hub.broadcast = lambda _f: None  # type: ignore[method-assign]
    await ears.set_tts_voice("aura-2-luna-en")

    # what `__main__` does on the next boot
    assert await store.get_setting("tts_voice") == "aura-2-luna-en"
