import os
import subprocess
import sys
from pathlib import Path

# Path to the script under test
SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "verify_release_tag.py"


def run_script(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Helper to run the verification script."""
    cmd = [sys.executable, str(SCRIPT_PATH)] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def create_pyproject(path: Path, version: str):
    """Create a minimal pyproject.toml."""
    content = f"""
[project]
name = "hefesto-ai"
version = "{version}"
"""
    (path / "pyproject.toml").write_text(content, encoding="utf-8")


def test_valid_release_tag_matches(tmp_path):
    """Test standard release tag matching."""
    create_pyproject(tmp_path, "1.2.3")
    result = run_script(tmp_path, ["--tag", "v1.2.3"])
    print(result.stdout)
    assert result.returncode == 0
    assert "SUCCESS" in result.stdout


def test_valid_rc_tag_matches(tmp_path):
    """Test release candidate tag matching."""
    create_pyproject(tmp_path, "1.2.3rc1")
    result = run_script(tmp_path, ["--tag", "v1.2.3rc1"])
    print(result.stdout)
    assert result.returncode == 0
    assert "SUCCESS" in result.stdout


def test_mismatch_fails(tmp_path):
    """Test version mismatch failure."""
    create_pyproject(tmp_path, "1.2.3")
    result = run_script(tmp_path, ["--tag", "v1.2.4"])
    assert result.returncode == 2
    assert "ERROR: tag version" in result.stderr


def test_invalid_tag_format(tmp_path):
    """Test invalid tag format (missing v)."""
    create_pyproject(tmp_path, "1.2.3")
    result = run_script(tmp_path, ["--tag", "1.2.3"])
    assert result.returncode == 2
    assert "must start with 'v'" in result.stderr


def test_missing_pyproject(tmp_path):
    """Test missing pyproject.toml."""
    result = run_script(tmp_path, ["--tag", "v1.2.3"])
    assert result.returncode == 1
    assert "not found" in result.stderr


def test_project_name_mismatch_fails(tmp_path):
    """Test that project name mismatch fails."""
    # Create pyproject with wrong name
    content = """
[project]
name = "wrong-name"
version = "1.2.3"
"""
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")

    result = run_script(tmp_path, ["--tag", "v1.2.3"])
    assert result.returncode == 1
    assert "project.name 'wrong-name' != 'hefesto-ai'" in result.stderr


def test_env_var_fallback(tmp_path):
    """Test GITHUB_REF_NAME env var fallback."""
    create_pyproject(tmp_path, "1.2.3")

    # Copy current environment
    run_env = os.environ.copy()
    run_env["GITHUB_REF_NAME"] = "v1.2.3"

    # Ensure PYTHONPATH includes current dir if needed, though script is standalone

    cmd = [sys.executable, str(SCRIPT_PATH)]
    result = subprocess.run(cmd, cwd=tmp_path, env=run_env, capture_output=True, text=True)

    assert result.returncode == 0
    assert "SUCCESS" in result.stdout
