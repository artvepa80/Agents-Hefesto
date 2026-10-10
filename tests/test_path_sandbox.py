"""Tests for hefesto.security.path_sandbox.resolve_under_root."""

import os

import pytest

from hefesto.security.path_sandbox import resolve_under_root


def test_relative_path_inside_root(tmp_path):
    (tmp_path / "src").mkdir()
    assert resolve_under_root("src", tmp_path) == (tmp_path / "src").resolve()


def test_root_itself_is_allowed(tmp_path):
    assert resolve_under_root(".", tmp_path) == tmp_path.resolve()


def test_absolute_path_inside_root(tmp_path):
    target = tmp_path / "a.cbl"
    target.write_text("x")
    assert resolve_under_root(str(target), tmp_path) == target.resolve()


@pytest.mark.parametrize("path", ["..", "../x", "src/../../x", "/etc/passwd"])
def test_paths_escaping_root_are_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        resolve_under_root(path, tmp_path / "root")


def test_sibling_with_same_prefix_is_rejected(tmp_path):
    (tmp_path / "root").mkdir()
    (tmp_path / "root-evil").mkdir()
    with pytest.raises(ValueError):
        resolve_under_root("../root-evil", tmp_path / "root")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_symlink_escaping_root_is_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        resolve_under_root("link/other", root)
