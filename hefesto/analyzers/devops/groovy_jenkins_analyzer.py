"""
Groovy/Jenkins Analyzer for Hefesto.

Detects security issues in Jenkinsfiles and Groovy scripts.
Part of Ola 2 DevOps language support.

Rules:
- GJ001: sh/bat with Groovy interpolation (command injection)
- GJ002: Download and execute (curl|sh, wget|bash)
- GJ003: Credential exposure to logs
- GJ004: TLS/cert validation bypass
- GJ005: Dangerous evaluate/GroovyShell patterns
"""

from __future__ import annotations

import re
from typing import List, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class GroovyJenkinsAnalyzer:
    """Analyzer for Jenkinsfiles and Groovy scripts."""

    # GJ001: sh/bat with interpolation
    GJ001_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r'\b(sh|bat)\s*\(\s*["\'].*\$\{[^}]+\}.*["\']\s*\)',
                re.I,
            ),
            "sh/bat with Groovy interpolation is vulnerable to command injection.",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "GJ001",
        ),
        (
            re.compile(
                r'\b(sh|bat)\s+["\'].*\$\{[^}]+\}.*["\']',
                re.I,
            ),
            "sh/bat with Groovy interpolation is vulnerable to command injection.",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "GJ001",
        ),
        (
            re.compile(
                r'\b(sh|bat)\s*\(\s*"[^"]*"\s*\+\s*\w+',
                re.I,
            ),
            "sh/bat with string concatenation is vulnerable to injection.",
            0.85,
            AnalysisIssueSeverity.HIGH,
            "GJ001",
        ),
    ]

    # GJ002: Download + execute
    GJ002_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r'\b(sh|bat)\s*[(\s]+["\'].*' r'(curl|wget)\b.*\|\s*(sh|bash|zsh)\b.*["\']',
                re.I,
            ),
            "Downloading and piping to shell in pipeline is RCE risk.",
            0.97,
            AnalysisIssueSeverity.CRITICAL,
            "GJ002",
        ),
        (
            re.compile(
                r"(curl|wget)\b.*\|\s*(sh|bash|zsh)\b",
                re.I,
            ),
            "curl/wget piped to shell detected (remote code execution).",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "GJ002",
        ),
    ]

    # GJ003: Credential exposure
    GJ003_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"\b(echo|println)\s*[(\s]+.*"
                r"(\$?\{?(?:PASSWORD|TOKEN|SECRET|API_KEY|CREDENTIAL)[^}]*\}?)",
                re.I,
            ),
            "Credential may be exposed in logs via echo/println.",
            0.92,
            AnalysisIssueSeverity.CRITICAL,
            "GJ003",
        ),
        (
            re.compile(
                r'\bsh\s*["\'].*echo\s+\$\{?(?:PASSWORD|TOKEN|SECRET|API_KEY)',
                re.I,
            ),
            "Credential may be exposed via sh echo command.",
            0.90,
            AnalysisIssueSeverity.CRITICAL,
            "GJ003",
        ),
        (
            re.compile(
                r"\bset\s+-x\b.*withCredentials",
                re.I | re.DOTALL,
            ),
            "set -x with credentials exposes secrets in logs.",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "GJ003",
        ),
        (
            re.compile(
                r"withCredentials.*\bset\s+-x\b",
                re.I | re.DOTALL,
            ),
            "set -x within withCredentials exposes secrets in logs.",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "GJ003",
        ),
    ]

    # GJ004: TLS bypass
    GJ004_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bcurl\b.*(\s-k\b|--insecure\b)", re.I),
            "curl with TLS verification disabled in pipeline.",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "GJ004",
        ),
        (
            re.compile(r"\bwget\b.*--no-check-certificate\b", re.I),
            "wget with certificate check disabled in pipeline.",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "GJ004",
        ),
        (
            re.compile(r"\bgit\b.*-c\s+http\.sslVerify\s*=\s*false\b", re.I),
            "git with sslVerify=false in pipeline.",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "GJ004",
        ),
    ]

    # GJ005: Dangerous evaluate patterns
    GJ005_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"\bevaluate\s*\(\s*new\s+File\s*\([^)]+\)\.text\s*\)",
                re.I,
            ),
            "evaluate(new File(...).text) executes arbitrary code from file.",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "GJ005",
        ),
        (
            re.compile(
                r"\bGroovyShell\s*\(\s*\)\.evaluate\s*\(",
                re.I,
            ),
            "GroovyShell().evaluate() can execute arbitrary code.",
            0.94,
            AnalysisIssueSeverity.CRITICAL,
            "GJ005",
        ),
        (
            re.compile(
                r"\bload\s+['\"].*\.groovy['\"]",
                re.I,
            ),
            "load 'script.groovy' loads external code; ensure source is trusted.",
            0.75,
            AnalysisIssueSeverity.MEDIUM,
            "GJ005",
        ),
        (
            re.compile(
                r"\bEval\s*\.\s*me\s*\(",
                re.I,
            ),
            "Eval.me() can execute arbitrary Groovy code.",
            0.93,
            AnalysisIssueSeverity.CRITICAL,
            "GJ005",
        ),
    ]

    def __init__(self) -> None:
        """Initialize the Groovy/Jenkins analyzer."""
        self.all_patterns = (
            self.GJ001_PATTERNS
            + self.GJ002_PATTERNS
            + self.GJ003_PATTERNS
            + self.GJ004_PATTERNS
            + self.GJ005_PATTERNS
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
            engine="hefesto-groovy-jenkins",
            metadata={"line_content": line_content},
        )

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """
        Analyze Groovy/Jenkinsfile content for security issues.

        Args:
            file_path: Path to the file being analyzed
            content: The Groovy/Jenkinsfile content

        Returns:
            List of AnalysisIssue objects
        """
        issues: List[AnalysisIssue] = []
        lines = content.splitlines()
        NL = chr(10)

        suggestions = {
            "GJ001": (
                "Use single quotes for sh/bat commands to prevent Groovy "
                "interpolation, or validate/escape inputs."
            ),
            "GJ002": (
                "Download files first, verify integrity (checksum/signature), " "then execute."
            ),
            "GJ003": (
                "Never echo or print credentials. Use withCredentials properly "
                "and avoid set -x with secrets."
            ),
            "GJ004": (
                "Do not disable TLS/certificate verification. " "Fix certificates/PKI instead."
            ),
            "GJ005": (
                "Avoid evaluate/GroovyShell for dynamic code. "
                "Use trusted shared libraries instead."
            ),
        }

        for pattern, msg, confidence, severity, rule_id in self.all_patterns:
            for m in pattern.finditer(content):
                offset = m.start()
                line_num = content[:offset].count(NL) + 1
                last_nl = content.rfind(NL, 0, offset)
                col = offset - last_nl if last_nl != -1 else offset + 1

                line_content = ""
                if 0 < line_num <= len(lines):
                    line_content = lines[line_num - 1].strip()

                # Map to issue types
                if rule_id in ("GJ001", "GJ002", "GJ005"):
                    issue_type = AnalysisIssueType.SHELL_COMMAND_INJECTION
                elif rule_id == "GJ003":
                    issue_type = AnalysisIssueType.HARDCODED_SECRET
                else:  # GJ004
                    issue_type = AnalysisIssueType.INSECURE_COMMUNICATION

                issues.append(
                    self._create_issue(
                        file_path=file_path,
                        line=line_num,
                        column=col,
                        issue_type=issue_type,
                        severity=severity,
                        message=msg,
                        suggestion=suggestions.get(rule_id, "Review this code."),
                        confidence=confidence,
                        rule_id=rule_id,
                        line_content=line_content,
                    )
                )

        return issues
