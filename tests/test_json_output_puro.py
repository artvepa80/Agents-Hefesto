"""Tests for deliverable (A): JSON puro output + default excludes.

Verifies:
1. --output json produces parseable JSON on stdout with no banners
2. DEFAULT_EXCLUDES are applied automatically
3. User --exclude patterns merge with defaults
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. JSON puro — stdout must be valid JSON when --output json
# ---------------------------------------------------------------------------


def test_json_output_is_parseable(tmp_path):
    """hefesto analyze --output json must produce pure JSON on stdout."""
    # Create a trivial Python file so there's something to analyze
    sample = tmp_path / "sample.py"
    sample.write_text("x = 1\n")

    result = subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", str(sample), "--output", "json"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # stdout must be valid JSON
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"stdout is not valid JSON.\n--- stdout ---\n{result.stdout[:500]}\n"
            f"--- stderr ---\n{result.stderr[:500]}"
        )

    # Sanity check structure
    assert "summary" in data, "JSON must contain 'summary' key"
    assert "files" in data, "JSON must contain 'files' key"


def test_json_output_banners_on_stderr(tmp_path):
    """When --output json, informational banners go to stderr, not stdout."""
    sample = tmp_path / "sample.py"
    sample.write_text("x = 1\n")

    result = subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", str(sample), "--output", "json"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # stderr should contain the "Analyzing:" banner (unless --quiet suppresses it)
    assert "Analyzing:" in result.stderr or result.stderr == "", (
        "Expected 'Analyzing:' banner on stderr or empty stderr (quiet)"
    )

    # stdout must NOT contain "Analyzing:" text
    assert "Analyzing:" not in result.stdout, "Banner text leaked to stdout in json mode"


def test_json_output_quiet_flag(tmp_path):
    """--output json --quiet should still produce valid JSON."""
    sample = tmp_path / "sample.py"
    sample.write_text("x = 1\n")

    result = subprocess.run(
        [
            sys.executable, "-m", "hefesto.cli.main", "analyze",
            str(sample), "--output", "json", "--quiet",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    data = json.loads(result.stdout)
    assert "summary" in data


def test_text_output_unchanged(tmp_path):
    """--output text should still print banners to stdout (no regression)."""
    sample = tmp_path / "sample.py"
    sample.write_text("x = 1\n")

    result = subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", str(sample), "--output", "text"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Text mode should have human-readable output on stdout
    assert "Analyzing:" in result.stdout or "Analysis" in result.stdout


# ---------------------------------------------------------------------------
# 2. DEFAULT_EXCLUDES
# ---------------------------------------------------------------------------


def test_default_excludes_list():
    """DEFAULT_EXCLUDES must contain expected directories."""
    from hefesto.core.analyzer_engine import DEFAULT_EXCLUDES

    for pattern in [".venv/", "venv/", "node_modules/", "__pycache__/", ".git/"]:
        assert pattern in DEFAULT_EXCLUDES, f"{pattern} missing from DEFAULT_EXCLUDES"


def test_default_excludes_applied(tmp_path):
    """Files inside DEFAULT_EXCLUDES dirs should be skipped automatically."""
    from hefesto.core.analyzer_engine import AnalyzerEngine

    # Create a file inside .venv/ which should be excluded by default
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "pkg.py").write_text("import os\n")

    # Create a normal file that should be included
    (tmp_path / "app.py").write_text("import os\n")

    engine = AnalyzerEngine(severity_threshold="LOW", verbose=False)
    files = engine._find_files(tmp_path, [])

    file_strs = [str(f) for f in files]
    assert any("app.py" in f for f in file_strs), "app.py should be found"
    assert not any(".venv" in f for f in file_strs), ".venv/ files should be excluded by default"


def test_user_excludes_merge_with_defaults(tmp_path):
    """User --exclude patterns add to DEFAULT_EXCLUDES, not replace them."""
    from hefesto.core.analyzer_engine import AnalyzerEngine

    # .venv/ should be excluded by default
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "x.py").write_text("a = 1\n")

    # custom/ should be excluded by user pattern
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    (custom_dir / "y.py").write_text("b = 2\n")

    # normal file
    (tmp_path / "z.py").write_text("c = 3\n")

    engine = AnalyzerEngine(severity_threshold="LOW", verbose=False)
    files = engine._find_files(tmp_path, ["custom/"])

    file_strs = [str(f) for f in files]
    assert any("z.py" in f for f in file_strs), "z.py should be found"
    assert not any(".venv" in f for f in file_strs), ".venv should still be excluded"
    assert not any("custom" in f for f in file_strs), "custom/ should be excluded by user pattern"
