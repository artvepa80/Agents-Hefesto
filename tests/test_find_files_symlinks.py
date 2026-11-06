"""A file reached through several symlinks is analyzed once."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hefesto.core.analyzer_engine import AnalyzerEngine


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlinked_copies_are_found_once(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    real = tmp_path / "a" / "helper.py"
    real.write_text("x = 1\n")
    (tmp_path / "b" / "helper.py").symlink_to(Path("..") / "a" / "helper.py")
    (tmp_path / "c.py").symlink_to(real)

    files = AnalyzerEngine()._find_files(tmp_path, [])

    assert [f.resolve() for f in files] == [real.resolve()]


def test_distinct_files_are_kept(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("x = 1\n")
    (tmp_path / "y.py").write_text("y = 1\n")

    files = AnalyzerEngine()._find_files(tmp_path, [])

    assert sorted(f.name for f in files) == ["x.py", "y.py"]
