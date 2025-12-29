"""
PowerShell Analyzer for Hefesto.

Detects security issues and anti-patterns in PowerShell scripts (.ps1, .psm1, .psd1).
Part of Ola 2 DevOps language support.
"""

import re
from typing import List, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class PowerShellAnalyzer:
    """Analyzer for PowerShell scripts."""

    # PS001: Invoke-Expression / iex (code injection risk)
    INVOKE_EXPRESSION_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\bInvoke-Expression\b", re.IGNORECASE),
            "Invoke-Expression allows arbitrary code execution (injection risk)",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "PS001",
        ),
        (
            re.compile(r"\biex\b", re.IGNORECASE),
            "iex (Invoke-Expression alias) allows arbitrary code execution",
            0.92,
            AnalysisIssueSeverity.CRITICAL,
            "PS001",
        ),
    ]

    # PS002: Download + Execute pattern (remote code execution)
    DOWNLOAD_EXECUTE_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"(?:DownloadString|DownloadFile)\s*\([^)]+\).*?" r"(?:Invoke-Expression|iex|\|)",
                re.IGNORECASE | re.DOTALL,
            ),
            "Download + Execute pattern detected (remote code execution risk)",
            0.98,
            AnalysisIssueSeverity.CRITICAL,
            "PS002",
        ),
        (
            re.compile(
                r"(?:Invoke-WebRequest|iwr|curl|wget)\s+.*?" r"(?:\|\s*(?:Invoke-Expression|iex))",
                re.IGNORECASE | re.DOTALL,
            ),
            "Web request piped to Invoke-Expression (remote code execution)",
            0.97,
            AnalysisIssueSeverity.CRITICAL,
            "PS002",
        ),
        (
            re.compile(
                r"New-Object\s+(?:Net\.)?WebClient.*?DownloadString",
                re.IGNORECASE | re.DOTALL,
            ),
            "WebClient.DownloadString used (potential remote code execution)",
            0.85,
            AnalysisIssueSeverity.HIGH,
            "PS002",
        ),
    ]

    # PS003: Start-Process with concatenated arguments
    START_PROCESS_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"Start-Process\s+.*?\$\w+",
                re.IGNORECASE,
            ),
            "Start-Process with variable interpolation (command injection risk)",
            0.80,
            AnalysisIssueSeverity.HIGH,
            "PS003",
        ),
        (
            re.compile(
                r"Start-Process\s+.*?-ArgumentList\s+.*?\+",
                re.IGNORECASE,
            ),
            "Start-Process with concatenated arguments (injection risk)",
            0.85,
            AnalysisIssueSeverity.HIGH,
            "PS003",
        ),
    ]

    # PS004: Hardcoded secrets
    SECRET_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"\$(?:password|passwd|pwd|secret|api_?key|token|credential)\s*=\s*"
                r"['\"][^'\"]+['\"]",
                re.IGNORECASE,
            ),
            "Hardcoded secret in variable assignment",
            0.90,
            AnalysisIssueSeverity.CRITICAL,
            "PS004",
        ),
        (
            re.compile(
                r"ConvertTo-SecureString\s+['\"][^'\"]+['\"]\s+-AsPlainText",
                re.IGNORECASE,
            ),
            "Hardcoded password in ConvertTo-SecureString",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "PS004",
        ),
    ]

    # PS005: Execution policy bypass
    EXECUTION_POLICY_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"Set-ExecutionPolicy\s+(?:Bypass|Unrestricted)",
                re.IGNORECASE,
            ),
            "Execution policy set to Bypass/Unrestricted (security bypass)",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "PS005",
        ),
        (
            re.compile(
                r"-ExecutionPolicy\s+(?:Bypass|Unrestricted)",
                re.IGNORECASE,
            ),
            "Execution policy bypass in command line",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "PS005",
        ),
    ]

    # PS006: TLS/Certificate validation bypass
    TLS_BYPASS_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"\[System\.Net\.ServicePointManager\]::ServerCertificateValidation"
                r"Callback\s*=",
                re.IGNORECASE,
            ),
            "Certificate validation callback override (MITM vulnerability)",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "PS006",
        ),
        (
            re.compile(
                r"\[Net\.ServicePointManager\]::SecurityProtocol\s*=.*?Ssl3",
                re.IGNORECASE,
            ),
            "SSL3 protocol enabled (insecure, deprecated)",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "PS006",
        ),
        (
            re.compile(
                r"-SkipCertificateCheck",
                re.IGNORECASE,
            ),
            "Certificate check skipped (MITM vulnerability)",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "PS006",
        ),
    ]

    def __init__(self):
        """Initialize the PowerShell analyzer."""
        self.all_patterns = (
            self.INVOKE_EXPRESSION_PATTERNS
            + self.DOWNLOAD_EXECUTE_PATTERNS
            + self.START_PROCESS_PATTERNS
            + self.SECRET_PATTERNS
            + self.EXECUTION_POLICY_PATTERNS
            + self.TLS_BYPASS_PATTERNS
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
        line_content: str = "",
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
            engine="hefesto-powershell",
            source="PowerShellAnalyzer",
            metadata={"line_content": line_content},
        )

    def _build_scan_content(self, content: str) -> str:
        """
        Build scan content with comments and strings masked.
        Preserves length for offset mapping.
        """
        NL = chr(10)
        out: List[str] = []
        n = len(content)
        i = 0

        in_single_line_comment = False
        in_block_comment = False
        in_single_string = False
        in_double_string = False

        while i < n:
            ch = content[i]
            nxt = content[i + 1] if i + 1 < n else ""

            # Handle newlines
            if ch == NL:
                in_single_line_comment = False
                out.append(ch)
                i += 1
                continue

            # Block comment end
            if in_block_comment:
                if ch == "#" and nxt == ">":
                    out.append(" ")
                    out.append(" ")
                    in_block_comment = False
                    i += 2
                    continue
                out.append(" ")
                i += 1
                continue

            # Line comment
            if in_single_line_comment:
                out.append(" ")
                i += 1
                continue

            # String handling - mask content
            if in_single_string:
                if ch == "'" and nxt == "'":
                    out.append("'")
                    out.append("'")
                    i += 2
                    continue
                if ch == "'":
                    in_single_string = False
                    out.append(ch)
                    i += 1
                    continue
                out.append(" ")
                i += 1
                continue

            if in_double_string:
                if ch == "`" and nxt == '"':
                    out.append(" ")
                    out.append(" ")
                    i += 2
                    continue
                if ch == '"':
                    in_double_string = False
                    out.append(ch)
                    i += 1
                    continue
                out.append(" ")
                i += 1
                continue

            # Start block comment <#
            if ch == "<" and nxt == "#":
                in_block_comment = True
                out.append(" ")
                out.append(" ")
                i += 2
                continue

            # Start line comment #
            if ch == "#":
                in_single_line_comment = True
                out.append(" ")
                i += 1
                continue

            # Start strings
            if ch == "'":
                in_single_string = True
                out.append(ch)
                i += 1
                continue

            if ch == '"':
                in_double_string = True
                out.append(ch)
                i += 1
                continue

            out.append(ch)
            i += 1

        return "".join(out)

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """
        Analyze PowerShell content for security issues.

        Args:
            file_path: Path to the file being analyzed
            content: The PowerShell script content

        Returns:
            List of AnalysisIssue objects
        """
        issues: List[AnalysisIssue] = []
        lines = content.splitlines()

        # Build scan content with comments/strings masked
        scan_content = self._build_scan_content(content)

        # Analyze each pattern
        for pattern, msg, confidence, severity, rule_id in self.all_patterns:
            for match in pattern.finditer(scan_content):
                # Calculate line number from offset
                offset = match.start()
                line_num = content[:offset].count(chr(10)) + 1
                col = offset - content.rfind(chr(10), 0, offset)

                # Get line content
                line_content = ""
                if 0 < line_num <= len(lines):
                    line_content = lines[line_num - 1].strip()

                # Determine issue type based on rule
                if rule_id == "PS001":
                    issue_type = AnalysisIssueType.PS_INVOKE_EXPRESSION
                elif rule_id == "PS002":
                    issue_type = AnalysisIssueType.PS_REMOTE_CODE_EXECUTION
                elif rule_id == "PS003":
                    issue_type = AnalysisIssueType.PS_COMMAND_INJECTION
                elif rule_id == "PS004":
                    issue_type = AnalysisIssueType.HARDCODED_SECRET
                elif rule_id == "PS005":
                    issue_type = AnalysisIssueType.PS_EXECUTION_POLICY_BYPASS
                else:  # PS006
                    issue_type = AnalysisIssueType.PS_TLS_BYPASS

                # Determine suggestion based on rule
                suggestions = {
                    "PS001": (
                        "Avoid Invoke-Expression. Use direct cmdlet calls or "
                        "parameter binding instead."
                    ),
                    "PS002": (
                        "Download files to disk first, verify integrity, "
                        "then execute. Never pipe directly to iex."
                    ),
                    "PS003": (
                        "Use argument arrays or splatting instead of "
                        "string concatenation with Start-Process."
                    ),
                    "PS004": (
                        "Use environment variables, secure vaults, or "
                        "credential managers for secrets."
                    ),
                    "PS005": ("Sign scripts properly instead of bypassing " "execution policy."),
                    "PS006": (
                        "Use proper certificate validation. "
                        "Never disable TLS/certificate checks."
                    ),
                }

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
