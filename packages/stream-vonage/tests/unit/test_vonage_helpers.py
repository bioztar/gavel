"""`detect_auth_style` / `missing_setting_name` — pure functions, no SDK or
network involved.

Every `Settings(...)` call here passes all four credential fields explicitly
(via `_settings`) rather than relying on defaults: init kwargs are
pydantic-settings' highest-priority source, so this is the only way to
guarantee these tests see exactly the credential state they're testing,
regardless of whatever the host's real environment/.env actually holds.
"""

from __future__ import annotations

from typing import Any

from stream_vonage.settings import Settings
from stream_vonage.vonage import detect_auth_style, missing_setting_name

_BLANK: dict[str, Any] = {
    "vonage_application_id": "",
    "vonage_private_key": "",
    "vonage_api_key": "",
    "vonage_api_secret": "",
}


def _settings(**overrides: str) -> Settings:
    return Settings(**{**_BLANK, **overrides})


def test_detect_auth_style_none_when_unconfigured() -> None:
    assert detect_auth_style(_settings()) is None


def test_detect_auth_style_jwt() -> None:
    settings = _settings(vonage_application_id="app-1", vonage_private_key="key")
    assert detect_auth_style(settings) == "jwt"


def test_detect_auth_style_api_key() -> None:
    settings = _settings(vonage_api_key="key-1", vonage_api_secret="secret")
    assert detect_auth_style(settings) == "api_key"


def test_missing_setting_name_defaults_to_application_id() -> None:
    assert missing_setting_name(_settings()) == "VONAGE_APPLICATION_ID"


def test_missing_setting_name_names_the_private_key_gap() -> None:
    settings = _settings(vonage_application_id="app-1")
    assert missing_setting_name(settings) == "VONAGE_PRIVATE_KEY"


def test_missing_setting_name_names_the_application_id_gap() -> None:
    settings = _settings(vonage_private_key="key")
    assert missing_setting_name(settings) == "VONAGE_APPLICATION_ID"


def test_missing_setting_name_falls_back_to_api_key_pair() -> None:
    settings = _settings(vonage_api_key="key-1")
    assert missing_setting_name(settings) == "VONAGE_API_SECRET"
