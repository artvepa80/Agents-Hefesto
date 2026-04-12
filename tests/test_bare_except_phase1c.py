"""Phase 1c regression tests — BARE_EXCEPT recall fix.

The legacy detector walked the GenericAST with ``NodeType.CATCH`` + a
regex on ``node.text`` and empirically emitted zero findings on real
bare-except Python code — the detector was dead code. Phase 1c closure
switches it to ``ast.ExceptHandler`` with ``node.type is None``.

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
    return [i for i in issues if i.issue_type == AnalysisIssueType.BARE_EXCEPT]


def test_bare_except_is_detected() -> None:
    code = """def f():
    try:
        x = 1
    except:
        pass
"""
    issues = _run(code)
    assert len(issues) == 1
    assert issues[0].line == 4


def test_typed_except_is_not_flagged() -> None:
    code = """def f():
    try:
        x = 1
    except ValueError:
        pass
"""
    assert _run(code) == []


def test_tuple_except_is_not_flagged() -> None:
    code = """def f():
    try:
        x = 1
    except (ValueError, TypeError):
        pass
"""
    assert _run(code) == []


def test_except_exception_is_not_flagged() -> None:
    code = """def f():
    try:
        x = 1
    except Exception:
        pass
"""
    assert _run(code) == []


def test_multiple_bare_excepts_each_emit_finding() -> None:
    code = """def a():
    try:
        x = 1
    except:
        pass

def b():
    try:
        y = 2
    except:
        pass
"""
    issues = _run(code)
    assert len(issues) == 2
    assert {i.line for i in issues} == {4, 10}


def test_docstring_mentioning_except_is_not_flagged() -> None:
    code = '''"""Module docstring discussing except: clauses."""


def render():
    return "do not use except: without a type"
'''
    assert _run(code) == []
