"""SEC-06 regression tests for the CLI side of telemetry.

``hefesto telemetry status`` used to print only the local log's state
("Enabled: False" by default) while the opt-out remote ping was still being
sent after every ``hefesto analyze``. The status now reports both, and the
ping and the status share one check (``remote_ping_enabled``).

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pytest
from click.testing import CliRunner

from hefesto.telemetry import client as tclient


@pytest.mark.parametrize(
    "value, ping, log",
    [
        (None, True, False),  # defaults: ping opt-out, local log opt-in
        ("", True, False),
        ("0", False, False),
        ("false", False, False),
        ("OFF", False, False),
        (" no ", False, False),
        ("1", True, True),
        ("true", True, True),
        ("yes", True, True),
    ],
)
def test_enablement_helpers(
    monkeypatch: pytest.MonkeyPatch, value: Optional[str], ping: bool, log: bool
) -> None:
    if value is None:
        monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)
    else:
        monkeypatch.setenv("HEFESTO_TELEMETRY", value)
    assert tclient.remote_ping_enabled() is ping
    assert tclient.local_log_enabled() is log


def _capture_urlopen(monkeypatch: pytest.MonkeyPatch) -> List[object]:
    calls: List[object] = []

    def fake_urlopen(req: object, timeout: Optional[float] = None) -> object:
        calls.append(req)
        raise OSError("network disabled in tests")

    monkeypatch.setattr(tclient.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_ping_not_sent_when_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    monkeypatch.setattr(tclient.Path, "home", lambda: tmp_path)
    calls = _capture_urlopen(monkeypatch)
    tclient._ping_remote({"event": "analyze"})
    assert calls == []


def test_ping_sent_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)
    monkeypatch.setattr(tclient.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(tclient, "_SESSION_ID_FILE", tmp_path / ".hefesto" / ".session_id")
    calls = _capture_urlopen(monkeypatch)
    tclient._ping_remote({"event": "analyze"})
    assert len(calls) == 1


def _status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: Optional[str]) -> str:
    from hefesto.cli.main import cli

    if value is None:
        monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)
    else:
        monkeypatch.setenv("HEFESTO_TELEMETRY", value)
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(tmp_path / "t.jsonl"))
    res = CliRunner().invoke(cli, ["telemetry", "status"])
    assert res.exit_code == 0, res.output
    return res.output


def test_status_default_reports_ping_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _status(monkeypatch, tmp_path, None)
    assert "Usage ping:  enabled" in out
    assert "Local log:   disabled" in out
    assert tclient.TELEMETRY_ENDPOINT in out


def test_status_disabled_reports_everything_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _status(monkeypatch, tmp_path, "0")
    assert "Usage ping:  disabled" in out
    assert "Local log:   disabled" in out


def test_get_status_includes_remote_ping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)
    monkeypatch.setenv("HEFESTO_TELEMETRY_PATH", str(tmp_path / "t.jsonl"))
    s = tclient.TelemetryClient().get_status()
    assert s["enabled"] is False
    assert s["remote_ping_enabled"] is True
    assert s["remote_endpoint"] == tclient.TELEMETRY_ENDPOINT
