"""Critical-test regression guard (opt-in ``critical_tests`` in .hefesto.yaml).

``policy`` parses and validates the config section. ``comparator`` compares a
test file's base and head sources and reports deleted, skipped, trivialized or
weakened tests. Both are pure: no git, no file system, no network.

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
    "SourceParseError",
    "TestChange",
    "TestRef",
    "compare_tests",
    "count_assertions",
    "parse_critical_tests",
    "parse_nodeid",
]
