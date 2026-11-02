"""Tests for the Action's install step (``scripts/action_install.sh``).

The ``multilang`` input is opt-in: by default the Action installs the base
package, and only ``true``/``1``/``yes`` installs the ``[multilang]`` extra.
The script runs with a fake ``python3`` on ``PATH`` that records the pip
arguments, so nothing is installed and nothing touches the network.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "action_install.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")

# Fake python3: "-c ..." is the version check (exit FAKE_PY_OK, default 0);
# "-m venv DIR" creates DIR/bin/python, which logs the pip arguments.
FAKE_PYTHON3 = """#!/usr/bin/env bash
if [ "$1" = "-c" ]; then exit "${FAKE_PY_OK:-0}"; fi
if [ "$1" = "--version" ]; then echo "Python 3.9.0"; exit 0; fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  cat > "$3/bin/python" <<'PY'
#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_LOG_DIR/pip_args"
PY
  chmod +x "$3/bin/python"
  exit 0
fi
exit 3
"""


def _run(tmp_path: Path, multilang: Optional[str], py_ok: int = 0):
    bin_dir = tmp_path / "bin"
    log_dir = tmp_path / "log"
    bin_dir.mkdir(exist_ok=True)
    log_dir.mkdir(exist_ok=True)
    fake = bin_dir / "python3"
    fake.write_text(FAKE_PYTHON3, encoding="utf-8")
    fake.chmod(0o755)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path),
        "RUNNER_TEMP": str(tmp_path / "runner_temp"),
        "GITHUB_ACTION_PATH": "/action path",
        "FAKE_LOG_DIR": str(log_dir),
        "FAKE_PY_OK": str(py_ok),
    }
    if multilang is not None:
        env["INPUT_MULTILANG"] = multilang
    proc = subprocess.run(
        ["bash", str(INSTALL)], env=env, capture_output=True, text=True, timeout=30
    )
    pip_log = log_dir / "pip_args"
    pip_args = pip_log.read_text(encoding="utf-8").splitlines() if pip_log.exists() else None
    return proc, pip_args


@pytest.mark.parametrize("value", [None, "", "false", "0", "no", "off", "multilang"])
def test_base_package_by_default(tmp_path: Path, value: Optional[str]) -> None:
    proc, pip_args = _run(tmp_path, value)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert pip_args is not None
    assert pip_args[-1] == "/action path"
    assert "multilang" not in " ".join(pip_args)


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", " true "])
def test_multilang_extra_when_enabled(tmp_path: Path, value: str) -> None:
    proc, pip_args = _run(tmp_path, value)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert pip_args is not None
    assert pip_args[:3] == ["-m", "pip", "install"]
    assert pip_args[-1] == "/action path[multilang]"
    assert "[multilang]" in proc.stdout


def test_old_python_fails_before_installing(tmp_path: Path) -> None:
    proc, pip_args = _run(tmp_path, "true", py_ok=1)
    assert proc.returncode == 1
    assert "::error::HefestoAI needs python3 >= 3.11" in proc.stdout
    assert pip_args is None


def test_action_yml_wires_the_input() -> None:
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    assert action["inputs"]["multilang"]["default"] == "false"
    install = next(s for s in action["runs"]["steps"] if s.get("name") == "Install HefestoAI")
    assert install["env"]["INPUT_MULTILANG"] == "${{ inputs.multilang }}"
    assert "scripts/action_install.sh" in install["run"]
