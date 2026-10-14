"""install-hooks in a user's project: packaged hooks, interpreter path, hooksPath, newlines."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")


def _env(**extra):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["HEFESTO_TELEMETRY"] = "0"
    env.update(extra)
    return env


def _install(cwd, *args):
    return subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "install-hooks", *args],
        cwd=cwd,
        env=_env(),
        capture_output=True,
        text=True,
    )


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    _git(tmp_path, "init", "-q")
    return tmp_path


def test_user_hooks_are_installed_with_message(repo):
    result = _install(repo)
    assert result.returncode == 0, result.stderr
    assert "Using the hooks shipped with hefesto-ai." in result.stdout
    for name in ("pre-commit", "pre-push"):
        dest = repo / ".git" / "hooks" / name
        assert os.stat(dest).st_mode & stat.S_IEXEC
    again = _install(repo)
    assert again.returncode == 0
    assert "pre-commit: already up to date." in again.stdout


def test_exits_1_when_nothing_installed(repo):
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    for name in ("pre-commit", "pre-push"):
        (hooks / name).write_text("#!/bin/sh\necho mine\n")
    result = _install(repo)
    assert result.returncode == 1
    assert "No hooks were installed" in result.stderr
    assert _install(repo, "--force").returncode == 0


# (a) the interpreter that ran install-hooks is written into the hook
@needs_bash
def test_a_hook_uses_installing_interpreter_without_path(repo):
    assert _install(repo).returncode == 0
    hook = (repo / ".git" / "hooks" / "pre-commit").read_text()
    assert sys.executable in hook
    (repo / "app.py").write_text("def run(x):\n    return eval(x)\n")
    _git(repo, "add", "app.py")
    env = _env(PATH="/usr/bin:/bin")  # no `hefesto` on PATH
    res = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "t"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0, res.stdout + res.stderr
    assert "EVAL_USAGE" in res.stdout + res.stderr


@needs_bash
def test_a_hook_fails_when_interpreter_and_path_are_gone(repo):
    assert _install(repo).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(hook.read_text().replace(sys.executable, "/nonexistent/python"))
    (repo / "a.py").write_text("x = 1\n")
    _git(repo, "add", "a.py")
    res = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "t"],
        cwd=repo,
        env=_env(PATH="/usr/bin:/bin"),
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "SKIP_HEFESTO_HOOKS=1" in res.stderr


# (b) core.hooksPath: nothing written, exit 1
def test_b_core_hooks_path_writes_nothing(repo):
    _git(repo, "config", "core.hooksPath", ".husky")
    result = _install(repo)
    assert result.returncode == 1
    assert "core.hooksPath" in result.stderr
    assert "hefesto-analyze" in result.stderr
    assert not (repo / ".husky").exists()
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


@needs_git
def test_b_worktree_uses_git_path_hooks(repo):
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-qm", "init")
    wt = repo.parent / (repo.name + "-wt")
    assert _git(repo, "worktree", "add", "-q", str(wt)).returncode == 0
    result = _install(wt)
    assert result.returncode == 0, result.stderr
    assert (repo / ".git" / "hooks" / "pre-commit").exists()


# (c) a project with its own scripts/git-hooks/ is not mistaken for Agents-Hefesto
def test_c_other_project_with_scripts_git_hooks_gets_user_hooks(repo):
    src = repo / "scripts" / "git-hooks"
    src.mkdir(parents=True)
    (src / "pre-commit").write_text("#!/bin/sh\necho theirs\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "other-app"\n')
    result = _install(repo)
    assert result.returncode == 0, result.stderr
    assert "Using the hooks shipped with hefesto-ai." in result.stdout
    assert "theirs" not in (repo / ".git" / "hooks" / "pre-commit").read_text()


def test_c_agents_hefesto_clone_gets_contributor_hooks(repo):
    src = repo / "scripts" / "git-hooks"
    src.mkdir(parents=True)
    for name in ("pre-commit", "pre-push"):
        (src / name).write_text(f"#!/bin/sh\necho {name}\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "hefesto-ai"\n')
    result = _install(repo)
    assert result.returncode == 0, result.stderr
    assert "Agents-Hefesto contributor hooks" in result.stdout
    assert (repo / ".git" / "hooks" / "pre-commit").read_text() == "#!/bin/sh\necho pre-commit\n"


# (d) LF line endings on every platform
def test_d_hooks_have_no_carriage_returns(repo):
    assert _install(repo).returncode == 0
    for name in ("pre-commit", "pre-push"):
        assert b"\r" not in (repo / ".git" / "hooks" / name).read_bytes()


@needs_bash
@pytest.mark.parametrize("name", ["pre-commit", "pre-push"])
def test_templates_are_valid_bash(tmp_path, name):
    from hefesto.cli.hook_templates import render

    hook = tmp_path / name
    hook.write_text(render(name, sys.executable))
    assert subprocess.run(["bash", "-n", str(hook)]).returncode == 0
