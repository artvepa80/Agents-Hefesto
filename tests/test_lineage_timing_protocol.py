"""Tests of the 7.3 additions to scripts/lineage_timing_protocol.py (no CLI runs)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lineage_timing_protocol.py"


@pytest.fixture(scope="module")
def protocol():
    spec = importlib.util.spec_from_file_location("lineage_timing_protocol", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeMachine:
    """A load source and a clock that advances only when the gate sleeps."""

    def __init__(self, loads):
        self.loads = list(loads)
        self.now = 0.0
        self.sleeps = []

    def load(self):
        return self.loads.pop(0) if len(self.loads) > 1 else self.loads[0]

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_gate_passes_at_once_when_quiet(protocol):
    fake = FakeMachine([1.0])
    assert protocol.wait_quiet(fake.load, 8, fake.sleep, fake.clock) == (True, 0.0, 1.0)
    assert fake.sleeps == []


def test_gate_threshold_is_a_quarter_of_the_cores_inclusive(protocol):
    fake = FakeMachine([2.01, 2.0])
    quiet, waited, last = protocol.wait_quiet(fake.load, 8, fake.sleep, fake.clock)
    assert (quiet, last) == (True, 2.0)
    assert waited == protocol.QUIET_POLL_S


def test_gate_waits_until_the_load_drops(protocol):
    fake = FakeMachine([9.0, 5.0, 3.0, 0.5])
    quiet, waited, _ = protocol.wait_quiet(fake.load, 8, fake.sleep, fake.clock)
    assert quiet and waited == 3 * protocol.QUIET_POLL_S


def test_gate_gives_up_after_30_minutes(protocol):
    fake = FakeMachine([40.0])
    quiet, waited, last = protocol.wait_quiet(fake.load, 8, fake.sleep, fake.clock)
    assert not quiet and last == 40.0
    assert waited == protocol.QUIET_WAIT_S == 1800
    assert sum(fake.sleeps) == 1800


def test_a_failed_gate_stops_the_rounds_before_any_cli_run(protocol, tmp_path, monkeypatch):
    def no_cli(*args, **kwargs):
        raise AssertionError("no CLI run after a failed gate")

    monkeypatch.setattr(protocol, "timed", no_cli)
    lines = []
    rows = protocol.run_rounds(
        lines.append,
        "python",
        tmp_path,
        {20: tmp_path / "syn20"},
        2,
        tmp_path / "rounds.csv",
        gate=lambda: (False, 1800.0, 40.0),
    )
    assert rows is None
    assert lines[-1] == "INVALID RUN: machine not quiet before round 0 in 30 min"


def test_a_gate_is_checked_before_every_round(protocol, tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "timed", lambda *a: (1, 0, 1))
    calls = []

    def gate():
        calls.append(1)
        return True, 0.0, 0.1

    rows = protocol.run_rounds(
        lambda text: None, "python", tmp_path, {20: tmp_path}, 3, tmp_path / "r.csv", gate=gate
    )
    assert len(calls) == 4  # warm-up and 3 rounds
    assert rows is not None and len(rows) == 8


def test_header_prints_the_cpu_model(protocol, tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "machine", lambda: {"cpu": "Fake CPU 9000", "cores": 8})
    monkeypatch.setattr(protocol, "git_dirty", lambda tree: False)
    monkeypatch.setattr(protocol, "git_sha", lambda tree: "0" * 40)
    monkeypatch.setattr(protocol, "interpreter", lambda py: ("3.13.5", "x"))
    lines = []
    opts = protocol.parse_args(["--repo", ".", "--main", ".", "--workdir", "w", "--out", "o"])
    assert protocol.header(lines.append, opts, tmp_path, tmp_path, "sha", "3.13.5")
    assert "cpu model Fake CPU 9000" in lines


def test_another_cpu_makes_the_run_invalid(protocol, tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "machine", lambda: {"cpu": "Other CPU", "cores": 8})
    monkeypatch.setattr(protocol, "git_dirty", lambda tree: False)
    monkeypatch.setattr(protocol, "git_sha", lambda tree: "0" * 40)
    monkeypatch.setattr(protocol, "interpreter", lambda py: ("3.13.5", "x"))
    argv = ["--repo", ".", "--main", ".", "--workdir", "w", "--out", "o"]
    opts = protocol.parse_args([*argv, "--expect-cpu", "Fake CPU 9000"])
    lines = []
    assert not protocol.preflight(lines.append, opts, tmp_path, tmp_path, "sha")
    assert lines[-1] == "INVALID RUN: cpu model 'Other CPU' is not --expect-cpu 'Fake CPU 9000'"
    opts = protocol.parse_args([*argv, "--expect-cpu", "Other CPU"])
    assert protocol.preflight(lambda text: None, opts, tmp_path, tmp_path, "sha")
