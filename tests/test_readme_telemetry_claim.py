"""The README's telemetry sentence matches the code (README = PyPI page).

The CLI is on by default (opt-out with HEFESTO_TELEMETRY=0, among other switches)
and the GitHub Action sends nothing unless its ``telemetry`` input is 1/true.
"""

from pathlib import Path

import yaml

from hefesto.telemetry.client import telemetry_enabled

ROOT = Path(__file__).resolve().parent.parent
CLAIM = (
    "The CLI sends anonymous usage events by default (a random id only; no code, file paths, "
    "findings, repository names, or IP). Turn it off with `hefesto telemetry disable`, "
    "HEFESTO_TELEMETRY=0, or DO_NOT_TRACK=1. The GitHub Action sends nothing unless you set "
    "telemetry: 1."
)


def test_readme_states_the_telemetry_defaults():
    assert CLAIM in (ROOT / "README.md").read_text(encoding="utf-8")


def test_cli_telemetry_default_and_opt_out(monkeypatch, tmp_path):
    monkeypatch.setenv("HEFESTO_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    assert telemetry_enabled() is True
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    assert telemetry_enabled() is False


def test_action_telemetry_is_off_by_default():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    assert action["inputs"]["telemetry"]["default"] == "0"
