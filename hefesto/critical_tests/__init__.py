"""Critical-test regression guard (opt-in ``critical_tests`` in .hefesto.yaml).

``policy`` parses and validates the config section. ``comparator`` compares a
test file's base and head sources and reports deleted, skipped, trivialized or
weakened tests. Both are pure: no git, no file system, no network.
``git_diff`` computes the merge-base and the changed files (with renames) and
reads file contents at a commit.

Copyright 2026 Narapa LLC, Miami, Florida
"""

from hefesto.critical_tests.comparator import (
    ASSERTS_REDUCED,
    DELETED,
    SKIPPED,
    TRIVIALIZED,
    SourceParseError,
    TestChange,
    compare_tests,
    count_assertions,
)
from hefesto.critical_tests.git_diff import (
    FileChange,
    GitError,
    changed_files,
    merge_base,
    pair_test_files,
    read_file_at,
)
from hefesto.critical_tests.policy import (
    ENFORCEMENTS,
    CriticalTestEntry,
    CriticalTestsPolicy,
    TestRef,
    parse_critical_tests,
    parse_nodeid,
)

__all__ = [
    "ASSERTS_REDUCED",
    "DELETED",
    "ENFORCEMENTS",
    "SKIPPED",
    "TRIVIALIZED",
    "CriticalTestEntry",
    "CriticalTestsPolicy",
    "FileChange",
    "GitError",
    "SourceParseError",
    "TestChange",
    "TestRef",
    "changed_files",
    "compare_tests",
    "count_assertions",
    "merge_base",
    "pair_test_files",
    "parse_critical_tests",
    "parse_nodeid",
    "read_file_at",
]
