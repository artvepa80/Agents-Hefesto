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
        files=2,
        issues=1,
        duration_ms=15,
        exit_code=0,
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
    props = body["properties"]
    assert props["files"] == 2
    assert props["issues"] == 1
    assert props["duration_ms"] == 15
    assert props["exit_code"] == 0
    assert props["version"]
    assert props["os"] == sys.platform
    assert props["py"] == f"{sys.version_info.major}.{sys.version_info.minor}"
    assert props["src"] in {"pypi", "editable", "unknown"}
    assert isinstance(props["env"], list)
    assert props["$geoip_disable"] is True
    assert "$ip" not in body and "ip" not in props
    assert "path" not in props and "code" not in props and "finding" not in props
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


def test_upgrade_cta_source_is_hook_or_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _seed_noticed(tmp_path)
    sent = _record(monkeypatch)
    client.capture("upgrade_cta_shown", cta="init")
    assert sent[0]["properties"]["source"] == "cli"
    assert sent[0]["properties"]["cta"] == "init"
    sent.clear()
    monkeypatch.setenv("HEFESTO_SOURCE", "ci")
    client.capture("upgrade_cta_shown", cta="init")
    assert sent == []
    monkeypatch.setenv("HEFESTO_SOURCE", "hook")
    client.capture("upgrade_cta_shown", cta="hook_blocked")
    assert sent[0]["properties"]["source"] == "hook"
    assert sent[0]["properties"]["cta"] == "hook_blocked"
    assert sent[0]["properties"]["source"] in {"hook", "cli"}


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


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


def _pypi(version: str):
    def _open(request: object, timeout: float = 0) -> _Body:
        _open.calls.append((getattr(request, "full_url", ""), timeout))
        return _Body(json.dumps({"info": {"version": version}}).encode("utf-8"))

    _open.calls = []  # type: ignore[attr-defined]
    return _open


# Tokens the client already treats as on (_TRUTHY) or off (_OPT_OUT), including
# surrounding space and mixed case, because both checks use strip().lower().
_UPDATE_CHECK_OFF = (
    ("HEFESTO_NO_UPDATE_CHECK", "1"),
    ("HEFESTO_NO_UPDATE_CHECK", "true"),
    ("HEFESTO_NO_UPDATE_CHECK", "yes"),
    ("HEFESTO_NO_UPDATE_CHECK", "on"),
    ("HEFESTO_NO_UPDATE_CHECK", " TRUE "),
    ("HEFESTO_TELEMETRY", "0"),
    ("HEFESTO_TELEMETRY", "false"),
    ("HEFESTO_TELEMETRY", "no"),
    ("HEFESTO_TELEMETRY", "off"),
    ("HEFESTO_TELEMETRY", " Off "),
    ("DO_NOT_TRACK", "1"),
    ("DO_NOT_TRACK", "true"),
    ("DO_NOT_TRACK", "yes"),
    ("DO_NOT_TRACK", "on"),
    ("DO_NOT_TRACK", " Yes "),
)


def _forbid_http(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, object]]:
    """Record every urllib request or urlopen, then fail the call."""
    calls: list[tuple[object, object]] = []

    def _boom(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("unexpected HTTP call")

    monkeypatch.setattr(client.urllib.request, "Request", _boom)
    monkeypatch.setattr(client.urllib.request, "urlopen", _boom)
    return calls


@pytest.mark.parametrize(("name", "value"), _UPDATE_CHECK_OFF)
def test_update_check_skips_network_and_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, value: str
) -> None:
    calls = _forbid_http(monkeypatch)
    monkeypatch.setenv(name, value)
    client.refresh_latest_version()
    assert calls == []
    assert not (tmp_path / ".latest_version").exists()


def test_update_check_runs_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("HEFESTO_NO_UPDATE_CHECK", "HEFESTO_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.delenv(name, raising=False)
    opened = _pypi("9.9.9")
    monkeypatch.setattr(client.urllib.request, "urlopen", opened)
    client.refresh_latest_version()
    assert len(opened.calls) == 1
    assert opened.calls[0][0] == client.PYPI_JSON_URL
    cache = tmp_path / ".latest_version"
    assert cache.is_file()
    loaded = json.loads(cache.read_text(encoding="utf-8"))
    assert loaded["version"] == "9.9.9"


def test_update_check_still_runs_when_only_telemetry_file_is_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``hefesto telemetry disable`` does not skip the version check."""
    (tmp_path / "telemetry_disabled").write_text("1\n", encoding="utf-8")
    opened = _pypi("9.9.9")
    monkeypatch.setattr(client.urllib.request, "urlopen", opened)
    client.refresh_latest_version()
    assert len(opened.calls) == 1
    assert (tmp_path / ".latest_version").is_file()


def test_pypi_notice_is_cached_for_a_day(monkeypatch: pytest.MonkeyPatch) -> None:
    opened = _pypi("9.9.9")
    monkeypatch.setattr(client.urllib.request, "urlopen", opened)
    client.refresh_latest_version()
    client.refresh_latest_version()
    assert len(opened.calls) == 1
    assert opened.calls[0][0] == client.PYPI_JSON_URL
    assert opened.calls[0][1] == client.PYPI_TIMEOUT
    notice = client.get_upgrade_notice("4.17.1")
    assert notice is not None
    assert "Hefesto 9.9.9 available" in notice
    assert "you have 4.17.1" in notice
    assert client.get_upgrade_notice("9.9.9") is None
    assert client.get_upgrade_notice("9.9.10") is None


def test_pypi_failure_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise TimeoutError("pypi")

    monkeypatch.setattr(client.urllib.request, "urlopen", _boom)
    client.refresh_latest_version()
    assert client.get_upgrade_notice("4.17.1") is None


def test_stale_version_cache_is_refetched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stale = {"version": "1.0.0", "ts": time.time() - client._CACHE_TTL_SECONDS - 5}
    (tmp_path / ".latest_version").write_text(json.dumps(stale), encoding="utf-8")
    opened = _pypi("8.0.0")
    monkeypatch.setattr(client.urllib.request, "urlopen", opened)
    client.refresh_latest_version()
    assert len(opened.calls) == 1
    notice = client.get_upgrade_notice("4.17.1")
    assert notice is not None and "Hefesto 8.0.0 available" in notice


def test_environment_labels_are_ci_docker_and_dogfood(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "CIRCLECI",
        "KUBERNETES_SERVICE_HOST",
        "HEFESTO_TELEMETRY_ENV",
        "HEFESTO_DOGFOOD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(client.os.path, "exists", lambda path: path == "/.dockerenv")
    monkeypatch.setattr(client, "install_source", lambda: "pypi")
    monkeypatch.setenv("CI", "true")
    flags = client.environment_flags()
    assert "ci" in flags and "docker" in flags
    assert "dogfood" not in flags
    monkeypatch.delenv("CI")
    monkeypatch.setattr(client.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(client, "install_source", lambda: "editable")
    assert client.environment_flags() == ["dogfood"]
    monkeypatch.setattr(client, "install_source", lambda: "pypi")
    monkeypatch.setenv("HEFESTO_TELEMETRY_ENV", "dogfood")
    assert client.environment_flags() == ["dogfood"]


def test_install_source_reads_the_package_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import hefesto

    monkeypatch.setattr(hefesto, "__file__", "/usr/lib/site-packages/hefesto/__init__.py")
    assert client.install_source() == "pypi"
    monkeypatch.setattr(hefesto, "__file__", "/workspace/hefesto/__init__.py")
    assert client.install_source() == "editable"


def test_analyze_command_sends_counts_and_the_pypi_notice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _seed_noticed(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    sent = _record(monkeypatch)
    opened = _pypi("9.9.9")
    monkeypatch.setattr(client.urllib.request, "urlopen", opened)
    from hefesto.cli.main import cli

    result = CliRunner().invoke(cli, ["analyze", "app.py"])
    assert result.exit_code == 0, result.output
    assert "Hefesto 9.9.9 available" in result.stdout
    assert "you have" in result.stdout
    analyze = [body for body in sent if body["event"] == "analyze"]
    assert len(analyze) == 1
    props = analyze[0]["properties"]
    for key in (
        "files",
        "issues",
        "duration_ms",
        "exit_code",
        "version",
        "os",
        "py",
        "env",
        "src",
    ):
        assert key in props
    assert props["files"] >= 1
    assert props["exit_code"] == 0
    assert isinstance(props["issues"], int)
    assert isinstance(props["duration_ms"], int)
    assert props["src"] in {"pypi", "editable"}
    blob = json.dumps(analyze[0])
    assert "app.py" not in blob
    assert str(tmp_path) not in blob
    assert _PLANTED_IP not in blob
    assert "$ip" not in analyze[0]
