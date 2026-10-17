"""A found file that is not valid UTF-8 is decoded with latin-1 and analyzed.

latin-1 maps every byte 0x00-0xff to one code point, so decoding never fails
and ASCII text (keys, secrets, line breaks) is unchanged:
https://docs.python.org/3/library/codecs.html#encodings-and-unicode
Each such file is listed as "decoded with fallback" in text, JSON and SARIF.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from hefesto.cli.main import _generate_report
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.reports.json_reporter import JSONReporter
from hefesto.reports.sarif_reporter import SARIFReporter
from hefesto.reports.text_reporter import TextReporter

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


def _latin1_project(tmp_path):
    root = tmp_path / "legacy"
    root.mkdir()
    body = '{"password": "%s", "note": "caf\xe9 cr\xe8me"}' % SECRET
    (root / "config.json").write_bytes(body.encode("latin-1"))
    return root


def _report(root):
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    report = engine.analyze_path(str(root))
    return _generate_report(report.file_results, 0, 0.0, "text", None, meta=engine._build_meta())


def test_fixture_is_not_utf8(tmp_path):
    raw = (_latin1_project(tmp_path) / "config.json").read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return
    raise AssertionError("fixture must not be valid UTF-8")


def test_latin1_secret_is_found_and_fails_the_gate(tmp_path):
    result = _run(str(_latin1_project(tmp_path)), "--fail-on", "CRITICAL")
    assert result.returncode == 1
    assert "HARDCODED_SECRET" in result.stdout
    assert "Files analyzed: 1" in result.stdout
    assert "CRITICAL or higher issues found" in result.stdout
    assert "could not be analyzed" not in result.stdout + result.stderr


def test_listed_in_text(tmp_path):
    text = TextReporter().generate(_report(_latin1_project(tmp_path)))
    assert "Decoded with fallback (latin-1): 1" in text
    assert "config.json" in text
    assert "Not analyzed" not in text


def test_listed_in_json(tmp_path):
    data = json.loads(JSONReporter().generate(_report(_latin1_project(tmp_path))))
    entries = data["meta"]["decoded_with_fallback"]
    assert len(entries) == 1
    assert entries[0]["path"].endswith("config.json")
    assert entries[0]["encoding"] == "latin-1"
    assert "not_analyzed" not in data["meta"]
    assert any(i["type"] == "HARDCODED_SECRET" for f in data["files"] for i in f["issues"])


def test_listed_in_sarif(tmp_path):
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report(_latin1_project(tmp_path)))
    run = log["runs"][0]
    notes = run["invocations"][0]["toolExecutionNotifications"]
    fallback = [n for n in notes if "decoded with fallback" in n["message"]["text"]]
    assert len(fallback) == 1
    assert fallback[0]["level"] == "warning"
    uri = fallback[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri.endswith("config.json")
    assert not [n for n in notes if n["level"] == "error"]
    assert any(r["ruleId"] == "J001" for r in run["results"])


def test_warning_on_stderr(tmp_path):
    result = _run(str(_latin1_project(tmp_path)), "--quiet")
    assert "decoded with fallback" in result.stderr
    assert "config.json" in result.stderr


def test_utf8_file_is_not_listed(tmp_path):
    root = tmp_path / "utf8"
    root.mkdir()
    (root / "config.json").write_text('{"note": "café"}', encoding="utf-8")
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    engine.analyze_path(str(root))
    assert "decoded_with_fallback" not in engine._build_meta()


def test_analyze_files_lists_fallback(tmp_path):
    path = _latin1_project(tmp_path) / "config.json"
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    engine.analyze_files([str(path)])
    assert [e["encoding"] for e in engine._build_meta()["decoded_with_fallback"]] == ["latin-1"]


def test_crlf_lines_are_kept_as_before(tmp_path):
    root = tmp_path / "crlf"
    root.mkdir()
    raw = b'{\r\n  "note": "caf\xe9",\r\n  "password": "' + SECRET.encode() + b'"\r\n}\r\n'
    (root / "config.json").write_bytes(raw)
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    report = engine.analyze_path(str(root))
    secrets = [i for i in report.get_all_issues() if i.issue_type.value == "HARDCODED_SECRET"]
    assert [i.line for i in secrets] == [3]
