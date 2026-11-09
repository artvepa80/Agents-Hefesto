"""The weekly full-matrix workflow must run the same steps as the PR workflows.

``weekly-full-matrix.yml`` copies the ``lint-and-test`` steps of ``ci.yml``
and the ``multilang-smoke`` steps of ``multilang-smoke.yml``. These tests
fail when one side changes without the other.
"""

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).parents[1] / ".github" / "workflows"
ALL_PYTHONS = ["3.11", "3.12", "3.13", "3.14", "3.15"]

# Steps the weekly copy leaves out on purpose.
CI_ONLY_STEPS = {"Commit metadata (PR range)", "Upload coverage"}


def _load(name: str) -> dict:
    """Load a workflow. PyYAML 1.1 treats the key ``on`` as boolean true."""
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def _without_checkout_ref(steps: list) -> list:
    """The weekly copy checks out ``main``; otherwise the steps are identical."""
    out = []
    for step in steps:
        step = dict(step)
        if str(step.get("uses", "")).startswith("actions/checkout@"):
            step.pop("with", None)
        out.append(step)
    return out


def test_triggers_and_permissions():
    data = _load("weekly-full-matrix.yml")
    assert set(data["on"]) == {"schedule", "workflow_dispatch"}
    assert data["permissions"] == {"contents": "read"}


def test_lint_and_test_steps_match_ci():
    ci = _load("ci.yml")["jobs"]["lint-and-test"]["steps"]
    expected = [s for s in ci if s.get("name") not in CI_ONLY_STEPS]
    weekly = _load("weekly-full-matrix.yml")["jobs"]["lint-and-test-full"]
    assert _without_checkout_ref(weekly["steps"]) == _without_checkout_ref(expected)
    assert weekly["strategy"] == {
        "fail-fast": False,
        "matrix": {"python-version": ALL_PYTHONS},
    }


def test_multilang_smoke_steps_match():
    smoke = _load("multilang-smoke.yml")["jobs"]["multilang-smoke"]
    weekly = _load("weekly-full-matrix.yml")["jobs"]["multilang-smoke-full"]
    assert _without_checkout_ref(weekly["steps"]) == _without_checkout_ref(smoke["steps"])
    assert weekly["strategy"] == {
        "fail-fast": False,
        "matrix": {"python-version": ALL_PYTHONS},
    }


def test_weekly_jobs_run_only_on_main():
    jobs = _load("weekly-full-matrix.yml")["jobs"]
    for job in jobs.values():
        assert job["if"] == "github.ref == 'refs/heads/main'"
        checkout = job["steps"][0]
        assert checkout["uses"].startswith("actions/checkout@")
        assert checkout["with"] == {"ref": "main"}
