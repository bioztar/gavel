"""Console surface: meetings, sessions carrying the agenda, the say-box, /live."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock

from ears.app import Ears
from ears.bus import Bus
from ears.db.store import Store
from ears.frames import Participant
from ears.settings import Settings
from ears.tts import TtsResult
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
                    "channels": [{"id": "20", "name": "Meeting room", "participants": 0}],
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

    sid = client.post("/api/sessions", json={"meetingId": meeting["id"]}).json()["sessionId"]
    [started] = [f for f in sent if f["type"] == "session.started"]
    assert started["sessionId"] == sid
    assert started["title"] == "Sync 2" and started["context"] == "ctx"
    assert started["agenda"]["sessionId"] == sid
    assert started["agenda"]["topics"][0]["mustHear"] == ["1"]

    # A new session ends the previous one.
    client.post("/api/sessions", json={"meetingId": None})
    assert [f["type"] for f in sent if f["type"].startswith("session.")] == [
        "session.started",
        "session.ended",
        "session.started",
    ]
    client.post("/api/sessions/end")
    assert ears.session_id is None


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
        types = [ws.receive_json()["type"] for _ in range(3)]
    assert types == ["ready", "participants", "session.started"]


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


def test_brain_state_is_proxied_for_the_console(httpx_mock: HTTPXMock) -> None:
    _, client, _ = make()
    httpx_mock.add_response(
        url="http://127.0.0.1:8788/state",
        json={"chairName": "Karen", "phase": "gathering", "readyToStart": True},
    )
    response = client.get("/api/brain-state")
    assert response.status_code == 200
    assert response.json() == {"chairName": "Karen", "phase": "gathering", "readyToStart": True}
