#!/usr/bin/env python3
"""
Guard: ensure the public repo does not contain paid/proprietary code.

Exit codes:
  0  — clean (no leaks detected)
  1  — leak(s) found

Also scans Markdown, rules, agent skills, code and config files (.md, .mdc,
.py, .txt, .json, .yml, .yaml, .toml everywhere) for private references:
private paths, private PR and repository mentions, and internal agent names.
Historical, legitimate mentions outside .claude/ and .cursor/ are listed per
file and rule in scripts/guard_markdown_allowlist.txt. The guard, its test file
and the allowlist are not scanned: they hold the patterns themselves.

Paths listed in FORBIDDEN_PATH_PREFIXES must not exist in the tree at all.

Run in CI or locally:
  python scripts/guard_public_repo.py
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories that MUST NOT exist in the public tree
BANNED_DIRS = [
    "hefesto/api",
    "hefesto/llm",
    "hefesto/licensing",
    "hefesto/omega",
    "hefesto/aegis",
    "omega",
    "iris",
    "tests_pro",
]

# Files that MUST NOT exist in the public tree
BANNED_FILES = [
    "hefesto/config/stripe_config.py",
    "hefesto/config/config_manager.py",
    "docker-compose.yml",
    "setup.py",
]

# Identifiers that MUST NOT appear in any .py file under hefesto/
BANNED_IDENTIFIERS = [
    "from hefesto.api",
    "from hefesto.llm",
    "from hefesto.licensing",
    "from hefesto.omega",
    "from hefesto.aegis",
    "import hefesto.api",
    "import hefesto.llm",
    "import hefesto.licensing",
    "import hefesto.omega",
    "import hefesto.aegis",
    "stripe_config",
    "STRIPE_CONFIG",
    "bigquery_dataset",
    "gemini_api_key",
    "FeatureGate",
    "LicenseKeyGenerator",
    "config_manager",
]


def check_banned_dirs() -> list[str]:
    errors: list[str] = []
    for d in BANNED_DIRS:
        path = REPO_ROOT / d
        if path.is_dir():
            errors.append(f"BANNED DIR exists: {d}/")
    return errors


def check_banned_files() -> list[str]:
    errors: list[str] = []
    for f in BANNED_FILES:
        path = REPO_ROOT / f
        if path.is_file():
            errors.append(f"BANNED FILE exists: {f}")
    return errors


def check_banned_identifiers() -> list[str]:
    errors: list[str] = []
    hefesto_dir = REPO_ROOT / "hefesto"
    if not hefesto_dir.is_dir():
        return errors

    for py_file in hefesto_dir.rglob("*.py"):
        rel = py_file.relative_to(REPO_ROOT)
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ident in BANNED_IDENTIFIERS:
            if ident in content:
                errors.append(f"BANNED IDENTIFIER '{ident}' in {rel}")
    return errors


# ---------------------------------------------------------------------------
# Markdown / skill scan: private references in docs, rules and agent skills.
# ---------------------------------------------------------------------------

# Rule id -> pattern. Plain words ("Swarm Gate", "landing page", "private
# repositories" in the GitHub sense) are public and are not matched; paths,
# file names, package names, the private repository name, "private repo" /
# "repo privado" mentions and private PR references are.
MARKDOWN_RULES: dict[str, re.Pattern[str]] = {
    "memory-md": re.compile(r"\bMEMORY\.md\b"),
    "swarm-path": re.compile(r"(?<![\w./-])swarm/"),
    "iris-path": re.compile(r"(?<![\w./-])iris/"),
    "hefesto-pro": re.compile(r"\bhefesto_pro\b"),
    "private-repo": re.compile(r"Agents-Hefesto-Pro-Private|\bPro-Private\b", re.IGNORECASE),
    "private-repo-mention": re.compile(
        r"\bprivate[\s-]+repo\b|\brepo(?:sitorio)?\s+privado\b", re.IGNORECASE
    ),
    "private-pr": re.compile(
        r"\bprivate\s+(?:(?:repo(?:sitory)?\s+)?PRs?\s*#?\d+|#\d+)|\bPRs?\s+privados?\b",
        re.IGNORECASE,
    ),
    "private-path": re.compile(r"landing-page/|agent-data/handoffs|/home/box/"),
}

# Internal agent names, stored as salted SHA-256 digests so this public file
# does not spell them out. A line is flagged when one word, or two or three
# words separated only by whitespace, normalize (accents removed, casefolded,
# spaces collapsed) to one of these digests. "hefesto-mcp-registry-check" is
# not a match: words joined by "-" or "_" are not checked as a phrase. The
# public product name "Hefesto code gate" (repo hefesto-code-gate) is not listed.
AGENT_NAME_RULE = "agent-name"
_NAME_SALT = "hefesto-guard-v1:"
MAX_NAME_WORDS = 3
AGENT_NAME_DIGESTS: frozenset[str] = frozenset(
    {
        "0bb9d7680d2ec07f2b29c4b71be4d4b55992c073abe47bd20a632079054f987d",
        "1ba5d75fed39317e52e5e56ecf8e1d89c914a6b89dd30527f612bde822fdf31b",
        "1fba7fa746a2d560e09dffc4d4c4b7f10492520702fde03e372ac82875a63e9b",
        "2f513c4d5da454a3de25dd691024579c493dce8b848da841d31d7672a10c7245",
        "3f1d2cbf9186a0cc15788b108ed1e1baea4001f48a594c7d0136424718ac19f7",
        "46ccbef84781768d0aa01a0d9f346d9311701046a2a46256088e1bfe556c06ed",
        "5cb0f0dfc23a35208e3322069f190be9f04131e310c3f134019284bb9fee6b74",
        "f0e87e115c7d55c42ef243bb7f4df1c90e17c74bf8276ef9976deb4b0e4da0d8",
    }
)

ALL_RULES = frozenset(MARKDOWN_RULES) | {AGENT_NAME_RULE}

# Code and config files outside docs/, .claude/ and .cursor/ get only these
# rules: the package legitimately imports the optional hefesto_pro plugin and
# names swarm/ or iris/ in path checks.
CODE_RULE_IDS = ("private-repo", "private-repo-mention", "private-pr", "private-path")

_WORD = re.compile(r"[^\W_]+")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


def name_digest(name: str) -> str:
    """Salted SHA-256 of a normalized name (see AGENT_NAME_DIGESTS)."""
    return hashlib.sha256((_NAME_SALT + _fold(name)).encode("utf-8")).hexdigest()


def _phrases(line: str) -> Iterator[str]:
    """Yield runs of 1..MAX_NAME_WORDS words joined only by whitespace."""
    words = list(_WORD.finditer(line))
    for i, first in enumerate(words):
        last = first
        for nxt in words[i : i + MAX_NAME_WORDS]:
            if nxt is not first and line[last.end() : nxt.start()].strip():
                break
            last = nxt
            yield line[first.start() : nxt.end()]


def find_agent_name(line: str, digests: frozenset[str] | None = None) -> str | None:
    """Return the matching phrase from ``line``, or None."""
    wanted = AGENT_NAME_DIGESTS if digests is None else digests
    return next((p for p in _phrases(line) if name_digest(p) in wanted), None)


# Every file with one of these suffixes is scanned, anywhere in the tree.
# Markdown, and text files under TEXT_DIRS, get every rule.
MARKDOWN_SUFFIXES = {".md", ".mdc"}
TEXT_DIRS = (".claude/", ".cursor/", "docs/")
TEXT_SUFFIXES = MARKDOWN_SUFFIXES | {".py", ".txt", ".json", ".yml", ".yaml", ".toml"}

# Agent skills and rules must be clean: the allowlist cannot cover them.
STRICT_PREFIXES = (".claude/", ".cursor/")

# The guard, its tests and its allowlist contain the patterns on purpose.
GUARD_SELF_FILES = frozenset(
    {
        "scripts/guard_public_repo.py",
        "scripts/guard_markdown_allowlist.txt",
        "tests/test_guard_public_repo_markdown.py",
    }
)

# Repository-relative path prefixes that must not exist in the public tree
# (for example internal logs). Empty for now; add a prefix to block it.
FORBIDDEN_PATH_PREFIXES: tuple[str, ...] = ()

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "htmlcov",
}

MARKDOWN_ALLOWLIST = REPO_ROOT / "scripts" / "guard_markdown_allowlist.txt"


def _parse_allowlist_line(line: str, where: str) -> tuple[str, str]:
    parts = line.split()
    if len(parts) != 2:
        raise ValueError(f"{where}: expected '<path> <rule>'")
    rel, rule = parts
    if rule not in ALL_RULES:
        raise ValueError(f"{where}: unknown rule '{rule}'")
    if rel.startswith(STRICT_PREFIXES):
        raise ValueError(f"{where}: {rel} cannot be allowlisted")
    return rel, rule


def load_markdown_allowlist(path: Path) -> set[tuple[str, str]]:
    """Parse ``<relative path> <rule id>`` lines; ``#`` starts a comment."""
    if not path.is_file():
        return set()
    allow: set[tuple[str, str]] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if line:
            allow.add(_parse_allowlist_line(line, f"{path.name}:{lineno}"))
    return allow


def _walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("venv"))
        files.extend(Path(dirpath) / name for name in sorted(filenames))
    return files


def _markdown_scan_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    for path in _walk_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in GUARD_SELF_FILES:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            targets.append(path)
    return targets


def _line_findings(
    line: str, rules: dict[str, re.Pattern[str]], check_names: bool
) -> Iterator[tuple[str, str]]:
    for rule, pattern in rules.items():
        match = pattern.search(line)
        if match:
            yield rule, match.group(0)
    name = find_agent_name(line) if check_names else None
    if name:
        yield AGENT_NAME_RULE, name


def _scan_markdown_file(
    rel: str, text: str, rules: dict[str, re.Pattern[str]], check_names: bool = True
) -> list[str]:
    return [
        f"PRIVATE REFERENCE '{rule}' in {rel}:{lineno}: {found!r}"
        for lineno, line in enumerate(text.splitlines(), 1)
        for rule, found in _line_findings(line, rules, check_names)
    ]


def check_markdown_leaks(
    root: Path = REPO_ROOT, allowlist: set[tuple[str, str]] | None = None
) -> list[str]:
    """Flag private paths, MEMORY.md, swarm/, iris/, hefesto_pro, private PRs,
    private repository mentions and internal agent names."""
    allow = load_markdown_allowlist(MARKDOWN_ALLOWLIST) if allowlist is None else allowlist
    errors: list[str] = []
    for path in _markdown_scan_targets(root):
        rel = path.relative_to(root).as_posix()
        strict = rel.startswith(STRICT_PREFIXES)
        doc = path.suffix.lower() in MARKDOWN_SUFFIXES or rel.startswith(TEXT_DIRS)
        active = MARKDOWN_RULES if doc else {r: MARKDOWN_RULES[r] for r in CODE_RULE_IDS}
        rules = {r: p for r, p in active.items() if strict or (rel, r) not in allow}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names = strict or (rel, AGENT_NAME_RULE) not in allow
        errors.extend(_scan_markdown_file(rel, text, rules, names))
    return errors


def check_forbidden_paths(
    root: Path = REPO_ROOT, prefixes: tuple[str, ...] | None = None
) -> list[str]:
    """Flag files whose repository-relative path starts with a forbidden prefix."""
    blocked = FORBIDDEN_PATH_PREFIXES if prefixes is None else prefixes
    if not blocked:
        return []
    errors: list[str] = []
    for path in _walk_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(blocked):
            errors.append(f"FORBIDDEN PATH exists: {rel}")
    return errors


def main() -> int:
    print("=" * 60)
    print("HEFESTO PUBLIC REPO GUARD")
    print("=" * 60)

    all_errors: list[str] = []
    all_errors.extend(check_banned_dirs())
    all_errors.extend(check_banned_files())
    all_errors.extend(check_banned_identifiers())
    all_errors.extend(check_markdown_leaks())
    all_errors.extend(check_forbidden_paths())

    if all_errors:
        print(f"\nFAILED — {len(all_errors)} leak(s) detected:\n")
        for e in all_errors:
            print(f"  - {e}")
        print()
        return 1

    print("\nPASSED — no paid code leaks detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
