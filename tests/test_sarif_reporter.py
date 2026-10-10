"""SARIF 2.1.0 output (``hefesto analyze --output/--format sarif``).

Every log is validated against the official OASIS SARIF 2.1.0 schema
(vendored in tests/fixtures/sarif) and checked against what GitHub code
scanning requires from an upload.
"""

import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
from click.testing import CliRunner

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
    AnalysisReport,
    AnalysisSummary,
    FileAnalysisResult,
)
from hefesto.reports import SARIFReporter
from hefesto.reports.sarif_reporter import FINGERPRINT_KEY, MAX_GZIP_BYTES

REPO = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (REPO / "tests" / "fixtures" / "sarif" / "sarif-schema-2.1.0.json").read_text(encoding="utf-8")
)


def _validate(log):
    jsonschema.Draft4Validator(SCHEMA).validate(log)
    _assert_github_accepts(log)


def _assert_github_accepts(log):
    """Fields and limits GitHub code scanning checks on upload."""
    assert log["version"] == "2.1.0"
    assert len(log["runs"]) == 1
    run = log["runs"][0]
    driver = run["tool"]["driver"]
    assert driver["name"] and driver["rules"] is not None
    rule_ids = [rule["id"] for rule in driver["rules"]]
    assert len(rule_ids) == len(set(rule_ids))
    for rule in driver["rules"]:
        assert rule["shortDescription"]["text"] and rule["fullDescription"]["text"]
        assert rule["help"]["text"] and rule["helpUri"].startswith("https://")
        props = rule["properties"]
        assert len(props["tags"]) <= 20
        if "security-severity" in props:
            assert 0.0 <= float(props["security-severity"]) <= 10.0
            assert "security" in props["tags"]
    assert len(run["results"]) <= 25_000
    for result in run["results"]:
        assert rule_ids[result["ruleIndex"]] == result["ruleId"]
        assert result["message"]["text"]
        assert result["level"] in ("error", "warning", "note")
        assert result["partialFingerprints"][FINGERPRINT_KEY]
        assert len(result.get("relatedLocations", [])) <= 1000
        physical = result["locations"][0]["physicalLocation"]
        assert physical["region"]["startLine"] >= 1
        location = physical["artifactLocation"]
        if location.get("uriBaseId") == "%SRCROOT%":
            assert not location["uri"].startswith("/")
            assert "\\" not in location["uri"]
    assert len(gzip.compress(json.dumps(log).encode())) <= MAX_GZIP_BYTES


def _issue(path, line, kind, severity, message="msg", **extra):
    return AnalysisIssue(
        file_path=str(path),
        line=line,
        column=0,
        issue_type=AnalysisIssueType[kind],
        severity=AnalysisIssueSeverity[severity],
        message=message,
        **extra,
    )


def _report(issues):
    by_file = {}
    for issue in issues:
        by_file.setdefault(issue.file_path, []).append(issue)
    results = [
        FileAnalysisResult(file_path=f, issues=found, lines_of_code=10, analysis_duration_ms=1.0)
        for f, found in by_file.items()
    ]
    summary = AnalysisSummary(
        files_analyzed=len(results),
        total_issues=len(issues),
        critical_issues=0,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        total_loc=10,
        duration_seconds=0.1,
    )
    return AnalysisReport(summary=summary, file_results=results)


# ---------------------------------------------------------------- reporter


def test_minimal_log_is_valid_with_no_findings(tmp_path):
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report([]))
    _validate(log)
    assert log["runs"][0]["results"] == []
    assert log["runs"][0]["tool"]["driver"]["rules"] == []


def test_rule_metadata_levels_and_security_severity(tmp_path):
    app = tmp_path / "src" / "app.py"
    app.parent.mkdir()
    app.write_text("x = 1\nAPI_KEY = 'abc'\n\n\ndef f():\n    pass\n")
    issues = [
        _issue(app, 2, "HARDCODED_SECRET", "CRITICAL", "Hardcoded secret", suggestion="Use env"),
        _issue(app, 5, "LONG_FUNCTION", "MEDIUM", "Too long", function_name="f"),
        _issue(app, 6, "MISSING_DOCSTRING", "LOW", "No docstring"),
        _issue(
            app,
            1,
            "COBOL_ACCEPT_UNVALIDATED",
            "HIGH",
            "ACCEPT",
            rule_id="COBOL010",
            metadata={"cwe": "CWE-20"},
            confidence=0.95,
        ),
    ]
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report(issues))
    _validate(log)
    rules = {r["id"]: r for r in log["runs"][0]["tool"]["driver"]["rules"]}
    assert set(rules) == {"HARDCODED_SECRET", "LONG_FUNCTION", "MISSING_DOCSTRING", "COBOL010"}

    secret = rules["HARDCODED_SECRET"]
    assert secret["name"] == "HardcodedSecret"
    assert secret["defaultConfiguration"]["level"] == "error"
    assert secret["properties"]["security-severity"] == "9.5"
    assert secret["properties"]["tags"][0] == "security"
    assert "Use env" in secret["help"]["text"] and "Use env" in secret["help"]["markdown"]

    cobol = rules["COBOL010"]
    assert cobol["properties"]["security-severity"] == "8.0"
    assert cobol["properties"]["tags"] == ["security", "cobol", "external/cwe/cwe-20"]
    assert cobol["properties"]["precision"] == "very-high"
    assert cobol["shortDescription"]["text"].startswith("COBOL ")

    assert "security-severity" not in rules["LONG_FUNCTION"]["properties"]
    assert rules["LONG_FUNCTION"]["defaultConfiguration"]["level"] == "warning"
    assert rules["MISSING_DOCSTRING"]["defaultConfiguration"]["level"] == "note"
    assert rules["MISSING_DOCSTRING"]["properties"]["problem.severity"] == "recommendation"

    by_rule = {r["ruleId"]: r for r in log["runs"][0]["results"]}
    assert by_rule["LONG_FUNCTION"]["properties"]["function"] == "f"
    assert by_rule["HARDCODED_SECRET"]["level"] == "error"


def test_rule_default_level_is_its_highest_severity(tmp_path):
    path = tmp_path / "a.py"
    path.write_text("a\nb\n")
    issues = [
        _issue(path, 1, "EVAL_USAGE", "MEDIUM"),
        _issue(path, 2, "EVAL_USAGE", "CRITICAL"),
    ]
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report(issues))
    rule = log["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["defaultConfiguration"]["level"] == "error"
    assert rule["properties"]["security-severity"] == "9.5"
    assert sorted(r["level"] for r in log["runs"][0]["results"]) == ["error", "warning"]


def test_uris_are_repo_relative_and_escaped(tmp_path):
    path = tmp_path / "my dir" / "app.py"
    path.parent.mkdir()
    path.write_text("eval(x)\n")
    outside = tmp_path.parent / "elsewhere.py"
    issues = [_issue(path, 1, "EVAL_USAGE", "HIGH"), _issue(outside, 1, "EVAL_USAGE", "HIGH")]
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report(issues))
    _validate(log)
    locations = [
        r["locations"][0]["physicalLocation"]["artifactLocation"] for r in log["runs"][0]["results"]
    ]
    assert {"uri": "my%20dir/app.py", "uriBaseId": "%SRCROOT%"} in locations
    assert {"uri": outside.resolve().as_uri()} in locations


def test_relative_paths_resolve_against_the_cwd(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text("eval(x)\n")
    monkeypatch.chdir(tmp_path / "pkg")
    log = SARIFReporter().generate_dict(_report([_issue("m.py", 1, "EVAL_USAGE", "HIGH")]))
    location = log["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"] == {"uri": "pkg/m.py", "uriBaseId": "%SRCROOT%"}


def test_fingerprints_survive_line_shifts_and_separate_duplicates(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("eval(a)\neval(a)\neval(b)\n")
    before = _fingerprints(tmp_path, path, [1, 2, 3])
    assert len(set(before)) == 3
    assert before[0].split(":")[0] == before[1].split(":")[0]
    assert before[0].endswith(":1") and before[1].endswith(":2")

    path.write_text("# new header\n\nimport os\neval(a)\neval(a)\neval(b)\n")
    after = _fingerprints(tmp_path, path, [4, 5, 6])
    assert after == before


def test_fingerprints_change_when_the_flagged_code_changes(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("eval(a)\n")
    first = _fingerprints(tmp_path, path, [1])
    path.write_text("eval(other)\n")
    assert _fingerprints(tmp_path, path, [1]) != first


def _fingerprints(root, path, lines):
    issues = [_issue(path, line, "EVAL_USAGE", "HIGH", f"eval at line {line}") for line in lines]
    log = SARIFReporter(root=str(root)).generate_dict(_report(issues))
    return [r["partialFingerprints"][FINGERPRINT_KEY] for r in log["runs"][0]["results"]]


def test_fingerprint_without_source_ignores_numbers_in_the_message(tmp_path):
    missing = tmp_path / "gone.py"
    one = _issue(missing, 3, "LONG_FUNCTION", "MEDIUM", "Function is 80 lines (line 3)")
    two = _issue(missing, 9, "LONG_FUNCTION", "MEDIUM", "Function is 81 lines (line 9)")
    reporter = SARIFReporter(root=str(tmp_path))
    first = reporter.generate_dict(_report([one]))["runs"][0]["results"][0]
    second = reporter.generate_dict(_report([two]))["runs"][0]["results"][0]
    assert first["partialFingerprints"] == second["partialFingerprints"]


def test_copybook_origin_becomes_a_related_location(tmp_path):
    program = tmp_path / "src" / "P1.cbl"
    copybook = tmp_path / "lib" / "AMTS.cpy"
    program.parent.mkdir()
    copybook.parent.mkdir()
    program.write_text("       COPY AMTS.\n")
    copybook.write_text("       01  AMT PIC S9(7) COMP-3.\n       01  AMT-X REDEFINES AMT.\n")
    origin = {"copybook": "AMTS", "file": str(copybook), "line": 2, "copy_lines": [1]}
    issue = _issue(
        program,
        1,
        "COBOL_REDEFINES_SENSITIVE",
        "MEDIUM",
        "REDEFINES",
        rule_id="COBOL004",
        metadata={"expanded_from": origin},
    )
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report([issue]))
    _validate(log)
    result = log["runs"][0]["results"][0]
    related = result["relatedLocations"][0]
    assert related["physicalLocation"]["artifactLocation"]["uri"] == "lib/AMTS.cpy"
    assert related["physicalLocation"]["region"]["startLine"] == 2
    assert "AMTS" in related["message"]["text"]


def test_results_are_capped_keeping_the_most_severe(tmp_path):
    path = tmp_path / "a.py"
    path.write_text("\n".join(f"x{n} = 1" for n in range(30)) + "\n")
    issues = [_issue(path, n + 1, "MAGIC_NUMBER", "LOW") for n in range(25)]
    issues += [_issue(path, 26 + n, "EVAL_USAGE", "CRITICAL") for n in range(5)]
    log = SARIFReporter(root=str(tmp_path), max_results=10).generate_dict(_report(issues))
    _validate(log)
    results = log["runs"][0]["results"]
    assert len(results) == 10
    assert sum(r["ruleId"] == "EVAL_USAGE" for r in results) == 5
    notes = log["runs"][0]["invocations"][0]["toolExecutionNotifications"]
    assert "20 lower-severity results were dropped" in notes[0]["message"]["text"]


def test_gzipped_size_limit_is_enforced(tmp_path, monkeypatch):
    import hefesto.reports.sarif_reporter as module

    monkeypatch.setattr(module, "MAX_GZIP_BYTES", 2_000)
    path = tmp_path / "a.py"
    issues = [
        _issue(path, n + 1, "EVAL_USAGE", "HIGH", f"unique message {n} " + os.urandom(16).hex())
        for n in range(200)
    ]
    log = SARIFReporter(root=str(tmp_path)).generate_dict(_report(issues))
    assert len(gzip.compress(json.dumps(log).encode())) <= 2_000
    assert 0 < len(log["runs"][0]["results"]) < 200
    jsonschema.Draft4Validator(SCHEMA).validate(log)


# --------------------------------------------------------------------- CLI


def _project(tmp_path):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    src = root / "src"
    src.mkdir()
    (src / "app.py").write_text(
        "import os\n"
        'API_KEY = "sk-live-1234567890abcdef1234567890abcdef"\n'
        "def run(cmd):\n"
        '    os.system("ls " + cmd)\n'
        "    return eval(cmd)\n"
    )
    (src / "pod.yaml").write_text(
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: x\nspec:\n  containers:\n"
        "  - name: a\n    image: nginx:1.25\n    securityContext:\n      privileged: true\n"
    )
    (src / "Dockerfile").write_text("FROM ubuntu:latest\nRUN curl http://x | sh\n")
    (src / "PAY.cbl").write_text(
        "\n".join(
            [
                "       IDENTIFICATION DIVISION.",
                "       PROGRAM-ID. PAY.",
                "       DATA DIVISION.",
                "       WORKING-STORAGE SECTION.",
                "       01  WS-PASSWORD PIC X(8) VALUE 'S3CRET99'.",
                "       PROCEDURE DIVISION.",
                "           GO TO DONE.",
                "       DONE.",
                "           STOP RUN.",
            ]
        )
        + "\n"
    )
    return root


def test_cli_sarif_covers_every_analyzer(tmp_path, monkeypatch):
    from hefesto.cli.main import cli

    root = _project(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    out = root / "reports" / "hefesto.sarif"
    result = CliRunner().invoke(
        cli,
        ["analyze", "src", "--severity", "LOW", "--quiet", "--no-config", "--sarif-file", str(out)],
    )
    assert result.exception is None or isinstance(result.exception, SystemExit), result.output
    log = json.loads(out.read_text(encoding="utf-8"))
    _validate(log)
    found = {
        (r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], r["ruleId"])
        for r in log["runs"][0]["results"]
    }
    uris = {uri for uri, _ in found}
    assert {"src/app.py", "src/pod.yaml", "src/Dockerfile", "src/PAY.cbl"} <= uris
    assert ("src/app.py", "HARDCODED_SECRET") in found
    assert ("src/app.py", "EVAL_USAGE") in found
    assert any(uri == "src/PAY.cbl" and rule.startswith("COBOL") for uri, rule in found)


def test_cli_format_sarif_writes_pure_json_to_stdout(tmp_path):
    root = _project(tmp_path)
    env = dict(os.environ, HEFESTO_TELEMETRY="0", PYTHONPATH=str(REPO))
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from hefesto.cli.main import cli; cli()",
            "analyze",
            "src",
            "--format",
            "sarif",
            "--severity",
            "LOW",
            "--no-config",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    log = json.loads(proc.stdout)
    _validate(log)
    assert "Analyzing" in proc.stderr
    assert log["runs"][0]["results"]


def test_config_file_accepts_sarif_output():
    from hefesto.config.project_config import _OUTPUTS

    assert "sarif" in _OUTPUTS
