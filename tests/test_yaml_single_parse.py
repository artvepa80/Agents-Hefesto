"""CSafeLoader and SafeLoader must report the same findings.

The syntax-error text and mark come from SafeLoader when the libyaml loader
fails, because the two loaders describe the same failure differently.
"""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from hefesto.analyzers.devops.yaml_analyzer import YamlAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.core.config_parse import loader_class

SYNTAX = AnalysisIssueType.YAML_SYNTAX_ERROR
SECRET = "AKIAABCDEFGHIJKLMNOP"

ANCHORS = """apiVersion: v1
kind: ConfigMap
metadata:
  name: cfg
  labels: &labels
    app: demo
data:
  token: "abcdefghijklmnop"
  copied: &tok "abcdefghijklmnop"
  again: *tok
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: web
        image: nginx
        securityContext:
          privileged: true
"""

CUSTOM_TAGS = """AWSTemplateFormatVersion: "2010-09-09"
Resources:
  Bucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref NameParam
      Arn: !GetAtt Bucket.Arn
      DBPassword: "super-secret-value"
"""

MULTI_BROKEN = ANCHORS + "---\nkind: ConfigMap\ndata: [unclosed\n"

HELM_TEMPLATE = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "chart.fullname" . }}
spec:
  template:
    spec:
      containers:
      - name: web
        image: nginx
        env:
        - name: AWS_ACCESS_KEY_ID
          value: "%s"
""" % SECRET


def _sig(issues):
    return sorted(
        (i.issue_type.value, i.line, i.column, i.severity.value, i.message, i.rule_id)
        for i in issues
    )


def _engine_issues(root: Path):
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    report = engine.analyze_path(str(root))
    issues = [i for fr in report.file_results for i in fr.issues]
    return issues, engine


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def both_loaders():
    c_loader = getattr(yaml, "CSafeLoader", None)
    if c_loader is None:
        pytest.skip("libyaml CSafeLoader is not installed")
    return c_loader, yaml.SafeLoader


def _cli_text(result) -> str:
    return (result.output or "") + (result.stderr or "")


def _with_loader(monkeypatch, loader, root: Path):
    monkeypatch.setattr("hefesto.core.config_parse.loader_class", lambda: loader)
    issues, engine = _engine_issues(root)
    return _sig(issues), issues, engine


class TestLoaderEquivalence:
    def test_anchors_aliases_and_lines_match(self, tmp_path, monkeypatch, both_loaders):
        _write(tmp_path, "app.yaml", ANCHORS)
        c_sig, c_issues, _ = _with_loader(monkeypatch, both_loaders[0], tmp_path)
        p_sig, p_issues, _ = _with_loader(monkeypatch, both_loaders[1], tmp_path)
        assert c_sig == p_sig
        assert SYNTAX not in {i.issue_type for i in c_issues}
        token_lines = [i.line for i in c_issues if "token" in i.message]
        assert token_lines == [8]
        privileged = [i.line for i in c_issues if "privileged" in i.message]
        assert privileged == [24]

    def test_custom_tags_match_including_syntax_line(self, tmp_path, monkeypatch, both_loaders):
        path = _write(tmp_path, "stack.yaml", CUSTOM_TAGS)
        c_sig, c_issues, _ = _with_loader(monkeypatch, both_loaders[0], tmp_path)
        p_sig, _, _ = _with_loader(monkeypatch, both_loaders[1], tmp_path)
        assert c_sig == p_sig
        syntax = [i for i in c_issues if i.issue_type == SYNTAX]
        assert len(syntax) == 1
        # The reported line is SafeLoader's mark, not the C loader's wording.
        with pytest.raises(yaml.YAMLError) as caught:
            list(yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader))
        assert syntax[0].line == caught.value.problem_mark.line + 1
        assert any("DBPassword" in i.message or "password" in i.message for i in c_issues)

    def test_multi_document_error_line_matches(self, tmp_path, monkeypatch, both_loaders):
        path = _write(tmp_path, "k8s.yaml", MULTI_BROKEN)
        c_sig, c_issues, _ = _with_loader(monkeypatch, both_loaders[0], tmp_path)
        p_sig, _, _ = _with_loader(monkeypatch, both_loaders[1], tmp_path)
        assert c_sig == p_sig
        syntax = [i for i in c_issues if i.issue_type == SYNTAX]
        assert len(syntax) == 1
        with pytest.raises(yaml.YAMLError) as caught:
            list(yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader))
        assert syntax[0].line == caught.value.problem_mark.line + 1

    def test_helm_template_is_not_a_syntax_error(self, tmp_path, monkeypatch, both_loaders):
        chart = tmp_path / "demo"
        (chart / "templates").mkdir(parents=True)
        (chart / "Chart.yaml").write_text("apiVersion: v2\nname: demo\nversion: 0.1.0\n")
        (chart / "templates" / "deploy.yaml").write_text(HELM_TEMPLATE)
        (chart / "values.yaml").write_text(
            'defaults: &defaults\n  password: "super-secret-value"\nservice:\n  <<: *defaults\n'
        )
        c_sig, c_issues, _ = _with_loader(monkeypatch, both_loaders[0], chart)
        p_sig, _, _ = _with_loader(monkeypatch, both_loaders[1], chart)
        assert c_sig == p_sig
        template_syntax = [
            i for i in c_issues if i.issue_type == SYNTAX and i.file_path.endswith("deploy.yaml")
        ]
        assert template_syntax == []
        assert any(
            i.file_path.endswith("deploy.yaml") and i.issue_type.value == "YAML_SECRET_EXPOSURE"
            for i in c_issues
        )
        assert any("password" in i.message for i in c_issues)

    def test_direct_analyzer_matches_on_a_single_document(
        self, tmp_path, monkeypatch, both_loaders
    ):
        text = 'privileged: true\npassword: "super-secret-value"\n'
        path = _write(tmp_path, "a.yaml", text)
        found = []
        for loader in both_loaders:
            monkeypatch.setattr(
                "hefesto.core.config_parse.loader_class", lambda loader=loader: loader
            )
            found.append(_sig(YamlAnalyzer().analyze(str(path), text)))
        assert found[0] == found[1]


class TestLibyamlFailClosed:
    def test_reader_error_is_a_syntax_finding_and_fails_the_gate(self, tmp_path, monkeypatch):
        path = _write(tmp_path, "broken.yaml", "a: 1\n")

        def boom(*_args, **_kwargs):
            # character is a code point: ReaderError.__str__ formats it with %x.
            raise yaml.reader.ReaderError(
                "<unicode string>", 0, 0, "unicode", "special characters are not allowed"
            )

        monkeypatch.setattr(yaml, "load_all", boom)
        runner = CliRunner()
        monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
        monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")
        result = runner.invoke(
            __import__("hefesto.cli.main", fromlist=["cli"]).cli,
            ["analyze", str(path), "--fail-on", "HIGH", "--no-config", "--severity", "LOW"],
        )
        text = _cli_text(result)
        assert result.exit_code == 1
        assert "YAML_SYNTAX_ERROR" in text
        assert "could not be analyzed" not in text
        assert "Gate passed" not in text

    def test_real_cparser_reader_error_fails_closed(self, tmp_path, monkeypatch):
        path = _write(tmp_path, "broken.yaml", "a: \x00\n")
        monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
        monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")
        runner = CliRunner()
        cli = __import__("hefesto.cli.main", fromlist=["cli"]).cli
        result = runner.invoke(
            cli,
            ["analyze", str(path), "--fail-on", "HIGH", "--no-config", "--severity", "LOW"],
        )
        text = _cli_text(result)
        assert result.exit_code == 1
        assert "YAML_SYNTAX_ERROR" in text
        assert "could not be analyzed" not in text
        # SafeLoader's wording. The libyaml loader says "control characters".
        assert "special characters are not allowed" in text

    def test_non_yaml_error_from_the_loader_is_not_analyzed(self, tmp_path, monkeypatch):
        path = _write(tmp_path, "broken.yaml", "a: 1\n")

        def boom(*_args, **_kwargs):
            raise RuntimeError("libyaml aborted")

        monkeypatch.setattr(yaml, "load_all", boom)
        monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
        monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")
        runner = CliRunner()
        cli = __import__("hefesto.cli.main", fromlist=["cli"]).cli
        result = runner.invoke(
            cli,
            ["analyze", str(path), "--fail-on", "CRITICAL", "--no-config"],
        )
        text = _cli_text(result)
        assert result.exit_code == 1
        assert "could not be analyzed" in text
        assert "Gate passed" not in text
        assert "RuntimeError" in text

    def test_non_utf8_yaml_is_analyzed(self, tmp_path, monkeypatch):
        path = tmp_path / "legacy.yaml"
        path.write_bytes(
            b'apiVersion: v1\nkind: ConfigMap\ndata:\n  key: "'
            + SECRET.encode("ascii")
            + b'"\n  note: "caf\xe9"\n'
        )
        monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
        monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")
        runner = CliRunner()
        cli = __import__("hefesto.cli.main", fromlist=["cli"]).cli
        result = runner.invoke(
            cli,
            ["analyze", str(path), "--fail-on", "CRITICAL", "--no-config", "--output", "json"],
        )
        text = _cli_text(result)
        assert result.exit_code == 1
        assert "YAML_SECRET_EXPOSURE" in text
        assert '"not_analyzed"' not in text
        assert "decoded_with_fallback" in text
        assert "latin-1" in text


def test_default_loader_is_csafe_when_present():
    chosen = loader_class()
    c_loader = getattr(yaml, "CSafeLoader", None)
    assert chosen is (c_loader if c_loader is not None else yaml.SafeLoader)
    assert chosen is not getattr(yaml, "Loader", None)
    assert chosen is not getattr(yaml, "FullLoader", None)
    assert chosen is not getattr(yaml, "UnsafeLoader", None)


def test_shebang_without_extension_is_still_supported(tmp_path):
    from hefesto.core.language_detector import LanguageDetector

    path = tmp_path / "build"
    path.write_text("#!/bin/bash\neval $1\n", encoding="utf-8")
    assert LanguageDetector.is_supported(path, path.read_text(encoding="utf-8"))
