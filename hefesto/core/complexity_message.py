"""Text of the cyclomatic complexity finding.

The message names the threshold that was crossed (#159). Identity keys (the
PR-review dedup key and the SARIF fingerprint fallback) drop that clause with
:func:`strip_threshold_clause`, so they match the keys of the earlier message
``Cyclomatic complexity too high (N)``.
"""

from __future__ import annotations

import re

_THRESHOLD_CLAUSE = re.compile(r", threshold \d+ for (?:MEDIUM|HIGH|CRITICAL)\)")


def complexity_message(complexity: int, threshold: int, severity: str) -> str:
    return f"Cyclomatic complexity too high ({complexity}, threshold {threshold} for {severity})"


def strip_threshold_clause(message: str) -> str:
    """Remove the ``, threshold N for SEVERITY`` clause added by complexity_message."""
    return _THRESHOLD_CLAUSE.sub(")", message)
