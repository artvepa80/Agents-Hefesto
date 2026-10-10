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
prev=""
for arg in "$@"; do
  if [ "$prev" = "--sarif-file" ] && [ -z "${FAKE_NO_SARIF:-}" ]; then
    mkdir -p "$(dirname "$arg")"
    echo '{"version": "2.1.0", "runs": []}' > "$arg"
  fi
  prev="$arg"
done
echo "Files analyzed: 3"
echo "Issues found: 2"
exit "${FAKE_HEFESTO_EXIT:-0}"
"""

FAKE_CURL = """#!/usr/bin/env bash
printf '%s\\n' "$@" >> "$FAKE_LOG_DIR/curl_calls"
exit 0
"""


def _run(
    tmp_path: Path,
    inputs: Dict[str, Optional[str]],
    hefesto_exit: int = 0,
    write_sarif: bool = True,
):
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
    if not write_sarif:
        env["FAKE_NO_SARIF"] = "1"
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


# ------------------------------------------------------------ SARIF (Phase 5)


def _outputs(r) -> Dict[str, str]:
    return dict(line.split("=", 1) for line in r["gh_output"].splitlines() if "=" in line)


def test_sarif_off_by_default(tmp_path: Path) -> None:
    r = _run(tmp_path, {})
    assert "--sarif-file" not in r["hefesto_args"]
    assert "sarif_file" not in _outputs(r)
    assert "SARIF file: off" in r["proc"].stdout


@pytest.mark.parametrize("value", ["true", "TRUE", "1", " yes "])
def test_sarif_written_and_flagged_for_upload(tmp_path: Path, value: str) -> None:
    r = _run(tmp_path, {"sarif": value, "format": "text"})
    args = r["hefesto_args"]
    assert args[args.index("--sarif-file") + 1] == "hefesto.sarif"
    assert args[args.index("--output") + 1] == "text"
    outputs = _outputs(r)
    assert outputs["sarif_file"] == "hefesto.sarif"
    assert outputs["upload_sarif"] == "true"
    assert (tmp_path / "hefesto.sarif").exists()


def test_sarif_custom_path_without_upload(tmp_path: Path) -> None:
    r = _run(
        tmp_path,
        {"sarif": "true", "sarif_file": "out/h.sarif", "upload_sarif": "false"},
    )
    args = r["hefesto_args"]
    assert args[args.index("--sarif-file") + 1] == "out/h.sarif"
    outputs = _outputs(r)
    assert outputs["sarif_file"] == "out/h.sarif"
    assert outputs["upload_sarif"] == "false"


def test_sarif_still_uploaded_when_the_gate_fails(tmp_path: Path) -> None:
    r = _run(tmp_path, {"sarif": "true"}, hefesto_exit=1)
    assert r["proc"].returncode == 1
    outputs = _outputs(r)
    assert outputs["exit_code"] == "1"
    assert outputs["sarif_file"] == "hefesto.sarif"


def test_missing_sarif_file_is_a_warning_not_an_output(tmp_path: Path) -> None:
    r = _run(tmp_path, {"sarif": "true"}, hefesto_exit=2, write_sarif=False)
    assert r["proc"].returncode == 2
    assert "sarif_file" not in _outputs(r)
    assert "::warning::sarif is enabled but hefesto.sarif was not written" in r["proc"].stdout


def test_stale_sarif_file_is_removed_before_the_run(tmp_path: Path) -> None:
    (tmp_path / "hefesto.sarif").write_text("stale", encoding="utf-8")
    r = _run(tmp_path, {"sarif": "true"}, hefesto_exit=2, write_sarif=False)
    assert not (tmp_path / "hefesto.sarif").exists()
    assert "sarif_file" not in _outputs(r)


def test_action_yml_passes_every_input_and_uploads_sarif() -> None:
    yaml = pytest.importorskip("yaml")
    action = yaml.safe_load((ENTRYPOINT.parents[1] / "action.yml").read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite"
    steps = action["runs"]["steps"]
    run_step = next(step for step in steps if step.get("id") == "analyze")
    for name in action["inputs"]:
        assert run_step["env"][f"INPUT_{name.upper()}"] == "${{ inputs.%s }}" % name
    upload = next(step for step in steps if "upload-sarif" in step.get("uses", ""))
    assert upload["uses"] == "github/codeql-action/upload-sarif@v4"
    assert "always()" in upload["if"]
    assert "steps.analyze.outputs.upload_sarif == 'true'" in upload["if"]
    assert upload["with"]["category"] == "${{ inputs.sarif_category }}"
    assert set(action["outputs"]) == {"exit_code", "sarif_file"}
