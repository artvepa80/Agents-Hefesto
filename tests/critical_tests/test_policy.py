"""Tests for the ``critical_tests`` section of .hefesto.yaml.

Copyright (c) 2026 Narapa LLC, Miami, Florida
"""

from pathlib import Path

import pytest

from hefesto.config.project_config import ConfigError, load_config, validate_config
from hefesto.critical_tests.policy import (
    CriticalTestsPolicy,
    parse_critical_tests,
    parse_nodeid,
)

VALID = {
    "enforcement": "block",
    "entries": [
        {
            "id": "authorization",
            "requirement": "Users must not access resources they do not own.",
            "tests": [
                "tests/test_auth.py::test_denies_other_user",
                "tests/test_auth.py::TestAdmin::test_admin_only",
            ],
        },
        {
            "id": "billing",
            "requirement": "Invoices are never negative.",
            "tests": ["tests/billing/test_invoice.py::test_no_negative_total"],
            "enforcement": "warn",
        },
    ],
}


def test_valid_policy_parses_with_inherited_enforcement():
    policy = parse_critical_tests(VALID)
    assert isinstance(policy, CriticalTestsPolicy)
    assert policy.enforcement == "block"
    auth, billing = policy.entries
    assert auth.id == "authorization"
    assert auth.enforcement == "block"  # inherited from the section
    assert billing.enforcement == "warn"  # per-entry override
    assert auth.tests[1].path == "tests/test_auth.py"
    assert auth.tests[1].qualname == "TestAdmin::test_admin_only"


def test_global_enforcement_defaults_to_warn():
    data = {"entries": [dict(VALID["entries"][0])]}
    policy = parse_critical_tests(data)
    assert policy.enforcement == "warn"
    assert policy.entries[0].enforcement == "warn"


def test_tests_by_file_groups_nodeids():
    grouped = parse_critical_tests(VALID).tests_by_file()
    assert grouped["tests/test_auth.py"] == [
        ("authorization", "test_denies_other_user"),
        ("authorization", "TestAdmin::test_admin_only"),
    ]
    assert list(grouped) == ["tests/test_auth.py", "tests/billing/test_invoice.py"]


@pytest.mark.parametrize(
    "data, message",
    [
        ("block", "must be a mapping"),
        ({"entries": []}, "at least one entry"),
        ({"entries": "x"}, "must be a list"),
        ({}, "'entries' is required"),
        ({"enforcement": "fail", "entries": VALID["entries"]}, "warn, block"),
        ({"entries": VALID["entries"], "files": ["a.py"]}, "unknown key 'files'"),
        (
            {"entries": [{"id": "a", "requirement": "r", "tests": ["t.py::t"], "x": 1}]},
            "unknown key 'x'",
        ),
        ({"entries": [{"requirement": "r", "tests": ["t.py::t"]}]}, "'id' is required"),
        ({"entries": [{"id": "a", "tests": ["t.py::t"]}]}, "'requirement' is required"),
        (
            {"entries": [{"id": "a", "requirement": " ", "tests": ["t.py::t"]}]},
            "'requirement' must be a non-empty string",
        ),
        ({"entries": [{"id": "a", "requirement": "r", "tests": []}]}, "at least one test"),
        (
            {
                "entries": [
                    {"id": "a", "requirement": "r", "tests": ["t.py::t"]},
                    {"id": "a", "requirement": "r", "tests": ["t.py::u"]},
                ]
            },
            "duplicate id 'a'",
        ),
        (
            {"entries": [{"id": "a", "requirement": "r", "tests": ["t.py::t", "t.py::t"]}]},
            "listed more than once",
        ),
        (
            {
                "entries": [
                    {"id": "a", "requirement": "r", "tests": ["t.py::t"], "enforcement": "error"}
                ]
            },
            "warn, block",
        ),
    ],
)
def test_invalid_policy_is_rejected(data, message):
    with pytest.raises(ConfigError, match=message):
        parse_critical_tests(data)


@pytest.mark.parametrize(
    "nodeid",
    [
        "tests/test_a.py::test_x[1]",  # parametrized ids are not accepted
        "tests/test_a.py",
        "tests/test_a.txt::test_x",
        "/abs/test_a.py::test_x",
        "../test_a.py::test_x",
        "tests/test_a.py::",
        "tests/test_a.py::test-x",
        "tests\\test_a.py::test_x",
    ],
)
def test_invalid_nodeids(nodeid):
    with pytest.raises(ConfigError):
        parse_nodeid("entries[0].tests[0]", nodeid)


def test_nodeid_leading_dot_slash_is_normalized():
    ref = parse_nodeid("t", "./tests/test_a.py::TestA::test_x")
    assert ref.path == "tests/test_a.py"
    assert ref.qualname == "TestA::test_x"
    assert ref.nodeid == "tests/test_a.py::TestA::test_x"


# ---------------------------------------------------------------- integration


def test_section_absent_means_no_policy(tmp_path: Path):
    cfg = tmp_path / ".hefesto.yaml"
    cfg.write_text("severity: high\n")
    loaded = load_config(cfg)
    assert loaded.critical_tests is None
    assert loaded.values == {"severity": "HIGH"}


def test_section_present_is_parsed_and_not_passed_to_analyze(tmp_path: Path):
    cfg = tmp_path / ".hefesto.yaml"
    cfg.write_text(
        "severity: high\n"
        "critical_tests:\n"
        "  entries:\n"
        "    - id: auth\n"
        "      requirement: Only owners read their data.\n"
        "      tests: [tests/test_auth.py::test_owner_only]\n"
    )
    # The CLI passes only analyze option names as allowed_keys.
    loaded = load_config(cfg, allowed_keys={"severity", "exclude"})
    assert "critical_tests" not in loaded.values
    assert loaded.critical_tests is not None
    assert loaded.critical_tests.entries[0].id == "auth"


def test_invalid_section_fails_config_validation():
    with pytest.raises(ConfigError, match="critical_tests"):
        validate_config({"critical_tests": {"entries": []}})


def test_null_section_means_no_policy(tmp_path: Path):
    cfg = tmp_path / ".hefesto.yaml"
    cfg.write_text("critical_tests:\n")
    assert load_config(cfg).critical_tests is None


# ---------------------------------------------------------------- CLI


def _repo_with_config(tmp_path: Path, config: str) -> Path:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "mod.py").write_text("x = 1\n")
    (root / ".hefesto.yaml").write_text(config)
    return root


def test_analyze_accepts_a_valid_section(tmp_path: Path):
    from click.testing import CliRunner

    from hefesto.cli.main import cli

    root = _repo_with_config(
        tmp_path,
        "critical_tests:\n"
        "  enforcement: block\n"
        "  entries:\n"
        "    - id: auth\n"
        "      requirement: Only owners read their data.\n"
        "      tests: [tests/test_auth.py::test_owner_only]\n",
    )
    result = CliRunner().invoke(cli, ["analyze", str(root / "mod.py"), "--quiet"])
    assert result.exit_code == 0, result.output


def test_analyze_rejects_an_invalid_section(tmp_path: Path):
    from click.testing import CliRunner

    from hefesto.cli.main import cli

    root = _repo_with_config(tmp_path, "critical_tests:\n  entries: []\n")
    result = CliRunner().invoke(cli, ["analyze", str(root / "mod.py"), "--quiet"])
    assert result.exit_code == 2
    assert "critical_tests" in result.output
