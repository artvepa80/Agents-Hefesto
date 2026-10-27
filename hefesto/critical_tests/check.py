"""Run the critical-test comparison for one pull request range.

Ties ``git_diff`` and ``comparator`` together: compute the merge-base of
``base_ref`` and ``head_ref``, find which mapped test files the range touched
(following renames), read both sides and compare the mapped tests. Each
change is attributed to the config entry that lists the test, with that
entry's enforcement. Nothing here decides an exit code or prints anything.

Copyright 2026 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from hefesto.critical_tests.comparator import SourceParseError, compare_tests
from hefesto.critical_tests.git_diff import (
    PathLike,
    changed_files,
    merge_base,
    pair_test_files,
    read_file_at,
)
from hefesto.critical_tests.policy import CriticalTestsPolicy


@dataclass(frozen=True)
class CriticalTestFinding:
    entry_id: str
    requirement: str
    enforcement: str
    nodeid: str
    rule_id: str
    kind: str
    detail: str
    warn_only: bool
    base_path: str
    head_path: Optional[str]


@dataclass
class CheckResult:
    base_sha: str
    head_ref: str
    findings: List[CriticalTestFinding] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def check_critical_tests(
    repo: PathLike,
    policy: CriticalTestsPolicy,
    base_ref: str,
    head_ref: str = "HEAD",
) -> CheckResult:
    """Compare every mapped test the ``base_ref...head_ref`` range touched."""
    base = merge_base(repo, base_ref, head_ref)
    result = CheckResult(base_sha=base, head_ref=head_ref)
    by_file = policy.tests_by_file()
    entries = {entry.id: entry for entry in policy.entries}
    changes = changed_files(repo, base, head_ref)
    for base_path, head_path in pair_test_files(changes, by_file):
        base_source = read_file_at(repo, base, base_path)
        if base_source is None:
            continue
        head_source = read_file_at(repo, head_ref, head_path) if head_path else None
        refs: List[Tuple[str, str]] = by_file[base_path]
        qualnames = list(dict.fromkeys(q for _, q in refs))
        try:
            test_changes = compare_tests(base_source, head_source, qualnames)
        except SourceParseError as exc:
            result.errors.append(f"{base_path}: {exc}")
            continue
        owners: Dict[str, List[str]] = {}
        for entry_id, qualname in refs:
            owners.setdefault(qualname, []).append(entry_id)
        for change in test_changes:
            for entry_id in owners.get(change.test, []):
                entry = entries[entry_id]
                result.findings.append(
                    CriticalTestFinding(
                        entry_id=entry_id,
                        requirement=entry.requirement,
                        enforcement=entry.enforcement,
                        nodeid=f"{base_path}::{change.test}",
                        rule_id=change.rule_id,
                        kind=change.kind,
                        detail=change.detail,
                        warn_only=change.warn_only,
                        base_path=base_path,
                        head_path=head_path,
                    )
                )
    return result


__all__ = ["CheckResult", "CriticalTestFinding", "check_critical_tests"]
