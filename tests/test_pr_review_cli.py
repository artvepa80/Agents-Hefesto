"""Smoke tests for the ``hefesto pr-review`` CLI command.

Focused on shape, not on the underlying detection — that is already
pinned by ``test_pr_review_orchestrator.py``. Here we verify:
- JSON output shape and schema version
- ``--strict`` flag passthrough
- ``--post`` shells out to ``gh`` via subprocess (mocked)

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List
from unittest.mock import patch

from click.testing import CliRunner

from hefesto.cli.main import cli


def _git(args: List[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": "/tmp",
        },
    )


def _tiny_repo(tmp_path: Path) -> "tuple[str, str]":
    _git(["init", "-q"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "baseline"], tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n\n\ndef new_fn():\n    return 2\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "edit"], tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return base, head


def test_pr_review_cli_emits_json_with_expected_schema(tmp_path: Path) -> None:
    base, head = _tiny_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "pr-review",
            "--project-root",
            str(tmp_path),
            "--base",
            base,
            "--head",
            head,
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["pr_review_version"] == 1
    assert payload["base_sha"] == base
    assert payload["head_sha"] == head
    assert payload["changed_files"] == ["app.py"]
    assert isinstance(payload["findings"], list)
    assert payload["strict"] is False
    assert "diagnostics" in payload


def test_pr_review_cli_strict_flag_passes_through(tmp_path: Path) -> None:
    base, head = _tiny_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "pr-review",
            "--project-root",
            str(tmp_path),
            "--base",
            base,
            "--head",
            head,
            "--strict",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["strict"] is True


def test_pr_review_cli_post_requires_repo_and_pr(tmp_path: Path) -> None:
    """Without --repo/--pr and no gh auto-detect, --post must exit 1 with
    a clear error message instead of silently attempting to post."""
    base, head = _tiny_repo(tmp_path)
    runner = CliRunner()
    with patch("hefesto.pr_review.post.detect_repo_and_pr", return_value=(None, None)):
        result = runner.invoke(
            cli,
            [
                "pr-review",
                "--project-root",
                str(tmp_path),
                "--base",
                base,
                "--head",
                head,
                "--post",
            ],
        )
    assert result.exit_code == 1
    assert "--repo and --pr are required" in result.output


def test_pr_review_cli_post_shells_out_to_gh(tmp_path: Path) -> None:
    """--post with explicit repo/pr must call subprocess.run for each
    in-hunk finding. We mock ``post_findings`` directly to keep the
    test offline and deterministic — mocking subprocess globally
    would interfere with the orchestrator's git commands."""
    captured: dict = {}

    def _fake_post(*, repo, pr_number, commit_id, findings, dry_run=False):
        captured["repo"] = repo
        captured["pr_number"] = pr_number
        captured["commit_id"] = commit_id
        captured["findings"] = findings
        return {"posted": len(findings), "failed": 0, "skipped_no_hunk": 0}

    # Build a repo with a real in-hunk SQLi so the CLI has something to post.
    _git(["init", "-q"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n")
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "baseline"], tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (tmp_path / "app.py").write_text(
        "def ok():\n    return 1\n\n\n"
        "def fetch(cur, user_id):\n"
        "    cur.execute('SELECT * FROM t WHERE id = ' + str(user_id))\n"
    )
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "add sqli"], tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    with patch("hefesto.pr_review.post.post_findings", side_effect=_fake_post):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "pr-review",
                "--project-root",
                str(tmp_path),
                "--base",
                base,
                "--head",
                head,
                "--post",
                "--repo",
                "owner/name",
                "--pr",
                "42",
            ],
        )
    assert result.exit_code == 0, result.output
    assert captured["repo"] == "owner/name"
    assert captured["pr_number"] == 42
    assert captured["commit_id"] == head
    in_hunk_findings = [f for f in captured["findings"] if f.get("in_hunk")]
    assert in_hunk_findings, "expected at least one in-hunk finding to post"
    # Every posted finding carries a stable dedup marker
    assert all(f["dedup_key"].startswith("sha256:") for f in in_hunk_findings)
