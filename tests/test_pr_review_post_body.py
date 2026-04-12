"""Pin the ``_format_comment_body`` output shape — G7 regression.

The deduped workflow template extracts dedup keys from existing PR
comments using ``jq capture("dedup_key=(?<k>sha256:[a-f0-9]+)")``. If
``_format_comment_body`` ever stops emitting the HTML marker in that
exact shape, the deduped pipeline will silently start posting
duplicate comments on every run.

This test is intentionally strict: it pins the marker format, not
just its presence. Any reformatting that would break the workflow's
regex will fail here first.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import re

from hefesto.pr_review.post import _format_comment_body


def test_body_starts_with_dedup_marker() -> None:
    body = _format_comment_body(
        {
            "dedup_key": "sha256:abc123def456",
            "severity": "HIGH",
            "type": "SQL_INJECTION_RISK",
            "message": "Potential SQL injection via string concatenation",
            "suggestion": "Use parameterized queries with placeholders",
        }
    )
    first_line = body.split("\n", 1)[0]
    assert first_line == "<!-- hefesto-pr-review: dedup_key=sha256:abc123def456 -->"


def test_body_marker_matches_workflow_jq_regex() -> None:
    """The deduped workflow uses
    ``jq capture("dedup_key=(?<k>sha256:[a-f0-9]+)")`` — verify the
    Python-side marker matches that exact shape."""
    hex64 = "0123456789abcdef" * 4  # 64 hex chars, real SHA-256 length
    body = _format_comment_body(
        {
            "dedup_key": f"sha256:{hex64}",
            "severity": "MEDIUM",
            "type": "HIGH_COMPLEXITY",
            "message": "Cyclomatic complexity too high",
        }
    )
    # Python-equivalent of the jq regex. Must match exactly once.
    pattern = re.compile(r"dedup_key=(sha256:[a-f0-9]+)")
    matches = pattern.findall(body)
    assert len(matches) == 1
    assert matches[0] == f"sha256:{hex64}"


def test_body_contains_severity_and_type_headline() -> None:
    body = _format_comment_body(
        {
            "dedup_key": "sha256:xyz",
            "severity": "CRITICAL",
            "type": "HARDCODED_SECRET",
            "message": "Hardcoded API key detected",
        }
    )
    assert "**[CRITICAL] HARDCODED_SECRET**" in body
    assert "Hardcoded API key detected" in body


def test_body_renders_suggestion_as_blockquote() -> None:
    body = _format_comment_body(
        {
            "dedup_key": "sha256:xyz",
            "severity": "HIGH",
            "type": "BARE_EXCEPT",
            "message": "Bare except clause catches all exceptions",
            "suggestion": "Catch specific exceptions",
        }
    )
    assert "> Catch specific exceptions" in body


def test_body_omits_suggestion_block_when_absent() -> None:
    body = _format_comment_body(
        {
            "dedup_key": "sha256:xyz",
            "severity": "LOW",
            "type": "INCOMPLETE_TODO",
            "message": "TODO comment found",
            "suggestion": None,
        }
    )
    assert "\n> " not in body


def test_body_first_line_is_always_the_marker() -> None:
    """Even if future versions add content, the marker must remain on
    line 1 so the jq pipeline finds it in the first line of the body."""
    for payload in (
        {"dedup_key": "sha256:a", "severity": "LOW", "type": "X", "message": "m"},
        {
            "dedup_key": "sha256:b",
            "severity": "HIGH",
            "type": "Y",
            "message": "m",
            "suggestion": "s",
        },
    ):
        body = _format_comment_body(payload)
        assert body.splitlines()[0].startswith("<!-- hefesto-pr-review: dedup_key=")
