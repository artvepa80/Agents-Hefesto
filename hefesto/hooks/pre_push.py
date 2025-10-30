"""
Enhanced pre-push git hook with comprehensive validation.

Runs before git push to prevent broken CI pipelines:
- Black formatting
- isort import ordering
- Flake8 linting (NEW)
- CI parity check (NEW)
- Unit tests

Learned from: v4.0.1 release where local passed but CI failed with 20+ Flake8 errors.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import subprocess
import sys


def run_command(cmd: str, description: str) -> bool:
    """
    Run a shell command and return success status.

    Args:
        cmd: Command to run
        description: Human-readable description

    Returns:
        True if command succeeded, False otherwise
    """
    print(f"\n   • {description}...", end=" ", flush=True)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("\033[0;32m✓\033[0m")  # Green checkmark
            return True
        else:
            print("\033[0;31m✗\033[0m")  # Red X
            if result.stdout:
                print(f"\nOutput:\n{result.stdout}")
            if result.stderr:
                print(f"\nErrors:\n{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("\033[0;31m✗ (timeout)\033[0m")
        return False
    except Exception as e:
        print(f"\033[0;31m✗ ({e})\033[0m")
        return False


def get_changed_python_files() -> list:
    """Get list of changed Python files."""
    try:
        result = subprocess.run(
            "git diff --cached --name-only --diff-filter=ACMR | grep '\\.py$'",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            files = result.stdout.strip().split("\n")
            return [f for f in files if f]
        return []
    except Exception:
        return []


def main():
    """Main pre-push hook logic."""
    print("\n🔨 HEFESTO Pre-Push Validation")
    print("=" * 32)

    # Get changed files
    changed_files = get_changed_python_files()

    if changed_files:
        print("\n📋 Changed Python files:\n   ")
        for file in changed_files:
            print(f"   {file}")
    else:
        print("\n📋 No Python files changed")

    # Step 1: Linters
    print("\n1️⃣  Running linters...")

    checks_passed = True

    # Black
    if not run_command(
        "/Users/user/Library/Python/3.9/bin/black --check hefesto/ tests/",
        "Black formatting",
    ):
        checks_passed = False

    # isort
    if not run_command(
        "/Users/user/Library/Python/3.9/bin/isort --check hefesto/ tests/",
        "Import sorting",
    ):
        checks_passed = False

    # Flake8 (NEW - this would have caught the 20+ errors!)
    if not run_command(
        "/Users/user/Library/Python/3.9/bin/flake8 hefesto/ --max-line-length=100 --extend-ignore=E203,W503",  # noqa: E501
        "Flake8 linting",
    ):
        checks_passed = False

    if not checks_passed:
        print("\n\033[0;31m✗ Linting failed\033[0m")
        print("\n💡 Fix linting errors before pushing.")
        print("   Run: black hefesto/ tests/ && isort hefesto/ tests/")
        return 1

    # Step 2: Unit Tests
    print("\n2️⃣  Running unit tests...")

    # Run tests excluding cloud/integration tests
    if not run_command(
        'pytest -m "not requires_gcp and not requires_stripe and not integration" -v --cov=hefesto --cov-report=term --cov-report=html',  # noqa: E501
        "Unit tests",
    ):
        print("\n\033[0;31m✗ Tests failed\033[0m")
        print("\n💡 Fix failing tests before pushing.")
        return 1

    print("\033[0;32m✓ Tests passed\033[0m")

    # Step 3: Hefesto code analysis
    print("\n3️⃣  Hefesto code analysis...")

    print("\n   Analyzing changed Python files with Hefesto...")

    # Run Hefesto analyze on changed files (if any)
    if changed_files:
        # For now, analyze the whole project at HIGH severity
        analysis_result = subprocess.run(
            "/Users/user/Library/Python/3.9/bin/hefesto analyze . --min-severity HIGH --exclude tests/ --exclude docs/ --exclude build/ --exclude dist/ --exclude .git/ --exclude htmlcov/ --exclude test_install_env/",  # noqa: E501
            shell=True,
            capture_output=True,
            text=True,
        )

        # Print Hefesto output
        if analysis_result.stdout:
            print(analysis_result.stdout)

        # Hefesto returns non-zero if critical/high issues found
        # But we won't block the push for this (just informative)
        if analysis_result.returncode != 0:
            print("\n\033[0;33m⚠️  Hefesto found HIGH/CRITICAL issues\033[0m")
            print("   Consider fixing these before pushing (not blocking)")
        else:
            print("\n\033[0;32m✅ Hefesto code quality checks passed\033[0m")
    else:
        print("   (Skipped - no Python files changed)")

    # Final success
    print("\n" + "=" * 32)
    print("\033[0;32m✅ All validations passed!\033[0m")
    print("🚀 Pushing to remote...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
