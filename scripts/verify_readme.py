#!/usr/bin/env python3
"""
Verify that README.md accurately reflects installed analyzers.

Usage:
    python scripts/verify_readme.py
"""

import pkgutil
import re
from pathlib import Path


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

    # Get version from package
    from importlib.metadata import version

    pkg_version = version("hefesto-ai")

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

    # Check version in GitHub Action reference or CLI Reference heading
    print(f"\n3. README Version")
    version_match = re.search(
        r"(?:Agents-Hefesto@v|CLI Reference \(v)(\d+\.\d+\.\d+)", readme_content
    )
    if version_match:
        readme_version = version_match.group(1)
        print(f"   README version: {readme_version}")
        print(f"   Package version: {pkg_version}")

        if readme_version != pkg_version:
            errors.append(f"Version mismatch: README={readme_version}, package={pkg_version}")
            print(f"   ❌ MISMATCH")
        else:
            print(f"   ✅ MATCH")
    else:
        errors.append("Version not found in README")
        print(f"   ❌ NOT FOUND")

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
