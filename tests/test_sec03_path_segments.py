"""SEC-03 regression tests: test/example paths are matched by segment, not substring.

Before the fix, ``SecurityAnalyzer`` skipped secret detection whenever the
file path contained the substring ``"test"`` or ``"example"`` anywhere, so
production files such as ``src/contest/config.py``, ``latest_settings.py`` or
anything analyzed under ``/tmp/pytest-of-<user>/`` were never scanned. The
assert detector had the same substring check for ``"test"``. There was also a
hardcoded exception that always scanned ``tests/fixtures/action/``.

Now a path is test/example code only when a directory segment is exactly
``test``/``tests``/``__tests__``/``example``/``examples`` or the file name
follows a test convention (``test_*``, ``*_test.*``, ``*.test.*``,
``*.spec.*``, ``conftest.py``) or is a ``*.example`` template. Absolute paths
are classified relative to the working directory when they are inside it.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from hefesto.analyzers.security import (
    SecurityAnalyzer,
    is_example_path,
    is_test_or_example_path,
    is_test_path,
)
from hefesto.core.analysis_models import AnalysisIssue, AnalysisIssueType
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.core.language_detector import Language
from hefesto.core.parsers.parser_factory import ParserFactory

# Built at runtime so the repo itself never contains a literal key-shaped string.
FAKE_AWS_KEY = "AKIA" + "Z" * 16
SECRET_CODE = f'AWS_ACCESS_KEY_ID = "{FAKE_AWS_KEY}"\n'


def _secrets(file_path: str, code: str = SECRET_CODE) -> List[AnalysisIssue]:
    issues = SecurityAnalyzer()._check_hardcoded_secrets(None, file_path, code)
    return [i for i in issues if i.issue_type == AnalysisIssueType.HARDCODED_SECRET]


def _asserts(file_path: str) -> List[AnalysisIssue]:
    code = "def f(x):\n    assert x > 0\n    return x\n"
    tree = ParserFactory.get_parser(Language.PYTHON).parse(code, file_path)
    issues = SecurityAnalyzer().analyze(tree, file_path, code)
    return [i for i in issues if i.issue_type == AnalysisIssueType.ASSERT_IN_PRODUCTION]


# --- production paths that merely contain "test"/"example" are scanned -------


@pytest.mark.parametrize(
    "file_path",
    [
        "src/contest/config.py",
        "contest/config.py",
        "latest_settings.py",
        "latest_app/settings.py",
        "app/attestation.py",
        "src/protest_handler.py",
        "testing_utils/config.py",
        "src/counterexample.py",
        "examples_lib/config.py",
        "fixtures/config.py",
        "app/fixtures/seed.py",
        "C:\\repo\\contest\\config.py",
    ],
)
def test_secret_detected_when_test_or_example_is_only_a_substring(file_path: str) -> None:
    assert not is_test_or_example_path(file_path)
    assert len(_secrets(file_path)) == 1, file_path


def test_secret_detected_under_pytest_tmp_path(tmp_path: Path) -> None:
    """``/tmp/pytest-of-<user>/pytest-N/test_x0/...`` is not a test directory."""
    target = tmp_path / "app" / "config.py"
    target.parent.mkdir(parents=True)
    target.write_text(SECRET_CODE, encoding="utf-8")

    assert "pytest" in str(target)
    assert len(_secrets(str(target))) == 1


def test_parent_directories_outside_the_project_do_not_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo checked out under ``.../tests/myrepo`` is still production code."""
    repo = tmp_path / "tests" / "myrepo"
    target = repo / "src" / "config.py"
    target.parent.mkdir(parents=True)
    target.write_text(SECRET_CODE, encoding="utf-8")
    monkeypatch.chdir(repo)

    assert not is_test_path(str(target))
    assert len(_secrets(str(target))) == 1

    # The same layout inside the project is test code.
    inner = repo / "tests" / "test_config.py"
    assert is_test_path(str(inner))


# --- real test and example code is still skipped ----------------------------


@pytest.mark.parametrize(
    "file_path",
    [
        "tests/test_x.py",
        "tests/helpers.py",
        "tests/fixtures/action/critical_secret.py",
        "test/settings.py",
        "pkg/tests/conftest.py",
        "web/__tests__/api.js",
        "app/test_config.py",
        "app/config_test.py",
        "pkg/server_test.go",
        "web/api.test.ts",
        "web/api.spec.js",
        "conftest.py",
        "Tests/Settings.py",
        "tests\\test_x.py",
    ],
)
def test_secret_skipped_in_test_code(file_path: str) -> None:
    assert is_test_path(file_path)
    assert _secrets(file_path) == []


@pytest.mark.parametrize(
    "file_path",
    ["examples/demo.py", "docs/example/settings.py", ".env.example", "config/app.py.example"],
)
def test_secret_skipped_in_example_code(file_path: str) -> None:
    assert is_example_path(file_path)
    assert not is_test_path(file_path)
    assert _secrets(file_path) == []


def test_no_hardcoded_exception_for_action_fixtures() -> None:
    """``tests/fixtures/action/`` is test code like any other ``tests/`` path."""
    assert _secrets("tests/fixtures/action/critical_secret.py") == []


# --- assert detector uses the same segment rule (tests only) ----------------


@pytest.mark.parametrize("file_path", ["contest/app.py", "latest_app/core.py", "src/attest.py"])
def test_assert_flagged_in_production_paths_containing_test(file_path: str) -> None:
    assert len(_asserts(file_path)) == 1


@pytest.mark.parametrize("file_path", ["tests/test_app.py", "app/test_core.py", "conftest.py"])
def test_assert_skipped_in_test_code(file_path: str) -> None:
    assert _asserts(file_path) == []


def test_assert_still_flagged_in_examples() -> None:
    """Only the secret detector skips examples; assert behavior there is unchanged."""
    assert len(_asserts("examples/demo.py")) == 1


# --- end to end through the engine ------------------------------------------


def test_engine_reports_secret_in_contest_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src" / "contest").mkdir(parents=True)
    (tmp_path / "src" / "contest" / "config.py").write_text(SECRET_CODE, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(SECRET_CODE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    engine.register_analyzer(SecurityAnalyzer())
    report = engine.analyze_path(str(tmp_path))
    secret_files = {
        Path(i.file_path).relative_to(tmp_path.resolve()).as_posix()
        for i in report.get_all_issues()
        if i.issue_type == AnalysisIssueType.HARDCODED_SECRET
    }
    assert secret_files == {"src/contest/config.py"}
