"""The README's telemetry sentence matches the code (README = PyPI page).

The CLI ping is on by default (opt-out with HEFESTO_TELEMETRY=0) and the GitHub
Action sends nothing unless its ``telemetry`` input is 1/true. If either default
changes, this test fails until the README sentence is updated with it.
"""

from pathlib import Path

import yaml

from hefesto.telemetry.client import remote_ping_enabled

ROOT = Path(__file__).resolve().parent.parent
CLAIM = (
    "The CLI sends one anonymous usage ping per run by default (no code, file paths or PII); "
    "turn it off with HEFESTO_TELEMETRY=0. The GitHub Action sends nothing unless you set "
    "telemetry: 1."
)


def test_readme_states_the_telemetry_defaults():
    assert CLAIM in (ROOT / "README.md").read_text(encoding="utf-8")


def test_cli_ping_is_on_by_default(monkeypatch):
    monkeypatch.delenv("HEFESTO_TELEMETRY", raising=False)
    assert remote_ping_enabled() is True


def test_cli_ping_is_off_when_opted_out(monkeypatch):
    monkeypatch.setenv("HEFESTO_TELEMETRY", "0")
    assert remote_ping_enabled() is False


def test_action_telemetry_is_off_by_default():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    assert action["inputs"]["telemetry"]["default"] == "0"
