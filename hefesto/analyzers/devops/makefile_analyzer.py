"""
Makefile Analyzer for Hefesto.

Detects security issues and risky patterns in Makefiles.
Part of Ola 2 DevOps language support.

Rules:
- MF001: Shell injection / dynamic execution sinks
- MF002: curl/wget piped to shell
- MF003: sudo usage in recipes
- MF004: TLS/cert validation bypass
- MF005: Dangerous deletes
"""

from __future__ import annotations

import re
from typing import List, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class MakefileAnalyzer:
    """Analyzer for Makefiles and *.mk files."""

    RECIPE_PREFIX = "\t"

    # MF001: Dynamic execution sinks + expansions
    MF001_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\b(eval)\b\s+.*(\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|`)", re.I),
            "Use of eval with expansions can lead to shell injection.",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "MF001",
        ),
        (
            re.compile(
                r"\b(sh|bash|zsh)\b\s+-c\s+['\"].*"
                r"(\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|`).*['\"]",
                re.I,
            ),
            "Shell -c with interpolated content can lead to command injection.",
            0.86,
            AnalysisIssueSeverity.HIGH,
            "MF001",
        ),
        (
            re.compile(r"\bxargs\b.*\b(sh|bash)\b\s+-c\b", re.I),
            "xargs invoking a shell increases injection risk.",
            0.80,
            AnalysisIssueSeverity.HIGH,
            "MF001",
        ),
        (
            re.compile(r"\$\(\s*shell\s+[^)]+\)", re.I),
            "Make $(shell ...) executes commands at parse time.",
            0.84,
            AnalysisIssueSeverity.HIGH,
            "MF001",
        ),
    ]

    # MF002: curl/wget piped to shell
    MF002_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh)\b", re.I),
            "Downloading and piping to a shell is a remote code execution risk.",
            0.97,
            AnalysisIssueSeverity.CRITICAL,
            "MF002",
        ),
        (
            re.compile(r"\b(curl|wget)\b.*\|\s*(sudo\s+)?(sh|bash|zsh)\b", re.I),
            "Downloading and piping to (sudo) shell is a high-confidence RCE.",
            0.98,
            AnalysisIssueSeverity.CRITICAL,
            "MF002",
        ),
    ]

    # MF003: sudo usage
    MF003_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"(^|\s)sudo(\s|$)", re.I),
            "Using sudo inside Make recipes is risky.",
            0.75,
            AnalysisIssueSeverity.MEDIUM,
            "MF003",
        ),
    ]

    # MF004: TLS/cert bypass
    MF004_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bcurl\b.*(\s-k\b|--insecure\b)", re.I),
            "curl used with TLS verification disabled (-k/--insecure).",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "MF004",
        ),
        (
            re.compile(r"\bwget\b.*--no-check-certificate\b", re.I),
            "wget used with certificate checks disabled.",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "MF004",
        ),
        (
            re.compile(r"\bgit\b.*-c\s+http\.sslVerify\s*=\s*false\b", re.I),
            "git used with sslVerify=false (TLS disabled).",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "MF004",
        ),
        (
            re.compile(
                r"\b(GIT_SSL_NO_VERIFY|NODE_TLS_REJECT_UNAUTHORIZED)" r"\s*=\s*(1|true|0)\b",
                re.I,
            ),
            "Environment variable disables TLS verification.",
            0.86,
            AnalysisIssueSeverity.HIGH,
            "MF004",
        ),
    ]

    # MF005: Dangerous deletes
    MF005_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\brm\b\s+-rf\s+/\s*($|;)", re.I),
            "rm -rf / is extremely dangerous.",
            0.99,
            AnalysisIssueSeverity.CRITICAL,
            "MF005",
        ),
        (
            re.compile(r"\brm\b\s+-rf\s+/\*\s*($|;)", re.I),
            "rm -rf /* is extremely dangerous.",
            0.99,
            AnalysisIssueSeverity.CRITICAL,
            "MF005",
        ),
        (
            re.compile(r"\brm\b\s+-rf\s+(\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|\*)", re.I),
            "rm -rf with variables/wildcards is risky.",
            0.82,
            AnalysisIssueSeverity.HIGH,
            "MF005",
        ),
    ]

    def __init__(self) -> None:
        """Initialize the Makefile analyzer."""
        self.all_patterns = (
            self.MF001_PATTERNS
            + self.MF002_PATTERNS
            + self.MF003_PATTERNS
            + self.MF004_PATTERNS
            + self.MF005_PATTERNS
        )

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
        line_content: str,
    ) -> AnalysisIssue:
        """Create a standardized AnalysisIssue."""
        return AnalysisIssue(
            file_path=file_path,
            line=line,
            column=column,
            issue_type=issue_type,
            severity=severity,
            message=message,
            suggestion=suggestion,
            confidence=confidence,
            rule_id=rule_id,
            engine="hefesto-makefile",
            metadata={"line_content": line_content},
        )

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """
        Analyze Makefile content. Only scans recipe lines (TAB-prefixed).

        Args:
            file_path: Path to the file being analyzed
            content: The Makefile content

        Returns:
            List of AnalysisIssue objects
        """
        issues: List[AnalysisIssue] = []
        lines = content.splitlines()

        suggestions = {
            "MF001": (
                "Avoid dynamic execution. Prefer explicit commands " "and safe argument handling."
            ),
            "MF002": (
                "Do not pipe downloads to a shell. Download, verify "
                "(checksum/signature), then execute."
            ),
            "MF003": (
                "Avoid sudo in builds. Use least-privilege environments "
                "or document manual steps."
            ),
            "MF004": "Do not disable TLS verification. Fix certificates/PKI instead.",
            "MF005": (
                "Add strict path guards (non-empty, expected prefix) " "before destructive deletes."
            ),
        }

        for idx, line in enumerate(lines, start=1):
            if not line.startswith(self.RECIPE_PREFIX):
                continue

            # Ignore comment-only recipe lines
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue

            scan_line = line

            for pattern, msg, confidence, severity, rule_id in self.all_patterns:
                for m in pattern.finditer(scan_line):
                    col = m.start() + 1

                    if rule_id in ("MF001", "MF002"):
                        issue_type = AnalysisIssueType.SHELL_COMMAND_INJECTION
                    elif rule_id == "MF004":
                        issue_type = AnalysisIssueType.INSECURE_COMMUNICATION
                    else:  # MF003, MF005
                        issue_type = AnalysisIssueType.SECURITY_MISCONFIGURATION

                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=idx,
                            column=col,
                            issue_type=issue_type,
                            severity=severity,
                            message=msg,
                            suggestion=suggestions.get(rule_id, "Review this line."),
                            confidence=confidence,
                            rule_id=rule_id,
                            line_content=line.strip(),
                        )
                    )

        return issues
