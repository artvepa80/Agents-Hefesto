"""The repo's contributor pre-commit hook gates staged files, honoring .hefesto.yaml."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "git-hooks" / "pre-commit"
PLANTED = (ROOT / ".github" / "action-smoke" / "critical_secret.py").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "dogfood_changed.py", tmp_path / "scripts")
    (tmp_path / ".hefesto.yaml").write_text("exclude:\n  - tests/fixtures/\n", encoding="utf-8")
    _make_venv(tmp_path / ".venv")
    return tmp_path


def _make_venv(path: Path) -> None:
    venv_bin = path / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(sys.executable)


def _bare_path() -> str:
    """PATH with git and bash, but no hefesto. Used with an empty PYTHONPATH."""
    dirs = {str(Path(shutil.which(tool) or "").parent) for tool in ("git", "bash")}
    return os.pathsep.join(sorted(dirs))


def _run_hook(repo: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HEFESTO_TELEMETRY"] = "0"
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("SKIP_HEFESTO_HOOKS", None)
    env.pop("VIRTUAL_ENV", None)
    env.update(extra)
    if env.get("PYTHONPATH") == "":
        del env["PYTHONPATH"]
    return subprocess.run(
        ["bash", str(HOOK)], cwd=repo, env=env, capture_output=True, text=True, timeout=120
    )


def _stage(repo: Path, name: str, text: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", name)


def test_threshold_is_one_variable_defaulting_to_critical() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert 'FAIL_ON="CRITICAL"' in text
    assert '--severity HIGH --fail-on "$FAIL_ON"' in text
    assert "--exclude" not in text


def test_staged_critical_blocks(repo: Path) -> None:
    _stage(repo, "app/secret.py", PLANTED)
    result = _run_hook(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Found CRITICAL issues" in result.stdout


def test_staged_file_excluded_by_config_is_skipped(repo: Path) -> None:
    _stage(repo, "tests/fixtures/secret.py", PLANTED)
    result = _run_hook(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "excluded by .hefesto.yaml: tests/fixtures/secret.py" in result.stderr


def test_unstaged_files_are_not_analyzed(repo: Path) -> None:
    (repo / "unstaged.py").write_text(PLANTED, encoding="utf-8")
    _stage(repo, "ok.py", "def add(a: int, b: int) -> int:\n    return a + b\n")
    result = _run_hook(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Analyzing 1 staged file(s)" in result.stdout


def test_no_interpreter_blocks_instead_of_skipping(repo: Path) -> None:
    shutil.rmtree(repo / ".venv")
    _stage(repo, "ok.py", "x = 1\n")
    result = _run_hook(repo, PATH=_bare_path(), PYTHONPATH="")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Commit blocked" in result.stderr
    assert "SKIP_HEFESTO_HOOKS=1" in result.stderr
    assert "Skipping" not in result.stdout + result.stderr


def test_skip_env_still_bypasses_without_interpreter(repo: Path) -> None:
    shutil.rmtree(repo / ".venv")
    result = _run_hook(repo, PATH=_bare_path(), SKIP_HEFESTO_HOOKS="1")
    assert result.returncode == 0


@pytest.mark.parametrize("where", ["venv", "virtual_env", "hefesto_on_path"])
def test_interpreter_is_found_without_dot_venv(repo: Path, tmp_path_factory, where: str) -> None:
    shutil.rmtree(repo / ".venv")
    extra = {"PATH": _bare_path(), "PYTHONPATH": ""}
    if where == "venv":
        _make_venv(repo / "venv")
    elif where == "virtual_env":
        outside = tmp_path_factory.mktemp("active-venv")
        _make_venv(outside)
        extra["VIRTUAL_ENV"] = str(outside)
    else:
        bindir = tmp_path_factory.mktemp("bin")
        script = bindir / "hefesto"
        script.write_text(f"#!{sys.executable}\nimport hefesto.cli.main\n", encoding="utf-8")
        script.chmod(0o755)
        extra["PATH"] = str(bindir) + os.pathsep + extra["PATH"]
    _stage(repo, "app/secret.py", PLANTED)
    result = _run_hook(repo, **extra)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Found CRITICAL issues" in result.stdout
