"""Characterization tests for ``scripts/validate_aggregates_jsonl.py``.

They pin the error list that ``validate_row()`` returns for valid rows, for
every error type, and with ``strict`` on and off, so splitting the function
cannot change its output. Missing-field errors come from iterating sets, whose
order depends on the hash seed, so those cases compare sorted lists.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_aggregates_jsonl.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_aggregates_jsonl", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load()

VALID_ROW: Dict[str, Any] = {
    "repo": "org/repo",
    "commit_sha": "abc1234",
    "window": "1h",
    "ts": "2026-10-29T12:00:00Z",
    "restart_count": 0,
    "oom_kill_count": 0,
    "error_rate": 0.0,
}

FULL_ROW: Dict[str, Any] = {
    **VALID_ROW,
    "latency_p95_delta": 1.5,
    "latency_p99_delta": 2,
    "memory_rss_slope": -0.25,
}


def _row(**changes: Any) -> Dict[str, Any]:
    row = dict(FULL_ROW)
    row.update(changes)
    return row


def _validate(row: Dict[str, Any], strict: bool = False) -> List[str]:
    result: List[str] = VALIDATOR.validate_row(row, 7, strict=strict)
    return result


@pytest.mark.parametrize("strict", [False, True])
def test_full_row_has_no_errors(strict: bool) -> None:
    assert _validate(FULL_ROW, strict=strict) == []


def test_valid_row_without_optional_metrics_passes_non_strict() -> None:
    assert _validate(VALID_ROW) == []


def test_valid_row_without_optional_metrics_strict_lists_each_one() -> None:
    assert sorted(_validate(VALID_ROW, strict=True)) == [
        "line 7: (strict) missing optional metric 'latency_p95_delta'",
        "line 7: (strict) missing optional metric 'latency_p99_delta'",
        "line 7: (strict) missing optional metric 'memory_rss_slope'",
    ]


@pytest.mark.parametrize(
    "ts", ["2026-10-29T12:00:00+00:00", "2026-10-29T12:00:00.123Z", "2026-10-29T12:00:00-05:00"]
)
def test_accepted_timestamps(ts: str) -> None:
    assert _validate(_row(ts=ts)) == []


def test_empty_row_reports_every_missing_field() -> None:
    assert sorted(_validate({})) == [
        "line 7: missing required field 'commit_sha'",
        "line 7: missing required field 'repo'",
        "line 7: missing required field 'ts'",
        "line 7: missing required field 'window'",
        "line 7: missing required metric 'error_rate'",
        "line 7: missing required metric 'oom_kill_count'",
        "line 7: missing required metric 'restart_count'",
    ]


def test_empty_row_strict_adds_optional_metrics() -> None:
    errors = _validate({}, strict=True)
    assert len(errors) == 10
    assert all("(strict)" in e for e in errors[-3:])


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({"repo": "noslash"}, "line 7: 'repo' should be 'org/repo' format, got 'noslash'"),
        ({"commit_sha": "xyz"}, "line 7: 'commit_sha' should be 7+ hex chars, got 'xyz'"),
        ({"window": "7d"}, "line 7: 'window' must be '1h' or '24h', got '7d'"),
        ({"ts": "yesterday"}, "line 7: 'ts' must be ISO-8601 UTC, got 'yesterday'"),
        ({"restart_count": -1}, "line 7: 'restart_count' must be non-negative int, got -1"),
        ({"restart_count": 1.5}, "line 7: 'restart_count' must be non-negative int, got 1.5"),
        ({"oom_kill_count": -2}, "line 7: 'oom_kill_count' must be non-negative int, got -2"),
        ({"oom_kill_count": "3"}, "line 7: 'oom_kill_count' must be non-negative int, got 3"),
        ({"error_rate": "0.1"}, "line 7: 'error_rate' must be float, got str"),
        (
            {"error_rate": 1.5},
            "line 7: 'error_rate' must be 0.0-1.0 (ratio, not percentage), got 1.5",
        ),
        (
            {"error_rate": -0.1},
            "line 7: 'error_rate' must be 0.0-1.0 (ratio, not percentage), got -0.1",
        ),
        ({"latency_p95_delta": "x"}, "line 7: 'latency_p95_delta' must be numeric (ms), got str"),
        (
            {"latency_p99_delta": [1]},
            "line 7: 'latency_p99_delta' must be numeric (ms), got list",
        ),
        (
            {"memory_rss_slope": "up"},
            "line 7: 'memory_rss_slope' must be numeric (MB/min), got str",
        ),
    ],
)
@pytest.mark.parametrize("strict", [False, True])
def test_each_error_type(changes: Dict[str, Any], expected: str, strict: bool) -> None:
    assert _validate(_row(**changes), strict=strict) == [expected]


@pytest.mark.parametrize("field", ["repo", "commit_sha", "window", "ts"])
def test_empty_identity_value_is_not_format_checked(field: str) -> None:
    assert _validate(_row(**{field: ""})) == []


@pytest.mark.parametrize("field", ["restart_count", "oom_kill_count", "error_rate"])
def test_none_metric_is_present_but_not_type_checked(field: str) -> None:
    assert _validate(_row(**{field: None})) == []


def test_bool_counts_are_accepted_as_ints() -> None:
    assert _validate(_row(restart_count=True, oom_kill_count=False, error_rate=True)) == []


def test_all_format_errors_keep_their_order() -> None:
    row = _row(
        repo="bad",
        commit_sha="nothex!",
        window="2h",
        ts="nope",
        restart_count=-1,
        oom_kill_count=-1,
        error_rate=2,
        latency_p95_delta="a",
        latency_p99_delta="b",
        memory_rss_slope="c",
    )
    assert _validate(row) == [
        "line 7: 'repo' should be 'org/repo' format, got 'bad'",
        "line 7: 'commit_sha' should be 7+ hex chars, got 'nothex!'",
        "line 7: 'window' must be '1h' or '24h', got '2h'",
        "line 7: 'ts' must be ISO-8601 UTC, got 'nope'",
        "line 7: 'restart_count' must be non-negative int, got -1",
        "line 7: 'oom_kill_count' must be non-negative int, got -1",
        "line 7: 'error_rate' must be 0.0-1.0 (ratio, not percentage), got 2",
        "line 7: 'latency_p95_delta' must be numeric (ms), got str",
        "line 7: 'latency_p99_delta' must be numeric (ms), got str",
        "line 7: 'memory_rss_slope' must be numeric (MB/min), got str",
    ]


def test_missing_fields_come_before_format_errors_and_strict_last() -> None:
    row = {"repo": "bad", "restart_count": -1}
    errors = _validate(row, strict=True)
    missing_identity = sorted(
        [
            "line 7: missing required field 'commit_sha'",
            "line 7: missing required field 'ts'",
            "line 7: missing required field 'window'",
        ]
    )
    assert sorted(errors[0:3]) == missing_identity
    assert errors[3] == "line 7: 'repo' should be 'org/repo' format, got 'bad'"
    assert sorted(errors[4:6]) == [
        "line 7: missing required metric 'error_rate'",
        "line 7: missing required metric 'oom_kill_count'",
    ]
    assert errors[6] == "line 7: 'restart_count' must be non-negative int, got -1"
    assert sorted(errors[7:]) == [
        "line 7: (strict) missing optional metric 'latency_p95_delta'",
        "line 7: (strict) missing optional metric 'latency_p99_delta'",
        "line 7: (strict) missing optional metric 'memory_rss_slope'",
    ]


def test_sample_file_validates() -> None:
    sample = SCRIPT.parents[1] / "docs" / "telemetry" / "examples" / "aggregates.sample.jsonl"
    if not sample.exists():
        pytest.skip("sample file not present")
    total, errors = VALIDATOR.validate_file(str(sample), strict=False)
    assert total > 0
    assert errors == []
