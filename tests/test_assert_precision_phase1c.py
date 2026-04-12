"""Phase 1c regression tests — ASSERT_IN_PRODUCTION precision cleanup.

The legacy detector walked the GenericAST and flagged any node whose
``text`` contained the substring ``"assert "`` — container nodes
(module root, class, function) include their entire descendant text, so
a single real assert is enough to make multiple container nodes "match",
and a docstring or string literal that merely mentions the word
``assert`` produces a finding in a file that has zero real ``ast.Assert``
statements.

Dogfood evidence (``hefesto analyze hefesto/``) showed 31 findings on
files where ``ast.parse`` reports *zero* real ``ast.Assert`` nodes —
100% FP rate in the offending files.

The fix switches the Python path to ``ast.parse`` + ``isinstance(node,
ast.Assert)``, matching the approach already used for ``eval``/``exec``.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.core.language_detector import Language
from hefesto.core.parsers.parser_factory import ParserFactory


def _run(code: str, file_path: str = "prod/module.py"):
    parser = ParserFactory.get_parser(Language.PYTHON)
    tree = parser.parse(code, file_path)
    issues = SecurityAnalyzer().analyze(tree, file_path, code)
    return [i for i in issues if i.issue_type == AnalysisIssueType.ASSERT_IN_PRODUCTION]


def test_docstring_mentioning_assert_is_not_flagged() -> None:
    code = '''"""Module docstring mentioning assert statements.

The legacy detector flagged this file because the substring
``assert `` appears in the docstring above. After the fix it must not.
"""


def parse(text):
    message = "assert_mode is legacy — do not rely on it."
    return message
'''
    assert _run(code) == []


def test_string_literal_with_assert_substring_is_not_flagged() -> None:
    code = """def build():
    return "assert this is not flagged"
"""
    assert _run(code) == []


def test_comment_mentioning_assert_is_not_flagged() -> None:
    code = """def render():
    # This comment references 'assert ' as a Python keyword
    return None
"""
    assert _run(code) == []


def test_real_assert_statement_still_fires() -> None:
    code = """def configure(options):
    assert options is not None
    return options
"""
    issues = _run(code)
    assert len(issues) == 1
    assert issues[0].line == 2


def test_multiple_real_asserts_produce_one_finding_each() -> None:
    code = """def process(payload):
    assert payload is not None
    assert "id" in payload
    return payload["id"]
"""
    issues = _run(code)
    assert len(issues) == 2
    assert {i.line for i in issues} == {2, 3}


def test_test_files_are_still_skipped() -> None:
    """Existing behaviour: files whose path contains 'test' are skipped so
    pytest assertions don't generate noise. Pin that this still holds."""
    code = "def test_x():\n    assert 1 == 1\n"
    assert _run(code, file_path="tests/test_something.py") == []


def test_security_analyzer_own_file_is_now_silent() -> None:
    """Dogfood regression: before the fix, ``_check_assert_usage`` raised 16
    findings against its own source file (all FPs — zero real asserts).
    After the fix it must emit zero."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "hefesto" / "analyzers" / "security.py"
    code = target.read_text(encoding="utf-8")
    issues = _run(code, file_path=str(target))
    assert issues == []
