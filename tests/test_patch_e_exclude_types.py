"""
Tests for Patch E: --exclude-types gate filtering.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def _find_repo_root() -> Path:
    """Find repository root by searching upward for pyproject.toml."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not find repo root (pyproject.toml not found)")


class TestExcludeTypesGateFiltering:
    """Tests for --exclude-types CLI option and gate filtering."""

    def test_fail_on_critical_without_exclude_returns_exit_1(self):
        """Without --exclude-types, CRITICAL complexity issues cause exit 2."""
        # Create a file with a very complex function (will trigger VERY_HIGH_COMPLEXITY)
        # We use a known complex pattern
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Generate a function with high cyclomatic complexity
            f.write("def complex_func(a, b, c, d, e, f, g, h, i, j):\n")
            for i in range(25):
                f.write(f"    if a == {i}: return {i}\n")
                f.write(f"    elif b == {i}: return {i * 2}\n")
            f.write("    return 0\n")
            temp_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hefesto.cli.main",
                    "analyze",
                    temp_file,
                    "--fail-on",
                    "CRITICAL",
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                cwd=_find_repo_root(),
            )
            # Should exit with code 2 because VERY_HIGH_COMPLEXITY is CRITICAL
            assert result.returncode == 1, (
                f"Expected exit code 1, got {result.returncode}. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )
        finally:
            Path(temp_file).unlink()

    def test_exclude_types_filters_complexity_returns_exit_0(self):
        """With --exclude-types VERY_HIGH_COMPLEXITY, complexity CRITICALs are ignored."""
        # Same complex function as above
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def complex_func(a, b, c, d, e, f, g, h, i, j):\n")
            for i in range(25):
                f.write(f"    if a == {i}: return {i}\n")
                f.write(f"    elif b == {i}: return {i * 2}\n")
            f.write("    return 0\n")
            temp_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hefesto.cli.main",
                    "analyze",
                    temp_file,
                    "--fail-on",
                    "CRITICAL",
                    "--quiet",
                    "--exclude-types",
                    "VERY_HIGH_COMPLEXITY",
                ],
                capture_output=True,
                text=True,
                cwd=_find_repo_root(),
            )
            # Should exit with code 0 because the only CRITICAL is excluded
            assert result.returncode == 0, (
                f"Expected exit code 0, got {result.returncode}. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )
        finally:
            Path(temp_file).unlink()

    def test_exclude_types_does_not_hide_security_criticals(self):
        """Excluding complexity types should NOT hide CRITICAL security issues (EVAL_USAGE)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # This file has an actual eval() call (CRITICAL security issue)
            f.write('result = eval("1+1")\n')
            temp_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hefesto.cli.main",
                    "analyze",
                    temp_file,
                    "--fail-on",
                    "CRITICAL",
                    "--quiet",
                    "--exclude-types",
                    "VERY_HIGH_COMPLEXITY,LONG_FUNCTION",
                ],
                capture_output=True,
                text=True,
                cwd=_find_repo_root(),
            )
            # Should still exit with code 2 because EVAL_USAGE is NOT excluded
            assert result.returncode == 1, (
                f"Expected exit code 1 (EVAL_USAGE not excluded), got {result.returncode}. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )
        finally:
            Path(temp_file).unlink()

    def test_exclude_multiple_types(self):
        """Multiple types can be excluded with comma-separated list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Long function that would trigger LONG_FUNCTION
            f.write("def long_func():\n")
            for i in range(60):
                f.write(f"    x{i} = {i}\n")
            f.write("    return x0\n")
            temp_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hefesto.cli.main",
                    "analyze",
                    temp_file,
                    "--fail-on",
                    "MEDIUM",
                    "--quiet",
                    "--exclude-types",
                    "LONG_FUNCTION,HIGH_COMPLEXITY",
                ],
                capture_output=True,
                text=True,
                cwd=_find_repo_root(),
            )
            # Should exit with code 0 because LONG_FUNCTION is excluded
            assert result.returncode == 0, (
                f"Expected exit code 0, got {result.returncode}. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )
        finally:
            Path(temp_file).unlink()

    def test_exclude_types_case_insensitive(self):
        """--exclude-types should be case-insensitive."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('result = eval("1+1")\n')
            temp_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hefesto.cli.main",
                    "analyze",
                    temp_file,
                    "--fail-on",
                    "CRITICAL",
                    "--quiet",
                    "--exclude-types",
                    "eval_usage",  # lowercase - should still match EVAL_USAGE
                ],
                capture_output=True,
                text=True,
                cwd=_find_repo_root(),
            )
            # Should exit with code 0 because EVAL_USAGE is excluded (case-insensitive)
            assert result.returncode == 0, (
                f"Expected exit code 0 (eval_usage excluded), got {result.returncode}. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )
        finally:
            Path(temp_file).unlink()
