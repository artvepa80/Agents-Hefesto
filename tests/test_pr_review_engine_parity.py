"""Regression tests for issue #152: pr-review must run the same analyzers as analyze."""

import subprocess
from pathlib import Path

from hefesto.cli.main import _setup_analyzer_engine
from hefesto.pr_review.orchestrator import _build_default_engine, run_pr_review


def _class_names(analyzers):
    return sorted(type(a).__name__ for a in analyzers)


def test_pr_review_engine_registers_same_analyzers_as_cli():
    cli_engine = _setup_analyzer_engine("LOW", quiet=True, json_mode=True)
    pr_engine = _build_default_engine()
    assert _class_names(pr_engine.analyzers) == _class_names(cli_engine.analyzers)
    assert _class_names(pr_engine._project_analyzers) == _class_names(cli_engine._project_analyzers)


def test_pr_review_engine_includes_narrow_semantic():
    assert "NarrowSemanticAnalyzer" in _class_names(_build_default_engine().analyzers)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_pr_review_reports_swallowed_exception_on_added_lines(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("x\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "app.py").write_text(
        "def load():\n"
        "    try:\n"
        "        return open('f').read()\n"
        "    except Exception:\n"
        "        pass\n"
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "add app")

    findings = run_pr_review(tmp_path, base="HEAD~1", head="HEAD").to_dict()["findings"]
    swallow = [f for f in findings if f["rule_id"] == "NS-SWALLOW-001"]
    assert len(swallow) == 1
    assert swallow[0]["file"] == "app.py"
    assert swallow[0]["line"] == 4
    assert swallow[0]["engine"] == "internal:narrow_semantic_v1"
