"""Vonage Video API client: session, publisher token, broadcast (HLS), archive.

Delegates entirely to the official Vonage server SDKs — token minting and the
`X-OPENTOK-AUTH`/RS256-application-JWT headers are the vendor's problem, not
ours. Two auth styles, whichever env-var pair is present (mission brief; not
covered by `docs/CONTRACT.md` — this is stream-vonage's own seam):

- **jwt** — `VONAGE_APPLICATION_ID` + `VONAGE_PRIVATE_KEY`. The current Vonage
  Application model. Wrapped by the `vonage` package (`Vonage(Auth(...)).video`,
  https://pypi.org/project/vonage/). Confirmed against v4.9.0 source: `Video`
  builds every REST call from `http_client.auth.application_id` and mints
  tokens via `auth.generate_application_jwt` — there is no api_key/api_secret
  path in this class, so this style is JWT-only, by design of the SDK itself.
- **api_key** — `VONAGE_API_KEY` + `VONAGE_API_SECRET`. The legacy TokBox/
  OpenTok project model. Wrapped by the `opentok` package (`OpenTok(key, secret)`,
  https://pypi.org/project/opentok/) — the classic `T1==` client token and the
  legacy REST auth header are entirely internal to that SDK.

In both styles the "project id" segment of `/v2/project/{id}/...` is the
application id (jwt) or the api key (api_key) — same slot, different value;
each SDK resolves it from its own credentials internally.

Verified by introspecting both packages' installed source (vonage==4.9.0,
opentok==3.15.0): `Video.create_session/generate_client_token/start_broadcast/
stop_broadcast/start_archive/stop_archive/send_signal` and `OpenTok.
create_session/generate_token/start_broadcast/stop_broadcast/start_archive/
stop_archive/send_signal` all exist with matching shapes — no hand-rolled JWT
or HMAC code needed for either style. Endpoint *behavior* (timing, exact
error codes) is not yet exercised against a real project — we don't have
Video credentials yet (mission blocker). `scripts/live_check.py` is the first
real run; note anything that doesn't match in this module's docstring once it
happens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from stream_vonage.settings import Settings

AuthStyle = Literal["jwt", "api_key"]

_TOKEN_TTL_S = 6 * 3600  # publisher token: comfortably longer than a demo slot


class VonageError(RuntimeError):
    """A Vonage SDK call failed."""


class VonageNotConfigured(VonageError):
    """Neither credential pair is present. `str(exc)` names the missing setting."""


def detect_auth_style(settings: Settings) -> AuthStyle | None:
    if settings.has_jwt_credentials:
        return "jwt"
    if settings.has_api_key_credentials:
        return "api_key"
    return None


def missing_setting_name(settings: Settings) -> str:
    """Which single env var to name in an error/log line. Prefers the current
    (jwt) style's first gap; falls back to the legacy style's; defaults to the
    current style's first var when neither pair was even started."""
    if settings.vonage_application_id or settings.vonage_private_key:
        return (
            "VONAGE_APPLICATION_ID" if not settings.vonage_application_id else "VONAGE_PRIVATE_KEY"
        )
    if settings.vonage_api_key or settings.vonage_api_secret:
        return "VONAGE_API_KEY" if not settings.vonage_api_key else "VONAGE_API_SECRET"
    return "VONAGE_APPLICATION_ID"


@dataclass(frozen=True)
class BroadcastResult:
    broadcast_id: str
    hls_url: str


@dataclass(frozen=True)
class ArchiveResult:
    archive_id: str
    url: str | None = None


class VonageClient:
    """Picks an auth style at construction time and wraps the matching
    official SDK. Both branches raise `VonageError` (wrapping the SDK's own
    exception) on failure, so `app.py` doesn't need to know which SDK is in
    play."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._style: AuthStyle | None = detect_auth_style(settings)
        self._jwt_client: Any = None  # vonage.Vonage, built lazily
        self._legacy_client: Any = None  # opentok.OpenTok, built lazily

    @property
    def auth_style(self) -> AuthStyle | None:
        return self._style

    def close(self) -> None:
        pass  # both SDKs manage their own HTTP client lifecycle internally

    def __enter__(self) -> VonageClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _require_style(self) -> AuthStyle:
        if self._style is None:
            raise VonageNotConfigured(f"{missing_setting_name(self._settings)} is not set")
        return self._style

    def _video(self):  # -> vonage_video.Video
        if self._jwt_client is None:
            from vonage import Auth, Vonage

            auth = Auth(
                application_id=self._settings.vonage_application_id,
                private_key=self._settings.vonage_private_key_pem,
            )
            self._jwt_client = Vonage(auth)
        return self._jwt_client.video  # type: ignore[attr-defined]

    def _opentok(self):  # -> opentok.OpenTok
        if self._legacy_client is None:
            from opentok import OpenTok

            self._legacy_client = OpenTok(
                self._settings.vonage_api_key, self._settings.vonage_api_secret
            )
        return self._legacy_client

    def create_session(self) -> str:
        """Mints a routed session (required for archiving/broadcast) and
        returns its session id."""
        style = self._require_style()
        try:
            if style == "jwt":
                from vonage_video.models.enums import ArchiveMode, MediaMode
                from vonage_video.models.session import SessionOptions

                # pyright's pydantic dataclass_transform support doesn't recognize
                # `Field(default, ...)`-style defaults (only a bare `= default`),
                # so it misreports every optional field here (e.g.
                # `p2p_preference`) as required. Confirmed against the installed
                # vonage_video==4.9.0 source: it has a real runtime default. A
                # pyright/pydantic stub gap, not a missing argument.
                session = self._video().create_session(
                    SessionOptions(  # pyright: ignore[reportCallIssue]
                        media_mode=MediaMode.ROUTED, archive_mode=ArchiveMode.MANUAL
                    )
                )
                return session.session_id
            from opentok import ArchiveModes, MediaModes

            session = self._opentok().create_session(
                media_mode=MediaModes.routed, archive_mode=ArchiveModes.manual
            )
            return session.session_id
        except Exception as exc:
            raise VonageError(f"session create failed: {exc}") from exc

    def generate_token(self, session_id: str, role: str = "publisher") -> str:
        style = self._require_style()
        try:
            if style == "jwt":
                from vonage_video.models.enums import TokenRole
                from vonage_video.models.token import TokenOptions

                jwt_role_map = {
                    "publisher": TokenRole.PUBLISHER,
                    "subscriber": TokenRole.SUBSCRIBER,
                }
                token = self._video().generate_client_token(
                    TokenOptions(
                        session_id=session_id,
                        role=jwt_role_map.get(role, TokenRole.PUBLISHER),
                        exp=_token_exp(),
                    )
                )
                return token.decode() if isinstance(token, bytes) else str(token)
            from opentok import Roles

            role_map = {"publisher": Roles.publisher, "subscriber": Roles.subscriber}
            return self._opentok().generate_token(
                session_id, role=role_map.get(role, Roles.publisher)
            )
        except Exception as exc:
            raise VonageError(f"token generation failed: {exc}") from exc

    def start_broadcast(self, session_id: str) -> BroadcastResult:
        style = self._require_style()
        try:
            if style == "jwt":
                from vonage_video.models.broadcast import (
                    BroadcastHls,
                    BroadcastOutputSettings,
                    CreateBroadcastRequest,
                )

                broadcast = self._video().start_broadcast(
                    CreateBroadcastRequest(  # pyright: ignore[reportCallIssue]
                        session_id=session_id,
                        outputs=BroadcastOutputSettings(
                            hls=BroadcastHls()  # pyright: ignore[reportCallIssue]
                        ),
                    )
                )
                hls_url = broadcast.broadcast_urls.hls if broadcast.broadcast_urls else None
                if not hls_url:
                    raise VonageError(f"broadcast start returned no HLS url: {broadcast}")
                return BroadcastResult(broadcast_id=str(broadcast.id), hls_url=str(hls_url))
            broadcast = self._opentok().start_broadcast(
                session_id, options={"outputs": {"hls": {}}}
            )
            hls_url = (broadcast.broadcastUrls or {}).get("hls")
            if not hls_url:
                raise VonageError(f"broadcast start returned no HLS url: {broadcast.broadcastUrls}")
            return BroadcastResult(broadcast_id=str(broadcast.id), hls_url=str(hls_url))
        except VonageError:
            raise
        except Exception as exc:
            raise VonageError(f"broadcast start failed: {exc}") from exc

    def stop_broadcast(self, broadcast_id: str) -> None:
        style = self._require_style()
        try:
            if style == "jwt":
                self._video().stop_broadcast(broadcast_id)
            else:
                self._opentok().stop_broadcast(broadcast_id)
        except Exception as exc:
            raise VonageError(f"broadcast stop failed: {exc}") from exc

    def start_archive(self, session_id: str) -> ArchiveResult:
        style = self._require_style()
        try:
            if style == "jwt":
                from vonage_video.models.archive import CreateArchiveRequest

                archive = self._video().start_archive(
                    CreateArchiveRequest(  # pyright: ignore[reportCallIssue]
                        session_id=session_id, name="gavel-submission"
                    )
                )
                return ArchiveResult(archive_id=str(archive.id), url=archive.url)
            archive = self._opentok().start_archive(session_id, name="gavel-submission")
            return ArchiveResult(archive_id=str(archive.id), url=archive.url)
        except Exception as exc:
            raise VonageError(f"archive start failed: {exc}") from exc

    def stop_archive(self, archive_id: str) -> ArchiveResult:
        """Stops the archive and returns whatever the SDK already knows. The
        `url` is usually still `None` here — Vonage uploads/encodes
        asynchronously after stop, so it can lag by anywhere from seconds to a
        couple of minutes. `GET /v2/project/{id}/archive/{archiveId}`
        (`Video.get_archive` / `OpenTok.get_archive`, not wired up here — not
        needed for the demo) if a URL is required immediately."""
        style = self._require_style()
        try:
            if style == "jwt":
                archive = self._video().stop_archive(archive_id)
                return ArchiveResult(archive_id=str(archive.id), url=archive.url)
            archive = self._opentok().stop_archive(archive_id)
            return ArchiveResult(archive_id=str(archive.id), url=archive.url)
        except Exception as exc:
            raise VonageError(f"archive stop failed: {exc}") from exc

    def send_signal(self, session_id: str, signal_type: str, data: str) -> None:
        """Depth addition #1: relays brain's live agenda/intervention state
        into the Vonage session so viewers on `/watch` (or any Vonage client)
        can subscribe to it. `type`/`data` follow the Vonage signal schema —
        every connected client's `session.on('signal:<type>', ...)` fires."""
        style = self._require_style()
        try:
            if style == "jwt":
                from vonage_video.models.signal import SignalData

                self._video().send_signal(session_id, SignalData(type=signal_type, data=data))
            else:
                self._opentok().send_signal(session_id, {"type": signal_type, "data": data})
        except Exception as exc:
            raise VonageError(f"signal failed: {exc}") from exc


def _token_exp() -> int:
    import time

    return int(time.time()) + _TOKEN_TTL_S
