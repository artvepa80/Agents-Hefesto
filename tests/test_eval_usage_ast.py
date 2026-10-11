"""EVAL_USAGE on JavaScript, TypeScript and Java comes from the parsed code.

The non-Python detector matched ``eval(`` / ``exec(`` anywhere in a line, so
``RegExp.prototype.exec`` (``/re/.exec(s)``), a project's own method named
``exec``, and the words in comments and strings were reported as dangerous
code execution. Calls are now read from the tree-sitter syntax tree:

* JavaScript/TypeScript: ``eval(...)`` (also ``window.eval``/``globalThis.eval``),
  and ``exec`` only when it is the ``child_process`` function (bound by
  ``require``/``import``) or Cypress ``cy.exec``.
* Java: ``exec`` on a ``Runtime`` (``Runtime.getRuntime().exec``), ``eval`` on
  a ``ScriptEngine``.
"""

import pytest

pytest.importorskip("tree_sitter_language_pack")

from hefesto.analyzers.security import SecurityAnalyzer  # noqa: E402
from hefesto.core.analysis_models import AnalysisIssueType  # noqa: E402
from hefesto.core.parsers.treesitter_parser import TreeSitterParser  # noqa: E402


def _eval_lines(language, code, file_path="src/app.js"):
    tree = TreeSitterParser(language).parse(code, file_path)
    issues = SecurityAnalyzer().analyze(tree, file_path, code)
    return sorted(i.line for i in issues if i.issue_type == AnalysisIssueType.EVAL_USAGE)


# ------------------------------------------------------------------ JavaScript


class TestJavaScriptEval:
    def test_eval_call(self):
        code = "const preTax = eval(req.body.preTax);\n"
        assert _eval_lines("javascript", code) == [1]

    def test_global_object_eval(self):
        code = "window.eval(src);\nglobalThis.eval(src);\n"
        assert _eval_lines("javascript", code) == [1, 2]

    def test_comment_and_string_are_not_calls(self):
        code = (
            "// Insecure use of eval() to parse inputs\n"
            "/* exec(cmd) */\n"
            "var xss = 'javascript:eval(document.body.innerHTML)';\n"
            "var t = `exec(${x})`;\n"
        )
        assert _eval_lines("javascript", code) == []

    def test_regexp_exec_is_not_code_execution(self):
        code = (
            "var m = /^verdict:\\s*(.+)$/m.exec(fm);\n"
            "var r = re.exec(s);\n"
            "while ((match = pattern.exec(text)) !== null) {}\n"
            "var o = a?.exec(x);\n"
        )
        assert _eval_lines("javascript", code) == []

    def test_own_method_or_function_named_exec(self):
        code = "db.exec('SELECT 1');\nfunction exec(q) { return q; }\nexec('x');\n"
        assert _eval_lines("javascript", code) == []

    def test_property_named_eval_is_not_eval(self):
        code = "x.eval(src);\nmath.evaluate(expr);\n"
        assert _eval_lines("javascript", code) == []

    def test_non_ascii_text_before_the_call(self):
        code = "var s = 'ñandú — café';\nconst v = eval(x);\n"
        assert _eval_lines("javascript", code) == [2]


class TestJavaScriptChildProcess:
    def test_exec_bound_from_require_member(self):
        code = 'var exec = require("child_process").exec;\nexec(cmd + "node x.js", cb);\n'
        assert _eval_lines("javascript", code) == [2]

    def test_destructured_and_aliased(self):
        code = (
            "const { exec, spawn } = require('child_process');\n"
            "const { exec: run } = require('node:child_process');\n"
            "exec(a);\nrun(b);\nspawn(c);\n"
        )
        assert _eval_lines("javascript", code) == [3, 4]

    def test_module_alias(self):
        code = "const cp = require('child_process');\ncp.exec(cmd);\nre.exec(s);\n"
        assert _eval_lines("javascript", code) == [2]

    def test_direct_require_call(self):
        code = "require('child_process').exec(cmd);\n"
        assert _eval_lines("javascript", code) == [1]

    def test_es_module_imports(self):
        code = (
            "import * as cp from 'child_process';\n"
            "import { exec as sh } from 'node:child_process';\n"
            "cp.exec(a);\nsh(b);\n"
        )
        assert _eval_lines("javascript", code) == [3, 4]

    def test_cypress_exec(self):
        code = 'cy.exec("npm run db:seed", { timeout: 1000 });\n'
        assert _eval_lines("javascript", code, "test/e2e/support/commands.js") == [1]


class TestTypeScript:
    def test_eval_and_regexp_exec(self):
        code = (
            'const hasFast = eval("(o) => %HasFastProperties(o)");\n'
            'const v = /^status:\\s*(.+)$/m.exec(fm)?.[1].trim() ?? "-";\n'
        )
        assert _eval_lines("typescript", code, "scripts/x.ts") == [1]


# ------------------------------------------------------------------ Java


class TestJava:
    def test_runtime_exec(self):
        code = (
            "class A {\n"
            "  void f(String t) throws Exception {\n"
            "    Process p = Runtime.getRuntime().exec(t);\n"
            "  }\n"
            "}\n"
        )
        assert _eval_lines("java", code, "src/A.java") == [3]

    def test_runtime_variable_and_field(self):
        code = (
            "class A {\n"
            "  private final Runtime rt = Runtime.getRuntime();\n"
            "  void f(String t, Runtime other) throws Exception {\n"
            "    rt.exec(t);\n"
            "    other.exec(t);\n"
            "    this.rt.exec(t);\n"
            "  }\n"
            "}\n"
        )
        assert _eval_lines("java", code, "src/A.java") == [4, 5, 6]

    def test_own_exec_method_is_not_code_execution(self):
        code = (
            "class CobolEsql {\n"
            "  public static void exec(Storage sqlca, String query) {\n"
            "    backend().exec(sqlca, query);\n"
            "    exec(sqlca, query);\n"
            '    CobolEsql.exec(sqlca, "SELECT 1");\n'
            "  }\n"
            "  // exec() with real DB\n"
            "}\n"
        )
        assert _eval_lines("java", code, "src/CobolEsql.java") == []

    def test_javadoc_mentioning_eval(self):
        code = "class W {\n  /** This prevents eval() from failing. */\n  void f() {}\n}\n"
        assert _eval_lines("java", code, "src/W.java") == []

    def test_script_engine_eval(self):
        code = (
            "class S {\n"
            "  void f(ScriptEngineManager m, String s) throws Exception {\n"
            '    ScriptEngine e = m.getEngineByName("js");\n'
            "    e.eval(s);\n"
            '    m.getEngineByName("js").eval(s);\n'
            "    expr.eval(s);\n"
            "  }\n"
            "}\n"
        )
        assert _eval_lines("java", code, "src/S.java") == [4, 5]


# ------------------------------------------------------------------ others


@pytest.mark.parametrize(
    "language, code",
    [
        ("go", 'package main\nfunc main() { exec("ls"); eval(x) }\n'),
        ("rust", "fn main() { exec(cmd); eval(x); }\n"),
        ("c_sharp", "class A { void F() { exec(cmd); eval(x); } }\n"),
    ],
)
def test_languages_without_an_eval_builtin(language, code):
    # Go, Rust and C# have no eval/exec builtin: such a call is a local function.
    assert _eval_lines(language, code, "src/main.x") == []
