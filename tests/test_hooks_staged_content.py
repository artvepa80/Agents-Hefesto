"""Both pre-commit hooks analyze the staged (index) content, not the working tree."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRIB_HOOK = ROOT / "scripts" / "git-hooks" / "pre-commit"
PLANTED = (ROOT / ".github" / "action-smoke" / "critical_secret.py").read_text(encoding="utf-8")
CLEAN = "def add(a: int, b: int) -> int:\n    return a + b\n"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


def _env(**extra: str) -> dict:
    env = os.environ.copy()
    env["HEFESTO_TELEMETRY"] = "0"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("SKIP_HEFESTO_HOOKS", None)
    env.update(extra)
    return env


def _git(cwd: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=_env(**extra),
    )


def _write(repo: Path, name: str, text: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _stage(repo: Path, name: str, text: str) -> None:
    _write(repo, name, text)
    _git(repo, "add", "--", name)


@pytest.fixture(params=["contributor", "user"])
def hook_repo(request, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    if request.param == "contributor":
        (repo / "scripts").mkdir()
        shutil.copy(ROOT / "scripts" / "dogfood_changed.py", repo / "scripts")
        (repo / ".hefesto.yaml").write_text("exclude:\n  - tests/fixtures/\n", encoding="utf-8")
        venv_bin = repo / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").symlink_to(sys.executable)
        hook = CONTRIB_HOOK
    else:
        result = subprocess.run(
            [sys.executable, "-m", "hefesto.cli.main", "install-hooks"],
            cwd=repo,
            env=_env(),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        hook = repo / ".git" / "hooks" / "pre-commit"
    return request.param, repo, hook


def _run(repo: Path, hook: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(hook)], cwd=repo, env=_env(), capture_output=True, text=True, timeout=120
    )


def _out(result: subprocess.CompletedProcess) -> str:
    return result.stdout + result.stderr


def test_secret_staged_then_cleaned_on_disk_blocks(hook_repo) -> None:
    _, repo, hook = hook_repo
    _stage(repo, "app/secret.py", PLANTED)
    _write(repo, "app/secret.py", CLEAN)
    result = _run(repo, hook)
    assert result.returncode == 1, _out(result)


def test_clean_staged_with_secret_only_on_disk_passes(hook_repo) -> None:
    _, repo, hook = hook_repo
    _stage(repo, "app/ok.py", CLEAN)
    _write(repo, "app/ok.py", PLANTED)
    result = _run(repo, hook)
    assert result.returncode == 0, _out(result)


def test_test_path_rule_still_applies_to_staged_copy(hook_repo) -> None:
    _, repo, hook = hook_repo
    _stage(repo, "tests/test_secret.py", PLANTED)
    result = _run(repo, hook)
    assert result.returncode == 0, _out(result)


def test_paths_with_spaces_and_real_paths_in_report(hook_repo) -> None:
    _, repo, hook = hook_repo
    _stage(repo, "my dir/secret file.py", PLANTED)
    _write(repo, "my dir/secret file.py", CLEAN)
    result = _run(repo, hook)
    assert result.returncode == 1, _out(result)
    assert "my dir/secret file.py" in _out(result)
    assert "hefesto-staged." not in _out(result)


def test_delete_only_commit_passes(hook_repo) -> None:
    _, repo, hook = hook_repo
    _stage(repo, "app/ok.py", CLEAN)
    _git(repo, "commit", "-q", "-m", "init", SKIP_HEFESTO_HOOKS="1")
    _git(repo, "rm", "-q", "app/ok.py")
    result = _run(repo, hook)
    assert result.returncode == 0, _out(result)


def test_temp_copy_is_removed(hook_repo, tmp_path: Path) -> None:
    _, repo, hook = hook_repo
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    _stage(repo, "app/secret.py", PLANTED)
    result = subprocess.run(
        ["bash", str(hook)],
        cwd=repo,
        env=_env(TMPDIR=str(tmpdir)),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1, _out(result)
    assert list(tmpdir.iterdir()) == []


@pytest.mark.parametrize("trailing", ["", "/"], ids=["no-slash", "trailing-slash"])
def test_symlinked_tmpdir(hook_repo, tmp_path: Path, trailing: str) -> None:
    """Reproduces a real bug: TMPDIR behind a symlink leaked the temp-copy path.

    hefesto prints resolved paths (findings, and the ``Config:`` line), so with
    TMPDIR behind a symlink the output showed ``.../real/hefesto-staged.XXXX/...``
    instead of the repository path, because the hook stripped only the
    unresolved prefix. It happens with and without a trailing '/'. Likely on
    macOS, where TMPDIR is under /var -> /private/var (not verified on a Mac).
    Fixed by resolving the copy's path with ``pwd -P`` in both hooks.
    """
    _, repo, hook = hook_repo
    real = tmp_path / "real-tmp"
    real.mkdir()
    link = tmp_path / "link-tmp"
    link.symlink_to(real, target_is_directory=True)
    _stage(repo, "src/leak.py", PLANTED)
    result = subprocess.run(
        ["bash", str(hook)],
        cwd=repo,
        env=_env(TMPDIR=str(link) + trailing),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1, _out(result)
    assert "src/leak.py" in _out(result)
    assert "hefesto-staged" not in _out(result)
    assert list(real.glob("hefesto-staged.*")) == []
