"""Machine-readable positioning says "release truth engine" with verified figures.

The agent card is served twice: from this repo (.well-known/agent-card.json)
and by the landing (private repo, landing-page/api/agent-card.js). The private
repo's tests/landing_js/agent-card-parity.test.mjs deep-compares its card with
this file on main, so change both together. CANONICAL_DESCRIPTION is pinned
here and in that private test.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CARD = json.loads((ROOT / ".well-known" / "agent-card.json").read_text(encoding="utf-8"))

CANONICAL_DESCRIPTION = (
    "Release truth engine for AI-generated code. Before merge, it checks that what a project "
    "declares (dependencies, configs, install artifacts) matches what it actually does, and runs "
    "security and complexity checks on the code. Analyzers for 22 formats (7 code languages + 15 "
    "DevOps/IaC); hefesto analyze runs 13 of them today."
)

# Retired or unverified claims (2026-10-10, Path Y).
BANNED = [
    r"code quality guardian",
    r"pre-commit guardian",
    r"\b17 languages\b",
    r"low false positives",
    r"0\.01\s?s(econds)?\b",
]
POSITIONING_FILES = [
    ".well-known/agent-card.json",
    "llms.txt",
    "pyproject.toml",
    "CLAUDE.md",
]


def test_card_description_is_canonical():
    assert CARD["description"] == CANONICAL_DESCRIPTION


def test_card_figures_are_the_verified_ones():
    text = json.dumps(CARD)
    assert "22 formats" in text
    assert "hefesto analyze runs 13" in text
    assert "7 code languages + 15" in CANONICAL_DESCRIPTION


@pytest.mark.parametrize("rel", POSITIONING_FILES)
def test_no_retired_claims(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    for pattern in BANNED:
        assert not re.search(pattern, text, re.I), f"{rel}: {pattern}"


def test_headlines_say_release_truth_engine():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    description = re.search(r'^description = "([^"]+)"', pyproject, re.M).group(1)
    assert description.startswith("Release truth engine for AI-generated code")
    claude_h1 = (ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()[0]
    assert "release truth engine" in claude_h1.lower()
    readme_h1 = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]
    assert "release truth engine" in readme_h1.lower()
    assert "release truth engine" in (ROOT / "llms.txt").read_text(encoding="utf-8").lower()
