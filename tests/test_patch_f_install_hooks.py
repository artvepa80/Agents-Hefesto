"""
Tests for Patch F: install-hooks command.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestInstallHooks:
    """Tests for 'hefesto install-hooks' command."""

    @pytest.fixture
    def env_with_path(self):
        """Environment with PYTHONPATH set to include current repo root."""
        env = os.environ.copy()
        root = Path(__file__).resolve().parent.parent
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        return env

    def test_install_hooks_copies_and_makes_executable(self, env_with_path):
        """Test that install-hooks copies the script and checks --exclude-types."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)

            # Setup fake repo structure
            (repo_root / ".git").mkdir()
            (repo_root / "scripts" / "git-hooks").mkdir(parents=True)

            # Create source hook with expected content
            source_hook = repo_root / "scripts" / "git-hooks" / "pre-push"
            source_content = "#!/bin/bash\nhefesto analyze --exclude-types VERY_HIGH_COMPLEXITY\n"
            source_hook.write_text(source_content)

            # Run install-hooks
            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert "Successfully installed pre-push hook" in result.stdout
            assert "This hook runs 'hefesto analyze' with security gate defaults" in result.stdout

            # Verify destination
            dest_hook = repo_root / ".git" / "hooks" / "pre-push"
            assert dest_hook.exists()
            assert dest_hook.read_text() == source_content

            # Verify executable permission
            st = os.stat(dest_hook)
            assert bool(st.st_mode & stat.S_IEXEC), "Hook should be executable"

    def test_install_hooks_validates_exclude_types(self, env_with_path):
        """Test that install-hooks warns if --exclude-types is missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)

            # Setup fake repo structure
            (repo_root / ".git").mkdir()
            (repo_root / "scripts" / "git-hooks").mkdir(parents=True)

            # Create source hook WITHOUT expected content
            source_hook = repo_root / "scripts" / "git-hooks" / "pre-push"
            source_content = "#!/bin/bash\nhefesto analyze\n"
            source_hook.write_text(source_content)

            # Run install-hooks
            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )

            # Should exit with error (validation failure)
            assert (
                result.returncode == 1
            ), f"Should exit 1 on validation failure. Stderr: {result.stderr}"
            assert (
                "ERROR: Installed hook does not appear to contain --exclude-types" in result.stderr
            )

    def test_install_hooks_fails_if_not_in_repo(self, env_with_path):
        """Test that install-hooks fails if .git dir not found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # No .git dir here
            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=tmp_dir,
                env=env_with_path,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 1
            assert "Not a git repository" in result.stderr

    def test_install_hooks_requires_force_to_overwrite_diff(self, env_with_path):
        """Test that install-hooks requires --force if destination exists and differs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / ".git" / "hooks").mkdir(parents=True)
            (repo_root / "scripts" / "git-hooks").mkdir(parents=True)

            source_hook = repo_root / "scripts" / "git-hooks" / "pre-push"
            source_hook.write_text(
                "#!/bin/bash\nhefesto analyze --exclude-types VERY_HIGH_COMPLEXITY\n"
            )

            dest_hook = repo_root / ".git" / "hooks" / "pre-push"
            dest_hook.write_text("OLD CONTENT")

            # First run without force -> fail
            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1
            assert "Pre-push hook already exists" in result.stdout
            assert "Use --force" in result.stdout

            # Second run with force -> success
            result_force = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks", "--force"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )
            assert result_force.returncode == 0, f"Force install failed: {result_force.stderr}"
            assert "--exclude-types" in dest_hook.read_text()

    def test_install_hooks_idempotent_if_identical(self, env_with_path):
        """Test that install-hooks does nothing if content matches."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / ".git" / "hooks").mkdir(parents=True)
            (repo_root / "scripts" / "git-hooks").mkdir(parents=True)

            content = "#!/bin/bash\nhefesto analyze --exclude-types VERY_HIGH_COMPLEXITY\n"
            source_hook = repo_root / "scripts" / "git-hooks" / "pre-push"
            source_hook.write_text(content)

            dest_hook = repo_root / ".git" / "hooks" / "pre-push"
            dest_hook.write_text(content)

            # Run without force -> should pass (up to date)
            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert "Pre-push hook is already up to date" in result.stdout
