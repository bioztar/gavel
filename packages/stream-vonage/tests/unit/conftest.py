"""Fixtures shared by the unit suite. `VonageClient` is mocked at the module
boundary (`stream_vonage.app.VonageClient`) with `FakeVonage` — see
README "Local dev" — so no test in `tests/unit/` makes a real network call or
needs a credential, whether or not it's exercising the credentials-present or
credentials-absent path."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from stream_vonage.app import create_app
from stream_vonage.settings import Settings
from stream_vonage.vonage import ArchiveResult, BroadcastResult, VonageError


@dataclass
class FakeVonage:
    """Stand-in for `VonageClient`. Records every method called (in order,
    including the auth-style-blind `_signal_relay_loop`) so tests can assert
    on the call sequence — e.g. that a failed `start_broadcast` rolls back
    the archive it already started."""

    calls: list[str] = field(default_factory=list)
    fail_on: str | None = None

    def __enter__(self) -> FakeVonage:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_on == name:
            raise VonageError(f"{name} failed (test-injected)")

    def create_session(self) -> str:
        self._record("create_session")
        return "sess-1"

    def generate_token(self, session_id: str, role: str = "publisher") -> str:
        self._record("generate_token")
        return "tok-1"

    def start_archive(self, session_id: str) -> ArchiveResult:
        self._record("start_archive")
        return ArchiveResult(archive_id="arc-1", url=None)

    def start_broadcast(self, session_id: str) -> BroadcastResult:
        self._record("start_broadcast")
        return BroadcastResult(broadcast_id="bcast-1", hls_url="https://example.invalid/hls.m3u8")

    def stop_broadcast(self, broadcast_id: str) -> None:
        self._record("stop_broadcast")

    def stop_archive(self, archive_id: str) -> ArchiveResult:
        self._record("stop_archive")
        return ArchiveResult(archive_id="arc-1", url="https://example.invalid/archive.mp4")

    def send_signal(self, session_id: str, signal_type: str, data: str) -> None:
        self._record("send_signal")


@pytest.fixture
def settings() -> Settings:
    # Credentials present (jwt style) so the happy-path endpoints don't 503.
    # brain_state_poll_seconds is large so the signal-relay thread parks in
    # its first Event.wait() and never reaches an actual httpx call before a
    # test's /stream/stop sets the stop event. The api_key pair is
    # explicitly blanked (not left to whatever the host's real env/.env
    # happens to hold) — init kwargs are pydantic-settings' highest-priority
    # source, so this guarantees test isolation from ambient credentials
    # regardless of what's actually configured on this machine.
    return Settings(
        vonage_application_id="app-1",
        vonage_private_key="fake-key",
        vonage_api_key="",
        vonage_api_secret="",
        brain_state_poll_seconds=1000.0,
    )


@pytest.fixture
def unconfigured_settings() -> Settings:
    # All four fields explicitly blanked — see the `settings` fixture above
    # for why a bare `Settings()` is not safe to use here.
    return Settings(
        vonage_application_id="",
        vonage_private_key="",
        vonage_api_key="",
        vonage_api_secret="",
    )


@pytest.fixture
def fake_vonage(monkeypatch: pytest.MonkeyPatch) -> FakeVonage:
    instance = FakeVonage()
    monkeypatch.setattr("stream_vonage.app.VonageClient", lambda settings: instance)
    return instance


@pytest.fixture
def client(settings: Settings, fake_vonage: FakeVonage) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def unconfigured_client(unconfigured_settings: Settings) -> TestClient:
    # No monkeypatch here: `VonageNotConfigured` is raised by the real
    # `VonageClient` before it ever touches an SDK or the network, so this
    # exercises the genuine missing-credentials code path.
    return TestClient(create_app(unconfigured_settings))
