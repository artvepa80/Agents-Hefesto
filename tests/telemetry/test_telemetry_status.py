"""``hefesto telemetry status`` / ``enable``: the named telemetry state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.telemetry import client


def _noticed(tmp_path: Path) -> None:
    (tmp_path / "telemetry_state.json").write_text(
        json.dumps({"notice_shown": True, "first_run_sent": True}), encoding="utf-8"
    )


def _status_json() -> dict:
    result = CliRunner().invoke(cli, ["telemetry", "status", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DO_NOT_TRACK",
        "HEFESTO_TELEMETRY",
        "HEFESTO_TELEMETRY_DEBUG",
        "HEFESTO_POSTHOG_KEY",
        "HEFESTO_POSTHOG_HOST",
    ):
        monkeypatch.delenv(name, raising=False)
    client._held = False


def test_fresh_machine_is_notice_pending(tmp_path: Path) -> None:
    info = _status_json()
    assert info["state"] == "notice_pending"
    assert info["enabled"] is True
    assert info["off_by"] is None


def test_noticed_machine_is_on(tmp_path: Path) -> None:
    _noticed(tmp_path)
    assert _status_json()["state"] == "on"


@pytest.mark.parametrize(
    ("env", "value", "source"),
    [("DO_NOT_TRACK", "1", "DO_NOT_TRACK"), ("HEFESTO_TELEMETRY", "off", "HEFESTO_TELEMETRY")],
)
def test_env_opt_out_names_its_switch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: str, value: str, source: str
) -> None:
    _noticed(tmp_path)
    monkeypatch.setenv(env, value)
    info = _status_json()
    assert (info["state"], info["off_by"], info["enabled"]) == ("off", source, False)


def test_empty_key_is_no_destination(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _noticed(tmp_path)
    monkeypatch.setenv("HEFESTO_POSTHOG_KEY", "")
    assert _status_json()["state"] == "no_destination"


def test_debug_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _noticed(tmp_path)
    monkeypatch.setenv("HEFESTO_TELEMETRY_DEBUG", "1")
    assert _status_json()["state"] == "debug"


def test_status_matches_what_capture_does(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each named state predicts whether ``capture`` sends."""
    monkeypatch.setenv("HEFESTO_TELEMETRY_UNDER_TEST", "1")
    sent: list[dict] = []
    monkeypatch.setattr(client, "_schedule_send", sent.append)
    _noticed(tmp_path)
    assert client.status()["state"] == "on"
    client.capture("analyze")
    assert len(sent) == 1
    client.disable()
    assert client.status()["state"] == "off"
    client.capture("analyze")
    assert len(sent) == 1


def test_status_is_read_only(tmp_path: Path) -> None:
    before = sorted(p.name for p in tmp_path.iterdir())
    result = CliRunner().invoke(cli, ["telemetry", "status"])
    assert result.exit_code == 0, result.output
    assert "notice" in result.output
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_disable_then_enable_round_trip(tmp_path: Path) -> None:
    _noticed(tmp_path)
    runner = CliRunner()
    out = runner.invoke(cli, ["telemetry", "disable"])
    assert "hefesto telemetry enable" in out.output
    assert _status_json()["off_by"] == "telemetry_disabled_file"
    out = runner.invoke(cli, ["telemetry", "enable"])
    assert out.exit_code == 0, out.output
    assert not (tmp_path / "telemetry_disabled").exists()
    assert _status_json()["state"] == "on"
    again = runner.invoke(cli, ["telemetry", "enable"])
    assert "already on" in again.output


def test_enable_says_when_env_still_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client.disable()
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    out = CliRunner().invoke(cli, ["telemetry", "enable"])
    assert out.exit_code == 0, out.output
    assert "still off" in out.output and "DO_NOT_TRACK" in out.output
    assert not (tmp_path / "telemetry_disabled").exists()
