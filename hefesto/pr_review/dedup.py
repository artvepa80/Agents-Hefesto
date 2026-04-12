"""Deterministic dedup keys for Phase 2 PR review.

The dedup key is a SHA-256 of ``{relative_path}|{line}|{issue_type}|
{normalized_message}``. It is emitted inline with each finding in the
PR review JSON so the workflow-layer posting pipeline can filter out
findings that were already commented on in a previous run.

Normalization goals:
- *Paths* inside messages are replaced with a placeholder so reruns from
  different checkout directories (``/runner/_work/...`` vs ``/home/me/...``)
  produce the same key.
- *Numbers* inside messages are replaced with a placeholder so metrics
  like "complexity = 14" do not cause every rerun to produce a new key
  if the complexity shifts by one.
- *Whitespace* is collapsed so formatting changes do not alter the key.

The normalization is deliberately aggressive. The ``relative_path`` and
``line`` are already captured explicitly in the key, so losing that
information inside ``message`` does not weaken identity — it strengthens
stability across reruns.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import hashlib
import re

from hefesto.core.analysis_models import AnalysisIssue

_WHITESPACE_RE = re.compile(r"\s+")
_PATH_RE = re.compile(r"(?:/[\w.\-]+)+")
_NUMBER_RE = re.compile(r"\b\d+\b")


def _normalize_message(message: str) -> str:
    out = message.lower().strip()
    out = _PATH_RE.sub("<path>", out)
    out = _NUMBER_RE.sub("<n>", out)
    out = _WHITESPACE_RE.sub(" ", out)
    return out.strip()


def compute_dedup_key(finding: AnalysisIssue, *, relative_path: str) -> str:
    """Return a stable ``sha256:<hex>`` dedup key for a finding.

    ``relative_path`` must be the path of the finding relative to the
    project root — passing an absolute path would couple the key to the
    current checkout directory and break dedup across reruns.
    """
    normalized = _normalize_message(finding.message)
    payload = f"{relative_path}|{finding.line}|" f"{finding.issue_type.value}|{normalized}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = ["compute_dedup_key"]
