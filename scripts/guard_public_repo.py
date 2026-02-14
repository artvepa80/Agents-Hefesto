#!/usr/bin/env python3
"""
Guard: ensure the public repo does not contain paid/proprietary code.

Exit codes:
  0  — clean (no leaks detected)
  1  — leak(s) found

Run in CI or locally:
  python scripts/guard_public_repo.py
"""

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
    errors = []
    for d in BANNED_DIRS:
        path = REPO_ROOT / d
        if path.is_dir():
            errors.append(f"BANNED DIR exists: {d}/")
    return errors


def check_banned_files() -> list[str]:
    errors = []
    for f in BANNED_FILES:
        path = REPO_ROOT / f
        if path.is_file():
            errors.append(f"BANNED FILE exists: {f}")
    return errors


def check_banned_identifiers() -> list[str]:
    errors = []
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


def main() -> int:
    print("=" * 60)
    print("HEFESTO PUBLIC REPO GUARD")
    print("=" * 60)

    all_errors: list[str] = []
    all_errors.extend(check_banned_dirs())
    all_errors.extend(check_banned_files())
    all_errors.extend(check_banned_identifiers())

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
