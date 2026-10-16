"""Turn cloud-analyzer findings into the issues the engine reports."""

from __future__ import annotations

from typing import List

from hefesto.analyzers.cloud.finding_schema import CloudFinding
from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

_SEVERITY = {
    "CRITICAL": AnalysisIssueSeverity.CRITICAL,
    "HIGH": AnalysisIssueSeverity.HIGH,
    "MEDIUM": AnalysisIssueSeverity.MEDIUM,
    "LOW": AnalysisIssueSeverity.LOW,
    "INFO": AnalysisIssueSeverity.LOW,
}

_CONFIDENCE = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5}


def cloud_findings_to_issues(findings: List[CloudFinding]) -> List[AnalysisIssue]:
    """Map ``CloudFinding`` values onto ``AnalysisIssue``.

    Cloud analyzers take ``(content, path)`` and do not fill a line number.
    Secret-like evidence uses ``HARDCODED_SECRET``. Insecure-default rules
    (``I001``) use ``SECURITY_MISCONFIGURATION``.
    """
    issues: List[AnalysisIssue] = []
    for finding in findings:
        evidence = finding.evidence or ""
        lowered = evidence.lower()
        if "I001" in (finding.rule_id or ""):
            issue_type = AnalysisIssueType.SECURITY_MISCONFIGURATION
        elif "hardcoded" in lowered or "secret" in lowered:
            issue_type = AnalysisIssueType.HARDCODED_SECRET
        else:
            issue_type = AnalysisIssueType.SECURITY_MISCONFIGURATION
        location = finding.location
        issues.append(
            AnalysisIssue(
                file_path=location.path,
                line=location.start_line or 1,
                column=1,
                issue_type=issue_type,
                severity=_SEVERITY.get(str(finding.severity).upper(), AnalysisIssueSeverity.MEDIUM),
                message=evidence,
                suggestion=finding.remediation,
                engine=f"hefesto-{finding.format}",
                rule_id=finding.rule_id,
                confidence=_CONFIDENCE.get(str(finding.confidence).upper(), 0.5),
            )
        )
    return issues
