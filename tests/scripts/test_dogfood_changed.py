"""The changed-file gate fails on a planted CRITICAL and passes when it should."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "dogfood_changed.py"


def _load():
    spec = importlib.util.spec_from_file_location("dogfood_changed", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MOD = _load()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def test_changed_files_skip_deletions(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "keep.py").write_text("x = 1\n")
    (tmp_path / "gone.py").write_text("y = 1\n")
    base = _commit_all(tmp_path, "base")
    (tmp_path / "keep.py").write_text("x = 2\n")
    (tmp_path / "gone.py").unlink()
    (tmp_path / "notes.md").write_text("# notes\n")
    head = _commit_all(tmp_path, "edit")
    assert MOD.changed_files(tmp_path, base, head) == ["keep.py", "notes.md"]


def test_zero_base_lists_files_in_head(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n")
    head = _commit_all(tmp_path, "init")
    assert MOD.changed_files(tmp_path, "0" * 40, head) == ["app.py"]


def test_missing_base_is_an_error(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n")
    head = _commit_all(tmp_path, "init")
    with pytest.raises(MOD.DogfoodError):
        MOD.changed_files(tmp_path, "deadbeef", head)


def test_gate_fails_on_planted_akia(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    secret = tmp_path / "prod_config.py"
    secret.write_text('AWS_ACCESS_KEY_ID = "AKIA0123456789012345"\n')
    assert MOD.run_changed_gate(tmp_path, ["prod_config.py"]) != 0
    out = capfd.readouterr().out
    assert "--fail-on critical" in out
    assert "Gate failure" in out


def test_ignore_comment_does_not_suppress(tmp_path: Path) -> None:
    """``# hefesto: ignore`` is not implemented; the planted key still fails."""
    path = tmp_path / "prod_config.py"
    path.write_text('API_KEY = "abcdefghijklmnopqrstuvwxyz"  # hefesto: ignore HARDCODED_SECRET\n')
    assert MOD.run_changed_gate(tmp_path, ["prod_config.py"]) != 0


def test_gate_passes_on_clean_python(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def add(left, right):\n    return left + right\n")
    assert MOD.run_changed_gate(tmp_path, ["app.py"]) == 0


def test_gate_passes_on_markdown_only(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "notes.md").write_text("# notes\n")
    assert MOD.run_changed_gate(tmp_path, ["notes.md"]) == 0
    out = capfd.readouterr().out
    assert "--allow-no-files" in out
    assert "Gate skipped: no files were analyzed (--allow-no-files)" in out


def test_gate_passes_when_no_files_changed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MOD.run_changed_gate(tmp_path, []) == 0
    out = capsys.readouterr().out
    assert "no changed .py files" in out
    assert "analyze was not run" in out


def test_gate_fails_on_ruff(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import os\n")
    assert MOD.run_changed_gate(tmp_path, ["app.py"]) != 0


def test_self_check_fails_planted_and_passes_current_tree() -> None:
    assert MOD.self_check(REPO_ROOT) == 0


def test_main_requires_base() -> None:
    assert MOD.main(["--repo", str(REPO_ROOT)]) == 2


def test_ruff_respects_extend_exclude(tmp_path: Path) -> None:
    """A changed file under an excluded path (scripts/) does not fail ruff."""
    (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = ["scripts"]\n')
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "legacy.py").write_text("import os\n")
    assert "--force-exclude" in MOD.ruff_argv(["scripts/legacy.py"])
    assert MOD.run_changed_gate(tmp_path, ["scripts/legacy.py"]) == 0


def test_ruff_still_fails_outside_excluded_paths(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = ["scripts"]\n')
    (tmp_path / "app.py").write_text("import os\n")
    assert MOD.run_changed_gate(tmp_path, ["app.py"]) != 0


@pytest.mark.parametrize(
    "name",
    [
        "tests/fixtures/devops_dispatch/json/config.json",
        "tests/fixtures/x/secret.py",
        ".github/action-smoke/critical_secret.py",
    ],
)
def test_fixture_paths_are_excluded_from_gate(name: str) -> None:
    kept, skipped = MOD.split_gate_files([name, "hefesto/core.py"])
    assert kept == ["hefesto/core.py"]
    assert skipped == [name]


def test_fixture_with_secret_does_not_fail_main(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("x\n")
    base = _commit_all(tmp_path, "base")
    fixture = tmp_path / "tests" / "fixtures" / "secret.py"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('AWS_ACCESS_KEY_ID = "AKIA0123456789012345"\n')
    _commit_all(tmp_path, "fixture")
    assert MOD.main(["--repo", str(tmp_path), "--base", base]) == 0
    assert "excluded from the gate" in capsys.readouterr().out


def test_non_fixture_secret_still_fails_main(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("x\n")
    base = _commit_all(tmp_path, "base")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "prod_config.py").write_text(
        'AWS_ACCESS_KEY_ID = "AKIA0123456789012345"\n'
    )
    _commit_all(tmp_path, "secret")
    assert MOD.main(["--repo", str(tmp_path), "--base", base]) == 1
