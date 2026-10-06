"""Tests for .hefesto.yaml project config (discovery, validation, precedence).

Copyright (c) 2026 Narapa LLC, Miami, Florida
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.cli.main import analyze, cli
from hefesto.config.project_config import (
    SUPPORTED_KEYS,
    ConfigError,
    discover_config,
    find_config,
    load_config,
    validate_config,
)

MISFORMATTED = "def f( a,b ):\n    return a\n"
# Triggers a single CRITICAL EVAL_USAGE finding.
EVAL_SNIPPET = "def run(cmd):\n    return eval(cmd)\n"

ANALYZE_OPTIONS = {param.name for param in analyze.params}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fake repo root (contains .git) with one Python file in src/."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "mod.py").write_text("x = 1\n")
    return root


@pytest.fixture(autouse=True)
def _no_telemetry(monkeypatch):
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")


def _invoke(args):
    return CliRunner().invoke(cli, ["analyze", *args])


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_finds_config_in_start_dir(self, repo):
        cfg = repo / "src" / ".hefesto.yaml"
        cfg.write_text("severity: HIGH\n")
        assert find_config(repo / "src") == cfg

    def test_walks_up_to_parent(self, repo):
        cfg = repo / ".hefesto.yaml"
        cfg.write_text("severity: HIGH\n")
        assert find_config(repo / "src") == cfg

    def test_file_start_uses_its_directory(self, repo):
        cfg = repo / ".hefesto.yml"
        cfg.write_text("severity: HIGH\n")
        assert find_config(repo / "src" / "mod.py") == cfg

    def test_nearest_config_wins(self, repo):
        (repo / ".hefesto.yaml").write_text("severity: HIGH\n")
        nearest = repo / "src" / ".hefesto.yaml"
        nearest.write_text("severity: LOW\n")
        assert find_config(repo / "src" / "mod.py") == nearest

    def test_stops_at_repo_root(self, repo):
        # A config above the repo root (directory containing .git) is not used.
        (repo.parent / ".hefesto.yaml").write_text("severity: HIGH\n")
        assert find_config(repo / "src") is None

    def test_config_at_repo_root_is_used(self, repo):
        cfg = repo / ".hefesto.yaml"
        cfg.write_text("severity: HIGH\n")
        assert find_config(repo) == cfg

    def test_both_extensions_is_an_error(self, repo):
        (repo / ".hefesto.yaml").write_text("severity: HIGH\n")
        (repo / ".hefesto.yml").write_text("severity: LOW\n")
        with pytest.raises(ConfigError, match="keep only one"):
            find_config(repo / "src")

    def test_no_config(self, repo):
        assert find_config(repo / "src") is None

    def test_multiple_paths_first_wins_with_warning(self, repo):
        (repo / "src" / ".hefesto.yaml").write_text("severity: HIGH\n")
        (repo / "other").mkdir()
        chosen, warnings = discover_config([str(repo / "src"), str(repo / "other")])
        assert chosen == repo / "src" / ".hefesto.yaml"
        assert len(warnings) == 1 and "only one config" in warnings[0]

    def test_multiple_paths_same_config_no_warning(self, repo):
        (repo / ".hefesto.yaml").write_text("severity: HIGH\n")
        (repo / "other").mkdir()
        chosen, warnings = discover_config([str(repo / "src"), str(repo / "other")])
        assert chosen == repo / ".hefesto.yaml"
        assert warnings == []


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_all_keys_valid(self):
        values = validate_config(
            {
                "severity": "low",
                "output": "JSON",
                "exclude": ["tests/", " docs/ "],
                "exclude_types": ["long_function", "VERY_HIGH_COMPLEXITY"],
                "fail_on": "high",
                "quiet": True,
                "max_issues": 5,
                "format_check": True,
                "enable_memory_budget_gate": False,
            }
        )
        assert values == {
            "severity": "LOW",
            "output": "json",
            "exclude": "tests/,docs/",
            "exclude_types": "LONG_FUNCTION,VERY_HIGH_COMPLEXITY",
            "fail_on": "HIGH",
            "quiet": True,
            "max_issues": 5,
            "format_check": True,
            "enable_memory_budget_gate": False,
        }
        assert set(values) == set(SUPPORTED_KEYS)

    def test_comma_string_and_dashed_keys(self):
        assert validate_config({"exclude": "a/, b/", "fail-on": "LOW"}) == {
            "exclude": "a/,b/",
            "fail_on": "LOW",
        }

    def test_null_values_are_ignored(self):
        assert validate_config({"fail_on": None, "severity": "HIGH"}) == {"severity": "HIGH"}

    def test_empty_document(self):
        assert validate_config(None) == {}

    @pytest.mark.parametrize(
        "data, message",
        [
            ({"rules": {"complexity": 1}}, "rule thresholds are not configurable yet"),
            ({"sevrity": "HIGH"}, "unknown key 'sevrity'"),
            ({"severity": "URGENT"}, "'severity' must be one of"),
            ({"severity": 3}, "'severity' must be one of"),
            ({"output": "xml"}, "'output' must be one of"),
            ({"fail_on": "nope"}, "'fail_on' must be one of"),
            ({"format_check": "yes please"}, "'format_check' must be true or false"),
            ({"quiet": 1}, "'quiet' must be true or false"),
            ({"max_issues": 0}, "'max_issues' must be a positive integer"),
            ({"max_issues": True}, "'max_issues' must be a positive integer"),
            ({"exclude": [1, 2]}, "'exclude' must be a list of strings"),
            ({"exclude_types": ["NOT_A_TYPE"]}, "unknown issue type(s): NOT_A_TYPE"),
            ({"fail_on": "LOW", "fail-on": "HIGH"}, "set more than once"),
        ],
    )
    def test_bad_values(self, data, message):
        with pytest.raises(ConfigError) as exc:
            validate_config(data)
        assert message in str(exc.value)

    def test_allowed_keys_limit_supported_keys(self):
        allowed = set(SUPPORTED_KEYS) - {"format_check"}
        assert validate_config({"severity": "HIGH"}, allowed) == {"severity": "HIGH"}
        with pytest.raises(ConfigError) as exc:
            validate_config({"format_check": True}, allowed)
        assert "unknown key 'format_check'" in str(exc.value)
        assert "no --format-check option" in str(exc.value)
        assert "format_check" not in str(exc.value).split("supported:")[1]

    def test_every_key_maps_to_an_analyze_option(self):
        assert set(SUPPORTED_KEYS) <= ANALYZE_OPTIONS

    def test_top_level_must_be_mapping(self):
        with pytest.raises(ConfigError, match="mapping"):
            validate_config(["severity", "HIGH"])

    def test_invalid_yaml(self, tmp_path):
        cfg = tmp_path / ".hefesto.yaml"
        cfg.write_text("severity: [HIGH\n")
        with pytest.raises(ConfigError, match="invalid YAML"):
            load_config(cfg)

    def test_load_empty_file(self, tmp_path):
        cfg = tmp_path / ".hefesto.yaml"
        cfg.write_text("# nothing yet\n")
        loaded = load_config(cfg)
        assert loaded.path == cfg and loaded.values == {}


# ---------------------------------------------------------------------------
# CLI integration and precedence
# ---------------------------------------------------------------------------


class TestCli:
    def test_discovered_config_is_applied_and_announced(self, repo):
        (repo / ".hefesto.yaml").write_text("severity: low\nexclude: [vendor/]\n")
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 0, result.output
        assert f"Config: {repo / '.hefesto.yaml'}" in result.output
        assert "Minimum severity: LOW" in result.output
        assert "Excluding: vendor/" in result.output

    def test_cli_flag_beats_config(self, repo):
        (repo / ".hefesto.yaml").write_text("severity: low\n")
        result = _invoke([str(repo / "src"), "--severity", "HIGH"])
        assert result.exit_code == 0, result.output
        assert "Minimum severity: HIGH" in result.output

    def test_cli_flag_equal_to_default_still_beats_config(self, repo):
        # --severity MEDIUM is the default value, but it was given explicitly.
        (repo / ".hefesto.yaml").write_text("severity: low\n")
        result = _invoke([str(repo / "src"), "--severity", "MEDIUM"])
        assert "Minimum severity: MEDIUM" in result.output

    def test_no_config_flag_ignores_file(self, repo):
        (repo / ".hefesto.yaml").write_text("severity: low\n")
        result = _invoke([str(repo / "src"), "--no-config"])
        assert result.exit_code == 0, result.output
        assert "Config:" not in result.output
        assert "Minimum severity: MEDIUM" in result.output

    def test_no_config_skips_invalid_file(self, repo):
        (repo / ".hefesto.yaml").write_text("rules: {}\n")
        result = _invoke([str(repo / "src"), "--no-config"])
        assert result.exit_code == 0, result.output

    def test_explicit_config_path(self, repo, tmp_path):
        (repo / ".hefesto.yaml").write_text("severity: low\n")
        explicit = tmp_path / "ci.yaml"
        explicit.write_text("severity: critical\n")
        result = _invoke([str(repo / "src"), "--config", str(explicit)])
        assert result.exit_code == 0, result.output
        assert f"Config: {explicit}" in result.output
        assert "Minimum severity: CRITICAL" in result.output

    def test_config_and_no_config_conflict(self, repo, tmp_path):
        explicit = tmp_path / "ci.yaml"
        explicit.write_text("severity: low\n")
        result = _invoke([str(repo / "src"), "--config", str(explicit), "--no-config"])
        assert result.exit_code == 2
        assert "cannot be used together" in result.output

    def test_invalid_config_exits_2_with_clear_error(self, repo):
        (repo / ".hefesto.yaml").write_text("severity: urgent\n")
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 2
        assert "invalid Hefesto config in" in result.output
        assert "'severity' must be one of" in result.output

    def test_quiet_from_config(self, repo):
        (repo / ".hefesto.yaml").write_text("quiet: true\n")
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 0, result.output
        assert "Analyzing:" not in result.output

    def test_fail_on_and_exclude_types_from_config(self, repo):
        (repo / "src" / "evil.py").write_text(EVAL_SNIPPET)
        (repo / ".hefesto.yaml").write_text("fail_on: HIGH\n")
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 1, result.output
        assert "EVAL_USAGE" in result.output

        # exclude_types from config applies to the gate.
        (repo / ".hefesto.yaml").write_text("fail_on: HIGH\nexclude_types: [eval_usage]\n")
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 0, result.output

        # An explicit --exclude-types replaces the config value.
        result = _invoke([str(repo / "src"), "--exclude-types", "LONG_FUNCTION"])
        assert result.exit_code == 1, result.output

    def test_cli_fail_on_beats_config(self, repo):
        (repo / "src" / "evil.py").write_text(EVAL_SNIPPET)
        (repo / ".hefesto.yaml").write_text("fail_on: LOW\nexclude: [nothing/]\n")
        result = _invoke([str(repo / "src"), "--exclude", "evil.py"])
        assert result.exit_code == 0, result.output
        assert "Excluding: evil.py" in result.output
        assert "nothing/" not in result.output

    def test_exclude_from_config_skips_files(self, repo):
        (repo / "src" / "evil.py").write_text(EVAL_SNIPPET)
        (repo / ".hefesto.yaml").write_text("fail_on: LOW\nexclude: [evil.py]\n")
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 0, result.output
        assert "EVAL_USAGE" not in result.output

    def test_format_check_from_config(self, repo):
        pytest.importorskip("black")
        (repo / "src" / "bad.py").write_text(MISFORMATTED)
        (repo / ".hefesto.yaml").write_text("format_check: true\nfail_on: LOW\n")
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 1, result.output
        assert "FORMAT_DRIFT" in result.output

        # Explicit CLI --fail-on overrides the config's fail_on.
        result = _invoke([str(repo / "src"), "--fail-on", "CRITICAL"])
        assert result.exit_code == 0, result.output
        assert "FORMAT_DRIFT" in result.output

        # exclude_types from config applies to FORMAT_DRIFT in the gate.
        (repo / ".hefesto.yaml").write_text(
            "format_check: true\nfail_on: LOW\nexclude_types: [FORMAT_DRIFT]\n"
        )
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 0, result.output

    def test_format_check_false_in_config(self, repo):
        pytest.importorskip("black")
        (repo / "src" / "bad.py").write_text(MISFORMATTED)
        (repo / ".hefesto.yaml").write_text("format_check: false\n")
        result = _invoke([str(repo / "src"), "--severity", "LOW"])
        assert result.exit_code == 0, result.output
        assert "FORMAT_DRIFT" not in result.output

    def test_output_json_from_config_keeps_stdout_pure(self, repo):
        (repo / ".hefesto.yaml").write_text("output: json\n")
        result = subprocess.run(
            [sys.executable, "-m", "hefesto.cli.main", "analyze", str(repo / "src")],
            capture_output=True,
            text=True,
            timeout=120,
            env=dict(os.environ, HEFESTO_TELEMETRY="0"),
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "summary" in data
        assert "Config:" in result.stderr

    def test_no_config_file_means_unchanged_defaults(self, repo):
        result = _invoke([str(repo / "src")])
        assert result.exit_code == 0, result.output
        assert "Config:" not in result.output
        assert "Minimum severity: MEDIUM" in result.output
