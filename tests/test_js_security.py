"""Experimental JavaScript and TypeScript XSS rules (JSX001, JSX002, JS002)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "js_security"

# (rule_id, line) for each fixture, analyzed as src/<name> so the tests/ skip
# does not hide the file. A line that is not listed must not be reported.
_EXPECTED = {
    "xss.jsx": {
        ("JSX001", 23),
        ("JSX001", 24),
        ("JSX001", 27),
        ("JSX001", 33),
        ("JSX001", 34),
        ("JSX001", 35),
        ("JSX001", 36),
        ("JSX002", 39),
        ("JSX002", 40),
        ("JSX002", 41),
        ("JSX002", 45),
    },
    "xss.tsx": {("JSX001", 9), ("JSX001", 11)},
    "dom.js": {
        ("JS002", 11),
        ("JS002", 15),
        ("JS002", 16),
        ("JS002", 17),
        ("JS002", 18),
        ("JS002", 21),
        ("JS002", 23),
    },
    "local_sanitize.jsx": {("JSX001", 9), ("JSX001", 10)},
    "require_sanitize.js": {("JS002", 10), ("JS002", 11)},
}


def _analyzer():
    from hefesto.analyzers.js_security import JsSecurityAnalyzer

    analyzer = JsSecurityAnalyzer()
    analyzer.js_rules = True
    return analyzer


def _issues(name: str, path: str | None = None):
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = (_FIXTURES / name).read_text(encoding="utf-8")
    language = "typescript" if name.endswith(".tsx") else "javascript"
    file_path = path or f"src/{name}"
    tree = TreeSitterParser(language).parse(code, file_path)
    return _analyzer().analyze(tree, file_path, code)


@pytest.mark.parametrize("name", sorted(_EXPECTED))
def test_fixture_reports_only_the_unsafe_sinks(name: str) -> None:
    issues = _issues(name)
    assert {(i.rule_id, i.line) for i in issues} == _EXPECTED[name]
    for issue in issues:
        assert issue.issue_type.value == "XSS_RISK"
        assert issue.severity.value == "HIGH"
        assert issue.metadata["cwe"] == "CWE-79"
        assert issue.engine == "internal:security"


def test_shelljs_exec_covers_every_import_form() -> None:
    """require, default import, ``import * as``, and ``import { exec }`` (plus aliases)."""
    from hefesto.analyzers.js_security import JsSecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = (_FIXTURES / "shell.ts").read_text(encoding="utf-8")
    tree = TreeSitterParser("typescript").parse(code, "src/shell.ts")
    issues = _analyzer().analyze(tree, "src/shell.ts", code)
    assert {(i.rule_id, i.line) for i in issues} == {
        ("JS001", 13),
        ("JS001", 14),
        ("JS001", 15),
        ("JS001", 16),
        ("JS001", 17),
        ("JS001", 18),
    }
    for issue in issues:
        assert issue.issue_type.value == "COMMAND_INJECTION"
        assert issue.severity.value == "HIGH"
        assert issue.metadata["cwe"] == "CWE-78"
    assert JsSecurityAnalyzer().analyze(tree, "src/shell.ts", code) == []


def test_child_process_exec_is_not_js001() -> None:
    """``child_process`` is the existing eval rule. JS001 is shelljs only."""
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = (
        'import { exec as childExec } from "child_process";\n'
        'const { exec: notShell } = require("child_process");\n'
        "export function ping(host: string) {\n"
        "  childExec(`ping -c 1 ${host}`);\n"
        "  notShell(`ping -c 1 ${host}`);\n"
        "}\n"
    )
    tree = TreeSitterParser("typescript").parse(code, "src/child.ts")
    assert _analyzer().analyze(tree, "src/child.ts", code) == []


def test_local_function_named_sanitize_is_still_reported() -> None:
    """The local name is not an allowlist. Only the import origin is."""
    issues = _issues("local_sanitize.jsx")
    assert {i.line for i in issues} == {9, 10}
    assert all(i.rule_id == "JSX001" for i in issues)


def test_flag_off_reports_nothing() -> None:
    from hefesto.analyzers.js_security import JsSecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = (_FIXTURES / "xss.jsx").read_text(encoding="utf-8")
    tree = TreeSitterParser("javascript").parse(code, "src/xss.jsx")
    assert JsSecurityAnalyzer().analyze(tree, "src/xss.jsx", code) == []


def test_test_paths_are_skipped() -> None:
    assert _issues("xss.jsx", "tests/fixtures/js_security/xss.jsx") == []
    assert _issues("dom.js", "examples/widget/dom.js") == []


def test_import_type_does_not_create_a_sanitizer() -> None:
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = (
        'import type { sanitize } from "sanitize-html";\n'
        "export function paint(el: HTMLElement, html: string) {\n"
        "  el.innerHTML = sanitize(html);\n"
        "}\n"
    )
    tree = TreeSitterParser("typescript").parse(code, "src/paint.ts")
    issues = _analyzer().analyze(tree, "src/paint.ts", code)
    assert [(i.rule_id, i.line) for i in issues] == [("JS002", 3)]


def test_other_languages_are_ignored() -> None:
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code = "def render(el, html):\n    el.innerHTML = html\n"
    tree = TreeSitterParser("python").parse(code, "src/render.py")
    assert _analyzer().analyze(tree, "src/render.py", code) == []


def test_lang_security_does_not_enable_js_rules() -> None:
    from hefesto.analyzers.js_security import JsSecurityAnalyzer
    from hefesto.core.analyzer_engine import AnalyzerEngine

    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    analyzer = JsSecurityAnalyzer()
    engine.register_analyzer(analyzer)
    engine.experimental = {"lang-security"}
    assert analyzer.js_rules is False
    engine.experimental = {"js-security"}
    assert analyzer.js_rules is True


def test_cli_flag_gates_sarif(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from hefesto.cli.main import cli

    src = tmp_path / "src"
    src.mkdir()
    (src / "View.jsx").write_text(
        (_FIXTURES / "local_sanitize.jsx").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    runner = CliRunner()
    off = runner.invoke(cli, ["analyze", str(src), "--output", "json", "--quiet"])
    assert off.exit_code == 0, off.output
    payload = json.loads(off.stdout)
    types = {issue["type"] for file in payload["files"] for issue in file["issues"]}
    assert "XSS_RISK" not in types

    other = runner.invoke(
        cli,
        ["analyze", str(src), "--output", "json", "--quiet", "--experimental", "lang-security"],
    )
    assert other.exit_code == 0, other.output
    other_types = {
        issue["type"] for file in json.loads(other.stdout)["files"] for issue in file["issues"]
    }
    assert "XSS_RISK" not in other_types

    on = runner.invoke(
        cli,
        [
            "analyze",
            str(src),
            "--output",
            "sarif",
            "--quiet",
            "--experimental",
            "js-security",
        ],
    )
    assert on.exit_code == 0, on.output
    sarif = json.loads(on.stdout)
    assert sarif["runs"][0]["properties"]["experimental"] == ["js-security"]
    rules = {rule["id"]: rule for rule in sarif["runs"][0]["tool"]["driver"]["rules"]}
    assert "JSX001" in rules
    tags = rules["JSX001"]["properties"]["tags"]
    assert "security" in tags
    assert "external/cwe/cwe-79" in tags
    assert rules["JSX001"]["properties"]["security-severity"] == "8.0"
