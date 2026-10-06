"""SEC-06 / BUG-13 regression tests for ``scripts/action_entrypoint.sh``.

The GitHub Action used to ``curl`` an anonymous ping to
``hefestoai.narapallc.com`` on every run, even with ``telemetry: 0`` (the
default, documented as opt-in). It also passed ``min_severity: INFO`` straight
to the CLI, which rejects it (exit 2).

These tests run the real entrypoint with fake ``hefesto`` and ``curl``
executables on ``PATH``, so nothing touches the network.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[2] / "scripts" / "action_entrypoint.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")

FAKE_HEFESTO = """#!/usr/bin/env bash
if [ "$1" = "--version" ]; then
  echo "hefesto, version 9.9.9"
  exit 0
fi
echo "$@" > "$FAKE_LOG_DIR/hefesto_args"
echo "${HEFESTO_TELEMETRY-<unset>}" > "$FAKE_LOG_DIR/hefesto_telemetry_env"
echo "Files analyzed: 3"
echo "Issues found: 2"
exit "${FAKE_HEFESTO_EXIT:-0}"
"""

FAKE_CURL = """#!/usr/bin/env bash
printf '%s\\n' "$@" >> "$FAKE_LOG_DIR/curl_calls"
exit 0
"""


def _run(tmp_path: Path, inputs: Dict[str, Optional[str]], hefesto_exit: int = 0):
    bin_dir = tmp_path / "bin"
    log_dir = tmp_path / "log"
    bin_dir.mkdir(exist_ok=True)
    log_dir.mkdir(exist_ok=True)
    for name, body in (("hefesto", FAKE_HEFESTO), ("curl", FAKE_CURL)):
        exe = bin_dir / name
        exe.write_text(body, encoding="utf-8")
        exe.chmod(0o755)

    gh_output = tmp_path / "gh_output"
    gh_output.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(tmp_path),
        "GITHUB_OUTPUT": str(gh_output),
        "GITHUB_WORKSPACE": str(tmp_path),
        "FAKE_LOG_DIR": str(log_dir),
        "FAKE_HEFESTO_EXIT": str(hefesto_exit),
    }
    for key, value in inputs.items():
        if value is not None:
            env[f"INPUT_{key.upper()}"] = value

    proc = subprocess.run(
        ["bash", str(ENTRYPOINT)], env=env, capture_output=True, text=True, timeout=30
    )
    curl_log = log_dir / "curl_calls"
    return {
        "proc": proc,
        "curl": curl_log.read_text(encoding="utf-8") if curl_log.exists() else None,
        "hefesto_args": (log_dir / "hefesto_args").read_text(encoding="utf-8").split(),
        "telemetry_env": (log_dir / "hefesto_telemetry_env").read_text(encoding="utf-8").strip(),
        "gh_output": gh_output.read_text(encoding="utf-8"),
    }


@pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off", "yes", "2", "enabled"])
def test_no_ping_unless_telemetry_is_1_or_true(tmp_path: Path, value: Optional[str]) -> None:
    r = _run(tmp_path, {"telemetry": value})
    assert r["proc"].returncode == 0, r["proc"].stderr
    assert r["curl"] is None, f"telemetry={value!r} must not ping, got: {r['curl']}"
    # The CLI's own ping is disabled too.
    assert r["telemetry_env"] == "0"
    assert "exit_code=0" in r["gh_output"]


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", " 1 "])
def test_ping_sent_when_telemetry_enabled(tmp_path: Path, value: str) -> None:
    r = _run(tmp_path, {"telemetry": value}, hefesto_exit=1)
    assert r["proc"].returncode == 1
    assert r["curl"] is not None
    assert "https://hefestoai.narapallc.com/api/telemetry" in r["curl"]
    assert '{"event":"action","v":"9.9.9","files":3,"issues":2,"exit_code":1}' in r["curl"], r[
        "curl"
    ]
    assert r["telemetry_env"] == "1"
    assert "exit_code=1" in r["gh_output"]


def test_exit_code_propagates_without_telemetry(tmp_path: Path) -> None:
    r = _run(tmp_path, {"telemetry": "0"}, hefesto_exit=1)
    assert r["proc"].returncode == 1
    assert "exit_code=1" in r["gh_output"]
    assert r["curl"] is None


@pytest.mark.parametrize("value", ["INFO", "info"])
def test_min_severity_info_maps_to_low(tmp_path: Path, value: str) -> None:
    r = _run(tmp_path, {"min_severity": value})
    args = r["hefesto_args"]
    assert args[args.index("--severity") + 1] == "LOW"
    assert "min_severity INFO is not supported" in r["proc"].stdout


def test_min_severity_passthrough(tmp_path: Path) -> None:
    r = _run(tmp_path, {"min_severity": "high"})
    args = r["hefesto_args"]
    assert args[args.index("--severity") + 1] == "HIGH"
