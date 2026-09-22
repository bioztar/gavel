"""The wire as the brain sees it: hello on connect, frames pushed, commands accepted; plus
the HTTP surface the operator console and the brain's store use."""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from conftest import Harness
from ears_meet.wire import Hub, create_api


class FakeSocket:
    """Just enough of starlette's WebSocket for Hub.serve."""

    def __init__(self, inbound: list[str]) -> None:
        self.sent: list[dict[str, Any]] = []
        self._inbound = asyncio.Queue[str]()
        for text in inbound:
            self._inbound.put_nowait(text)
        self.client = SimpleNamespace(host="127.0.0.1", port=1234)
        self.url = SimpleNamespace(path="/")

    async def receive_text(self) -> str:
        text = await self._inbound.get()
        if text == "<close>":
            raise WebSocketDisconnect(1000)
        return text

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    def close(self) -> None:
        self._inbound.put_nowait("<close>")


@pytest.mark.asyncio
async def test_brain_socket_hello_then_live_frames_then_commands(joined: Harness) -> None:
    hub = Hub()
    joined.ears.hub = hub  # the real hub, not the test capture
    speak = json.dumps(
        {"type": "speak", "utteranceId": "u1", "audio": base64.b64encode(b"a").decode()}
    )
    ws = FakeSocket([speak])
    task = asyncio.create_task(hub.serve(ws, joined.ears.hello(), joined.ears.command))  # type: ignore[arg-type]
    await asyncio.sleep(0.02)
    assert len(hub) == 1

    joined.indicator("p1", True)
    joined.advance(0.3)
    await asyncio.sleep(0.02)
    types = [f["type"] for f in ws.sent]
    assert types[:4] == ["voice", "ready", "participants", "session.started"]
    assert "speaking.start" in types and "turn.start" in types
    spoken = [f for f in ws.sent if f["type"] == "spoken"]
    assert spoken and spoken[0]["utteranceId"] == "u1" and joined.player.played == [b"a"]

    ws.close()
    await asyncio.wait_for(task, 1)
    assert len(hub) == 0


def test_health_status_and_selfcheck(joined: Harness) -> None:
    client = TestClient(create_api(joined.ears))
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["inCall"] and health["participants"] == 2
    assert health["channelId"] == "abc-defg-hij"
    status = client.get("/api/status").json()
    assert status["egressSeen"] is False and status["stt"] is False
    check = client.get("/api/selfcheck").json()
    assert check["ok"] is True and check["missingRequired"] == []


def test_selfcheck_outside_a_call_is_503(harness: Harness) -> None:
    client = TestClient(create_api(harness.ears))
    assert client.get("/api/selfcheck").status_code == 503
    assert client.get("/health").json()["status"] == "joining"


def test_sessions_and_stop_and_present(joined: Harness) -> None:
    client = TestClient(create_api(joined.ears))
    sid = client.post("/api/sessions", json={"title": "Standup"}).json()["sessionId"]
    assert joined.ears.session_id == sid
    assert joined.of_type("session.started")[-1]["title"] == "Standup"
    assert client.post("/api/stop").json() == {"ok": True}
    joined.surface.stage_ok = False
    assert client.post("/api/present").json() == {"presenting": False}
    assert client.post("/api/sessions/end").json() == {"ok": True}
    assert joined.ears.session_id is None


def test_say_without_tts_credentials_is_503(joined: Harness) -> None:
    client = TestClient(create_api(joined.ears))
    assert client.post("/api/say", json={"text": "hello"}).status_code == 503


def test_memory_store_round_trip(joined: Harness) -> None:
    client = TestClient(create_api(joined.ears))
    sid = joined.ears.session_id
    body = {"discordId": "p1", "name": "Vitaly", "summary": "Ship Friday", "sessionId": sid}
    created = client.post("/api/memories", json=body).json()
    assert created["summary"] == "Ship Friday" and created["status"] == "open"
    assert created["discordId"] == "p1" and "discord_id" not in created
    listed = client.get("/api/memories", params={"sessionId": sid}).json()
    assert [m["id"] for m in listed] == [created["id"]]
    assert client.get("/api/memories", params={"discordId": "p2"}).json() == []
    mid = created["id"]
    resolved = client.patch(f"/api/memories/{mid}", json={"status": "resolved"}).json()
    assert resolved["status"] == "resolved" and resolved["resolvedAt"]
    assert client.get("/api/memories", params={"status": "open"}).json() == []
    assert client.patch("/api/memories/not-a-uuid", json={"status": "open"}).status_code == 422
    assert (
        client.patch(
            f"/api/memories/{'0' * 8}-0000-0000-0000-{'0' * 12}", json={"status": "open"}
        ).status_code
        == 404
    )


def test_interventions_and_llm_usage(joined: Harness) -> None:
    client = TestClient(create_api(joined.ears))
    sid = joined.ears.session_id
    iv = client.post(
        "/api/interventions",
        json={
            "sessionId": sid,
            "kind": "cutoff",
            "targetId": "p1",
            "line": "wrap up",
            "source": "llm",
        },
    )
    assert iv.status_code == 200
    call = client.post(
        "/api/llm-calls",
        json={
            "sessionId": sid,
            "agent": "chair",
            "model": "m",
            "inputTokens": 10,
            "outputTokens": 5,
        },
    )
    assert call.status_code == 200
    usage = client.get(f"/api/sessions/{sid}/usage").json()
    assert usage["calls"] == 1 and usage["inputTokens"] == 10 and usage["outputTokens"] == 5
    assert client.get("/api/sessions/current/usage").json() == usage
