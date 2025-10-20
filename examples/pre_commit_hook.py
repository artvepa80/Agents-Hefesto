#!/usr/bin/env python3
"""
Pre-commit hook example for Hefesto.

Install:
    1. Save this file to .git/hooks/pre-commit
    2. chmod +x .git/hooks/pre-commit
    3. Configure environment variables

Copyright © 2025 Narapa LLC
"""

import subprocess
import sys
import os


def get_staged_python_files():
    """Get list of staged Python files."""
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return []
    
    files = result.stdout.strip().split('\n')
    return [f for f in files if f.endswith('.py') and f]


def analyze_with_hefesto(file_path):
    """
    Analyze a file with Hefesto API.
    
    For simplicity, this example just checks for hardcoded secrets.
    In production, you'd call the full Hefesto API.
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️  Could not read {file_path}: {e}")
        return True
    
    # Simple check for common issues
    issues = []
    
    if 'password = "' in content or "password = '" in content:
        issues.append("Hardcoded password detected")
    
    if 'API_KEY = "' in content or "API_KEY = '" in content:
        issues.append("Hardcoded API key detected")
    
    if "eval(" in content or "exec(" in content:
        issues.append("Dangerous function (eval/exec) detected")
    
    if issues:
        print(f"\n❌ {file_path}:")
        for issue in issues:
            print(f"   • {issue}")
        return False
    
    return True


def main():
    """Main pre-commit hook logic."""
    print("🔨 Hefesto Pre-Commit Hook")
    print("=" * 60)
    
    # Get staged files
    files = get_staged_python_files()
    
    if not files:
        print("✓ No Python files to check")
        return 0
    
    print(f"\n🔍 Checking {len(files)} Python file(s)...\n")
    
    all_passed = True
    
    for file_path in files:
        if analyze_with_hefesto(file_path):
            print(f"✅ {file_path}")
        else:
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✅ All checks passed - proceeding with commit")
        return 0
    else:
        print("❌ Issues found - commit blocked")
        print("\n💡 To bypass (NOT recommended):")
        print("   git commit --no-verify")
        print("\n💡 For full analysis:")
        print("   hefesto serve")
        print("   # Then use API for detailed suggestions")
        return 1


if __name__ == '__main__':
    sys.exit(main())

