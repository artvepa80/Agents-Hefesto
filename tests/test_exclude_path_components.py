"""Exclude patterns match path components below the analysis root.

Default excludes (``build/``, ``dist/``, ``venv/`` ...) and ``--exclude``
patterns used to be matched as substrings of the absolute path. A target
whose own path contained a pattern (a checkout in ``app-build/``, a project
under ``venv/``) was silently analyzed with zero files, and in-tree names
such as ``rebuild/`` were dropped as if they were ``build/``.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto.analyzers.operational_truth.imports_vs_deps import ImportsVsDepsAnalyzer
from hefesto.core.analyzer_engine import AnalyzerEngine, path_is_excluded

PY_SOURCE = 'import os\n\n\ndef run(cmd):\n    os.system("ls " + cmd)\n'
COPYBOOK = "       01  REC.\n           05 F PIC X.\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"
    "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
    "           COPY SHAREDREC.\n"
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _names(root: Path, files):
    return sorted(Path(f).resolve().relative_to(root.resolve()).as_posix() for f in files)


def _engine() -> AnalyzerEngine:
    return AnalyzerEngine(severity_threshold="LOW", quiet=True)


class TestRootPathIsNotMatched:
    @pytest.mark.parametrize("name", ["app-build", "rebuild", "app-dist", "my.venv"])
    def test_root_whose_name_ends_like_a_default_exclude(self, tmp_path, name):
        root = tmp_path / name
        _write(root / "src" / "app.py", PY_SOURCE)
        assert _names(root, _engine()._find_files(root, [])) == ["src/app.py"]

    @pytest.mark.parametrize("parent", ["build", "dist", "venv", "node_modules", "x.egg-info"])
    def test_root_below_a_directory_named_like_a_default_exclude(self, tmp_path, parent):
        root = tmp_path / parent / "project"
        _write(root / "app.py", PY_SOURCE)
        assert _names(root, _engine()._find_files(root, [])) == ["app.py"]

    def test_user_pattern_matching_the_root_name_does_not_suppress_the_root(self, tmp_path):
        root = tmp_path / "custom"
        _write(root / "app.py", PY_SOURCE)
        assert _names(root, _engine()._find_files(root, ["custom/"])) == ["app.py"]

    def test_cli_cd_into_root_and_analyze_dot(self, tmp_path):
        root = tmp_path / "app-build"
        _write(root / "src" / "app.py", PY_SOURCE)
        env = dict(os.environ, HEFESTO_TELEMETRY="0")
        result = subprocess.run(
            [sys.executable, "-m", "hefesto.cli.main", "analyze", ".", "--fail-on", "HIGH"],
            cwd=root,
            capture_output=True,
            text=True,
            env=env,
        )
        assert "Files analyzed: 1" in result.stdout, result.stdout + result.stderr
        assert result.returncode == 1, result.stdout + result.stderr


class TestNestedExcludesStillApply:
    def test_default_excludes_below_the_root(self, tmp_path):
        _write(tmp_path / "app.py", PY_SOURCE)
        for d in ("build", "dist", "venv", ".venv", "node_modules", "pkg.egg-info", "a/build"):
            _write(tmp_path / d / "skip.py", PY_SOURCE)
        assert _names(tmp_path, _engine()._find_files(tmp_path, [])) == ["app.py"]

    def test_names_that_only_contain_an_exclude_are_kept(self, tmp_path):
        for d in ("rebuild", "build-tools", "distro", "myvenv", "dist.d"):
            _write(tmp_path / d / "keep.py", PY_SOURCE)
        assert _names(tmp_path, _engine()._find_files(tmp_path, [])) == [
            "build-tools/keep.py",
            "dist.d/keep.py",
            "distro/keep.py",
            "myvenv/keep.py",
            "rebuild/keep.py",
        ]

    def test_user_patterns(self, tmp_path):
        _write(tmp_path / "app.py", PY_SOURCE)
        _write(tmp_path / "evil.py", PY_SOURCE)
        _write(tmp_path / "pkg" / "custom" / "x.py", PY_SOURCE)
        _write(tmp_path / "customer" / "y.py", PY_SOURCE)
        _write(tmp_path / "src" / "legacy" / "z.py", PY_SOURCE)
        _write(tmp_path / "legacy" / "w.py", PY_SOURCE)
        found = _engine()._find_files(tmp_path, ["custom/", "evil.py", "src/legacy/"])
        assert _names(tmp_path, found) == ["app.py", "customer/y.py", "legacy/w.py"]


class TestPathIsExcluded:
    @pytest.mark.parametrize(
        "rel, patterns, expected",
        [
            (("build", "a.py"), ["build/"], True),
            (("rebuild", "a.py"), ["build/"], False),
            (("x", "build", "a.py"), ["build/"], True),
            (("build",), ["build/"], False),  # a file named build is not a build/ dir
            (("pkg.egg-info", "a.py"), [".egg-info/"], True),
            (("src", "legacy", "a.py"), ["src/legacy/"], True),
            (("legacy", "a.py"), ["src/legacy/"], False),
            (("evil.py",), ["evil.py"], True),
            (("sub", "evil.py"), ["evil.py"], True),
            (("notevil.py",), ["evil.py"], False),
            (("tests", "t.py"), ["tests"], True),
            (("a.py",), [" ", ""], False),
            (("win", "a.py"), ["win\\"], True),
            (("x", "a.py"), ["./x/"], True),
        ],
    )
    def test_matching(self, rel, patterns, expected):
        assert path_is_excluded(rel, patterns) is expected

    def test_directory_walk_form(self):
        assert path_is_excluded(("a", "build"), ["build/"], is_dir=True)
        assert not path_is_excluded(("a", "rebuild"), ["build/"], is_dir=True)


class TestCopybookDiscovery:
    def test_extensionless_copybook_found_when_root_ends_like_an_exclude(self, tmp_path):
        root = tmp_path / "cobol-build"
        _write(root / "copy" / "SHAREDREC", COPYBOOK)
        found = AnalyzerEngine._extra_copybook_candidates(root, [])
        assert _names(root, found) == ["copy/SHAREDREC"]

    def test_extensionless_copybook_in_nested_build_is_excluded(self, tmp_path):
        _write(tmp_path / "copy" / "KEEP", COPYBOOK)
        _write(tmp_path / "build" / "SKIP", COPYBOOK)
        _write(tmp_path / "rebuild" / "ALSO", COPYBOOK)
        found = AnalyzerEngine._extra_copybook_candidates(tmp_path, [])
        assert _names(tmp_path, found) == ["copy/KEEP", "rebuild/ALSO"]

    def test_user_pattern_on_extensionless_copybook(self, tmp_path):
        _write(tmp_path / "copy" / "KEEP", COPYBOOK)
        _write(tmp_path / "old" / "SKIP", COPYBOOK)
        found = AnalyzerEngine._extra_copybook_candidates(tmp_path, ["old/"])
        assert _names(tmp_path, found) == ["copy/KEEP"]

    def test_prepare_cobol_index_under_dist_root(self, tmp_path):
        root = tmp_path / "app-dist"
        _write(root / "cpy" / "SHAREDREC.cpy", COPYBOOK)
        for n in range(2):
            _write(root / "cbl" / f"P{n}.cbl", PROGRAM)
        engine = _engine()
        engine.prepare_cobol_index([str(root)], [])
        assert engine._cobol_index is not None
        assert len(engine._cobol_index.dependent_programs("SHAREDREC")) == 2

    def test_analyze_path_resolves_copybook_under_build_parent(self, tmp_path):
        root = tmp_path / "build" / "app"
        _write(root / "SHAREDREC", COPYBOOK)
        _write(root / "P.cbl", PROGRAM)
        report = _engine().analyze_path(str(root))
        analyzed = sorted(Path(fr.file_path).name for fr in report.file_results)
        rules = {i.rule_id for fr in report.file_results for i in fr.issues}
        assert "P.cbl" in analyzed
        assert "COBOL015" not in rules  # SHAREDREC (no extension) was indexed


class TestImportsVsDeps:
    PYPROJECT = '[project]\nname = "demo"\nversion = "1"\ndependencies = ["click"]\n'

    @pytest.mark.parametrize("parent", ["build", "docs", "examples", "tests", "venv"])
    def test_project_below_an_excluded_name_is_scanned(self, tmp_path, parent):
        root = tmp_path / parent / "proj"
        _write(root / "pyproject.toml", self.PYPROJECT)
        _write(root / "demo" / "__init__.py", "")
        _write(root / "demo" / "main.py", "import click\nimport requests\n")
        msgs = " ".join(i.message for i in ImportsVsDepsAnalyzer().analyze_project(root))
        assert "requests" in msgs

    def test_excluded_dirs_inside_the_project_are_still_skipped(self, tmp_path):
        _write(tmp_path / "pyproject.toml", self.PYPROJECT)
        _write(tmp_path / "demo" / "__init__.py", "")
        _write(tmp_path / "demo" / "main.py", "import click\n")
        _write(tmp_path / "tests" / "test_x.py", "import requests\n")
        assert ImportsVsDepsAnalyzer().analyze_project(tmp_path) == []
