"""A found file the engine cannot analyze is reported, and fails --fail-on.

4.20.0 dropped such a file without a trace: an analyzer exception (for
example RecursionError on a JSON file nested deeper than the interpreter's
recursion limit) was swallowed by ``AnalyzerEngine._analyze_file``, so a run
printed "Gate passed" over a file it never checked.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto.analyzers.devops.json_analyzer import JsonAnalyzer
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.reports.sarif_reporter import SARIFReporter

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET = "Sup3rS3cretValue!2026"


def _run(*args):
    env = dict(os.environ, HEFESTO_TELEMETRY="0", HEFESTO_NO_UPSELL="1")
    return subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", *args, "--no-config"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def _deep_json(depth: int) -> str:
    pad = "[" * depth + "]" * depth
    return '{"password": "%s", "pad": %s}' % (SECRET, pad)


def _project_with_deep_json(tmp_path, depth=5000):
    root = tmp_path / "deep"
    root.mkdir()
    (root / "app.py").write_text("def ok():\n    return 1\n")
    (root / "config.json").write_text(_deep_json(depth))
    return root


class _RaisingAnalyzer:
    def analyze(self, file_path, content):
        raise RuntimeError("analyzer exploded")


@pytest.fixture
def raising_toml(monkeypatch):
    """Make the TOML analyzer raise, to exercise the engine's handler."""
    from hefesto.analyzers.devops import toml_analyzer

    monkeypatch.setattr(toml_analyzer.TomlAnalyzer, "analyze", _RaisingAnalyzer.analyze)


def _project_with_toml(tmp_path):
    root = tmp_path / "toml"
    root.mkdir()
    (root / "app.py").write_text("def ok():\n    return 1\n")
    (root / "pyproject.toml").write_text('[tool.x]\nname = "x"\n')
    return root


class TestDeepJson:
    def test_secret_reported_at_depth_5000(self):
        issues = JsonAnalyzer().analyze("config.json", _deep_json(5000))
        assert any(i.rule_id == "J001" for i in issues)

    @pytest.mark.parametrize("margin", [5, 20, 50, 100])
    def test_depth_near_recursion_limit(self, margin):
        depth = sys.getrecursionlimit() - margin
        issues = JsonAnalyzer().analyze("config.json", _deep_json(depth))
        assert [i.rule_id for i in issues].count("J001") == 1

    def test_deep_json_is_classified_without_crashing(self):
        from hefesto.core.language_detector import LanguageDetector

        LanguageDetector.detect(Path("config.json"), _deep_json(200000))

    def test_cli_deep_json_fails_critical_gate(self, tmp_path):
        result = _run(str(_project_with_deep_json(tmp_path)), "--fail-on", "CRITICAL")
        assert result.returncode == 1
        assert "Gate passed" not in result.stdout
        assert "HARDCODED_SECRET" in result.stdout
        assert "Files analyzed: 2" in result.stdout

    def test_cli_very_deep_json_fails_critical_gate(self, tmp_path):
        root = _project_with_deep_json(tmp_path, depth=200000)
        result = _run(str(root), "--fail-on", "CRITICAL")
        assert result.returncode == 1
        assert "Gate passed" not in result.stdout


class TestEngineRecordsNotAnalyzed:
    def test_analyzer_exception_is_recorded(self, tmp_path, raising_toml):
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        report = engine.analyze_path(str(_project_with_toml(tmp_path)))
        assert report.summary.files_analyzed == 1
        entries = engine._build_meta()["not_analyzed"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["path"].endswith("pyproject.toml")
        assert entry["reason"] == "analyzer_error"
        assert entry["exception"] == "RuntimeError"
        assert entry["language"] == "toml"

    def test_non_utf8_file_is_analyzed_not_dropped(self, tmp_path):
        root = tmp_path / "latin1"
        root.mkdir()
        (root / "legacy.py").write_bytes(b"# caf\xe9\nx = 1\n")
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        report = engine.analyze_path(str(root))
        meta = engine._build_meta()
        assert report.summary.files_analyzed == 1
        assert "not_analyzed" not in meta
        assert [e["encoding"] for e in meta["decoded_with_fallback"]] == ["latin-1"]

    def test_clean_run_has_no_not_analyzed_key(self, tmp_path):
        root = tmp_path / "clean"
        root.mkdir()
        (root / "ok.py").write_text("def ok():\n    return 1\n")
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine.analyze_path(str(root))
        assert "not_analyzed" not in engine._build_meta()

    def test_warning_on_stderr_even_when_quiet(self, tmp_path, raising_toml, capsys):
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        engine.analyze_path(str(_project_with_toml(tmp_path)))
        err = capsys.readouterr().err
        assert "could not be analyzed" in err
        assert "pyproject.toml" in err


class TestReportsShowNotAnalyzed:
    def _report(self, tmp_path):
        from hefesto.cli.main import _generate_report

        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        report = engine.analyze_path(str(_project_with_toml(tmp_path)))
        return _generate_report(
            report.file_results, 0, 0.0, "text", None, meta=engine._build_meta()
        )

    def test_text(self, tmp_path, raising_toml):
        from hefesto.reports.text_reporter import TextReporter

        text = TextReporter().generate(self._report(tmp_path))
        assert "Not analyzed: 1" in text
        assert "pyproject.toml" in text
        assert "RuntimeError" in text

    def test_json(self, tmp_path, raising_toml):
        from hefesto.reports.json_reporter import JSONReporter

        data = json.loads(JSONReporter().generate(self._report(tmp_path)))
        assert data["meta"]["not_analyzed"][0]["reason"] == "analyzer_error"

    def test_sarif(self, tmp_path, raising_toml):
        log = SARIFReporter(root=str(tmp_path)).generate_dict(self._report(tmp_path))
        notes = log["runs"][0]["invocations"][0]["toolExecutionNotifications"]
        errors = [n for n in notes if n["level"] == "error"]
        assert len(errors) == 1
        assert "not analyzed" in errors[0]["message"]["text"]
        uri = errors[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        assert uri.endswith("pyproject.toml")


class TestGateFailsClosed:
    @pytest.fixture(autouse=True)
    def _raise_in_subprocess(self, monkeypatch):
        # The CLI runs in a subprocess; sitecustomize there makes TOML raise.
        hook = Path(__file__).parent / "fixtures" / "raise_toml"
        monkeypatch.setenv("PYTHONPATH", f"{hook}{os.pathsep}{os.environ.get('PYTHONPATH', '')}")

    def test_fail_on_exits_1(self, tmp_path):
        result = _run(str(_project_with_toml(tmp_path)), "--fail-on", "CRITICAL")
        assert result.returncode == 1
        assert "Gate failure: 1 file(s) could not be analyzed (exit 1)" in result.stdout
        assert "Gate passed" not in result.stdout

    def test_json_output_stdout_is_pure_json(self, tmp_path):
        result = _run(str(_project_with_toml(tmp_path)), "--fail-on", "LOW", "--output", "json")
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["meta"]["not_analyzed"][0]["path"].endswith("pyproject.toml")

    def test_without_fail_on_exit_0(self, tmp_path):
        result = _run(str(_project_with_toml(tmp_path)))
        assert result.returncode == 0
        assert "Not analyzed: 1" in result.stdout

    def test_opt_out_flag(self, tmp_path):
        result = _run(
            str(_project_with_toml(tmp_path)), "--fail-on", "CRITICAL", "--allow-not-analyzed"
        )
        assert result.returncode == 0
        assert "--allow-not-analyzed" in result.stdout
        assert "could not be analyzed" in result.stderr

    def test_opt_out_still_fails_on_findings(self, tmp_path):
        root = _project_with_toml(tmp_path)
        (root / "config.json").write_text(json.dumps({"password": SECRET}))
        result = _run(str(root), "--fail-on", "CRITICAL", "--allow-not-analyzed")
        assert result.returncode == 1
        assert "CRITICAL or higher issues found" in result.stdout

    def test_allow_no_files_does_not_hide_a_failed_file(self, tmp_path):
        root = tmp_path / "only"
        root.mkdir()
        (root / "pyproject.toml").write_text('[tool.x]\nname = "x"\n')
        result = _run(str(root), "--fail-on", "CRITICAL", "--allow-no-files")
        assert result.returncode == 1
        assert "could not be analyzed" in result.stdout

    def test_quiet_still_fails_and_warns(self, tmp_path):
        result = _run(str(_project_with_toml(tmp_path)), "--fail-on", "CRITICAL", "--quiet")
        assert result.returncode == 1
        assert "could not be analyzed" in result.stderr

    def test_no_files_warning_names_the_failed_file(self, tmp_path):
        root = tmp_path / "only"
        root.mkdir()
        (root / "pyproject.toml").write_text('[tool.x]\nname = "x"\n')
        result = _run(str(root), "--fail-on", "CRITICAL", "--allow-no-files")
        assert result.returncode == 1
        assert "1 file(s) could not be analyzed" in result.stderr

    def test_flag_is_cli_only(self):
        from hefesto.config.project_config import SUPPORTED_KEYS

        assert "allow_not_analyzed" not in SUPPORTED_KEYS


class TestCounterexamples:
    def test_deep_cloudformation_is_not_dropped(self, tmp_path):
        root = tmp_path / "cfn"
        root.mkdir()
        pad = "[" * 5000 + "]" * 5000
        (root / "stack.json").write_text(
            '{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {"B": {"Type":'
            ' "AWS::S3::Bucket", "Properties": {"Pad": %s}}}}' % pad
        )
        result = _run(str(root), "--fail-on", "CRITICAL", "--output", "json")
        data = json.loads(result.stdout)
        analyzed = [f["file"] for f in data["files"]]
        failed = [e["path"] for e in data.get("meta", {}).get("not_analyzed", [])]
        # Python 3.12+ parses it and the CloudFormation walk overflows (not
        # analyzed, gate fails); 3.10/3.11 cannot parse it, so it is classified
        # as plain JSON and gets the regex analysis (analyzed, nothing found).
        assert any(p.endswith("stack.json") for p in analyzed + failed)
        assert result.returncode == (1 if failed else 0)
        if failed:
            assert "Gate passed" not in result.stdout + result.stderr


def test_os_error_on_read_is_still_read_error(tmp_path, monkeypatch):
    root = tmp_path / "oserr"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")

    def boom(self, path):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(AnalyzerEngine, "_read_source", boom)
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    engine.analyze_path(str(root))
    [entry] = engine._build_meta()["not_analyzed"]
    assert entry["reason"] == "read_error"
    assert entry["exception"] == "PermissionError"
