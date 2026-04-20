"""Tests for scripts/verify_readme.py version parity checking."""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "verify_readme.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_readme_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_readme_script"] = module
    spec.loader.exec_module(module)
    return module


def _setup_repo(tmp_path: Path, version: str, files: dict[str, str]) -> Path:
    """Create a fake repo layout with pyproject.toml + given files."""
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "hefesto-ai"\nversion = "{version}"\n'
    )
    for rel_path, content in files.items():
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return tmp_path


def test_all_files_match_passes_with_exit_0(tmp_path):
    mod = _load_module()
    repo = _setup_repo(
        tmp_path,
        "4.11.4",
        {
            "README.md": (
                "uses: artvepa80/Agents-Hefesto@v4.11.4\n"
                "## CLI Reference (v4.11.4)\n"
                "rev: v4.11.4\n"
            ),
            "llms.txt": "- uses: artvepa80/Agents-Hefesto@v4.11.4\n",
            "server.json": '{"version": "4.11.4"}\n',
            ".well-known/agent-card.json": '{"version": "4.11.4"}\n',
            "skill/SKILL.md": "Version: 4.11.4\n",
            ".github/copilot-instructions.md": (
                "- **Version:** 4.11.4\n" "- uses: artvepa80/Agents-Hefesto@v4.11.4\n"
            ),
        },
    )
    errors = mod.check_version_parity(repo, "4.11.4")
    assert errors == []


def test_llms_txt_drift_detected_on_action_ref(tmp_path):
    mod = _load_module()
    repo = _setup_repo(
        tmp_path,
        "4.11.4",
        {
            "README.md": (
                "uses: artvepa80/Agents-Hefesto@v4.11.4\n"
                "## CLI Reference (v4.11.4)\n"
                "rev: v4.11.4\n"
            ),
            "llms.txt": "- uses: artvepa80/Agents-Hefesto@v4.11.1\n",  # drift
            "server.json": '{"version": "4.11.4"}\n',
            ".well-known/agent-card.json": '{"version": "4.11.4"}\n',
            "skill/SKILL.md": "Version: 4.11.4\n",
            ".github/copilot-instructions.md": (
                "- **Version:** 4.11.4\n" "- uses: artvepa80/Agents-Hefesto@v4.11.4\n"
            ),
        },
    )
    errors = mod.check_version_parity(repo, "4.11.4")
    assert len(errors) == 1
    assert "llms.txt:1" in errors[0]
    assert "4.11.1" in errors[0]
    assert "expected 4.11.4" in errors[0]


def test_skill_md_version_case_insensitive_match(tmp_path):
    """Regex must match 'Version:' (capital V) as used in SKILL.md."""
    mod = _load_module()
    repo = _setup_repo(
        tmp_path,
        "4.11.4",
        {
            "README.md": (
                "uses: artvepa80/Agents-Hefesto@v4.11.4\n"
                "## CLI Reference (v4.11.4)\n"
                "rev: v4.11.4\n"
            ),
            "llms.txt": "- uses: artvepa80/Agents-Hefesto@v4.11.4\n",
            "server.json": '{"version": "4.11.4"}\n',
            ".well-known/agent-card.json": '{"version": "4.11.4"}\n',
            "skill/SKILL.md": "Package: hefesto-ai | Version: 4.11.1 | License: MIT\n",
            ".github/copilot-instructions.md": (
                "- **Version:** 4.11.4\n" "- uses: artvepa80/Agents-Hefesto@v4.11.4\n"
            ),
        },
    )
    errors = mod.check_version_parity(repo, "4.11.4")
    assert len(errors) == 1
    assert "skill/SKILL.md" in errors[0]
    assert "4.11.1" in errors[0]


def test_copilot_instructions_detects_both_version_header_and_action_ref(tmp_path):
    """copilot-instructions.md has two distinct patterns; both must drift-check."""
    mod = _load_module()
    repo = _setup_repo(
        tmp_path,
        "4.11.4",
        {
            "README.md": (
                "uses: artvepa80/Agents-Hefesto@v4.11.4\n"
                "## CLI Reference (v4.11.4)\n"
                "rev: v4.11.4\n"
            ),
            "llms.txt": "- uses: artvepa80/Agents-Hefesto@v4.11.4\n",
            "server.json": '{"version": "4.11.4"}\n',
            ".well-known/agent-card.json": '{"version": "4.11.4"}\n',
            "skill/SKILL.md": "Version: 4.11.4\n",
            ".github/copilot-instructions.md": (
                "- **Version:** 4.11.1\n"  # drift 1: version header
                "- uses: artvepa80/Agents-Hefesto@v4.11.2\n"  # drift 2: action ref
            ),
        },
    )
    errors = mod.check_version_parity(repo, "4.11.4")
    assert len(errors) == 2
    messages = " | ".join(errors)
    assert "version header" in messages
    assert "action ref" in messages
    assert "4.11.1" in messages
    assert "4.11.2" in messages


def test_multiple_drifts_in_same_file_all_reported(tmp_path):
    """README has 3 active refs; if 2 drift, both must be reported (re.finditer)."""
    mod = _load_module()
    repo = _setup_repo(
        tmp_path,
        "4.11.4",
        {
            "README.md": (
                "uses: artvepa80/Agents-Hefesto@v4.11.4\n"  # OK
                "## CLI Reference (v4.11.3)\n"  # drift
                "rev: v4.11.2\n"  # drift
            ),
            "llms.txt": "- uses: artvepa80/Agents-Hefesto@v4.11.4\n",
            "server.json": '{"version": "4.11.4"}\n',
            ".well-known/agent-card.json": '{"version": "4.11.4"}\n',
            "skill/SKILL.md": "Version: 4.11.4\n",
            ".github/copilot-instructions.md": (
                "- **Version:** 4.11.4\n" "- uses: artvepa80/Agents-Hefesto@v4.11.4\n"
            ),
        },
    )
    errors = mod.check_version_parity(repo, "4.11.4")
    assert len(errors) == 2
    joined = " | ".join(errors)
    assert "CLI ref" in joined and "4.11.3" in joined
    assert "pre-commit rev" in joined and "4.11.2" in joined


@pytest.mark.parametrize(
    "ver_str,should_match",
    [
        ("Agents-Hefesto@v4.11.4", True),
        ("Agents-Hefesto@v4.11", False),  # two-component, rejected
        ("Agents-Hefesto@v4.11.4.5", False),  # four-component, rejected by lookahead
        ("Agents-Hefesto@v4.11.4.dev0", False),  # dev suffix, rejected by lookahead
    ],
)
def test_action_ref_regex_rejects_malformed(ver_str, should_match):
    """Guard against reverting strict pattern back to loose [\\d.]+."""
    mod = _load_module()
    readme_entry = dict(mod.VERSION_REFERENCES)["README.md"]
    pattern = readme_entry[0][0]  # first pattern: action ref
    assert bool(re.search(pattern, ver_str)) == should_match


def test_historical_prose_ref_does_not_cause_false_positive(tmp_path):
    """Architectural defense: README with historical version refs in prose
    (migration notes, headings, analyzer tables, changelog excerpts) must
    NOT be flagged as drift. The narrow anchoring patterns must protect
    against this."""
    mod = _load_module()
    repo = _setup_repo(
        tmp_path,
        "4.11.4",
        {
            "README.md": (
                "# PR review (new in v4.11.2) — analyze only changed code\n"
                "    uses: artvepa80/Agents-Hefesto@v4.11.4\n"
                "## PR Review (v4.11.2)\n"  # historical heading
                "| **YAML** | YamlAnalyzer | v4.4.0 |\n"  # analyzer table
                "## CLI Reference (v4.11.4)\n"
                "    rev: v4.11.4\n"
                "### v4.11.2 (2026-04-12)\n"  # changelog embedded
                "### v4.9.9 (2026-03-13)\n"  # historical changelog
            ),
            "llms.txt": "- uses: artvepa80/Agents-Hefesto@v4.11.4\n",
            "server.json": '{"version": "4.11.4"}\n',
            ".well-known/agent-card.json": '{"version": "4.11.4"}\n',
            "skill/SKILL.md": "Version: 4.11.4\n",
            ".github/copilot-instructions.md": (
                "- **Version:** 4.11.4\n" "- uses: artvepa80/Agents-Hefesto@v4.11.4\n"
            ),
        },
    )
    errors = mod.check_version_parity(repo, "4.11.4")
    assert errors == []


def test_script_ignores_files_not_in_version_references(tmp_path):
    """CHANGELOG.md historical entries must not be flagged (file not in list)."""
    mod = _load_module()
    repo = _setup_repo(
        tmp_path,
        "4.11.4",
        {
            "README.md": (
                "uses: artvepa80/Agents-Hefesto@v4.11.4\n"
                "## CLI Reference (v4.11.4)\n"
                "rev: v4.11.4\n"
            ),
            "llms.txt": "- uses: artvepa80/Agents-Hefesto@v4.11.4\n",
            "server.json": '{"version": "4.11.4"}\n',
            ".well-known/agent-card.json": '{"version": "4.11.4"}\n',
            "skill/SKILL.md": "Version: 4.11.4\n",
            ".github/copilot-instructions.md": (
                "- **Version:** 4.11.4\n" "- uses: artvepa80/Agents-Hefesto@v4.11.4\n"
            ),
            "CHANGELOG.md": (
                "## [4.11.4] - 2026-04-17\n"
                "## [4.11.3] - 2026-04-14\n"  # historical, would drift if checked
                "## [4.10.0] - 2026-04-12\n"  # historical
            ),
        },
    )
    errors = mod.check_version_parity(repo, "4.11.4")
    assert errors == []
