"""Both telemetry HTTP calls close their response, also when reading fails."""

from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto.telemetry import client


class _Response:
    def __init__(self, body: bytes = b"", fail_read: bool = False) -> None:
        self._body = body
        self._fail_read = fail_read
        self.closed = False

    def read(self) -> bytes:
        if self._fail_read:
            raise OSError("connection reset")
        return self._body

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


class _SyncThread:
    """Run the target inline so the test sees the finished send."""

    def __init__(self, target: Any, **_kwargs: Any) -> None:
        self._target = target

    def start(self) -> None:
        self._target()

    def join(self, timeout: float | None = None) -> None:
        return None


def test_pypi_check_closes_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response(json.dumps({"info": {"version": "9.9.9"}}).encode())
    monkeypatch.setattr(client.urllib.request, "urlopen", lambda *_a, **_k: response)
    assert client._fetch_pypi_version() == "9.9.9"
    assert response.closed


def test_pypi_check_closes_response_when_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response(fail_read=True)
    monkeypatch.setattr(client.urllib.request, "urlopen", lambda *_a, **_k: response)
    with pytest.raises(OSError):
        client._fetch_pypi_version()
    assert response.closed


def test_event_send_closes_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response(b"{}")
    monkeypatch.setattr(client.urllib.request, "urlopen", lambda *_a, **_k: response)
    monkeypatch.setattr(client.threading, "Thread", _SyncThread)
    client._schedule_send({"event": "test"})
    assert response.closed
