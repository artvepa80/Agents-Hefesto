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
    return [m for m in mods if m.endswith('_analyzer')]


def extract_readme_analyzers(readme_path):
    """Extract DevOps analyzers mentioned in README."""
    content = Path(readme_path).read_text()
    
    # Find the DevOps/Config line in the feature table
    match = re.search(
        r'\| \*\*DevOps/Config \((\d+)\)\*\* \| ([^|]+) \|',
        content
    )
    
    if not match:
        return None, []
    
    count = int(match.group(1))
    formats_text = match.group(2).strip()
    
    # Parse the formats
    formats = [f.strip() for f in formats_text.split(',')]
    
    return count, formats


def main():
    readme_path = Path(__file__).parent.parent / 'README.md'
    readme_content = readme_path.read_text()
    
    # Get actual analyzers
    actual = get_devops_analyzers()
    actual_count = len(actual)
    
    # Get README data
    readme_count, readme_formats = extract_readme_analyzers(readme_path)
    
    # Get version from package
    from importlib.metadata import version
    pkg_version = version('hefesto-ai')
    
    print("=" * 60)
    print("README vs Reality Check")
    print("=" * 60)
    
    errors = []
    
    # Check DevOps analyzers
    print(f"\n1. DevOps Analyzers")
    print(f"   Actual: {actual_count}")
    print(f"   README claims: {readme_count}")
    
    if readme_count != actual_count:
        errors.append(f"DevOps count mismatch: README={readme_count}, actual={actual_count}")
        print(f"   ❌ MISMATCH")
    else:
        print(f"   ✅ MATCH")
    
    # Check Code Languages count
    print(f"\n2. Code Languages")
    code_lang_match = re.search(r'\| \*\*Code Languages \((\d+)\)\*\*', readme_content)
    if code_lang_match:
        readme_lang_count = int(code_lang_match.group(1))
        expected_lang_count = 7  # Python, TS, JS, Java, Go, Rust, C#
        print(f"   README claims: {readme_lang_count}")
        print(f"   Expected: {expected_lang_count}")
        
        if readme_lang_count != expected_lang_count:
            errors.append(f"Code Languages mismatch: README={readme_lang_count}, expected={expected_lang_count}")
            print(f"   ❌ MISMATCH")
        else:
            print(f"   ✅ MATCH")
    else:
        errors.append("Code Languages count not found in README")
        print(f"   ❌ NOT FOUND")
    
    # Check Quick Start version
    print(f"\n3. Quick Start Version")
    version_match = re.search(r'hefesto --version\s+#\s+Should show:\s+(\S+)', readme_content)
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
        errors.append("Version not found in Quick Start")
        print(f"   ❌ NOT FOUND")
    
    # Check badge count (should be 17 = 7 + 10)
    print(f"\n4. Languages Badge")
    badge_match = re.search(r'languages-(\d+)-green', readme_content)
    if badge_match:
        badge_count = int(badge_match.group(1))
        expected_total = 7 + actual_count  # Code + DevOps
        print(f"   Badge shows: {badge_count}")
        print(f"   Expected: {expected_total}")
        
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
        print(f"   - {actual_count} DevOps analyzers")
        print(f"   - 7 Code languages")
        print(f"   - Version: {pkg_version}")
        print(f"   - Total: {7 + actual_count} formats")
        return 0


if __name__ == '__main__':
    exit(main())
