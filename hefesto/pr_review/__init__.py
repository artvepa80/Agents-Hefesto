"""Phase 2 — OSS PR review.

Provides deterministic diff parsing, scoped analysis, and a JSON review
output that external tooling (``gh`` CLI, GitHub Actions workflows) can
consume to post review comments. This package contains *zero* network
code — posting and dedup enforcement live in the workflow layer so the
Python core stays pure-functional and testable without VCR/mocking of
the GitHub API. See ``docs`` or the ``examples/github-actions/``
workflow templates for the posting pipeline.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from hefesto.pr_review.dedup import compute_dedup_key
from hefesto.pr_review.diff import FileDiff, Hunk, parse_unified_diff

__all__ = [
    "FileDiff",
    "Hunk",
    "parse_unified_diff",
    "compute_dedup_key",
]
