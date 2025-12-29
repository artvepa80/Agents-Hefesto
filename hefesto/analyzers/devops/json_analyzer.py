"""
JSON Analyzer for Hefesto.

Detects security issues and misconfigurations in JSON files.
Part of Ola 2 DevOps language support.
"""

import json
import re
from typing import Any, List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class JsonAnalyzer:
    """Analyzer for JSON configuration files."""

    # J001: Secret key patterns
    SECRET_KEY_PATTERNS = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "apikey",
        "api-key",
        "token",
        "access_token",
        "auth_token",
        "client_secret",
        "private_key",
        "credential",
        "auth",
        "bearer",
    ]

    # J002: Insecure URL patterns
    INSECURE_URL_KEYS = [
        "url",
        "endpoint",
        "api_url",
        "base_url",
        "server",
        "host",
        "webhook",
        "callback",
    ]

    # J005: Dangerous flag patterns
    DANGEROUS_FLAGS = [
        ("insecure", True),
        ("skip_tls_verify", True),
        ("skipTlsVerify", True),
        ("verify", False),
        ("verify_ssl", False),
        ("ssl_verify", False),
        ("allow_insecure", True),
        ("allowInsecure", True),
        ("disable_ssl", True),
        ("disableSsl", True),
        ("NODE_TLS_REJECT_UNAUTHORIZED", "0"),
    ]

    def __init__(self):
        """Initialize the JSON analyzer."""
        pass

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
            engine="hefesto-json",
            source="JsonAnalyzer",
            metadata={"line_content": line_content},
        )

    def _find_line_for_pattern(
        self, content: str, pattern: str, start_pos: int = 0
    ) -> Tuple[int, int, str]:
        """Find line number, column, and content for a pattern match."""
        pos = content.find(pattern, start_pos)
        if pos == -1:
            return 1, 1, ""

        line_num = content[:pos].count(chr(10)) + 1
        last_newline = content.rfind(chr(10), 0, pos)
        col = pos - last_newline if last_newline != -1 else pos + 1

        lines = content.splitlines()
        line_content = lines[line_num - 1] if 0 < line_num <= len(lines) else ""

        return line_num, col, line_content.strip()

    def _check_secrets(
        self,
        data: Any,
        file_path: str,
        content: str,
        path: str = "",
        issues: Optional[List[AnalysisIssue]] = None,
    ) -> List[AnalysisIssue]:
        """Recursively check for hardcoded secrets (J001)."""
        if issues is None:
            issues = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                key_lower = key.lower()

                # Check if key suggests a secret
                is_secret_key = any(pattern in key_lower for pattern in self.SECRET_KEY_PATTERNS)

                if is_secret_key and isinstance(value, str) and len(value) > 0:
                    # Skip environment variable references
                    if value.startswith("$") or value.startswith("${"):
                        continue
                    # Skip placeholder patterns
                    if value.startswith("<") and value.endswith(">"):
                        continue
                    if "{{" in value and "}}" in value:
                        continue

                    line, col, line_content = self._find_line_for_pattern(content, f'"{key}"')

                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line,
                            column=col,
                            issue_type=AnalysisIssueType.HARDCODED_SECRET,
                            severity=AnalysisIssueSeverity.CRITICAL,
                            message=f"Hardcoded secret in key '{key}'",
                            suggestion=(
                                "Use environment variables or a secrets manager "
                                "instead of hardcoding secrets."
                            ),
                            confidence=0.90,
                            rule_id="J001",
                            line_content=line_content,
                        )
                    )

                # Recurse into nested structures
                self._check_secrets(data[key], file_path, content, current_path, issues)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._check_secrets(item, file_path, content, f"{path}[{i}]", issues)

        return issues

    def _check_insecure_urls(
        self,
        data: Any,
        file_path: str,
        content: str,
        path: str = "",
        issues: Optional[List[AnalysisIssue]] = None,
    ) -> List[AnalysisIssue]:
        """Check for insecure HTTP URLs (J002)."""
        if issues is None:
            issues = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                key_lower = key.lower()

                # Check if key suggests a URL field
                is_url_key = any(pattern in key_lower for pattern in self.INSECURE_URL_KEYS)

                if is_url_key and isinstance(value, str):
                    if value.startswith("http://") and "localhost" not in value:
                        line, col, line_content = self._find_line_for_pattern(content, value)

                        issues.append(
                            self._create_issue(
                                file_path=file_path,
                                line=line,
                                column=col,
                                issue_type=AnalysisIssueType.INSECURE_COMMUNICATION,
                                severity=AnalysisIssueSeverity.MEDIUM,
                                message=f"Insecure HTTP URL in '{key}'",
                                suggestion=(
                                    "Use HTTPS instead of HTTP for secure " "communication."
                                ),
                                confidence=0.85,
                                rule_id="J002",
                                line_content=line_content,
                            )
                        )

                # Recurse
                self._check_insecure_urls(data[key], file_path, content, current_path, issues)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._check_insecure_urls(item, file_path, content, f"{path}[{i}]", issues)

        return issues

    def _check_dangerous_flags(
        self,
        data: Any,
        file_path: str,
        content: str,
        path: str = "",
        issues: Optional[List[AnalysisIssue]] = None,
    ) -> List[AnalysisIssue]:
        """Check for dangerous security flags (J005)."""
        if issues is None:
            issues = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                # Check against known dangerous flags
                for flag_name, dangerous_value in self.DANGEROUS_FLAGS:
                    if key.lower() == flag_name.lower() and value == dangerous_value:
                        line, col, line_content = self._find_line_for_pattern(content, f'"{key}"')

                        issues.append(
                            self._create_issue(
                                file_path=file_path,
                                line=line,
                                column=col,
                                issue_type=AnalysisIssueType.SECURITY_MISCONFIGURATION,
                                severity=AnalysisIssueSeverity.HIGH,
                                message=f"Dangerous flag '{key}' set to {value}",
                                suggestion=(
                                    "Security flags like TLS/SSL verification "
                                    "should not be disabled."
                                ),
                                confidence=0.92,
                                rule_id="J005",
                                line_content=line_content,
                            )
                        )

                # Recurse
                self._check_dangerous_flags(data[key], file_path, content, current_path, issues)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._check_dangerous_flags(item, file_path, content, f"{path}[{i}]", issues)

        return issues

    def _check_docker_creds(self, data: Any, file_path: str, content: str) -> List[AnalysisIssue]:
        """Check for Docker registry credentials in plain text (J004)."""
        issues: List[AnalysisIssue] = []

        if not isinstance(data, dict):
            return issues

        # Check for Docker config.json patterns
        auths = data.get("auths", {})
        if isinstance(auths, dict):
            for registry, auth_data in auths.items():
                if isinstance(auth_data, dict):
                    if "auth" in auth_data and isinstance(auth_data["auth"], str):
                        line, col, line_content = self._find_line_for_pattern(content, '"auth"')

                        issues.append(
                            self._create_issue(
                                file_path=file_path,
                                line=line,
                                column=col,
                                issue_type=AnalysisIssueType.HARDCODED_SECRET,
                                severity=AnalysisIssueSeverity.CRITICAL,
                                message=(
                                    f"Docker registry credentials for '{registry}' " "in plain text"
                                ),
                                suggestion=(
                                    "Use Docker credential helpers or environment "
                                    "variables for registry authentication."
                                ),
                                confidence=0.95,
                                rule_id="J004",
                                line_content=line_content,
                            )
                        )

        return issues

    def _fallback_regex_analysis(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """Fallback regex-based analysis for invalid JSON."""
        issues: List[AnalysisIssue] = []

        # Simple regex patterns for common issues
        secret_pattern = re.compile(
            r'"(password|api_?key|token|secret|credential)"' r'\s*:\s*"([^"]+)"',
            re.IGNORECASE,
        )

        for match in secret_pattern.finditer(content):
            key = match.group(1)
            value = match.group(2)

            # Skip placeholders
            if value.startswith("$") or value.startswith("<"):
                continue

            line = content[: match.start()].count(chr(10)) + 1
            col = match.start() - content.rfind(chr(10), 0, match.start())

            lines = content.splitlines()
            line_content = lines[line - 1].strip() if 0 < line <= len(lines) else ""

            issues.append(
                self._create_issue(
                    file_path=file_path,
                    line=line,
                    column=col,
                    issue_type=AnalysisIssueType.HARDCODED_SECRET,
                    severity=AnalysisIssueSeverity.CRITICAL,
                    message=f"Potential hardcoded secret in key '{key}'",
                    suggestion="Use environment variables for secrets.",
                    confidence=0.70,  # Lower confidence for regex fallback
                    rule_id="J001",
                    line_content=line_content,
                )
            )

        return issues

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """
        Analyze JSON content for security issues.

        Args:
            file_path: Path to the file being analyzed
            content: The JSON content

        Returns:
            List of AnalysisIssue objects
        """
        issues: List[AnalysisIssue] = []

        # Try to parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback to regex for invalid JSON
            return self._fallback_regex_analysis(file_path, content)

        # Run all checks
        issues.extend(self._check_secrets(data, file_path, content))
        issues.extend(self._check_insecure_urls(data, file_path, content))
        issues.extend(self._check_dangerous_flags(data, file_path, content))
        issues.extend(self._check_docker_creds(data, file_path, content))

        return issues
