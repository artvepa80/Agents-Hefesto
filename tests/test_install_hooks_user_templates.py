"""install-hooks in a user's project: packaged templates and exit codes."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto.cli.hook_templates import TEMPLATES

ROOT = Path(__file__).resolve().parent.parent


def _run(cwd, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["HEFESTO_TELEMETRY"] = "0"
    return subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "install-hooks", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def test_installs_packaged_hooks_without_scripts_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "template not found" not in result.stderr
    for name, content in TEMPLATES.items():
        dest = tmp_path / ".git" / "hooks" / name
        assert dest.read_text() == content
        assert os.stat(dest).st_mode & stat.S_IEXEC


def test_second_run_is_up_to_date_and_exits_0(tmp_path):
    (tmp_path / ".git").mkdir()
    assert _run(tmp_path).returncode == 0
    again = _run(tmp_path)
    assert again.returncode == 0
    assert "pre-commit: already up to date." in again.stdout


def test_exits_1_when_nothing_installed(tmp_path):
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    for name in TEMPLATES:
        (hooks / name).write_text("#!/bin/sh\necho mine\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "No hooks were installed" in result.stderr
    assert (hooks / "pre-commit").read_text() == "#!/bin/sh\necho mine\n"
    forced = _run(tmp_path, "--force")
    assert forced.returncode == 0
    assert (hooks / "pre-commit").read_text() == TEMPLATES["pre-commit"]


def test_exits_1_when_contributor_templates_all_missing_and_hooks_differ(tmp_path):
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    src = tmp_path / "scripts" / "git-hooks"
    src.mkdir(parents=True)
    (src / "pre-push").write_text("#!/bin/sh\necho repo\n")
    (hooks / "pre-push").write_text("#!/bin/sh\necho other\n")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "Skipping pre-commit" in result.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_templates_are_valid_bash(tmp_path, name):
    hook = tmp_path / name
    hook.write_text(TEMPLATES[name])
    assert subprocess.run(["bash", "-n", str(hook)]).returncode == 0
