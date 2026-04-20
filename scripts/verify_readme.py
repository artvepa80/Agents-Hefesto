#!/usr/bin/env python3
"""
Verify that README.md accurately reflects installed analyzers
and that all version references across the repo match pyproject.toml.

Usage:
    python scripts/verify_readme.py

Design notes
------------
Version parity is enforced via VERSION_REFERENCES — a list of
(file, [(regex, description), ...]) tuples. Patterns are anchored by
context (``Agents-Hefesto@v``, ``CLI Reference (v``, ``rev: v``,
``"version": "..."``) to avoid false positives on historical version
references in README prose (e.g., migration notes, analyzer tables,
embedded changelog excerpts).

Known limitations:

1. Historical prose collision: a future line like ``upgrading from
   Agents-Hefesto@v4.11.0`` would trigger a false positive because the
   anchor is shared with active refs. If that becomes a problem, switch
   to explicit ``<!-- version-check -->`` ... ``<!-- /version-check -->``
   block anchoring.

2. Pre-release / build-metadata suffixes: the ``(?![\d.])`` lookahead
   rejects ``.dev0`` / ``.5`` suffixes, but ``-rc1`` and ``+build`` pass
   it (``-`` and ``+`` are not in the char class). If the project ever
   publishes a pre-release, ``pyproject.toml`` would hold the full
   ``4.X.Y-rc1`` while regex extracts only ``4.X.Y`` → false drift.
   Project currently uses flat SemVer; extend lookahead to
   ``(?![\d.\-+])`` when that changes.

Pattern-not-found (``if not found_any``) raises an error on purpose: if a
version reference is removed from a tracked file (e.g., legitimate refactor),
VERSION_REFERENCES must be updated in the same change. A silent warning here
would let new version references be added without drift protection.
"""

import pkgutil
import re
from pathlib import Path

# Files with version references that must match pyproject.toml [project] version.
# When adding new files with version refs, add them here.
# Each entry: (relative_path, [(regex, description), ...])
# Use re.finditer so ALL occurrences in a file are validated.
#   Pattern uses (\d+\.\d+\.\d+)(?![\d.]) — strict SemVer + negative lookahead
#   to reject malformed suffixes like 4.11.4.5 or 4.11.4.dev0. Without the
#   lookahead, \d+\.\d+\.\d+ is greedy but not anchored right, so 4.11.4.5
#   would silently capture 4.11.4 and pass validation.
VERSION_REFERENCES = [
    (
        "README.md",
        [
            (r"Agents-Hefesto@v(\d+\.\d+\.\d+)(?![\d.])", "action ref"),
            (r"CLI Reference \(v(\d+\.\d+\.\d+)(?![\d.])\)", "CLI ref"),
            (r"rev: v(\d+\.\d+\.\d+)(?![\d.])", "pre-commit rev"),
        ],
    ),
    ("llms.txt", [(r"Agents-Hefesto@v(\d+\.\d+\.\d+)(?![\d.])", "action ref")]),
    ("server.json", [(r'"version":\s*"(\d+\.\d+\.\d+)(?![\d.])"', "MCP metadata")]),
    (
        ".well-known/agent-card.json",
        [(r'"version":\s*"(\d+\.\d+\.\d+)(?![\d.])"', "A2A metadata")],
    ),
    ("skill/SKILL.md", [(r"Version:\s*(\d+\.\d+\.\d+)(?![\d.])", "skill metadata")]),
    (
        ".github/copilot-instructions.md",
        [
            (r"\*\*Version:\*\* (\d+\.\d+\.\d+)(?![\d.])", "version header"),
            (r"Agents-Hefesto@v(\d+\.\d+\.\d+)(?![\d.])", "action ref"),
        ],
    ),
]


def check_version_parity(repo_root, source_version):
    """Check all files in VERSION_REFERENCES for drift from source_version.

    Returns a list of error strings (empty if all match).
    Prints per-file status.
    """
    errors = []
    for rel_path, patterns in VERSION_REFERENCES:
        file_path = repo_root / rel_path
        if not file_path.exists():
            print(f"   ⚠ {rel_path}: file missing, skipping")
            continue
        content = file_path.read_text()
        for pattern, description in patterns:
            found_any = False
            for match in re.finditer(pattern, content):
                found_any = True
                ref_version = match.group(1)
                line_num = content[: match.start()].count("\n") + 1
                location = f"{rel_path}:{line_num}"
                if ref_version != source_version:
                    msg = (
                        f"{location} ({description}): {ref_version} " f"(expected {source_version})"
                    )
                    errors.append(f"Version drift — {msg}")
                    print(f"   ❌ {msg}")
                else:
                    print(f"   ✅ {location} ({description}): {ref_version}")
            if not found_any:
                msg = f"{rel_path} ({description}): pattern not found"
                errors.append(msg)
                print(f"   ⚠ {msg}")
    return errors


def get_devops_analyzers():
    """Get list of installed DevOps analyzers."""
    import hefesto.analyzers.devops as devops

    mods = sorted([m.name for m in pkgutil.iter_modules(devops.__path__)])
    return [m for m in mods if m.endswith("_analyzer")]


def extract_readme_analyzers(readme_path):
    """Extract DevOps analyzers mentioned in README Language Support table."""
    content = Path(readme_path).read_text()

    # Match rows with "rules" or "aligned" (DevOps section) but not Cloud (which uses "Security")
    devops_section = re.search(
        r"### DevOps & Configuration(.*?)### Cloud Infrastructure", content, re.DOTALL
    )
    if not devops_section:
        return None, []

    devops_rows = re.findall(r"\| \*\*(\w+)\*\* \|", devops_section.group(1))

    if not devops_rows:
        return None, []

    return len(devops_rows), devops_rows


def get_cloud_analyzers():
    """Get list of installed Cloud analyzers."""
    # We manually count these because they are structured differently (packages)
    # CloudFormation, ARM, Helm, Serverless
    return ["cloudformation", "arm", "helm", "serverless"]


def main():
    readme_path = Path(__file__).parent.parent / "README.md"
    readme_content = readme_path.read_text()

    # Get actual analyzers
    devops_actual = get_devops_analyzers()
    devops_count = len(devops_actual)

    cloud_actual = get_cloud_analyzers()
    cloud_count = len(cloud_actual)

    code_count = 7  # Python, TS, JS, Java, Go, Rust, C#

    # Get README data
    readme_devops_count, _ = extract_readme_analyzers(readme_path)

    # Get version from pyproject.toml (single source of truth)
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pkg_version = tomllib.load(f)["project"]["version"]

    print("=" * 60)
    print("README vs Reality Check")
    print("=" * 60)

    errors = []

    # Check DevOps analyzers
    print(f"\n1. DevOps Analyzers")
    print(f"   Actual: {devops_count}")
    print(f"   README claims: {readme_devops_count}")

    if readme_devops_count != devops_count:
        errors.append(f"DevOps count mismatch: README={readme_devops_count}, actual={devops_count}")
        print(f"   ❌ MISMATCH")
    else:
        print(f"   ✅ MATCH")

    # Check Code Languages count (count rows in Code Languages table)
    print(f"\n2. Code Languages")
    code_lang_rows = re.findall(
        r"\| (?:Python|TypeScript|JavaScript|Java|Go|Rust|C#) \|", readme_content
    )
    if code_lang_rows:
        readme_lang_count = len(code_lang_rows)
        expected_lang_count = code_count
        print(f"   README claims: {readme_lang_count}")
        print(f"   Expected: {expected_lang_count}")

        if readme_lang_count != expected_lang_count:
            errors.append(
                f"Code Languages mismatch: README={readme_lang_count}, expected={expected_lang_count}"
            )
            print(f"   ❌ MISMATCH")
        else:
            print(f"   ✅ MATCH")
    else:
        errors.append("Code Languages count not found in README")
        print(f"   ❌ NOT FOUND")

    # Check version parity across all tracked files (see VERSION_REFERENCES)
    print(f"\n3. Version Parity (pyproject.toml → all tracked files)")
    print(f"   Source version (pyproject.toml): {pkg_version}")
    repo_root = Path(__file__).parent.parent
    version_errors = check_version_parity(repo_root, pkg_version)
    errors.extend(version_errors)

    # Check badge count (should be 21 = 7 + 10 + 4)
    print(f"\n4. Languages Badge")
    badge_match = re.search(r"languages-(\d+)-green", readme_content)
    if badge_match:
        badge_count = int(badge_match.group(1))
        expected_total = code_count + devops_count + cloud_count
        print(f"   Badge shows: {badge_count}")
        print(
            f"   Expected: {expected_total} (7 Code + {devops_count} DevOps + {cloud_count} Cloud)"
        )

        if badge_count != expected_total:
            errors.append(f"Badge count mismatch: badge={badge_count}, expected={expected_total}")
            print(f"   ❌ MISMATCH")
        else:
            print(f"   ✅ MATCH")
    else:
        errors.append("Languages badge not found")
        print(f"   ❌ NOT FOUND")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print("Verification: FAILED")
        print("=" * 60)
        print("\nErrors:")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("Verification: PASSED")
        print("=" * 60)
        print("\n✅ All checks passed!")
        print(f"   - {devops_count} DevOps analyzers")
        print(f"   - {cloud_count} Cloud analyzers")
        print(f"   - {code_count} Code languages")
        print(f"   - Version: {pkg_version}")
        print(f"   - Total: {code_count + devops_count + cloud_count} formats")
        return 0


if __name__ == "__main__":
    exit(main())
