"""YAML_SYNTAX_ERROR must only flag YAML that really does not parse.

Two valid inputs were reported as syntax errors:

* multi-document streams (``---`` between documents), the normal form of
  Kubernetes manifests, because the check used a single-document loader;
* Helm chart templates (``<chart>/templates/**``), which are Go templates
  rendered into YAML by Helm and are not YAML until rendered.
"""

from hefesto.analyzers.devops.yaml_analyzer import YamlAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.core.analyzer_engine import AnalyzerEngine

SYNTAX = AnalysisIssueType.YAML_SYNTAX_ERROR

MULTI_DOC = """apiVersion: v1
kind: Service
metadata:
  name: web
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 1
"""

HELM_TEMPLATE = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "chart.fullname" . }}
  labels:
    {{- include "chart.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
"""


def _syntax(path, content):
    return [i for i in YamlAnalyzer().analyze(str(path), content) if i.issue_type == SYNTAX]


def _chart(tmp_path):
    chart = tmp_path / "mychart"
    (chart / "templates" / "tests").mkdir(parents=True)
    (chart / "Chart.yaml").write_text("apiVersion: v2\nname: mychart\nversion: 0.1.0\n")
    return chart


class TestMultiDocument:
    def test_valid_multi_document_stream_is_not_an_error(self, tmp_path):
        assert _syntax(tmp_path / "k8s.yaml", MULTI_DOC) == []

    def test_leading_and_trailing_separators(self, tmp_path):
        assert _syntax(tmp_path / "k8s.yaml", "---\n" + MULTI_DOC + "---\n") == []

    def test_error_in_a_later_document_is_reported_on_its_line(self, tmp_path):
        broken = MULTI_DOC + "---\nkind: ConfigMap\ndata: [unclosed\n"
        issues = _syntax(tmp_path / "k8s.yaml", broken)
        assert len(issues) == 1
        assert issues[0].line >= broken.count("\n") - 1

    def test_single_broken_document_still_reported(self, tmp_path):
        assert len(_syntax(tmp_path / "a.yaml", "key: [unclosed\n")) == 1


class TestHelmTemplates:
    def test_chart_template_is_not_parsed_as_yaml(self, tmp_path):
        chart = _chart(tmp_path)
        assert _syntax(chart / "templates" / "deployment.yaml", HELM_TEMPLATE) == []

    def test_nested_chart_template_directory(self, tmp_path):
        chart = _chart(tmp_path)
        path = chart / "templates" / "tests" / "test-connection.yaml"
        assert _syntax(path, HELM_TEMPLATE) == []

    def test_template_syntax_outside_a_chart_is_still_checked(self, tmp_path):
        # No Chart.yaml: e.g. an Ansible file with an unquoted "{{" is a real error.
        (tmp_path / "templates").mkdir()
        assert len(_syntax(tmp_path / "templates" / "deployment.yaml", HELM_TEMPLATE)) == 1

    def test_chart_file_without_template_actions_is_still_checked(self, tmp_path):
        chart = _chart(tmp_path)
        assert len(_syntax(chart / "templates" / "raw.yaml", "key: [unclosed\n")) == 1

    def test_chart_metadata_files_are_still_checked(self, tmp_path):
        chart = _chart(tmp_path)
        assert len(_syntax(chart / "values.yaml", "image: {{ .Values.x }}\n")) == 1

    def test_other_rules_still_run_on_chart_templates(self, tmp_path):
        chart = _chart(tmp_path)
        content = HELM_TEMPLATE + "  awsKey: AKIAABCDEFGHIJKLMNOP\n"
        rules = {
            i.issue_type
            for i in YamlAnalyzer().analyze(str(chart / "templates" / "s.yaml"), content)
        }
        assert AnalysisIssueType.YAML_SECRET_EXPOSURE in rules
        assert SYNTAX not in rules


def test_engine_reports_no_syntax_errors_for_a_chart_and_manifests(tmp_path):
    chart = _chart(tmp_path)
    (chart / "templates" / "deployment.yaml").write_text(HELM_TEMPLATE)
    (tmp_path / "manifests.yaml").write_text(MULTI_DOC)
    report = AnalyzerEngine(severity_threshold="LOW").analyze_path(str(tmp_path))
    rules = {i.issue_type for fr in report.file_results for i in fr.issues}
    assert len(report.file_results) >= 3
    assert SYNTAX not in rules
