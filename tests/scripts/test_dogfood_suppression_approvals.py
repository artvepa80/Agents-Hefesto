"""Approval lines for new line suppressions in the changed-file gate.

``scripts/dogfood_changed.py --fail-on-new-suppressions`` fails on each new
``# hefesto: ignore[TYPE] reason`` comment unless the pull request body has a
maintainer approval line for that exact ``file:line``::

    Suppression approved by Arturo on 2026-10-29: path/to/file.py:12

The body is read from the event payload (``GITHUB_EVENT_PATH``), so no token
is needed. The list of new suppressions always goes to ``GITHUB_STEP_SUMMARY``
when that variable is set.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dogfood_changed.py"


def _load():
    spec = importlib.util.spec_from_file_location("dogfood_changed_approvals", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MOD = _load()


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "a.py").write_text(
        "import marshal  # hefesto: ignore[PICKLE_USAGE] trusted input\n"
        "import pickle  # hefesto: ignore[PICKLE_USAGE] signed cache\n"
        "\nx = 1\nprint(pickle, marshal)\n"
    )
    _git(tmp_path, "commit", "-qam", "head")
    return tmp_path, base


# --- parsing approval lines -------------------------------------------------


def test_parse_approvals_reads_each_line() -> None:
    body = (
        "Intro text\n"
        "Suppression approved by Arturo on 2026-10-29: a.py:2\r\n"
        "  Suppression approved by Arturo on 2026-10-30: pkg/b.py:14  \n"
    )
    assert MOD.parse_suppression_approvals(body) == {("a.py", 2), ("pkg/b.py", 14)}


@pytest.mark.parametrize(
    "line",
    [
        "Suppression approved by Someone on 2026-10-29: a.py:2",
        "Suppression approved by Arturo on 29/10/2026: a.py:2",
        "Suppression approved by Arturo on 2026-10-29: a.py",
        "Suppression approved by Arturo on 2026-10-29: a.py:2, b.py:3",
        "> Suppression approved by Arturo on 2026-10-29: a.py:2",
        "suppression approved by arturo on 2026-10-29: a.py:2",
        "Suppression approved by Arturo on 2026-10-29: a.py:2 extra",
    ],
)
def test_parse_approvals_rejects_other_formats(line: str) -> None:
    assert MOD.parse_suppression_approvals(line) == set()


@pytest.mark.parametrize("body", [None, ""])
def test_parse_approvals_empty_body(body: Optional[str]) -> None:
    assert MOD.parse_suppression_approvals(body) == set()


# --- reading the event payload ----------------------------------------------


def test_pr_body_from_event_payload(tmp_path: Path) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"body": "hello"}}))
    assert MOD.pull_request_body({"GITHUB_EVENT_PATH": str(event)}) == "hello"


@pytest.mark.parametrize(
    "payload", [{"pull_request": {"body": None}}, {"before": "abc"}, {"pull_request": "x"}, []]
)
def test_pr_body_absent(tmp_path: Path, payload: object) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload))
    assert MOD.pull_request_body({"GITHUB_EVENT_PATH": str(event)}) is None


def test_pr_body_without_event_path_or_unreadable(tmp_path: Path) -> None:
    assert MOD.pull_request_body({}) is None
    assert MOD.pull_request_body({"GITHUB_EVENT_PATH": str(tmp_path / "missing.json")}) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert MOD.pull_request_body({"GITHUB_EVENT_PATH": str(bad)}) is None


# --- end to end ------------------------------------------------------------


def _run(repo_path: Path, base: str, extra_env: Dict[str, str], *flags: str):
    env = {"HEFESTO_TELEMETRY": "0", "PATH": "/usr/bin:/bin", **extra_env}
    if "PYTHONPATH" in os.environ:
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]
    cmd = [sys.executable, str(SCRIPT), "--repo", str(repo_path), "--base", base, "--head", "HEAD"]
    return subprocess.run([*cmd, *flags], capture_output=True, text=True, env=env)


def _event(tmp: Path, body: str) -> Dict[str, str]:
    path = tmp / "event.json"
    path.write_text(json.dumps({"pull_request": {"body": body}}))
    return {"GITHUB_EVENT_PATH": str(path)}


def test_unapproved_suppressions_fail(repo, tmp_path_factory) -> None:
    path, base = repo
    tmp = tmp_path_factory.mktemp("evt")
    result = _run(path, base, _event(tmp, "no approvals"), "--fail-on-new-suppressions")
    assert result.returncode == 1
    assert "Unapproved new line suppressions (2)" in result.stdout


def test_one_approval_covers_only_its_line(repo, tmp_path_factory) -> None:
    path, base = repo
    tmp = tmp_path_factory.mktemp("evt")
    body = "Suppression approved by Arturo on 2026-10-29: a.py:2\n"
    result = _run(path, base, _event(tmp, body), "--fail-on-new-suppressions")
    assert result.returncode == 1
    assert "Unapproved new line suppressions (1)" in result.stdout
    assert "a.py:1 [PICKLE_USAGE] trusted input" in result.stdout.split("Unapproved")[1]


def test_every_suppression_approved_passes(repo, tmp_path_factory) -> None:
    path, base = repo
    tmp = tmp_path_factory.mktemp("evt")
    body = (
        "Suppression approved by Arturo on 2026-10-29: a.py:2\n"
        "Suppression approved by Arturo on 2026-10-29: a.py:1\n"
    )
    result = _run(path, base, _event(tmp, body), "--fail-on-new-suppressions")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Unapproved new line suppressions (0)" in result.stdout


def test_approval_for_a_different_line_does_not_count(repo, tmp_path_factory) -> None:
    path, base = repo
    tmp = tmp_path_factory.mktemp("evt")
    body = (
        "Suppression approved by Arturo on 2026-10-29: a.py:20\n"
        "Suppression approved by Arturo on 2026-10-29: b.py:3\n"
    )
    result = _run(path, base, _event(tmp, body), "--fail-on-new-suppressions")
    assert result.returncode == 1


def test_without_flag_suppressions_only_listed(repo) -> None:
    path, base = repo
    result = _run(path, base, {})
    assert result.returncode == 0
    assert "New line suppressions (2)" in result.stdout


def test_step_summary_always_written(repo, tmp_path_factory) -> None:
    path, base = repo
    tmp = tmp_path_factory.mktemp("evt")
    summary = tmp / "summary.md"
    summary.write_text("previous step\n")
    body = "Suppression approved by Arturo on 2026-10-29: a.py:2\n"
    env = {**_event(tmp, body), "GITHUB_STEP_SUMMARY": str(summary)}
    _run(path, base, env)
    text = summary.read_text()
    assert text.startswith("previous step\n")
    assert "New line suppressions (2)" in text
    assert "a.py:2 [PICKLE_USAGE] signed cache" in text
    assert "(approved)" in text.split("a.py:2")[1].splitlines()[0]
    assert "not approved" in text.split("a.py:1 ")[1].splitlines()[0]


def test_step_summary_written_with_no_suppressions(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "a.py").write_text("x = 2\n")
    _git(tmp_path, "commit", "-qam", "head")
    summary = tmp_path / "summary.md"
    _run(tmp_path, base, {"GITHUB_STEP_SUMMARY": str(summary)}, "--fail-on-new-suppressions")
    assert "New line suppressions (0)" in summary.read_text()
