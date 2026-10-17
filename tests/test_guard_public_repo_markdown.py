"""Tests for the Markdown/skill scan in scripts/guard_public_repo.py."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "guard_public_repo.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("guard_public_repo", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "text",
    [
        "See the private `swarm/storage/sqlite_store.py:31`.",
        "Source: `MEMORY.md` (COBOL status).",
        "Fixed in private #169 (`a31c06a`).",
        "Upstream: artvepa80/Agents-Hefesto-Pro-Private/pull/164",
        "Loaded from `iris/core/iris_alert_manager.py`.",
        "Import `hefesto_pro.api_hardening`.",
        "Card at `landing-page/api/agent-card.js`.",
        "Handoff `/home/box/agent-data/handoffs/x.md`.",
    ],
)
def test_skill_markdown_leaks_are_flagged(tmp_path: Path, text: str) -> None:
    _write(tmp_path, ".claude/skills/demo/SKILL.md", f"# Demo\n\n{text}\n")
    errors = guard.check_markdown_leaks(tmp_path, allowlist=set())
    assert errors, text
    assert ".claude/skills/demo/SKILL.md:3" in errors[0]


@pytest.mark.parametrize(
    "rel", [".cursor/rules/x.mdc", "docs/notes.md", "README.md", "docs/sub/data.txt"]
)
def test_other_scanned_locations(tmp_path: Path, rel: str) -> None:
    _write(tmp_path, rel, "see MEMORY.md\n")
    assert guard.check_markdown_leaks(tmp_path, allowlist=set())


def test_public_mentions_are_not_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        ".claude/skills/demo/SKILL.md",
        "\n".join(
            [
                "Fixed in #127 (`fc9d072`) and PR #35.",
                "The private repo keeps its own copy.",
                "Swarm Gate is a CI name; swarming bees; the iris of an eye.",
                "Use `hefesto analyze` and the `skill/` folder.",
                "A landing page is a web page.",
            ]
        ),
    )
    _write(tmp_path, "hefesto/x.py", "# MEMORY.md is not scanned in .py here\n")
    assert guard.check_markdown_leaks(tmp_path, allowlist=set()) == []


def test_allowlist_suppresses_listed_file_and_rule(tmp_path: Path) -> None:
    _write(tmp_path, "CHANGELOG.md", "Docs: MEMORY.md updated.\n")
    assert guard.check_markdown_leaks(tmp_path, allowlist={("CHANGELOG.md", "memory-md")}) == []
    assert guard.check_markdown_leaks(tmp_path, allowlist={("CHANGELOG.md", "swarm-path")})


def test_allowlist_never_covers_skill_or_rule_dirs(tmp_path: Path) -> None:
    _write(tmp_path, ".claude/skills/demo/SKILL.md", "see MEMORY.md\n")
    allow = {(".claude/skills/demo/SKILL.md", "memory-md")}
    assert guard.check_markdown_leaks(tmp_path, allowlist=allow)


def test_load_allowlist_parses_and_rejects_strict_dirs(tmp_path: Path) -> None:
    f = tmp_path / "allow.txt"
    f.write_text("# comment\n\nCHANGELOG.md memory-md  # historical\n", encoding="utf-8")
    assert guard.load_markdown_allowlist(f) == {("CHANGELOG.md", "memory-md")}
    f.write_text(".cursor/rules/x.mdc memory-md\n", encoding="utf-8")
    with pytest.raises(ValueError):
        guard.load_markdown_allowlist(f)
    f.write_text("README.md no-such-rule\n", encoding="utf-8")
    with pytest.raises(ValueError):
        guard.load_markdown_allowlist(f)


def test_repository_is_clean_with_committed_allowlist() -> None:
    root = SCRIPT.parent.parent
    allow = guard.load_markdown_allowlist(root / "scripts" / "guard_markdown_allowlist.txt")
    assert guard.check_markdown_leaks(root, allowlist=allow) == []
