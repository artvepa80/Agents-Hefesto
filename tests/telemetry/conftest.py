"""Keep telemetry unit tests off the network and off the real home directory."""

from __future__ import annotations

import pytest

from hefesto.telemetry import client


@pytest.fixture(autouse=True)
def _isolate_telemetry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("HEFESTO_TELEMETRY_UNDER_TEST", "1")
    monkeypatch.setenv("HEFESTO_STATE_DIR", str(tmp_path))
    for name in (
        "HEFESTO_TELEMETRY",
        "DO_NOT_TRACK",
        "HEFESTO_NO_UPDATE_CHECK",
        "HEFESTO_TELEMETRY_DEBUG",
        "HEFESTO_POSTHOG_KEY",
        "HEFESTO_POSTHOG_HOST",
        "HEFESTO_SOURCE",
        "CI",
        "GITHUB_ACTIONS",
        "CLAUDECODE",
        "CURSOR_EDITOR",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(client, "_held", False)

    def _refuse_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("telemetry test opened a socket")

    monkeypatch.setattr(client.urllib.request, "urlopen", _refuse_network)
