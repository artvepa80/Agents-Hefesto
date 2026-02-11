from click.testing import CliRunner

from hefesto.cli.main import cli
from hefesto.core.drift_runner import DriftRunner, DriftRunResult


class FakeFinding:
    def __init__(self, severity="LOW"):
        self.severity = severity
        self.rule_id = "TEST_RULE"
        self.evidence = "Test evidence"


def test_drift_command_wires_args(monkeypatch, tmp_path):
    template = tmp_path / "template.yml"
    template.write_text("Resources: {}", encoding="utf-8")

    calls = {}

    def fake_run(self, template_path, *, region, stack_name=None, tags=None, autoresolve=True):
        calls["template_path"] = template_path
        calls["region"] = region
        calls["stack_name"] = stack_name
        calls["tags"] = tags
        calls["autoresolve"] = autoresolve

        return DriftRunResult(
            findings=[],
            summary={
                "region": region,
                "stack_name": stack_name,
                "autoresolve": autoresolve,
                "resolved_resources": 3,
                "findings": 0,
            },
        )

    monkeypatch.setattr(DriftRunner, "run", fake_run)

    r = CliRunner()
    res = r.invoke(
        cli,
        [
            "drift",
            str(template),
            "--region",
            "us-east-1",
            "--stack-name",
            "MyStack",
            "--tags",
            "env=prod,team=narapa",
        ],
    )

    assert res.exit_code == 0
    assert calls["region"] == "us-east-1"
    assert calls["stack_name"] == "MyStack"
    assert calls["tags"] == {"env": "prod", "team": "narapa"}
    assert calls["autoresolve"] is True
    assert "Region: us-east-1" in res.output
    assert "Stack: MyStack" in res.output


def test_drift_command_fails_on_high_severity(monkeypatch, tmp_path):
    template = tmp_path / "template.yml"
    template.write_text("Resources: {}", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return DriftRunResult(
            findings=[FakeFinding("HIGH")],
            summary={
                "region": "us-east-1",
                "findings": 1,
                "autoresolve": True,
                "resolved_resources": 0,
            },
        )

    monkeypatch.setattr(DriftRunner, "run", fake_run)

    r = CliRunner()
    res = r.invoke(cli, ["drift", str(template), "--region", "us-east-1"])

    assert res.exit_code == 2
    assert "HIGH" in res.output
