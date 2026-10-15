"""PostHog usage events: opt-out, notice, payload, and the CLI entry point."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.telemetry import client

_PLANTED_PATH = "/home/secret/repo/app.py"
_PLANTED_CODE = "password = 'hunter2'"
_PLANTED_FINDING = "SQL injection in app.py"
_PLANTED_REPO = "Agents-Hefesto-private"
_PLANTED_IP = "203.0.113.50"


def _seed_noticed(tmp_path: Path) -> None:
    state = {
        "install_id": "11111111-1111-4111-8111-111111111111",
        "notice_shown": True,
        "first_run_sent": True,
    }
    (tmp_path / "telemetry_state.json").write_text(json.dumps(state), encoding="utf-8")
    client._held = False


def _record(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []

    def _capture(payload: dict) -> None:
        sent.append(payload)

    monkeypatch.setattr(client, "_schedule_send", _capture)
    return sent


def test_opt_out_env_dnt_and_disable_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _seed_noticed(tmp_path)
    sent = _record(monkeypatch)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    client.capture("analyze", path=_PLANTED_PATH)
    monkeypatch.delenv("HEFESTO_TELEMETRY")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    client.capture("analyze", code=_PLANTED_CODE)
    monkeypatch.delenv("DO_NOT_TRACK")
    (tmp_path / "telemetry_disabled").write_text("1\n", encoding="utf-8")
    client.capture("analyze", finding=_PLANTED_FINDING)
    assert sent == []


def test_disable_command_writes_the_opt_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from hefesto.cli.main import cli

    _seed_noticed(tmp_path)
    sent = _record(monkeypatch)
    result = CliRunner().invoke(cli, ["telemetry", "disable"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "telemetry_disabled").is_file()
    client.capture("analyze")
    assert sent == []


def test_debug_prints_the_event_and_does_not_send(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_noticed(tmp_path)
    monkeypatch.setenv("HEFESTO_TELEMETRY_DEBUG", "1")
    client.capture("analyze", path=_PLANTED_PATH, ip=_PLANTED_IP)
    err = capsys.readouterr().err
    assert '"event":"analyze"' in err
    assert '"$geoip_disable":true' in err
    assert _PLANTED_PATH not in err
    assert _PLANTED_IP not in err
    assert client.POSTHOG_API_KEY not in err


def test_payload_has_no_pii_paths_findings_or_ip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _seed_noticed(tmp_path)
    sent = _record(monkeypatch)
    client.capture(
        "analyze",
        path=_PLANTED_PATH,
        code=_PLANTED_CODE,
        finding=_PLANTED_FINDING,
        repo=_PLANTED_REPO,
        ip=_PLANTED_IP,
    )
    assert len(sent) == 1
    body = sent[0]
    blob = json.dumps(body)
    for planted in (_PLANTED_PATH, _PLANTED_CODE, _PLANTED_FINDING, _PLANTED_REPO, _PLANTED_IP):
        assert planted not in blob
    assert set(body["properties"]) == {"source", "$geoip_disable", "$process_person_profile"}
    assert body["properties"]["$geoip_disable"] is True
    assert "$ip" not in body and "ip" not in body["properties"]
    assert body["distinct_id"] == "11111111-1111-4111-8111-111111111111"


@pytest.mark.parametrize("event", client.EVENTS)
def test_every_event_disables_geoip(event: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEFESTO_SOURCE", "hook")
    body = client.build_event(event)
    assert body["properties"]["$geoip_disable"] is True
    assert body["event"] == event
    assert body["properties"]["source"] in client.CTA_SOURCES


def test_notice_is_printed_before_any_send(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sent = _record(monkeypatch)
    client.prepare_cli("analyze")
    notice = capsys.readouterr().err
    assert client.NOTICE in notice
    assert sent == []
    client.capture("analyze", path=_PLANTED_PATH)
    assert sent == []
    client._held = False
    client.capture("analyze")
    assert len(sent) == 1
    assert client.NOTICE not in capsys.readouterr().err


def test_send_returns_before_a_slow_socket(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _seed_noticed(tmp_path)
    entered = threading.Event()

    def _slow(*_args: object, **_kwargs: object) -> None:
        entered.set()
        time.sleep(2)

    monkeypatch.setattr(client.urllib.request, "urlopen", _slow)
    started = time.perf_counter()
    client.capture("analyze")
    assert time.perf_counter() - started < 0.5
    assert entered.wait(timeout=1)


def test_empty_key_from_env_or_config_sends_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _seed_noticed(tmp_path)
    sent = _record(monkeypatch)
    monkeypatch.setenv("HEFESTO_POSTHOG_KEY", "")
    client.capture("analyze")
    monkeypatch.delenv("HEFESTO_POSTHOG_KEY")
    (tmp_path / "telemetry.json").write_text(json.dumps({"posthog_api_key": ""}), encoding="utf-8")
    client.capture("analyze")
    (tmp_path / "telemetry.json").write_text(
        json.dumps({"posthog_api_key": client.POSTHOG_API_KEY}), encoding="utf-8"
    )
    monkeypatch.setenv("HEFESTO_POSTHOG_KEY", "   ")
    client.capture("analyze")
    assert sent == []
    assert client.resolved_posthog_key() == ""


def test_builtin_key_and_host_are_the_us_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HEFESTO_POSTHOG_KEY", raising=False)
    monkeypatch.delenv("HEFESTO_POSTHOG_HOST", raising=False)
    assert client.resolved_posthog_key() == client.POSTHOG_API_KEY
    assert client.resolved_posthog_key().startswith("phc_")
    assert client.resolved_posthog_host() == "https://us.i.posthog.com"


def test_upgrade_cta_source_is_hook_ci_or_action(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _seed_noticed(tmp_path)
    sent = _record(monkeypatch)
    client.capture("upgrade_cta_shown")
    assert sent == []
    monkeypatch.setenv("HEFESTO_SOURCE", "hook")
    client.capture("upgrade_cta_shown")
    assert sent[0]["properties"]["source"] == "hook"
    assert sent[0]["properties"]["source"] in {"hook", "ci", "action"}


def test_cli_entry_points_exit_2_on_usage_errors(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["HEFESTO_TELEMETRY"] = "0"
    env["HEFESTO_STATE_DIR"] = str(tmp_path)
    module = subprocess.run(
        [sys.executable, "-m", "hefesto", "not-a-command"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert module.returncode == 2
    script = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.argv=['hefesto','not-a-command']; "
                "from hefesto.cli.main import cli; cli()"
            ),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert script.returncode == 2
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    assert 'hefesto = "hefesto.cli.main:cli"' in pyproject.read_text(encoding="utf-8")


def test_main_preserves_click_usage_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto.cli.main import main

    monkeypatch.setattr(sys, "argv", ["hefesto", "not-a-command"])
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


def test_telemetry_is_hooked_inside_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto.cli.main import cli

    seen: list[str] = []
    monkeypatch.setattr(client, "prepare_cli", lambda sub: seen.append(sub or ""))
    result = CliRunner().invoke(cli, ["telemetry", "disable"])
    assert result.exit_code == 0, result.output
    assert seen == ["telemetry"]


def test_install_hooks_emits_hooks_installed_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if subprocess.run(["git", "--version"], capture_output=True, check=False).returncode != 0:
        pytest.skip("git not available")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    events: list[str] = []
    monkeypatch.setattr(client, "capture", lambda event, **_extra: events.append(event))
    monkeypatch.chdir(tmp_path)
    from hefesto.cli.main import cli

    first = CliRunner().invoke(cli, ["install-hooks"])
    assert first.exit_code == 0, first.output
    second = CliRunner().invoke(cli, ["install-hooks"])
    assert second.exit_code == 0, second.output
    assert events.count("hooks_installed") == 1
    hook = (tmp_path / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "HEFESTO_SOURCE=hook" in hook
