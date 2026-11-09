"""hefesto init and the one-time PRO line after a hook block."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.cli import growth
from hefesto.cli.growth import (
    CTA_LINE,
    HOOK_BLOCKED_PRICING_URL,
    INIT_PRICING_URL,
    UTM_CAMPAIGN,
    UTM_MEDIUM,
    UTM_SOURCE,
    show_upgrade_cta,
)
from hefesto.telemetry import client
from hefesto.telemetry.client import NOTICE

_INIT_URL = (
    "https://hefestoai.narapallc.com/"
    "?utm_source=hefesto-cli&utm_medium=cli"
    "&utm_campaign=growth_q4_2026&utm_content=init#pricing"
)
_BLOCKED_URL = (
    "https://hefestoai.narapallc.com/"
    "?utm_source=hefesto-cli&utm_medium=cli"
    "&utm_campaign=growth_q4_2026&utm_content=hook_blocked#pricing"
)

_CURRENT_COPY = (
    "README.md",
    "LICENSE-COMMERCIAL.md",
    "llms.txt",
    "scripts/README.md",
    ".github/copilot-instructions.md",
    "docs/GETTING_STARTED.md",
    "docs/LICENSE_GATES.md",
    "docs/INTEGRATION.md",
    "docs/telemetry.md",
    "hefesto/cli/main.py",
    "hefesto/cli/growth.py",
    "skills/hefestoai/commands.md",
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HEFESTO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("HEFESTO_TELEMETRY_UNDER_TEST", "1")
    for name in (
        "HEFESTO_TELEMETRY",
        "DO_NOT_TRACK",
        "HEFESTO_TELEMETRY_DEBUG",
        "HEFESTO_SOURCE",
        "CI",
        "GITHUB_ACTIONS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(client, "_held", False)
    monkeypatch.setattr(growth, "stdout_is_tty", lambda: False)

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("init test opened a socket")

    monkeypatch.setattr(client.urllib.request, "urlopen", _refuse)


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
    monkeypatch.setattr(client, "_schedule_send", lambda payload: sent.append(payload))
    return sent


def test_utm_constants_and_both_urls_are_exact() -> None:
    assert UTM_SOURCE == "hefesto-cli"
    assert UTM_MEDIUM == "cli"
    assert UTM_CAMPAIGN == "growth_q4_2026"
    assert INIT_PRICING_URL == _INIT_URL
    assert HOOK_BLOCKED_PRICING_URL == _BLOCKED_URL
    assert CTA_LINE == f"PRO $8/mo: {_BLOCKED_URL}"
    for banned in ("trial", "discount", "credit card", "validat", "%", "coupon"):
        assert banned not in CTA_LINE.lower()
        assert banned not in INIT_PRICING_URL.lower()


def test_init_is_idempotent_and_prints_the_init_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if subprocess.run(["git", "--version"], capture_output=True, check=False).returncode != 0:
        pytest.skip("git not available")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    from hefesto.cli.main import cli

    runner = CliRunner()
    first = runner.invoke(cli, ["init"])
    assert first.exit_code == 0, first.output
    second = runner.invoke(cli, ["init"])
    assert second.exit_code == 0, second.output
    assert _INIT_URL not in first.stdout
    assert _INIT_URL not in second.stdout
    assert "already up to date" in second.stdout
    hook = (tmp_path / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "HEFESTO_SOURCE=hook" in hook


def test_init_prints_the_telemetry_notice_and_does_not_send(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if subprocess.run(["git", "--version"], capture_output=True, check=False).returncode != 0:
        pytest.skip("git not available")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    sent = _record(monkeypatch)
    from hefesto.cli.main import cli

    result = CliRunner().invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert NOTICE in result.stderr
    assert sent == []
    assert _INIT_URL not in result.stdout


def test_cta_prints_once_and_emits_hook_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_noticed(tmp_path)
    monkeypatch.setenv("HEFESTO_SOURCE", "hook")
    monkeypatch.setattr(growth, "stdout_is_tty", lambda: True)
    sent = _record(monkeypatch)
    show_upgrade_cta()
    show_upgrade_cta()
    err = capsys.readouterr().err
    assert err.count(CTA_LINE) == 1
    assert _BLOCKED_URL in err
    assert len(sent) == 1
    assert sent[0]["event"] == "upgrade_cta_shown"
    assert sent[0]["properties"]["source"] == "hook"
    assert sent[0]["properties"]["cta"] == "hook_blocked"
    assert sent[0]["properties"]["source"] in {"hook", "cli"}
    assert set(sent[0]["properties"]) == {
        "source",
        "cta",
        "$geoip_disable",
        "$process_person_profile",
    }
    assert sent[0]["distinct_id"] == "11111111-1111-4111-8111-111111111111"
    blob = json.dumps(sent[0])
    assert "/home/" not in blob
    assert "finding" not in blob


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [("CI", "true"), ("GITHUB_ACTIONS", "true"), ("GITHUB_ACTIONS", "1")],
)
def test_cta_never_in_ci(
    env_name: str,
    env_value: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_noticed(tmp_path)
    monkeypatch.setenv("HEFESTO_SOURCE", "hook")
    monkeypatch.setenv(env_name, env_value)
    sent = _record(monkeypatch)
    show_upgrade_cta()
    assert capsys.readouterr().err == ""
    assert sent == []


def test_hook_block_prints_the_cta_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _seed_noticed(tmp_path)
    monkeypatch.setenv("HEFESTO_SOURCE", "hook")
    monkeypatch.setattr(growth, "stdout_is_tty", lambda: True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("eval(x)\n", encoding="utf-8")
    sent = _record(monkeypatch)
    from hefesto.cli.main import cli

    runner = CliRunner()
    first = runner.invoke(cli, ["analyze", "app.py", "--fail-on", "HIGH"])
    assert first.exit_code == 1, first.output
    assert first.stderr.count(_BLOCKED_URL) == 1
    assert "PRO $8/mo" in first.stderr
    second = runner.invoke(cli, ["analyze", "app.py", "--fail-on", "HIGH"])
    assert second.exit_code == 1, second.output
    assert _BLOCKED_URL not in second.stderr
    cta = [body for body in sent if body["event"] == "upgrade_cta_shown"]
    assert len(cta) == 1
    assert cta[0]["properties"]["source"] == "hook"
    assert cta[0]["properties"]["cta"] == "hook_blocked"


def test_current_copy_uses_only_the_two_prices() -> None:
    root = Path(__file__).resolve().parents[1]
    banned = (
        "$8/month",
        "$19/month",
        "$8 USD",
        "$19 USD",
        "14-day",
        "free trial",
        "no credit card",
        "credit card required",
        "founding price",
        "Custom pricing",
    )
    for relative in _CURRENT_COPY:
        text = (root / relative).read_text(encoding="utf-8")
        for phrase in banned:
            assert phrase not in text, f"{relative} contains {phrase!r}"
