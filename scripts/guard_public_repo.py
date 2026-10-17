#!/usr/bin/env python3
"""
Guard: ensure the public repo does not contain paid/proprietary code.

Exit codes:
  0  — clean (no leaks detected)
  1  — leak(s) found

Also scans Markdown, rules and agent skills (.md/.mdc everywhere, plus text
files under .claude/, .cursor/ and docs/) for private references. Historical,
legitimate mentions outside .claude/ and .cursor/ are listed per file and rule
in scripts/guard_markdown_allowlist.txt.

Run in CI or locally:
  python scripts/guard_public_repo.py
"""

from __future__ import annotations

import os
import re
import sys
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

# Rule id -> pattern. Plain words ("private repo", "Swarm Gate", "landing page")
# are public and are not matched; only paths, file names, package names, the
# private repository name and "private #NNN" style PR references are.
MARKDOWN_RULES: dict[str, re.Pattern[str]] = {
    "memory-md": re.compile(r"\bMEMORY\.md\b"),
    "swarm-path": re.compile(r"(?<![\w./-])swarm/"),
    "iris-path": re.compile(r"(?<![\w./-])iris/"),
    "hefesto-pro": re.compile(r"\bhefesto_pro\b"),
    "private-repo": re.compile(r"Agents-Hefesto-Pro-Private|\bPro-Private\b", re.IGNORECASE),
    "private-pr": re.compile(r"\bprivate\s+(?:PRs?\s*)?#\d+", re.IGNORECASE),
    "private-path": re.compile(r"landing-page/|agent-data/handoffs|/home/box/"),
}

# Markdown files are scanned everywhere; these directories are also scanned
# for other text files.
MARKDOWN_SUFFIXES = {".md", ".mdc"}
TEXT_DIRS = (".claude/", ".cursor/", "docs/")
TEXT_SUFFIXES = MARKDOWN_SUFFIXES | {".txt", ".json", ".yml", ".yaml", ".toml"}

# Agent skills and rules must be clean: the allowlist cannot cover them.
STRICT_PREFIXES = (".claude/", ".cursor/")

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
}

MARKDOWN_ALLOWLIST = REPO_ROOT / "scripts" / "guard_markdown_allowlist.txt"


def _parse_allowlist_line(line: str, where: str) -> tuple[str, str]:
    parts = line.split()
    if len(parts) != 2:
        raise ValueError(f"{where}: expected '<path> <rule>'")
    rel, rule = parts
    if rule not in MARKDOWN_RULES:
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


def _markdown_scan_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("venv"))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            suffix = path.suffix.lower()
            if suffix in MARKDOWN_SUFFIXES or (
                rel.startswith(TEXT_DIRS) and suffix in TEXT_SUFFIXES
            ):
                targets.append(path)
    return targets


def _scan_markdown_file(rel: str, text: str, rules: dict[str, re.Pattern[str]]) -> list[str]:
    errors: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for rule, pattern in rules.items():
            match = pattern.search(line)
            if match:
                errors.append(f"PRIVATE REFERENCE '{rule}' in {rel}:{lineno}: {match.group(0)!r}")
    return errors


def check_markdown_leaks(
    root: Path = REPO_ROOT, allowlist: set[tuple[str, str]] | None = None
) -> list[str]:
    """Flag private paths, MEMORY.md, swarm/, iris/, hefesto_pro and private PRs."""
    allow = load_markdown_allowlist(MARKDOWN_ALLOWLIST) if allowlist is None else allowlist
    errors: list[str] = []
    for path in _markdown_scan_targets(root):
        rel = path.relative_to(root).as_posix()
        strict = rel.startswith(STRICT_PREFIXES)
        rules = {r: p for r, p in MARKDOWN_RULES.items() if strict or (rel, r) not in allow}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        errors.extend(_scan_markdown_file(rel, text, rules))
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
