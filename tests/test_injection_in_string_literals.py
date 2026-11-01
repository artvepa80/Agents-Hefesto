"""SQL and command injection rules ignore code that is data inside a Python
string literal (#156)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from hefesto.analyzers.python_strings import inside_string, python_string_spans
from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.core.language_detector import Language
from hefesto.core.parsers.parser_factory import ParserFactory

INJECTION_TYPES = {AnalysisIssueType.SQL_INJECTION_RISK, AnalysisIssueType.COMMAND_INJECTION}
FIXTURE = Path(__file__).parent / "fixtures" / "sqli_safe_patterns" / "true_positive_concat.py"


def _run(code: str, file_path: str = "src/codegen.py"):
    tree = ParserFactory.get_parser(Language.PYTHON).parse(code, file_path)
    issues = SecurityAnalyzer().analyze(tree, file_path, code)
    return [i for i in issues if i.issue_type in INJECTION_TYPES]


def test_issue_repro_has_no_injection_findings() -> None:
    code = (
        'TEMPLATE = """\n'
        "def get_user(user_id):\n"
        '    query = "SELECT * FROM users WHERE id = " + user_id\n'
        "    return db.execute(query)\n"
        '"""\n'
        "SNIPPET = 'import os\\nos.system(\"ls \" + cmd)\\n'\n"
    )
    assert _run(code) == []


def test_command_sink_inside_single_line_string_is_skipped() -> None:
    code = "HELP = \"run os.system('ls ' + d) to list\"\n"
    assert _run(code) == []


def test_sql_in_template_is_skipped_even_with_real_sink_in_scope() -> None:
    code = (
        "def render(cur):\n"
        '    doc = """\n'
        '    q = "SELECT * FROM t WHERE id = " + uid\n'
        '    """\n'
        "    cur.execute('SELECT 1')\n"
        "    return doc\n"
    )
    assert _run(code) == []


def test_real_command_injection_still_fires() -> None:
    code = "import os\n\ndef ls(d):\n    os.system('ls ' + d)\n"
    issues = _run(code)
    assert [(i.issue_type, i.line) for i in issues] == [(AnalysisIssueType.COMMAND_INJECTION, 4)]


def test_real_sql_injection_after_a_template_still_fires() -> None:
    code = (
        'DOC = """os.system("x " + y)"""\n'
        "def get(cur, uid):\n"
        '    cur.execute("SELECT * FROM t WHERE id = " + uid)\n'
    )
    issues = _run(code)
    assert [(i.issue_type, i.line) for i in issues] == [(AnalysisIssueType.SQL_INJECTION_RISK, 3)]


def test_true_positive_fixture_still_fires() -> None:
    code = FIXTURE.read_text()
    lines = sorted(i.line for i in _run(code, "app/true_positive_concat.py"))
    assert lines == [10, 16, 23]


def test_unparsable_python_keeps_line_based_detection() -> None:
    code = "def f(d:\n    os.system('ls ' + d)\n"
    issues = SecurityAnalyzer()._check_command_injection(None, "broken.py", code)
    assert len(issues) == 1


def test_non_python_files_are_unchanged() -> None:
    code = "const s = \"os.system('ls ' + d)\";\n"
    issues = SecurityAnalyzer()._check_command_injection(None, "app.js", code)
    assert len(issues) == 1


def test_real_sink_after_a_quoted_sink_on_the_same_line_fires() -> None:
    code = "import os\n\ndef f(d):\n    print('os.system(x)'); os.system('ls ' + d)\n"
    assert [i.line for i in _run(code)] == [4]


# Sinks inside f-string replacement fields are code, not data.


def test_command_sink_in_fstring_replacement_field_fires() -> None:
    code = "import os\n\n\ndef show(fn):\n    return f\"{os.popen('cat ' + fn).read()}\"\n"
    assert [(i.issue_type, i.line) for i in _run(code)] == [
        (AnalysisIssueType.COMMAND_INJECTION, 5)
    ]


def test_command_sink_after_nested_quotes_in_fstring_fires() -> None:
    # Not valid syntax before 3.12: there the file is checked line by line.
    code = 'import os\n\n\ndef run(d, k):\n    print(f"{d["k"]} {os.system("ls " + k)}")\n'
    assert [(i.issue_type, i.line) for i in _run(code)] == [
        (AnalysisIssueType.COMMAND_INJECTION, 5)
    ]


def test_only_sql_sink_inside_fstring_replacement_field_fires() -> None:
    code = (
        "def get(cur, uid):\n"
        '    q = "SELECT * FROM users WHERE id=" + uid\n'
        '    print(f"{cur.execute(q)}")\n'
    )
    assert [(i.issue_type, i.line) for i in _run(code)] == [
        (AnalysisIssueType.SQL_INJECTION_RISK, 2)
    ]


@pytest.mark.skipif(sys.version_info < (3, 12), reason="f-string parts are tokens on 3.12+")
def test_sink_text_in_fstring_literal_part_is_skipped() -> None:
    code = "import os\n\n\ndef f(d):\n    HELP = f\"run os.system('ls ' + d) in {d}\"\n"
    assert _run(code) == []


@pytest.mark.parametrize(
    "literal",
    [
        "b\"os.system('ls ' + d)\"",
        "r\"os.system('ls ' + d)\"",
        "rb'os.system(\"ls \" + d)'",
        '"a \\"os.system(\'ls \' + d)\\" b"',
    ],
    ids=["bytes", "raw", "raw-bytes", "escaped-quote"],
)
def test_sink_inside_bytes_raw_or_escaped_literal_is_skipped(literal: str) -> None:
    code = f"import os\n\n\ndef f(d):\n    HELP = {literal}\n"
    assert _run(code) == []


def test_inside_string_is_not_linear_in_the_number_of_literals() -> None:
    n = 20_000
    spans = python_string_spans("".join(f"X{i} = 'value'\n" for i in range(n)))
    assert spans is not None and len(spans) == n
    t0 = time.perf_counter()
    hits = sum(inside_string(spans, row, 0) for row in range(1, n + 1))
    # A linear scan per call is ~2e8 comparisons here (tens of seconds).
    assert time.perf_counter() - t0 < 2.0
    assert hits == 0
    quote = len(f"X{n - 1} = ")
    assert inside_string(spans, n, quote + 1) and not inside_string(spans, n, quote)


def test_sql_check_on_many_literals_finishes_quickly() -> None:
    code = "def f(cur):\n    cur.execute('SELECT 1')\n" + "".join(
        f"X{i} = 'value'\n" for i in range(20_000)
    )
    t0 = time.perf_counter()
    issues = SecurityAnalyzer()._check_sql_injection(None, "big.py", code)
    # The quadratic version took about 30 s on this input.
    assert time.perf_counter() - t0 < 5.0
    assert issues == []
