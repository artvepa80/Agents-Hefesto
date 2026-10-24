"""Function-level findings in ``hefesto pr-review``.

Complexity, long-function and deep-nesting findings are reported on the
``def`` line. Before this fix the default (changed-lines) filter compared
only that line with the diff, so a PR that changed a function's body but
not its ``def`` line never surfaced the finding. PR #146 hit this: the
complexity of ``load_upsell_state`` went from 10 (MEDIUM) to 11 (HIGH)
through body edits and ``pr-review`` reported nothing.

Invariants pinned here:

- I1: a function-level finding is ``in_hunk`` when an added line falls
  inside the function's span (``line`` .. ``end_line``).
- I2: ``line`` stays the ``def`` line, so ``dedup_key`` does not change.
- I3: ``anchor_line`` is an added line inside the span (the first one),
  or ``line`` itself for line-level findings; ``None`` when not in a hunk.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.pr_review.dedup import compute_dedup_key
from hefesto.pr_review.orchestrator import run_pr_review
from hefesto.pr_review.post import post_findings

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    "HOME": "/tmp",
}


def _git(args: List[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True, env=_GIT_ENV
    ).stdout.strip()


def _commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content)
    _git(["add", name], repo)
    _git(["commit", "-q", "-m", f"edit {name}"], repo)
    return _git(["rev-parse", "HEAD"], repo)


def _repo(tmp_path: Path, name: str, content: str) -> str:
    _git(["init", "-q"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    return _commit(tmp_path, name, content)


@pytest.fixture
def engine() -> AnalyzerEngine:
    from hefesto.analyzers import CodeSmellAnalyzer, ComplexityAnalyzer, SecurityAnalyzer

    eng = AnalyzerEngine(severity_threshold="LOW")
    eng.register_analyzer(ComplexityAnalyzer())
    eng.register_analyzer(CodeSmellAnalyzer())
    eng.register_analyzer(SecurityAnalyzer())
    return eng


def _found(
    repo: Path, base: str, head: str, eng: AnalyzerEngine, kind: str
) -> List[Dict[str, Any]]:
    """Default-mode findings of one type."""
    return _of(run_pr_review(repo, base=base, head=head, engine=eng).findings, kind)


def _of(findings: List[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    return [f for f in findings if f["type"] == kind]


# Shape of PR #146's ``load_upsell_state``: the def line is untouched, a
# body edit adds one decision point and complexity goes 10 -> 11.
_HEADER = "import json\n\n\n"
_DEF = "def load_state(path, loaded):\n"
_BODY_10 = (
    "    if not path:\n"  # 1 (+1 base = 2)
    "        return None\n"
    "    if not isinstance(loaded, dict):\n"  # 3
    "        return None\n"
    "    last = loaded.get('last')\n"
    "    if last is not None and isinstance(last, bool):\n"  # 4
    "        return None\n"
    "    counts = loaded.get('counts', {})\n"
    "    if not isinstance(counts, dict):\n"  # 5
    "        return None\n"
    "    clean = {}\n"
    "    for key, value in counts.items():\n"  # 6
    "        if not isinstance(key, str):\n"  # 7
    "            return None\n"
    "        if value < 0:\n"  # 8
    "            return None\n"
    "        clean[key] = value\n"
    "    total = loaded.get('total', 0)\n"
    "    if total < 0:\n"  # 9
    "        return None\n"
    "    if total > 10**9:\n"  # 10
    "        return None\n"
)
_TAIL_BASE = "    return {'last': last, 'counts': clean, 'total': total}\n"
_TAIL_HEAD = (
    "    times = loaded.get('times', {})\n"
    "    if not isinstance(times, dict):\n"  # 11 -> HIGH
    "        return None\n"
    "    return {'last': last, 'counts': clean, 'total': total, 'times': times}\n"
)
_DEF_LINE = _HEADER.count("\n") + 1  # 4
_FIRST_ADDED = _DEF_LINE + 1 + _BODY_10.count("\n")  # first line of _TAIL_HEAD


def test_body_edit_surfaces_new_high_complexity_like_pr_146(
    tmp_path: Path, engine: AnalyzerEngine
) -> None:
    base = _repo(tmp_path, "growth.py", _HEADER + _DEF + _BODY_10 + _TAIL_BASE)
    head = _commit(tmp_path, "growth.py", _HEADER + _DEF + _BODY_10 + _TAIL_HEAD)

    result = run_pr_review(tmp_path, base=base, head=head, engine=engine)

    high = _of(result.findings, "HIGH_COMPLEXITY")
    assert len(high) == 1, result.findings
    finding = high[0]
    assert finding["severity"] == "HIGH"
    assert finding["message"] == "Cyclomatic complexity too high (11)"
    assert finding["in_hunk"] is True
    assert finding["line"] == _DEF_LINE  # I2: still the def line
    assert finding["anchor_line"] == _FIRST_ADDED  # I3: first added line in the span


def test_dedup_key_stays_on_def_line(tmp_path: Path, engine: AnalyzerEngine) -> None:
    base = _repo(tmp_path, "growth.py", _HEADER + _DEF + _BODY_10 + _TAIL_BASE)
    head = _commit(tmp_path, "growth.py", _HEADER + _DEF + _BODY_10 + _TAIL_HEAD)
    finding = _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY")[0]
    issue = AnalysisIssue(
        file_path=str(tmp_path / "growth.py"),
        line=_DEF_LINE,
        column=0,
        issue_type=AnalysisIssueType.HIGH_COMPLEXITY,
        severity=AnalysisIssueSeverity.HIGH,
        message="Cyclomatic complexity too high (11)",
    )
    assert finding["dedup_key"] == compute_dedup_key(issue, relative_path="growth.py")


def test_edit_outside_function_stays_filtered(tmp_path: Path, engine: AnalyzerEngine) -> None:
    content = _HEADER + _DEF + _BODY_10 + _TAIL_HEAD
    base = _repo(tmp_path, "growth.py", content)
    head = _commit(tmp_path, "growth.py", content + "\n\ndef helper():\n    return 42\n")

    result = run_pr_review(tmp_path, base=base, head=head, engine=engine)
    assert _of(result.findings, "HIGH_COMPLEXITY") == []

    strict = run_pr_review(tmp_path, base=base, head=head, strict=True, engine=engine)
    high = _of(strict.findings, "HIGH_COMPLEXITY")
    assert len(high) == 1
    assert high[0]["in_hunk"] is False
    assert high[0]["anchor_line"] is None


def test_edit_above_function_does_not_count(tmp_path: Path, engine: AnalyzerEngine) -> None:
    body = _DEF + _BODY_10 + _TAIL_HEAD
    base = _repo(tmp_path, "growth.py", _HEADER + body)
    head = _commit(tmp_path, "growth.py", "import json\nimport os\n\n\n" + body)
    assert _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY") == []


def test_deletion_only_hunk_inside_body_does_not_count(
    tmp_path: Path, engine: AnalyzerEngine
) -> None:
    """A pure deletion has no new-side line to anchor on, and removing
    lines cannot raise complexity, length or nesting."""
    padded = _BODY_10.replace("    clean = {}\n", "    clean = {}\n    unused = 1\n")
    base = _repo(tmp_path, "growth.py", _HEADER + _DEF + padded + _TAIL_HEAD)
    head = _commit(tmp_path, "growth.py", _HEADER + _DEF + _BODY_10 + _TAIL_HEAD)
    assert _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY") == []


def test_signature_only_edit_counts(tmp_path: Path, engine: AnalyzerEngine) -> None:
    multi_def = "def load_state(\n    path,\n    loaded,\n):\n"
    base = _repo(tmp_path, "growth.py", _HEADER + multi_def + _BODY_10 + _TAIL_HEAD)
    head = _commit(
        tmp_path,
        "growth.py",
        _HEADER + multi_def.replace("    loaded,\n", "    loaded=None,\n") + _BODY_10 + _TAIL_HEAD,
    )
    high = _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY")
    assert len(high) == 1
    assert high[0]["line"] == _DEF_LINE
    assert high[0]["anchor_line"] == _DEF_LINE + 2


def test_decorator_only_edit_does_not_count(tmp_path: Path, engine: AnalyzerEngine) -> None:
    """Python's AST starts a decorated function at ``def``, not at the
    decorator. Decorators do not change complexity, length or nesting,
    so a decorator-only edit does not surface the function's findings."""
    base = _repo(tmp_path, "growth.py", _HEADER + "@staticmethod\n" + _DEF + _BODY_10 + _TAIL_HEAD)
    head = _commit(tmp_path, "growth.py", _HEADER + "@classmethod\n" + _DEF + _BODY_10 + _TAIL_HEAD)
    assert _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY") == []


def test_decorated_function_body_edit_counts(tmp_path: Path, engine: AnalyzerEngine) -> None:
    base = _repo(tmp_path, "growth.py", _HEADER + "@cache\n" + _DEF + _BODY_10 + _TAIL_BASE)
    head = _commit(tmp_path, "growth.py", _HEADER + "@cache\n" + _DEF + _BODY_10 + _TAIL_HEAD)
    high = _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY")
    assert len(high) == 1
    assert high[0]["line"] == _DEF_LINE + 1
    assert high[0]["anchor_line"] == _FIRST_ADDED + 1


def test_nested_function_edit_surfaces_outer_and_inner(
    tmp_path: Path, engine: AnalyzerEngine
) -> None:
    """The outer function's complexity counts the inner function's
    branches, so an edit inside the inner body is inside both spans."""
    inner_base = "    def inner(x):\n" + "".join(
        f"        if x == {i}:\n            return {i}\n" for i in range(10)
    )
    inner_head = inner_base + "        if x == 99:\n            return 99\n"
    outer = "def outer(x):\n"
    tail = "        return -1\n    return inner(x)\n"
    base = _repo(tmp_path, "nest.py", outer + inner_base + tail)
    head = _commit(tmp_path, "nest.py", outer + inner_head + tail)

    found = _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY")
    lines = sorted(f["line"] for f in found)
    assert lines == [1, 2], found
    assert all(f["in_hunk"] for f in found)
    added = 2 + 2 * 10 + 1
    assert {f["anchor_line"] for f in found} == {added}


def test_outer_edit_outside_inner_span_does_not_surface_inner(
    tmp_path: Path, engine: AnalyzerEngine
) -> None:
    inner = "    def inner(x):\n" + "".join(
        f"        if x == {i}:\n            return {i}\n" for i in range(11)
    )
    outer = "def outer(x):\n"
    base = _repo(tmp_path, "nest.py", outer + inner + "    return inner(x)\n")
    head = _commit(tmp_path, "nest.py", outer + inner + "    return inner(x) + 1\n")
    found = _found(tmp_path, base, head, engine, "HIGH_COMPLEXITY")
    assert [f["line"] for f in found] == [1]


def test_long_function_body_edit_counts(tmp_path: Path, engine: AnalyzerEngine) -> None:
    body = "".join(f"    v{i} = {i}\n" for i in range(55))
    base = _repo(tmp_path, "long.py", "def long_one():\n" + body + "    return 0\n")
    head = _commit(tmp_path, "long.py", "def long_one():\n" + body + "    return 1\n")
    found = _found(tmp_path, base, head, engine, "LONG_FUNCTION")
    assert len(found) == 1
    assert found[0]["line"] == 1
    assert found[0]["anchor_line"] == 57


def test_deep_nesting_body_edit_counts(tmp_path: Path, engine: AnalyzerEngine) -> None:
    nested = (
        "def deep(a):\n"
        "    if a:\n"
        "        for b in a:\n"
        "            if b:\n"
        "                for c in b:\n"
        "                    if c:\n"
        "                        return c\n"
        "    return None\n"
    )
    base = _repo(tmp_path, "deep.py", nested)
    head = _commit(tmp_path, "deep.py", nested.replace("return c\n", "return c + 1\n"))
    found = _found(tmp_path, base, head, engine, "DEEP_NESTING")
    assert len(found) == 1
    assert found[0]["in_hunk"] is True
    assert found[0]["anchor_line"] == 7


def test_line_level_finding_anchor_is_its_own_line(tmp_path: Path, engine: AnalyzerEngine) -> None:
    base = _repo(tmp_path, "app.py", "def ok():\n    return 1\n")
    head = _commit(
        tmp_path,
        "app.py",
        "def ok():\n    return 1\n\n\ndef fetch(cur, uid):\n"
        # The fixture's query line is split in two literals so that this
        # test file itself is not reported as SQL injection.
        "    cur.execute('SELECT * FROM t WHERE id = '"
        # (second half of the same fixture line)
        " + str(uid))\n",
    )
    sqli = _found(tmp_path, base, head, engine, "SQL_INJECTION_RISK")
    assert sqli and all(f["anchor_line"] == f["line"] == 6 for f in sqli)


# ---------------------------------------------------------------- unit


def _issue(line: int, end_line: Any = None) -> AnalysisIssue:
    return AnalysisIssue(
        file_path="f.py",
        line=line,
        column=0,
        issue_type=AnalysisIssueType.HIGH_COMPLEXITY,
        severity=AnalysisIssueSeverity.HIGH,
        message="m",
        end_line=end_line,
    )


@pytest.mark.parametrize(
    ("line", "end_line", "changed", "expected"),
    [
        (10, None, {10}, 10),  # line-level hit
        (10, None, {11}, None),  # line-level miss: no span
        (10, 20, {15, 18}, 15),  # body overlap: first added line
        (10, 20, {10, 15}, 10),  # def line changed: anchor on def line
        (10, 20, {20}, 20),  # last line of the span is inside
        (10, 20, {9, 21}, None),  # just outside both ends
        (10, 20, set(), None),  # nothing added (deletions only)
        (10, 5, {7}, None),  # bogus span (end before start) is ignored
    ],
)
def test_hunk_anchor(line: int, end_line: Any, changed: set, expected: Any) -> None:
    from hefesto.pr_review.orchestrator import _hunk_anchor

    assert _hunk_anchor(_issue(line, end_line), changed) == expected


def test_post_uses_anchor_line(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[List[str]] = []

    class _Done:
        returncode = 0
        stderr = ""

    def _fake_run(args: List[str], **_: Any) -> _Done:
        calls.append(args)
        return _Done()

    monkeypatch.setattr("hefesto.pr_review.post.subprocess.run", _fake_run)
    finding = {
        "file": "growth.py",
        "line": 4,
        "anchor_line": 27,
        "in_hunk": True,
        "dedup_key": "sha256:00",
        "severity": "HIGH",
        "type": "HIGH_COMPLEXITY",
        "message": "Cyclomatic complexity too high (11)",
    }
    legacy = {k: v for k, v in finding.items() if k != "anchor_line"}
    counts = post_findings(repo="o/r", pr_number=1, commit_id="abc", findings=[finding, legacy])
    assert counts == {"posted": 2, "failed": 0, "skipped_no_hunk": 0}
    assert "line=27" in calls[0]
    assert "line=4" in calls[1]  # older JSON without anchor_line still posts on line
