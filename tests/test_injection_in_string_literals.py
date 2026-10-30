"""SQL and command injection rules ignore code that is data inside a Python
string literal (#156)."""

from __future__ import annotations

from pathlib import Path

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
