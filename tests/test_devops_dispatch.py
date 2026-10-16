"""CLI dispatch for the nine analyzers that used to be skipped.

Each case runs ``hefesto analyze`` the way a hook does (``--no-config``,
JSON on stdout) and checks the language and a rule id from that analyzer.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "devops_dispatch"

CASES = [
    ("json/config.json", "json", "J001"),
    ("toml/config.toml", "toml", "T001"),
    ("powershell/script.ps1", "powershell", "PS001"),
    ("make/Makefile", "makefile", "MF002"),
    ("groovy/Jenkinsfile", "groovy", "GJ002"),
    ("cloudformation/template.yaml", "cloudformation", "CFN_S001"),
    ("arm/azure.json", "arm", "ARM_S001"),
    ("serverless/serverless.yml", "serverless", "SLS_S001"),
]


def _run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HEFESTO_TELEMETRY"] = "0"
    env["HEFESTO_NO_UPSELL"] = "1"
    env["CI"] = "true"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "hefesto.cli.main",
            "analyze",
            *args,
            "--no-config",
            "--severity",
            "LOW",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        timeout=60,
    )


def _report(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _rules(report: dict) -> list:
    return [issue.get("rule_id") for item in report["files"] for issue in item["issues"]]


@pytest.mark.parametrize("rel,language,rule", CASES)
def test_each_format_produces_a_finding(rel, language, rule):
    report = _report(_run(str(FIXTURES / rel)))
    assert report["summary"]["files_analyzed"] == 1
    assert report["files"][0]["language"] == language
    assert rule in _rules(report)


def test_helm_values_are_helm_and_templates_stay_yaml():
    report = _report(_run(str(FIXTURES / "helm" / "demo")))
    by_name = {Path(item["file"]).name: item for item in report["files"]}
    assert by_name["values.yaml"]["language"] == "helm"
    assert "HELM_S001" in [issue.get("rule_id") for issue in by_name["values.yaml"]["issues"]]
    assert by_name["Chart.yaml"]["language"] == "yaml"
    template = by_name["deploy.yaml"]
    assert template["language"] == "yaml"
    assert not any(issue.get("type") == "YAML_SYNTAX_ERROR" for issue in template["issues"])


def test_text_and_markdown_stay_ignored(tmp_path):
    root = tmp_path / "notes"
    root.mkdir()
    (root / "notes.md").write_text("# notes\n")
    (root / "readme.txt").write_text("plain text\n")
    report = _report(_run(str(root)))
    assert report["summary"]["files_analyzed"] == 0
    assert report["files"] == []


def test_tf_json_stays_terraform_even_with_a_cloudformation_key():
    report = _report(_run(str(FIXTURES / "overlaps" / "stack.tf.json")))
    assert report["summary"]["files_analyzed"] == 1
    assert report["files"][0]["language"] == "terraform"


def test_resources_array_stays_json():
    report = _report(_run(str(FIXTURES / "overlaps" / "resources-list.json")))
    assert report["summary"]["files_analyzed"] == 1
    assert report["files"][0]["language"] == "json"


def test_arm_schema_wins_when_a_cloudformation_key_is_also_present():
    report = _report(_run(str(FIXTURES / "overlaps" / "both.json")))
    assert report["files"][0]["language"] == "arm"
    assert "ARM_S001" in _rules(report)


def test_serverless_filename_without_service_or_provider_stays_yaml():
    path = FIXTURES / "overlaps" / "not-serverless" / "serverless.yml"
    report = _report(_run(str(path)))
    assert report["files"][0]["language"] == "yaml"
    assert "SLS_S001" not in _rules(report)


def test_values_yaml_without_chart_yaml_stays_yaml():
    report = _report(_run(str(FIXTURES / "overlaps" / "orphan" / "values.yaml")))
    assert report["files"][0]["language"] == "yaml"


def test_package_metadata_and_lockfiles_do_not_flood():
    report = _report(_run(str(FIXTURES / "noise")))
    names = {Path(item["file"]).name for item in report["files"]}
    assert "package-lock.json" not in names
    assert "composer.lock" not in names
    assert "package.json" in names
    assert "tsconfig.json" in names

    package = next(item for item in report["files"] if item["file"].endswith("package.json"))
    messages = " ".join(issue["message"] for issue in package["issues"])
    assert "author" not in messages
    assert "credential-providers" not in messages
    assert any(issue.get("rule_id") == "J001" for issue in package["issues"])

    tsconfig = next(item for item in report["files"] if item["file"].endswith("tsconfig.json"))
    ts_messages = " ".join(issue["message"] for issue in tsconfig["issues"])
    assert "author" not in ts_messages
    assert any(issue.get("rule_id") == "J001" for issue in tsconfig["issues"])

    # A path named on the command line is still analyzed.
    direct = _report(_run(str(FIXTURES / "noise" / "package-lock.json")))
    assert direct["summary"]["files_analyzed"] == 1
    assert direct["files"][0]["language"] == "json"
    direct_messages = " ".join(issue["message"] for issue in direct["files"][0]["issues"])
    assert "credential-providers" not in direct_messages
    assert any(issue.get("rule_id") == "J001" for issue in direct["files"][0]["issues"])
