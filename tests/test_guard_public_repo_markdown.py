"""Tests for the Markdown/skill scan in scripts/guard_public_repo.py."""

import importlib.util
import re
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
        "Card at `landing-page/api/demo.js`.",
        "Handoff `/home/box/agent-data/handoffs/x.md`.",
        "The private repo keeps its own copy.",
        "Lo arregla el repo privado.",
        "Fixed in private repo PR #999.",
        "See private PR 999.",
        "El PR privado de la demo agrega un test.",
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
                "Private repositories need `actions: read`.",
                "Private PR numbers never go in the public copy.",
                "The Hefesto code gate skills live in hefesto-code-gate.",
                "User-Agent: hefesto-mcp-registry-check/1.0",
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


# ---------------------------------------------------------------------------
# Agent names, wider file scope and self-exclusion.
# ---------------------------------------------------------------------------

SYNTHETIC_NAMES = ("zeta relay", "quokkabot")


@pytest.fixture
def synthetic_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    digests = frozenset(guard.name_digest(n) for n in SYNTHETIC_NAMES)
    monkeypatch.setattr(guard, "AGENT_NAME_DIGESTS", digests)


@pytest.mark.parametrize(
    "text",
    [
        "Relayed by Zeta Relay at 10:00.",
        "ZETA   relay reviewed it",
        "Approved (quokkabot).",
        "Revisado por Quókkabot.",
    ],
)
def test_agent_names_are_flagged(tmp_path: Path, synthetic_agents: None, text: str) -> None:
    _write(tmp_path, "docs/worklog/x.md", f"# Log\n\n{text}\n")
    errors = guard.check_markdown_leaks(tmp_path, allowlist=set())
    assert errors, text
    assert "'agent-name'" in errors[0]
    assert "docs/worklog/x.md:3" in errors[0]


@pytest.mark.parametrize(
    "text",
    [
        "zeta-relay-check/1.0 is a user agent string.",
        "The zeta of the relay.",
        "quokka bot",
    ],
)
def test_agent_name_lookalikes_are_not_flagged(
    tmp_path: Path, synthetic_agents: None, text: str
) -> None:
    _write(tmp_path, "docs/x.md", f"{text}\n")
    assert guard.check_markdown_leaks(tmp_path, allowlist=set()) == []


def test_agent_name_digests_are_shipped_without_plain_names() -> None:
    digests = guard.AGENT_NAME_DIGESTS
    assert len(digests) == 8
    assert all(re.fullmatch(r"[0-9a-f]{64}", d) for d in digests)
    # The public product is not an agent name.
    for public in ("hefesto code gate", "hefesto-code-gate", "hefesto", "hefestoai"):
        assert guard.name_digest(public) not in digests


def test_name_digest_folds_case_accents_and_spaces() -> None:
    assert guard.name_digest("Zeta  Relay") == guard.name_digest("zeta relay")
    assert guard.name_digest("Quókkabot") == guard.name_digest("quokkabot")


@pytest.mark.parametrize(
    "rel",
    [
        "tests/test_cards.py",
        "scripts/tool.py",
        "hefesto/x.py",
        ".github/workflows/x.yml",
        "pyproject.toml",
    ],
)
def test_code_and_config_files_are_scanned(tmp_path: Path, rel: str) -> None:
    _write(tmp_path, rel, '"""Card served from landing-page/demo.js."""\n')
    errors = guard.check_markdown_leaks(tmp_path, allowlist=set())
    assert errors and "'private-path'" in errors[0]


@pytest.mark.parametrize("rel", sorted(guard.GUARD_SELF_FILES))
def test_guard_and_its_tests_are_not_scanned(tmp_path: Path, rel: str) -> None:
    _write(tmp_path, rel, "pattern: landing-page/ and the private repo\n")
    assert guard.check_markdown_leaks(tmp_path, allowlist=set()) == []


def test_new_rules_can_be_allowlisted_outside_strict_dirs(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "History is tracked in our private repo.\n")
    assert guard.check_markdown_leaks(tmp_path, allowlist=set())
    allow = {("README.md", "private-repo-mention")}
    assert guard.check_markdown_leaks(tmp_path, allowlist=allow) == []


def test_forbidden_path_prefixes(tmp_path: Path) -> None:
    _write(tmp_path, "docs/logs/2026-01-01.md", "notes\n")
    _write(tmp_path, "docs/guide.md", "guide\n")
    errors = guard.check_forbidden_paths(tmp_path, prefixes=("docs/logs/",))
    assert errors == ["FORBIDDEN PATH exists: docs/logs/2026-01-01.md"]
    assert guard.check_forbidden_paths(tmp_path, prefixes=()) == []


def test_agent_name_rule_can_be_allowlisted(tmp_path: Path, synthetic_agents: None) -> None:
    _write(tmp_path, "docs/x.md", "Zeta Relay\n")
    assert guard.check_markdown_leaks(tmp_path, allowlist={("docs/x.md", "agent-name")}) == []
