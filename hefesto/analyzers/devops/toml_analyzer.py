"""
TOML Analyzer for Hefesto.

Detects security issues and misconfigurations in TOML files.
Part of Ola 2 DevOps language support.
"""

import re
from typing import Any, List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

try:
    import tomllib as tomli  # Python >= 3.11
except ImportError:
    try:
        import tomli  # Python 3.10
    except ImportError:
        tomli = None


class TomlAnalyzer:
    """Analyzer for TOML configuration files."""

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

    INSECURE_URL_KEYS = [
        "url",
        "endpoint",
        "api_url",
        "base_url",
        "server",
        "host",
        "webhook",
        "callback",
        "repository",
        "source",
    ]

    DANGEROUS_FLAGS = [
        ("insecure", True),
        ("skip_tls_verify", True),
        ("verify", False),
        ("verify_ssl", False),
        ("ssl_verify", False),
        ("allow_insecure", True),
        ("disable_ssl", True),
        ("node_tls_reject_unauthorized", "0"),
        ("node_tls_reject_unauthorized", 0),
    ]

    # Localhost hostnames exempt from HTTP warnings
    LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")

    def __init__(self):
        """Initialize the TOML analyzer."""
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
            engine="hefesto-toml",
            metadata={"line_content": line_content},
        )

    def _find_line_for_key(self, content: str, key: str) -> Tuple[int, int, str]:
        """Find line number, column, and content for a TOML key."""
        NL = chr(10)
        pat = re.compile(rf"(^|\s){re.escape(key)}\s*=", re.MULTILINE)
        m = pat.search(content)
        if not m:
            return 1, 1, ""

        # Calculate position at start of key, not the whitespace before
        key_pos = m.start() + len(m.group(1))
        line = content[:key_pos].count(NL) + 1
        last_nl = content.rfind(NL, 0, key_pos)
        col = key_pos - last_nl if last_nl != -1 else key_pos + 1
        lines = content.splitlines()
        line_content = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        return line, col, line_content

    def _check_secrets(
        self,
        data: Any,
        file_path: str,
        content: str,
        path: str = "",
        issues: Optional[List[AnalysisIssue]] = None,
    ) -> List[AnalysisIssue]:
        """Recursively check for hardcoded secrets (T001)."""
        if issues is None:
            issues = []

        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = str(key).lower()
                is_secret_key = any(p in key_lower for p in self.SECRET_KEY_PATTERNS)

                if is_secret_key and isinstance(value, str) and value:
                    # Skip environment variable references
                    if value.startswith("$") or value.startswith("${"):
                        continue
                    # Skip placeholder patterns
                    if value.startswith("<") and value.endswith(">"):
                        continue
                    if "{{" in value and "}}" in value:
                        continue

                    line, col, line_content = self._find_line_for_key(content, str(key))
                    issues.append(
                        self._create_issue(
                            file_path=file_path,
                            line=line,
                            column=col,
                            issue_type=AnalysisIssueType.HARDCODED_SECRET,
                            severity=AnalysisIssueSeverity.CRITICAL,
                            message=f"Hardcoded secret in key '{key}'",
                            suggestion=("Use environment variables or a secrets manager."),
                            confidence=0.90,
                            rule_id="T001",
                            line_content=line_content,
                        )
                    )

                # Recurse into nested structures
                self._check_secrets(value, file_path, content, path, issues)

        elif isinstance(data, list):
            for item in data:
                self._check_secrets(item, file_path, content, path, issues)

        return issues

    def _check_insecure_urls(
        self,
        data: Any,
        file_path: str,
        content: str,
        issues: Optional[List[AnalysisIssue]] = None,
    ) -> List[AnalysisIssue]:
        """Check for insecure HTTP URLs (T003)."""
        if issues is None:
            issues = []

        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = str(key).lower()
                is_url_key = any(p in key_lower for p in self.INSECURE_URL_KEYS)

                if is_url_key and isinstance(value, str):
                    is_local = any(h in value for h in self.LOCAL_HOSTS)
                    if value.startswith("http://") and not is_local:
                        line, col, line_content = self._find_line_for_key(content, str(key))
                        issues.append(
                            self._create_issue(
                                file_path=file_path,
                                line=line,
                                column=col,
                                issue_type=AnalysisIssueType.INSECURE_COMMUNICATION,
                                severity=AnalysisIssueSeverity.MEDIUM,
                                message=f"Insecure HTTP URL in '{key}'",
                                suggestion="Use HTTPS instead of HTTP.",
                                confidence=0.85,
                                rule_id="T003",
                                line_content=line_content,
                            )
                        )

                # Recurse
                self._check_insecure_urls(value, file_path, content, issues)

        elif isinstance(data, list):
            for item in data:
                self._check_insecure_urls(item, file_path, content, issues)

        return issues

    def _check_dangerous_flags(
        self,
        data: Any,
        file_path: str,
        content: str,
        issues: Optional[List[AnalysisIssue]] = None,
    ) -> List[AnalysisIssue]:
        """Check for dangerous security flags (T002)."""
        if issues is None:
            issues = []

        if isinstance(data, dict):
            for key, value in data.items():
                for flag_name, dangerous_value in self.DANGEROUS_FLAGS:
                    if str(key).lower() == flag_name.lower() and value == dangerous_value:
                        line, col, line_content = self._find_line_for_key(content, str(key))
                        issues.append(
                            self._create_issue(
                                file_path=file_path,
                                line=line,
                                column=col,
                                issue_type=AnalysisIssueType.SECURITY_MISCONFIGURATION,
                                severity=AnalysisIssueSeverity.HIGH,
                                message=f"Dangerous flag '{key}' set to {value}",
                                suggestion=("Do not disable TLS/certificate verification."),
                                confidence=0.92,
                                rule_id="T002",
                                line_content=line_content,
                            )
                        )

                # Recurse
                self._check_dangerous_flags(value, file_path, content, issues)

        elif isinstance(data, list):
            for item in data:
                self._check_dangerous_flags(item, file_path, content, issues)

        return issues

    def _fallback_regex_analysis(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """Fallback regex-based analysis when tomli is not available."""
        issues: List[AnalysisIssue] = []
        NL = chr(10)

        # Simple regex for common secret patterns in TOML
        secret_pat = re.compile(
            r"(?mi)^\s*(password|api_?key|token|secret|credential)\s*=" r'\s*"(.*?)"\s*$'
        )

        for m in secret_pat.finditer(content):
            key, value = m.group(1), m.group(2)
            if value.startswith("$") or value.startswith("<"):
                continue

            line = content[: m.start()].count(NL) + 1
            col = m.start() - content.rfind(NL, 0, m.start())
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
                    confidence=0.65,
                    rule_id="T001",
                    line_content=line_content,
                )
            )

        return issues

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """
        Analyze TOML content for security issues.

        Args:
            file_path: Path to the file being analyzed
            content: The TOML content

        Returns:
            List of AnalysisIssue objects
        """
        issues: List[AnalysisIssue] = []

        # Check if tomli is available
        if tomli is None:
            return self._fallback_regex_analysis(file_path, content)

        # Try to parse TOML
        try:
            data = tomli.loads(content)
        except Exception:
            return self._fallback_regex_analysis(file_path, content)

        # Run all checks
        issues.extend(self._check_secrets(data, file_path, content))
        issues.extend(self._check_dangerous_flags(data, file_path, content))
        issues.extend(self._check_insecure_urls(data, file_path, content))

        return issues
