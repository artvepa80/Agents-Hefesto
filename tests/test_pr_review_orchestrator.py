"""Canary / integration tests for ``hefesto/pr_review/orchestrator.py``.

Each test sets up a real temporary git repo, commits a baseline, makes
a scoped edit, and runs ``run_pr_review`` against the actual ``git
diff`` output. These cover the end-to-end slice: diff retrieval → parse
→ scoped analysis → filter → JSON. Unit tests for each layer live in
the sibling files; this file owns the wiring invariants.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

import pytest

from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.pr_review.orchestrator import run_pr_review


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


def _init_repo_with_baseline(tmp_path: Path) -> str:
    _git(["init", "-q"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "clean.py").write_text("def ok():\n    return 1\n")
    _git(["add", "clean.py"], tmp_path)
    _git(["commit", "-q", "-m", "baseline"], tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return head


def _edit_and_commit(tmp_path: Path, path: str, content: str) -> str:
    (tmp_path / path).write_text(content)
    _git(["add", path], tmp_path)
    _git(["commit", "-q", "-m", f"edit {path}"], tmp_path)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def minimal_engine() -> AnalyzerEngine:
    """Engine wired with just SecurityAnalyzer — fast and deterministic."""
    from hefesto.analyzers import SecurityAnalyzer

    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.register_analyzer(SecurityAnalyzer())
    return engine


def test_clean_edit_produces_no_findings(tmp_path: Path, minimal_engine: AnalyzerEngine) -> None:
    base = _init_repo_with_baseline(tmp_path)
    head = _edit_and_commit(
        tmp_path,
        "clean.py",
        "def ok():\n    return 1\n\n\ndef also_ok():\n    return 2\n",
    )
    result = run_pr_review(tmp_path, base=base, head=head, engine=minimal_engine)
    assert result.changed_files == ["clean.py"]
    assert result.findings == []
    assert result.head_sha == head
    assert result.base_sha == base


def test_injected_sqli_on_new_line_is_flagged_in_hunk(
    tmp_path: Path, minimal_engine: AnalyzerEngine
) -> None:
    base = _init_repo_with_baseline(tmp_path)
    # Introduce a real SQL injection — + concat with user input inside
    # a function that has an execute sink.
    new_body = (
        "def ok():\n"
        "    return 1\n"
        "\n"
        "def fetch(cur, user_id):\n"
        "    cur.execute('SELECT * FROM t WHERE id = ' + str(user_id))\n"
    )
    head = _edit_and_commit(tmp_path, "clean.py", new_body)

    result = run_pr_review(tmp_path, base=base, head=head, engine=minimal_engine)

    sqli = [f for f in result.findings if f["type"] == "SQL_INJECTION_RISK"]
    assert len(sqli) >= 1
    assert sqli[0]["in_hunk"] is True
    assert sqli[0]["file"] == "clean.py"
    assert sqli[0]["dedup_key"].startswith("sha256:")


def test_finding_outside_hunk_is_filtered_by_default(
    tmp_path: Path, minimal_engine: AnalyzerEngine
) -> None:
    """If the SQLi predates the PR and the PR edits a different line,
    the default (non-strict) mode must NOT surface the legacy finding."""
    # Baseline already has a SQLi on line 2
    _git(["init", "-q"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "app.py").write_text(
        "def fetch(cur, user_id):\n"
        "    cur.execute('SELECT * FROM t WHERE id = ' + str(user_id))\n"
    )
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "baseline with sqli"], tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # PR only appends a harmless helper far away from the SQLi line.
    new_body = (
        "def fetch(cur, user_id):\n"
        "    cur.execute('SELECT * FROM t WHERE id = ' + str(user_id))\n"
        "\n"
        "\n"
        "def helper():\n"
        "    return 42\n"
    )
    head = _edit_and_commit(tmp_path, "app.py", new_body)

    result = run_pr_review(tmp_path, base=base, head=head, engine=minimal_engine)

    # Default mode: the pre-existing SQLi is NOT in the hunk, so silent.
    assert result.findings == []


def test_strict_mode_surfaces_findings_outside_hunks(
    tmp_path: Path, minimal_engine: AnalyzerEngine
) -> None:
    """Same setup as the previous test, but strict mode reveals the
    file-level pre-existing SQLi with ``in_hunk=False``."""
    _git(["init", "-q"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "app.py").write_text(
        "def fetch(cur, user_id):\n"
        "    cur.execute('SELECT * FROM t WHERE id = ' + str(user_id))\n"
    )
    _git(["add", "app.py"], tmp_path)
    _git(["commit", "-q", "-m", "baseline with sqli"], tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    head = _edit_and_commit(
        tmp_path,
        "app.py",
        (
            "def fetch(cur, user_id):\n"
            "    cur.execute('SELECT * FROM t WHERE id = ' + str(user_id))\n"
            "\n"
            "\n"
            "def helper():\n"
            "    return 42\n"
        ),
    )

    result = run_pr_review(tmp_path, base=base, head=head, strict=True, engine=minimal_engine)
    sqli = [f for f in result.findings if f["type"] == "SQL_INJECTION_RISK"]
    assert len(sqli) == 1
    assert sqli[0]["in_hunk"] is False


def test_findings_outside_diff_scope_are_ignored(
    tmp_path: Path, minimal_engine: AnalyzerEngine
) -> None:
    """Sanity: a file untouched by the diff must not appear in findings
    even if the engine discovers issues in it."""
    _git(["init", "-q"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "untouched.py").write_text(
        "def fetch(cur, user_id):\n"
        "    cur.execute('SELECT * FROM t WHERE id = ' + str(user_id))\n"
    )
    (tmp_path / "touched.py").write_text("def ok():\n    return 1\n")
    _git(["add", "untouched.py", "touched.py"], tmp_path)
    _git(["commit", "-q", "-m", "baseline"], tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    head = _edit_and_commit(
        tmp_path,
        "touched.py",
        "def ok():\n    return 1\n\n\ndef new_fn():\n    return 2\n",
    )
    result = run_pr_review(tmp_path, base=base, head=head, engine=minimal_engine)
    assert result.changed_files == ["touched.py"]
    assert all(f["file"] == "touched.py" for f in result.findings)
