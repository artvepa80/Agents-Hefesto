"""Phase 1c regression tests — SQL_INJECTION_RISK precision cleanup.

These tests pin the production false-positive class that motivated Phase 1c:
DB-API parameterized queries flagged as SQL injection because the detector
treated ``%s`` / ``%(name)s`` placeholders as Python ``%`` operator usage.

Each fixture lives as a standalone file under
``tests/fixtures/sqli_safe_patterns/`` so it can be inspected by hand and
re-run with any future detector. The tests here assert before/after recall
and precision on that fixture corpus.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import AnalysisIssue, AnalysisIssueType
from hefesto.core.language_detector import Language
from hefesto.core.parsers.parser_factory import ParserFactory

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sqli_safe_patterns"

SAFE_FIXTURES = [
    "psycopg2_percent_s.py",
    "sqlite3_qmark.py",
    "sqlalchemy_text_bind.py",
    "django_raw_params.py",
]
TRUE_POSITIVE_FIXTURE = "true_positive_concat.py"
EXPECTED_TP_COUNT = 3


def _run(fixture: str) -> List[AnalysisIssue]:
    path = FIXTURE_DIR / fixture
    code = path.read_text()
    parser = ParserFactory.get_parser(Language.PYTHON)
    tree = parser.parse(code, str(path))
    issues = SecurityAnalyzer().analyze(tree, str(path), code)
    return [i for i in issues if i.issue_type == AnalysisIssueType.SQL_INJECTION_RISK]


def test_psycopg2_percent_s_is_not_flagged() -> None:
    """psycopg2 ``%s`` is a server-side placeholder, not Python interpolation."""
    assert _run("psycopg2_percent_s.py") == []


def test_sqlite3_qmark_is_not_flagged() -> None:
    """sqlite3 ``?`` placeholders never triggered even in the legacy detector."""
    assert _run("sqlite3_qmark.py") == []


def test_sqlalchemy_text_bind_is_not_flagged() -> None:
    """SQLAlchemy ``text('SELECT ... :param')`` with bind parameters is safe."""
    assert _run("sqlalchemy_text_bind.py") == []


def test_django_raw_params_is_not_flagged() -> None:
    """Django ``Model.objects.raw(sql, [param])`` is a parameterized call."""
    assert _run("django_raw_params.py") == []


def test_true_positive_concat_still_fires() -> None:
    """The precision fix must not regress recall on real injection patterns.

    The TP fixture covers the three canonical dangerous patterns:
    - f-string interpolation of user input into SQL
    - Python ``%`` operator with user input
    - ``+`` concatenation of user input
    """
    issues = _run(TRUE_POSITIVE_FIXTURE)
    assert len(issues) == EXPECTED_TP_COUNT, f"expected {EXPECTED_TP_COUNT} TPs, got {len(issues)}"


def test_full_corpus_precision_is_100_percent() -> None:
    """Corpus-level assertion: every safe fixture is silent and every TP fires."""
    fp_count = sum(len(_run(f)) for f in SAFE_FIXTURES)
    tp_count = len(_run(TRUE_POSITIVE_FIXTURE))
    assert fp_count == 0, f"{fp_count} false positives across safe fixtures"
    assert tp_count == EXPECTED_TP_COUNT


# ---------------------------------------------------------------------------
# Recall gap — documented conservative trade-off
# ---------------------------------------------------------------------------
#
# ``_PY_PERCENT_OPERATOR`` distinguishes the Python ``%`` operator from
# DB-API placeholders by requiring that the char right after ``%`` is NOT
# a printf format-spec character followed by end-of-spec (``\W`` or
# end-of-line). The consequence is a known false-negative class:
#
#     q = "SELECT * FROM t WHERE id = %s" % i
#
# If the variable is a *single-letter* name that is ALSO a printf format
# specifier (``s d i o u x X e E f F g G c r p %`` — 17 chars total),
# and it appears at end-of-line, the regex classifies it as a placeholder
# and the line does NOT fire. Multi-character names (``uid``, ``name``,
# ``row``, ``rows[0]``, ``self.id``) DO fire because the second char
# breaks the end-of-spec pattern.
#
# This is a deliberate conservative trade-off: tightening the distinction
# the "right way" requires tokenizing the line or AST-parsing the module
# to find ``BinOp(op=Mod, left=Constant(str))``. The regex approach
# prioritizes eliminating the 100% FP class from DB-API placeholders over
# catching a rare single-letter-variable pattern. Documented as Phase 1c
# debt — the proper fix is an AST-based binop walk on Python files.
# ---------------------------------------------------------------------------


FORMAT_SPEC_CHARS = "sdiouxXeEfFgGcrp%"


def test_recall_gap_single_char_format_spec_variable_not_flagged() -> None:
    """Pin the conservative FN class introduced by the Phase 1c regex.

    All 17 printf format-spec chars become false negatives when used as
    a 1-char variable name at end-of-line. Multi-char variables ARE
    caught. This test will start failing if someone tightens the rule
    (e.g. via AST binop walk), which is the desired signal — the
    tightening should be deliberate, not accidental.
    """
    import ast

    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.analysis_models import AnalysisIssueType
    from hefesto.core.language_detector import Language
    from hefesto.core.parsers.parser_factory import ParserFactory

    parser = ParserFactory.get_parser(Language.PYTHON)
    sa = SecurityAnalyzer()

    for char in FORMAT_SPEC_CHARS:
        # Need a distinct name to avoid shadowing; the var happens to be
        # a 1-char identifier that the format-spec filter treats as a spec.
        if char == "%":
            # '%' cannot be a Python identifier; skip as N/A for FN class
            continue
        code = (
            "def q(cur, " + char + "):\n"
            f'    cur.execute("SELECT * FROM t WHERE id = %s" % {char})\n'
        )
        # Sanity check: this IS a real Python % BinOp
        py_tree = ast.parse(code)
        binops = [
            n for n in ast.walk(py_tree) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod)
        ]
        assert binops, f"fixture for {char!r} is not actually a Mod BinOp"

        tree = parser.parse(code, "prod.py")
        issues = [
            i
            for i in sa.analyze(tree, "prod.py", code)
            if i.issue_type == AnalysisIssueType.SQL_INJECTION_RISK
        ]
        assert issues == [], (
            f"unexpected detection for 1-char format-spec var {char!r}: "
            f"conservative FN class is documented and should not fire"
        )


def test_recall_multi_char_variable_does_fire() -> None:
    """Symmetry for the recall gap: multi-char variables (even those
    starting with a format-spec char like ``self``, ``rows``, ``uid``)
    DO fire, because the char after the first is a word char, breaking
    the end-of-spec lookahead."""
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.analysis_models import AnalysisIssueType
    from hefesto.core.language_detector import Language
    from hefesto.core.parsers.parser_factory import ParserFactory

    parser = ParserFactory.get_parser(Language.PYTHON)
    sa = SecurityAnalyzer()

    for varname in ("uid", "rows", "self.id", "ctx"):
        code = (
            "def q(cur, arg):\n" f'    cur.execute("SELECT * FROM t WHERE id = %s" % {varname})\n'
        )
        tree = parser.parse(code, "prod.py")
        issues = [
            i
            for i in sa.analyze(tree, "prod.py", code)
            if i.issue_type == AnalysisIssueType.SQL_INJECTION_RISK
        ]
        assert issues, f"multi-char var {varname!r} should be flagged (real % BinOp)"


# ---------------------------------------------------------------------------
# Unit test directly over _PY_PERCENT_OPERATOR.search to catch regex drift
# without needing the full analyzer stack.
# ---------------------------------------------------------------------------


def test_py_percent_operator_regex_table() -> None:
    """Match/no-match table for the core distinguishing regex.

    Documents the exact contract so future refactors can't silently
    change semantics. Cases are (line, should_match) tuples.
    """
    from hefesto.analyzers.security import _PY_PERCENT_OPERATOR

    cases = [
        # --- MATCH: real Python % operator with a multi-char expression ---
        ('q = "..." % rows[0]', True),
        ('q = "..." % uid', True),
        ('q = "..." % name', True),
        ('q = "..." % self.name', True),
        ('q = "..." % (1, 2)', True),
        ('q = "..." % {"k": v}', True),
        ("q = '...' % rows", True),
        # --- NO MATCH: DB-API placeholders inside string literals ---
        ('cur.execute("SELECT * FROM t WHERE id = %s", (user_id,))', False),
        ('cur.execute("SELECT ... BETWEEN %s AND %s", (a, b))', False),
        ('cur.execute("... WHERE id = %(uid)s", {"uid": u})', False),
        ("cur.execute('DELETE FROM t WHERE id = ?', (x,))", False),
        ('db.execute(text("SELECT WHERE id = :user_id"), {"user_id": u})', False),
        # --- NO MATCH: format-spec char followed by end-of-spec (recall gap) ---
        ('q = "..." % s', False),  # 1-char var 's'
        ('q = "..." % i', False),  # 1-char var 'i'
        ('q = "..." % x', False),  # 1-char var 'x'
    ]
    for line, expected in cases:
        actual = bool(_PY_PERCENT_OPERATOR.search(line))
        assert actual == expected, f"regex({line!r}) = {actual}, expected {expected}"
