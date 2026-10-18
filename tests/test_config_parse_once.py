"""Each config file is parsed once.

The guard counts parser calls. It does not use wall-clock time, so a slow CI
machine cannot fail it. A document ``yaml.parse`` rejects is loaded once,
with ``SafeLoader``. A ``CSafeLoader`` exception after that scan accepted
the document (a timestamp ``ValueError``) is the extra ``SafeLoader`` parse
when libyaml is installed, so the mark and the message stay the ones
``SafeLoader`` reports.
"""

import importlib
import json

import pytest
import yaml

from hefesto.analyzers.devops import toml_analyzer
from hefesto.core.analyzer_engine import AnalyzerEngine

_ALLOWED_LOADERS = {yaml.SafeLoader}
if getattr(yaml, "CSafeLoader", None) is not None:
    _ALLOWED_LOADERS.add(yaml.CSafeLoader)


@pytest.fixture
def parses(monkeypatch):
    counts = {"yaml": 0, "json": 0, "toml": 0, "safe_load": 0, "loaders": []}
    real_load_all = yaml.load_all
    real_json = json.loads
    real_toml = toml_analyzer.tomli.loads

    def load_all(stream, Loader=None):
        if Loader not in _ALLOWED_LOADERS:
            raise AssertionError("refusing loader %r" % (Loader,))
        counts["yaml"] += 1
        counts["loaders"].append(Loader)
        return real_load_all(stream, Loader=Loader)

    def safe_load(*_args, **_kwargs):
        counts["safe_load"] += 1
        raise AssertionError("safe_load is the pure-Python loader")

    def loads(text, *args, **kwargs):
        counts["json"] += 1
        return real_json(text, *args, **kwargs)

    def toml_loads(text, *args, **kwargs):
        counts["toml"] += 1
        return real_toml(text, *args, **kwargs)

    monkeypatch.setattr(yaml, "load_all", load_all)
    monkeypatch.setattr(yaml, "safe_load", safe_load)
    monkeypatch.setattr(yaml, "safe_load_all", safe_load)
    monkeypatch.setattr(yaml, "unsafe_load", safe_load)
    monkeypatch.setattr(json, "loads", loads)
    monkeypatch.setattr(toml_analyzer.tomli, "loads", toml_loads)
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    monkeypatch.setenv("HEFESTO_NO_UPSELL", "1")
    return counts


def _engine():
    return AnalyzerEngine(severity_threshold="LOW", quiet=True)


def _write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _analyze(root):
    _engine().analyze_path(str(root))


K8S = """apiVersion: v1
kind: ConfigMap
metadata:
  name: cfg
  labels: &labels
    app: demo
data:
  token: &tok abcdefghijklmnop
  copied: *tok
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels: &web
    app: demo
spec:
  template:
    metadata:
      labels:
        <<: *web
    spec:
      containers:
      - name: web
        image: nginx
"""

CFN_YAML = """AWSTemplateFormatVersion: "2010-09-09"
Resources:
  Bucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: demo-bucket
"""

SERVERLESS = """service: demo
provider:
  name: aws
  runtime: python3.12
"""

HELM_TEMPLATE = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
"""


def test_yaml_file_is_parsed_once_on_a_directory_and_as_a_single_file(tmp_path, parses):
    directory = tmp_path / "dir"
    directory.mkdir()
    _write(directory, "app.yaml", K8S)
    _analyze(directory)
    assert parses["yaml"] == 1
    assert parses["safe_load"] == 0

    single = _write(tmp_path, "one.yaml", K8S)
    parses["yaml"] = 0
    _analyze(single)
    # Discovery used to classify the file before analysis, which parsed it
    # again on a different string. One call means that extra parse is gone
    # and detection shares the analyzer's parse.
    assert parses["yaml"] == 1
    assert parses["json"] == 0
    assert parses["toml"] == 0


def test_two_yaml_files_are_two_parses(tmp_path, parses):
    _write(tmp_path, "a.yaml", "a: 1\n")
    _write(tmp_path, "b.yml", "b: 2\n")
    _analyze(tmp_path)
    assert parses["yaml"] == 2
    assert parses["safe_load"] == 0


def test_cloud_yaml_formats_are_parsed_once(tmp_path, parses):
    _write(tmp_path, "stack.yaml", CFN_YAML)
    _write(tmp_path, "serverless.yml", SERVERLESS)
    chart = tmp_path / "chart"
    _write(chart, "Chart.yaml", "apiVersion: v2\nname: demo\nversion: 0.1.0\n")
    _write(chart, "values.yaml", "replicaCount: 1\nimage: nginx\n")
    _write(chart / "templates", "deploy.yaml", HELM_TEMPLATE)
    _analyze(tmp_path)
    # Chart.yaml, values.yaml, stack.yaml, serverless.yml. The template is
    # Go text and is not parsed.
    assert parses["yaml"] == 4
    assert parses["safe_load"] == 0


def test_helm_template_file_is_not_parsed(tmp_path, parses):
    chart = tmp_path / "chart"
    _write(chart, "Chart.yaml", "apiVersion: v2\nname: demo\nversion: 0.1.0\n")
    template = _write(chart / "templates", "deploy.yaml", HELM_TEMPLATE)
    _analyze(template)
    assert parses["yaml"] == 0


def test_parser_error_is_one_safeloader_parse(tmp_path, parses, monkeypatch):
    """``yaml.parse`` rejects this stream, so ``CSafeLoader`` is not called."""
    path = _write(tmp_path, "bad.yaml", "a: [\n")
    _analyze(path)
    assert parses["loaders"] == [yaml.SafeLoader]
    monkeypatch.setattr("hefesto.core.config_parse.loader_class", lambda: yaml.SafeLoader)
    parses["yaml"] = 0
    parses["loaders"] = []
    _analyze(path)
    assert parses["loaders"] == [yaml.SafeLoader]


def test_c_loader_valueerror_is_reparsed_with_safeloader(tmp_path, parses, monkeypatch):
    """A bad timestamp is events the parser accepts. ``load_all`` raises.

    With libyaml, ``CSafeLoader`` runs and ``SafeLoader`` runs again.
    Forcing ``SafeLoader`` is one call: the event scan is not a second load.
    """
    path = _write(tmp_path, "bad.yaml", "created: 2001-13-01\n")
    _analyze(path)
    if getattr(yaml, "CSafeLoader", None) is None:
        assert parses["loaders"] == [yaml.SafeLoader]
    else:
        assert parses["loaders"] == [yaml.CSafeLoader, yaml.SafeLoader]
    monkeypatch.setattr("hefesto.core.config_parse.loader_class", lambda: yaml.SafeLoader)
    parses["loaders"] = []
    _analyze(path)
    assert parses["loaders"] == [yaml.SafeLoader]


def test_json_toml_and_terraform_json_parse_once(tmp_path, parses):
    _write(tmp_path, "app.json", '{"name": "demo", "password": "super-secret-value"}\n')
    _write(
        tmp_path,
        "azure.json",
        '{"$schema": "https://schema.management.azure.com/schemas/'
        '2019-04-01/deploymentTemplate.json#", "contentVersion": "1.0.0.0",'
        ' "resources": []}\n',
    )
    _write(
        tmp_path,
        "stack.json",
        '{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}\n',
    )
    _write(tmp_path, "config.toml", '[tool]\nname = "demo"\n')
    _write(tmp_path, "stack.tf.json", '{"resource": {"aws_s3_bucket": {"b": {}}}}\n')
    _analyze(tmp_path)
    # app.json, azure.json and stack.json. stack.tf.json is Terraform.
    assert parses["json"] == 3
    assert parses["toml"] == 1
    assert parses["yaml"] == 0
    assert parses["safe_load"] == 0


_REGEX_FORMATS = [
    (
        "Makefile",
        "all:\n\t@echo hi\n",
        "hefesto.analyzers.devops.makefile_analyzer",
        "MakefileAnalyzer",
    ),
    (
        "Jenkinsfile",
        "pipeline { agent any }\n",
        "hefesto.analyzers.devops.groovy_jenkins_analyzer",
        "GroovyJenkinsAnalyzer",
    ),
    (
        "script.ps1",
        'Write-Output "hi"\n',
        "hefesto.analyzers.devops.powershell_analyzer",
        "PowerShellAnalyzer",
    ),
    (
        "Dockerfile",
        "FROM ubuntu:22.04\nUSER root\n",
        "hefesto.analyzers.devops.dockerfile_analyzer",
        "DockerfileAnalyzer",
    ),
    (
        "main.tf",
        'resource "aws_s3_bucket" "b" {\n  bucket = "demo"\n}\n',
        "hefesto.analyzers.devops.terraform_analyzer",
        "TerraformAnalyzer",
    ),
    (
        "script.sh",
        "#!/bin/bash\necho hi\n",
        "hefesto.analyzers.devops.shell_analyzer",
        "ShellAnalyzer",
    ),
    (
        "query.sql",
        "SELECT id FROM users;\n",
        "hefesto.analyzers.devops.sql_analyzer",
        "SqlAnalyzer",
    ),
]


@pytest.mark.parametrize("name,text,module_name,class_name", _REGEX_FORMATS)
def test_regex_config_format_is_analyzed_once(
    tmp_path, parses, monkeypatch, name, text, module_name, class_name
):
    cls = getattr(importlib.import_module(module_name), class_name)
    calls = []
    original = cls.analyze

    def wrapped(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(cls, "analyze", wrapped)
    _analyze(_write(tmp_path, name, text))
    assert calls == [1]
    assert parses["yaml"] == 0
    assert parses["json"] == 0
    assert parses["toml"] == 0
    assert parses["safe_load"] == 0
