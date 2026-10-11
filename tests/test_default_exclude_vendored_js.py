"""Vendored and minified JavaScript is excluded by default.

A minified bundle or a library copied into the repo (``jquery.min.js``,
``static/js/libs/ace.js``, ``assets/vendor/...``) is third-party code the
project does not edit. Analyzing it buried a project's own findings under
hundreds of library findings (a Java web app with 589 analyzed files reported
about 1,900 findings from bundled jQuery, Ace and RequireJS) and produced
EVAL_USAGE on ``eval`` calls inside those libraries. The rule only looks at
JavaScript files (``.js``, ``.mjs``, ``.cjs``) and at their path below the
analysis root; ``--include-vendored`` (or ``include_vendored: true`` in
``.hefesto.yaml``) analyzes them again.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto.core.analyzer_engine import AnalyzerEngine, is_vendored_js

JS = "function f(a) { return a + 1; }\n"


def _write(path: Path, text: str = JS) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _names(root: Path, files):
    return sorted(Path(f).resolve().relative_to(root.resolve()).as_posix() for f in files)


def _parts(rel: str):
    return tuple(rel.split("/"))


class TestIsVendoredJs:
    @pytest.mark.parametrize(
        "rel",
        [
            # minified file names, at any depth
            "jquery.min.js",
            "src/main/resources/webgoat/static/js/libs/require.min.js",
            "app/assets/vendor/chart/raphael-min.js",
            "static/js/libs/backbone-min.js",
            "dist2/app.min.mjs",
            "pkg/index.min.cjs",
            "web/JQUERY.MIN.JS",
            # package-manager / vendoring directories, at any depth
            "vendor/jquery.js",
            "app/assets/vendor/bootstrap/bootstrap.js",
            "public/vendors/chart.js",
            "bower_components/angular/angular.js",
            "jspm_packages/npm/lodash/index.js",
            # library directories inside a web static-asset directory
            "src/main/resources/webgoat/static/js/libs/ace.js",
            "src/main/resources/webgoat/static/js/libs/jquery-ui-1.10.4.js",
            "src/main/resources/webgoat/static/plugins/bootstrap-wysihtml5/js/wysihtml5-0.3.0.js",
            "public/js/lib/moment.js",
            "assets/third_party/d3.js",
            "wwwroot/lib/jquery/dist/jquery.js",
        ],
    )
    def test_vendored_or_minified(self, rel):
        assert is_vendored_js(_parts(rel))

    @pytest.mark.parametrize(
        "rel",
        [
            # the project's own code
            "lib/application.js",
            "lib/router/index.js",
            "src/libs/util.js",
            "plugins/my-plugin.js",
            "app/routes/contributions.js",
            "src/main/resources/webgoat/static/js/goatApp/view/MenuView.js",
            "src/main/resources/lessons/challenges/js/challenge8.js",
            "public/js/app.js",
            "static/js/main.js",
            # names that only resemble the patterns
            "vendor.js",
            "src/vendor.config.js",
            "minimal.js",
            "admin.js",
            "src/min.js",
            "jquery.min.js.map",
            "static/libs.js",
            # not JavaScript: Go/PHP/Ruby vendor trees and minified TypeScript stay in scope
            "vendor/github.com/pkg/errors/errors.go",
            "vendor/autoload.php",
            "static/js/libs/helper.py",
            "src/app.min.ts",
            "static/js/libs/types.d.ts",
        ],
    )
    def test_project_code(self, rel):
        assert not is_vendored_js(_parts(rel))

    def test_directories_above_the_root_do_not_count(self):
        # rel parts start below the analysis root; an analyzed directory named
        # vendor/ or static/libs/ is passed as its contents only
        assert not is_vendored_js(("app.js",))
        assert not is_vendored_js(("js", "app.js"))


class TestFindFiles:
    def _tree(self, root: Path):
        _write(root / "app.js")
        _write(root / "lib" / "own.js")
        _write(root / "static" / "js" / "main.js")
        _write(root / "static" / "js" / "libs" / "require.min.js", "eval(text);\n")
        _write(root / "static" / "js" / "libs" / "ace.js")
        _write(root / "static" / "plugins" / "w" / "js" / "w.js")
        _write(root / "assets" / "vendor" / "jquery.js")
        _write(root / "bundle-min.js")
        _write(root / "vendor" / "tool.py", "import os\n")

    def test_vendored_and_minified_js_are_excluded_by_default(self, tmp_path):
        self._tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        assert _names(tmp_path, engine._find_files(tmp_path, [])) == [
            "app.js",
            "lib/own.js",
            "static/js/main.js",
            "vendor/tool.py",
        ]

    def test_include_vendored_analyzes_them(self, tmp_path):
        self._tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine.set_include_vendored(True)
        assert len(engine._find_files(tmp_path, [])) == 9

    def test_user_excludes_still_apply_with_include_vendored(self, tmp_path):
        self._tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine.set_include_vendored(True)
        names = _names(tmp_path, engine._find_files(tmp_path, ["static/"]))
        assert not any(n.startswith("static/") for n in names)

    def test_root_inside_a_vendor_directory_is_still_analyzed(self, tmp_path):
        root = tmp_path / "static" / "js" / "libs" / "mylib"
        _write(root / "index.js")
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        assert _names(root, engine._find_files(root, [])) == ["index.js"]

    def test_single_file_target_is_never_excluded(self, tmp_path):
        target = _write(tmp_path / "static" / "js" / "libs" / "jquery.min.js")
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        assert engine._find_files(target, []) == [target]


def _run(*args: str, cwd: Path):
    return subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=dict(os.environ, HEFESTO_TELEMETRY="0"),
        timeout=120,
    )


def _analyzed(stdout: str) -> int:
    return json.loads(stdout)["summary"]["files_analyzed"]


# A JavaScript file only counts as analyzed when its tree-sitter grammar is
# installed (the [multilang] extra). Without it the CLI reports the file as
# parser_unavailable, so the tests that count analyzed JS files run in the
# multilang-smoke workflow, not in lint-and-test.
needs_js_parser = pytest.mark.skipif(
    importlib.util.find_spec("tree_sitter_language_pack") is None,
    reason="needs the [multilang] extra (tree_sitter_language_pack)",
)


class TestCli:
    def _tree(self, root: Path):
        _write(root / "app.py", "import os\n")
        _write(root / "static" / "js" / "libs" / "jquery.min.js")

    def test_default_skips_vendored(self, tmp_path):
        self._tree(tmp_path)
        res = _run(".", "--no-config", "--output", "json", cwd=tmp_path)
        assert res.returncode == 0, res.stderr
        files = [f["file"] for f in json.loads(res.stdout)["files"]]
        assert not any(f.endswith("jquery.min.js") for f in files)

    @needs_js_parser
    def test_flag_includes_vendored(self, tmp_path):
        self._tree(tmp_path)
        default = _run(".", "--no-config", "--output", "json", cwd=tmp_path)
        res = _run(".", "--no-config", "--include-vendored", "--output", "json", cwd=tmp_path)
        assert res.returncode == 0, res.stderr
        assert _analyzed(res.stdout) == _analyzed(default.stdout) + 1

    @needs_js_parser
    def test_config_key_includes_vendored(self, tmp_path):
        self._tree(tmp_path)
        _write(tmp_path / ".hefesto.yaml", "include_vendored: true\n")
        res = _run(".", "--output", "json", cwd=tmp_path)
        assert res.returncode == 0, res.stderr
        files = [f["file"] for f in json.loads(res.stdout)["files"]]
        assert any(f.endswith("jquery.min.js") for f in files), files


# -- Skip report: how many files were left out as vendored --------------------

SKIP_LINE = "skipped as vendored (use --include-vendored)"


def _vendored_tree(root: Path) -> None:
    _write(root / "src" / "app.py", "import os\n")
    _write(root / "static" / "js" / "libs" / "jquery.min.js")
    _write(root / "static" / "js" / "libs" / "ace.js")
    _write(root / "assets" / "vendor" / "chart.js")
    # already excluded by a default exclude: not counted as vendored
    _write(root / "node_modules" / "lib" / "index.min.js")


class TestSkipReportEngine:
    def test_counts_vendored_files_once(self, tmp_path):
        _vendored_tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine._find_files(tmp_path, [])
        engine._find_files(tmp_path, [])  # same path again: no double count
        skipped = engine._build_meta()["vendored_skipped"]
        assert skipped["count"] == 3
        assert [Path(p).name for p in skipped["examples"]] == [
            "chart.js",
            "ace.js",
            "jquery.min.js",
        ]

    def test_user_excluded_files_are_not_counted(self, tmp_path):
        _vendored_tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine._find_files(tmp_path, ["static/"])
        assert engine._build_meta()["vendored_skipped"]["count"] == 1

    def test_no_entry_without_vendored_files(self, tmp_path):
        _write(tmp_path / "app.js")
        _write(tmp_path / "lib" / "own.js")
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine._find_files(tmp_path, [])
        assert "vendored_skipped" not in engine._build_meta()

    def test_no_entry_with_include_vendored(self, tmp_path):
        _vendored_tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine.set_include_vendored(True)
        engine._find_files(tmp_path, [])
        assert "vendored_skipped" not in engine._build_meta()

    def test_examples_are_capped(self, tmp_path):
        for n in range(30):
            _write(tmp_path / "vendor" / f"lib{n:02d}.js")
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine._find_files(tmp_path, [])
        skipped = engine._build_meta()["vendored_skipped"]
        assert skipped["count"] == 30
        assert len(skipped["examples"]) == 20


class TestSkipReportOutput:
    def test_text_reports_the_count(self, tmp_path):
        _vendored_tree(tmp_path)
        res = _run(".", "--no-config", cwd=tmp_path)
        assert res.returncode == 0, res.stderr
        assert f"3 files {SKIP_LINE}" in res.stdout

    def test_text_singular(self, tmp_path):
        _write(tmp_path / "app.py", "import os\n")
        _write(tmp_path / "vendor" / "one.js")
        res = _run(".", "--no-config", cwd=tmp_path)
        assert f"1 file {SKIP_LINE}" in res.stdout

    def test_text_has_no_line_when_nothing_was_skipped(self, tmp_path):
        _write(tmp_path / "app.py", "import os\n")
        res = _run(".", "--no-config", cwd=tmp_path)
        assert res.returncode == 0, res.stderr
        assert "skipped as vendored" not in res.stdout + res.stderr

    def test_text_has_no_line_with_include_vendored(self, tmp_path):
        _vendored_tree(tmp_path)
        res = _run(".", "--no-config", "--include-vendored", cwd=tmp_path)
        assert "skipped as vendored" not in res.stdout + res.stderr

    def test_json_meta_field(self, tmp_path):
        _vendored_tree(tmp_path)
        res = _run(".", "--no-config", "--output", "json", cwd=tmp_path)
        assert res.returncode == 0, res.stderr
        report = json.loads(res.stdout)
        assert report["meta"]["vendored_skipped"]["count"] == 3
        assert len(report["meta"]["vendored_skipped"]["examples"]) == 3

    def test_json_has_no_field_when_nothing_was_skipped(self, tmp_path):
        _write(tmp_path / "app.py", "import os\n")
        res = _run(".", "--no-config", "--output", "json", cwd=tmp_path)
        assert "vendored_skipped" not in json.loads(res.stdout).get("meta", {})

    def test_sarif_tool_notification(self, tmp_path):
        _vendored_tree(tmp_path)
        res = _run(".", "--no-config", "--output", "sarif", cwd=tmp_path)
        assert res.returncode == 0, res.stderr
        invocation = json.loads(res.stdout)["runs"][0]["invocations"][0]
        texts = [n["message"]["text"] for n in invocation["toolExecutionNotifications"]]
        assert any(f"3 files {SKIP_LINE}" in t for t in texts), texts
        assert invocation["executionSuccessful"] is True

    def test_sarif_has_no_notification_when_nothing_was_skipped(self, tmp_path):
        _write(tmp_path / "app.py", "import os\n")
        res = _run(".", "--no-config", "--output", "sarif", cwd=tmp_path)
        invocation = json.loads(res.stdout)["runs"][0]["invocations"][0]
        assert "toolExecutionNotifications" not in invocation
