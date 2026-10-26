"""Tests for hefesto.critical_tests.git_diff (merge-base, name-status, renames)."""

import subprocess
from pathlib import Path

import pytest

from hefesto.critical_tests.git_diff import (
    ADDED,
    DELETED_FILE,
    MODIFIED,
    RENAMED,
    FileChange,
    GitError,
    changed_files,
    merge_base,
    parse_name_status,
    read_file_at,
    pair_test_files,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_auth.py").write_text("def test_a():\n    assert 1 == 1\n" * 1)
    (tests / "test_gone.py").write_text("def test_g():\n    assert True is True\n")
    (tests / "test_edit.py").write_text("def test_e():\n    assert 2 == 2\n")
    _commit(tmp_path, "base")
    return tmp_path


# ------------------------------------------------------------ parsing


def test_parse_name_status_handles_each_status() -> None:
    raw = "M\0a.py\0A\0b.py\0D\0c.py\0R087\0old.py\0new.py\0T\0d.py\0"
    assert parse_name_status(raw) == [
        FileChange(MODIFIED, "a.py", "a.py"),
        FileChange(ADDED, None, "b.py"),
        FileChange(DELETED_FILE, "c.py", None),
        FileChange(RENAMED, "old.py", "new.py", similarity=87),
        FileChange(MODIFIED, "d.py", "d.py"),
    ]


def test_parse_name_status_empty() -> None:
    assert parse_name_status("") == []


def test_parse_name_status_rejects_truncated_rename() -> None:
    with pytest.raises(GitError):
        parse_name_status("R100\0old.py\0")


def test_parse_name_status_rejects_unknown_status() -> None:
    with pytest.raises(GitError):
        parse_name_status("X\0a.py\0")


def test_parse_name_status_keeps_paths_with_spaces_and_tabs() -> None:
    raw = "R100\0tests/old name.py\0tests/new\tname.py\0"
    assert parse_name_status(raw) == [
        FileChange(RENAMED, "tests/old name.py", "tests/new\tname.py", similarity=100)
    ]


# ------------------------------------------------------------ git


def test_merge_base_of_diverged_branch(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "x.py").write_text("x = 1\n")
    _commit(repo, "feature")
    _git(repo, "checkout", "-q", "main")
    (repo / "y.py").write_text("y = 1\n")
    _commit(repo, "main moves on")
    assert merge_base(repo, "main", "feature") == base


def test_merge_base_unknown_ref_raises(repo: Path) -> None:
    with pytest.raises(GitError):
        merge_base(repo, "no-such-branch", "HEAD")


def test_changed_files_detects_rename_modify_delete_add(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", "tests/test_auth.py", "tests/test_authorization.py")
    (repo / "tests" / "test_gone.py").unlink()
    (repo / "tests" / "test_edit.py").write_text("def test_e():\n    pass\n")
    (repo / "tests" / "test_new.py").write_text("def test_n():\n    assert 3 == 3\n")
    head = _commit(repo, "head")
    by_kind = {(c.status, c.old_path, c.new_path) for c in changed_files(repo, base, head)}
    assert by_kind == {
        (RENAMED, "tests/test_auth.py", "tests/test_authorization.py"),
        (DELETED_FILE, "tests/test_gone.py", None),
        (MODIFIED, "tests/test_edit.py", "tests/test_edit.py"),
        (ADDED, None, "tests/test_new.py"),
    }


def test_changed_files_ignores_user_diff_config(repo: Path) -> None:
    _git(repo, "config", "diff.renames", "false")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", "tests/test_auth.py", "tests/test_renamed.py")
    head = _commit(repo, "rename")
    assert [c.status for c in changed_files(repo, base, head)] == [RENAMED]


def test_read_file_at(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    assert read_file_at(repo, head, "tests/test_edit.py") == "def test_e():\n    assert 2 == 2\n"
    assert read_file_at(repo, head, "tests/missing.py") is None


# ------------------------------------------------------------ pairing


def test_pairs_follow_renames_and_deletions() -> None:
    changes = [
        FileChange(RENAMED, "tests/test_auth.py", "tests/test_authz.py", similarity=95),
        FileChange(DELETED_FILE, "tests/test_gone.py", None),
        FileChange(MODIFIED, "tests/test_edit.py", "tests/test_edit.py"),
        FileChange(MODIFIED, "tests/test_other.py", "tests/test_other.py"),
        FileChange(ADDED, None, "tests/test_auth.py"),
    ]
    mapped = [
        "tests/test_auth.py",
        "tests/test_gone.py",
        "tests/test_edit.py",
        "tests/test_same.py",
    ]
    assert pair_test_files(changes, mapped) == [
        ("tests/test_auth.py", "tests/test_authz.py"),
        ("tests/test_gone.py", None),
        ("tests/test_edit.py", "tests/test_edit.py"),
    ]


def test_pairs_ignore_added_files() -> None:
    changes = [FileChange(ADDED, None, "tests/test_auth.py")]
    assert pair_test_files(changes, ["tests/test_auth.py"]) == []
