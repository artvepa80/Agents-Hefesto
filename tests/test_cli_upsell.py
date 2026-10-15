"""PRO/OMEGA notices: one stderr line, weekly cap, and no retired offer copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.cli import growth
from hefesto.cli.growth import (
    GATED_ENRICH_LINE,
    GATED_INFO_LINE,
    GATED_IRIS_LINE,
    GATED_SCOPE_LINE,
    GATED_SERVE_LINE,
    HOOK_BLOCKED_LINE,
    INIT_LINE,
    SWARM_FACT,
    is_analyze_milestone,
    load_upsell_state,
    milestone_line,
    note_finished_analysis,
    show_notice,
    show_upgrade_cta,
)
from hefesto.telemetry import client

_BANNED = (
    "14-day",
    "free trial",
    "no credit card",
    "credit card required",
    "discount",
    "$8/month",
    "$19/month",
)

_LINES = (
    INIT_LINE,
    HOOK_BLOCKED_LINE,
    GATED_SERVE_LINE,
    GATED_ENRICH_LINE,
    GATED_SCOPE_LINE,
    GATED_INFO_LINE,
    GATED_IRIS_LINE,
    milestone_line(25),
    SWARM_FACT,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HEFESTO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("HEFESTO_TELEMETRY_UNDER_TEST", "1")
    for name in (
        "HEFESTO_TELEMETRY",
        "DO_NOT_TRACK",
        "HEFESTO_NO_UPSELL",
        "HEFESTO_TELEMETRY_DEBUG",
        "HEFESTO_SOURCE",
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "CIRCLECI",
        "IRIS_BQ_PROJECT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(client, "_held", False)
    monkeypatch.setattr(growth, "stdout_is_tty", lambda: True)
    state = {
        "install_id": "11111111-1111-4111-8111-111111111111",
        "notice_shown": True,
        "first_run_sent": True,
    }
    (tmp_path / "telemetry_state.json").write_text(json.dumps(state), encoding="utf-8")

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("upsell test opened a socket")

    monkeypatch.setattr(client.urllib.request, "urlopen", _refuse)


def _record(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []
    monkeypatch.setattr(client, "_schedule_send", lambda payload: sent.append(payload))
    return sent


def test_swarm_fact_is_within_280_characters() -> None:
    assert len(SWARM_FACT) <= 280
    assert "security analysis pipeline" in SWARM_FACT
    assert "BLOCK" in SWARM_FACT
    assert "\n" not in SWARM_FACT


def test_notice_lines_reject_retired_offer_copy() -> None:
    for line in _LINES:
        assert "\n" not in line
        lowered = line.lower()
        for phrase in _BANNED:
            assert phrase not in lowered
        if line != SWARM_FACT:
            assert "$8/mo" in line or "$19/mo" in line


def test_gated_prices_follow_the_tier() -> None:
    assert "PRO ($8/mo)" in GATED_SERVE_LINE
    assert "PRO ($8/mo)" in GATED_ENRICH_LINE
    assert "PRO ($8/mo)" in GATED_SCOPE_LINE
    assert "PRO ($8/mo)" in GATED_INFO_LINE
    assert "OMEGA ($19/mo)" in GATED_IRIS_LINE
    assert "utm_content=gated_serve" in GATED_SERVE_LINE
    assert "utm_content=gated_iris" in GATED_IRIS_LINE
    assert INIT_LINE.startswith("Plans: PRO $8/mo · OMEGA $19/mo.")
    assert "utm_content=init" in INIT_LINE


def test_milestones_are_25_then_every_100() -> None:
    assert [n for n in range(1, 330) if is_analyze_milestone(n)] == [25, 125, 225, 325]


def test_one_notice_per_week_across_types(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sent = _record(monkeypatch)
    assert show_notice("init", INIT_LINE) is True
    assert show_upgrade_cta() is False
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert INIT_LINE in err
    assert HOOK_BLOCKED_LINE not in err
    assert sent[0]["properties"]["cta"] == "init"
    assert sent[0]["properties"]["source"] == "cli"


def test_each_type_shows_at_most_three_times(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(growth.time, "time", lambda: 1_700_000_000.0)
    assert show_notice("gated_info", GATED_INFO_LINE) is True
    state = load_upsell_state()
    assert state is not None
    state["last_shown_at"] = 1_700_000_000.0 - (8 * 24 * 60 * 60)
    state["counts"]["gated_info"] = 3
    (tmp_path / "upsell.json").write_text(json.dumps(state), encoding="utf-8")
    assert show_notice("gated_info", GATED_INFO_LINE) is False
    assert show_notice("init", INIT_LINE) is True


def test_corrupt_state_shows_nothing_and_is_left_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "upsell.json"
    path.write_text("{not json", encoding="utf-8")
    assert show_notice("init", INIT_LINE) is False
    assert note_finished_analysis() is None
    assert path.read_text(encoding="utf-8") == "{not json"
    assert capsys.readouterr().err == ""


def test_opt_outs_and_ci_vendors_suppress_the_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cases = (
        ("HEFESTO_TELEMETRY", "0"),
        ("DO_NOT_TRACK", "1"),
        ("HEFESTO_NO_UPSELL", "1"),
        ("CI", "true"),
        ("GITLAB_CI", "true"),
        ("CIRCLECI", "true"),
    )
    for name, value in cases:
        monkeypatch.setenv(name, value)
        assert show_notice("init", INIT_LINE) is False, name
        monkeypatch.delenv(name)
    monkeypatch.setenv("JENKINS_URL", "http://jenkins.example")
    assert show_notice("init", INIT_LINE) is False
    assert capsys.readouterr().err == ""


def test_quiet_machine_and_no_tty_suppress_the_line(monkeypatch: pytest.MonkeyPatch) -> None:
    assert show_notice("init", INIT_LINE, quiet=True) is False
    assert show_notice("init", INIT_LINE, machine=True) is False
    monkeypatch.setattr(growth, "stdout_is_tty", lambda: False)
    assert show_notice("init", INIT_LINE) is False


def test_milestone_line_after_25_finished_analyses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sent = _record(monkeypatch)
    for _ in range(24):
        assert note_finished_analysis() is not None
    assert growth.show_milestone(24, quiet=False, machine=False) is False
    count = note_finished_analysis()
    assert growth.show_milestone(count, quiet=False, machine=False) is True
    err = capsys.readouterr().err
    assert err.strip() == milestone_line(25)
    assert sent[0]["properties"]["cta"] == "analyze_milestone"
    assert "utm_content=analyze_milestone" in err


def test_info_prints_the_pro_line_after_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _record(monkeypatch)
    from hefesto.cli.main import cli

    result = CliRunner().invoke(cli, ["info"])
    assert result.exit_code == 1
    assert result.stderr.index("This feature requires") < result.stderr.index(GATED_INFO_LINE)
    assert result.stderr.count("\n") >= 2


def test_analyze_json_and_quiet_skip_the_milestone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    state = {"last_shown_at": None, "counts": {}, "successful_analyses": 24}
    (tmp_path / "upsell.json").write_text(json.dumps(state), encoding="utf-8")
    from hefesto.cli.main import cli

    runner = CliRunner()
    quiet = runner.invoke(cli, ["analyze", "app.py", "--quiet"])
    assert quiet.exit_code == 0, quiet.output
    assert "hefesto-swarm" not in quiet.stderr
    loaded = json.loads((tmp_path / "upsell.json").read_text(encoding="utf-8"))
    loaded["successful_analyses"] = 24
    loaded["last_shown_at"] = None
    (tmp_path / "upsell.json").write_text(json.dumps(loaded), encoding="utf-8")
    as_json = runner.invoke(cli, ["analyze", "app.py", "--output", "json"])
    assert as_json.exit_code == 0, as_json.output
    assert "hefesto-swarm" not in as_json.stderr
    assert as_json.stdout.lstrip().startswith("{")
