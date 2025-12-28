"""
Terraform/HCL Analyzer for Hefesto DevOps Support (internal).

Detects infrastructure security issues in Terraform configurations:
- Open security groups (0.0.0.0/0 ingress)
- Hardcoded secrets (AWS keys, passwords in variables)
- Missing encryption (S3, EBS, RDS without encryption)
- Public access enabled (public_access_block, publicly_accessible)
- Overly permissive IAM policies

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from typing import List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class TerraformAnalyzer:
    ENGINE = "internal:terraform_analyzer"

    OPEN_SG_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r'\bcidr_blocks\s*=\s*\[\s*"0\.0\.0\.0/0"\s*\]', re.IGNORECASE),
            "Security group allows ingress from 0.0.0.0/0 (world-open)",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "TF001",
        ),
        (
            re.compile(r'\bcidr_block\s*=\s*"0\.0\.0\.0/0"', re.IGNORECASE),
            "Security group allows ingress from 0.0.0.0/0 (world-open)",
            0.93,
            AnalysisIssueSeverity.CRITICAL,
            "TF001B",
        ),
        (
            re.compile(r'\bipv6_cidr_blocks\s*=\s*\[\s*"::/0"\s*\]', re.IGNORECASE),
            "Security group allows ingress from ::/0 (IPv6 world-open)",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "TF002",
        ),
        (
            re.compile(r'\bipv6_cidr_block\s*=\s*"::/0"', re.IGNORECASE),
            "Security group allows ingress from ::/0 (IPv6 world-open)",
            0.93,
            AnalysisIssueSeverity.CRITICAL,
            "TF002B",
        ),
    ]

    SECRET_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\b(AKIA|ASIA|AIDA)[0-9A-Z]{16}\b"),
            "AWS Access Key ID appears in Terraform file",
            0.98,
            AnalysisIssueSeverity.CRITICAL,
            "TF010",
        ),
        (
            re.compile(r'\bpassword\s*=\s*"[^"]{4,}"', re.IGNORECASE),
            "Hardcoded password in Terraform configuration",
            0.90,
            AnalysisIssueSeverity.CRITICAL,
            "TF011",
        ),
        (
            re.compile(r'\bsecret\s*=\s*"[^"]{8,}"', re.IGNORECASE),
            "Hardcoded secret in Terraform configuration",
            0.88,
            AnalysisIssueSeverity.CRITICAL,
            "TF012",
        ),
        (
            re.compile(r'\bapi_key\s*=\s*"[^"]{10,}"', re.IGNORECASE),
            "Hardcoded API key in Terraform configuration",
            0.88,
            AnalysisIssueSeverity.CRITICAL,
            "TF013",
        ),
    ]

    ENCRYPTION_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bencrypted\s*=\s*false\b", re.IGNORECASE),
            "Resource explicitly disables encryption",
            0.95,
            AnalysisIssueSeverity.HIGH,
            "TF020",
        ),
        (
            re.compile(r"\bstorage_encrypted\s*=\s*false\b", re.IGNORECASE),
            "RDS storage encryption disabled",
            0.95,
            AnalysisIssueSeverity.HIGH,
            "TF021",
        ),
        (
            re.compile(r'\bkms_key_id\s*=\s*""\b', re.IGNORECASE),
            "Empty KMS key ID (no encryption key specified)",
            0.80,
            AnalysisIssueSeverity.MEDIUM,
            "TF022",
        ),
    ]

    PUBLIC_ACCESS_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bpublicly_accessible\s*=\s*true\b", re.IGNORECASE),
            "Resource is publicly accessible",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "TF030",
        ),
        (
            re.compile(r"\bblock_public_acls\s*=\s*false\b", re.IGNORECASE),
            "S3 public ACLs not blocked",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "TF031",
        ),
        (
            re.compile(r"\bblock_public_policy\s*=\s*false\b", re.IGNORECASE),
            "S3 public policy not blocked",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "TF032",
        ),
        (
            re.compile(r"\bignore_public_acls\s*=\s*false\b", re.IGNORECASE),
            "S3 not ignoring public ACLs",
            0.88,
            AnalysisIssueSeverity.MEDIUM,
            "TF033",
        ),
    ]

    IAM_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r'"Action"\s*:\s*"\*"', re.IGNORECASE),
            "IAM policy allows all actions (Action: *)",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "TF040",
        ),
        (
            re.compile(r'"Resource"\s*:\s*"\*"', re.IGNORECASE),
            "IAM policy applies to all resources (Resource: *)",
            0.85,
            AnalysisIssueSeverity.HIGH,
            "TF041",
        ),
    ]

    def _create_issue(
        self,
        file_path: str,
        line: int,
        column: int,
        issue_type: AnalysisIssueType,
        severity: AnalysisIssueSeverity,
        message: str,
        suggestion: str,
        confidence: float,
        rule_id: str,
        line_content: Optional[str] = None,
    ) -> AnalysisIssue:
        md = {"line_content": (line_content or "").strip()[:200]}
        return AnalysisIssue(
            file_path=file_path,
            line=line,
            column=column,
            issue_type=issue_type,
            severity=severity,
            message=message,
            suggestion=suggestion,
            engine=self.ENGINE,
            confidence=confidence,
            rule_id=rule_id,
            metadata=md,
        )

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        issues: List[AnalysisIssue] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            for pattern, msg, conf, sev, rule in self.OPEN_SG_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.TF_OPEN_SECURITY_GROUP,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Restrict CIDR blocks to specific IP ranges "
                                "or reference known security groups."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

            for pattern, msg, conf, sev, rule in self.SECRET_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.TF_HARDCODED_SECRET,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Use variables with sensitive=true and inject via "
                                "Secret Manager or Vault."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

            for pattern, msg, conf, sev, rule in self.ENCRYPTION_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.TF_MISSING_ENCRYPTION,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Enable encryption (encrypted=true) and configure a " "KMS key."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

            for pattern, msg, conf, sev, rule in self.PUBLIC_ACCESS_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.TF_PUBLIC_ACCESS,
                            severity=sev,
                            message=msg,
                            suggestion=("Disable public access unless explicitly required."),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

            for pattern, msg, conf, sev, rule in self.IAM_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line_num,
                            column=1,
                            issue_type=AnalysisIssueType.TF_OVERLY_PERMISSIVE,
                            severity=sev,
                            message=msg,
                            suggestion=(
                                "Apply least privilege with specific actions and "
                                "scoped resources."
                            ),
                            confidence=conf,
                            rule_id=rule,
                            line_content=line,
                        )
                    )
                    break

        return issues


__all__ = ["TerraformAnalyzer"]
