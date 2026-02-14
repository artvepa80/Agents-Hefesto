"""
Tests for Patch F: install-hooks command.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import os
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

    def _create_hook_templates(self, repo_root):
        """Create both hook templates in the repo structure."""
        hooks_dir = repo_root / "scripts" / "git-hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        pre_push = hooks_dir / "pre-push"
        pre_push.write_text("#!/bin/bash\necho pre-push\n")

        pre_commit = hooks_dir / "pre-commit"
        pre_commit.write_text("#!/bin/bash\necho pre-commit\n")

        return pre_push, pre_commit

    def test_install_hooks_copies_and_makes_executable(self, env_with_path):
        """Test that install-hooks copies both hooks and makes them executable."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / ".git").mkdir()

            pre_push_src, pre_commit_src = self._create_hook_templates(repo_root)

            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert "pre-commit: installed to" in result.stdout
            assert "pre-push: installed to" in result.stdout

            # Verify both destinations exist and are executable
            for hook_name in ("pre-commit", "pre-push"):
                dest = repo_root / ".git" / "hooks" / hook_name
                assert dest.exists(), f"{hook_name} should exist"
                st = os.stat(dest)
                assert bool(st.st_mode & stat.S_IEXEC), f"{hook_name} should be executable"

            # Verify content matches
            assert (
                repo_root / ".git" / "hooks" / "pre-push"
            ).read_text() == pre_push_src.read_text()
            assert (
                repo_root / ".git" / "hooks" / "pre-commit"
            ).read_text() == pre_commit_src.read_text()

    def test_install_hooks_skips_missing_templates(self, env_with_path):
        """Test that install-hooks skips hooks whose templates don't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / ".git").mkdir()
            (repo_root / "scripts" / "git-hooks").mkdir(parents=True)

            # Only create pre-push, not pre-commit
            (repo_root / "scripts" / "git-hooks" / "pre-push").write_text(
                "#!/bin/bash\necho ok\n"
            )

            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert "Skipping pre-commit" in result.stderr
            assert "pre-push: installed to" in result.stdout

    def test_install_hooks_fails_if_not_in_repo(self, env_with_path):
        """Test that install-hooks fails if .git dir not found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
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
        """Test that install-hooks warns if destination exists and differs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / ".git" / "hooks").mkdir(parents=True)

            pre_push_src, pre_commit_src = self._create_hook_templates(repo_root)

            # Write different content to destination
            dest_hook = repo_root / ".git" / "hooks" / "pre-push"
            dest_hook.write_text("OLD CONTENT")

            # Run without force -> warns but continues (exit 0, other hooks may install)
            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert "pre-push: already exists" in result.stdout
            assert "Use --force to overwrite" in result.stdout
            # pre-commit should still install
            assert "pre-commit: installed to" in result.stdout

            # Run with force -> overwrites
            result_force = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks", "--force"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )
            assert result_force.returncode == 0, f"Force install failed: {result_force.stderr}"
            assert dest_hook.read_text() == pre_push_src.read_text()

    def test_install_hooks_idempotent_if_identical(self, env_with_path):
        """Test that install-hooks does nothing if content matches."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / ".git" / "hooks").mkdir(parents=True)

            pre_push_src, pre_commit_src = self._create_hook_templates(repo_root)

            # Copy same content to destinations
            dest_push = repo_root / ".git" / "hooks" / "pre-push"
            dest_push.write_text(pre_push_src.read_text())
            dest_commit = repo_root / ".git" / "hooks" / "pre-commit"
            dest_commit.write_text(pre_commit_src.read_text())

            result = subprocess.run(
                [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
                cwd=repo_root,
                env=env_with_path,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert "pre-push: already up to date." in result.stdout
            assert "pre-commit: already up to date." in result.stdout
