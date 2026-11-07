"""Unit tests for scripts/release_gate.py (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_gate", ROOT / "scripts" / "release_gate.py")
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_timing_fields_are_ignored() -> None:
    a = {"timestamp": 1, "summary": {"duration_seconds": 2.0, "total_issues": 3}, "files": []}
    b = {"timestamp": 9, "summary": {"duration_seconds": 7.5, "total_issues": 3}, "files": []}
    assert gate.normalize(a) == gate.normalize(b)


def test_a_finding_change_is_a_difference() -> None:
    a = {"files": [{"file": "x", "duration_ms": 1, "issues": [{"line": 1}]}]}
    b = {"files": [{"file": "x", "duration_ms": 5, "issues": [{"line": 2}]}]}
    assert gate.normalize(a) != gate.normalize(b)


def test_file_order_does_not_matter() -> None:
    a = {"files": [{"file": "b"}, {"file": "a"}]}
    b = {"files": [{"file": "a"}, {"file": "b"}]}
    assert gate.normalize(a) == gate.normalize(b)


def test_corpora_are_pinned_by_full_sha() -> None:
    rows = gate.read_corpora(gate.CORPORA)
    assert rows
    for _name, url, sha in rows:
        assert url.startswith("https://github.com/")
        assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)
