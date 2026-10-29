"""Collapse findings that several patterns of one rule report on the same line."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from hefesto.core.analysis_models import AnalysisIssue


def keep_best_per_line(issues: List[AnalysisIssue], rule_ids: Iterable[str]) -> List[AnalysisIssue]:
    """Keep one finding per (line, rule_id) for ``rule_ids``: the highest confidence.

    Ties keep the earlier finding. The kept finding takes the position of the
    first finding for that key, so output order is otherwise unchanged.
    """
    rules = set(rule_ids)
    best: Dict[Tuple[int, str], AnalysisIssue] = {}
    for issue in issues:
        if issue.rule_id not in rules:
            continue
        key = (issue.line, issue.rule_id)
        current = best.get(key)
        if current is None or (issue.confidence or 0.0) > (current.confidence or 0.0):
            best[key] = issue

    result: List[AnalysisIssue] = []
    emitted = set()
    for issue in issues:
        if issue.rule_id not in rules:
            result.append(issue)
            continue
        key = (issue.line, issue.rule_id)
        if key not in emitted:
            emitted.add(key)
            result.append(best[key])
    return result
