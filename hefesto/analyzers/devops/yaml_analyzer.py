"""
YAML Analyzer - Internal fallback for Hefesto v4.4.0.

Provides basic YAML analysis when yamllint is not available.
Detects common issues in GitHub Actions, Kubernetes manifests, etc.

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from typing import List, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

try:
    import yaml  # type: ignore

    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    YAML_AVAILABLE = False


class YamlAnalyzer:
    """
    Internal YAML analyzer for DevOps configurations.

    Provides fallback analysis when external providers (yamllint)
    are not available. Focuses on high-value, low-false-positive rules.
    """

    SECRET_PATTERNS_CRITICAL: List[Tuple[str, str]] = [
        (r"\b(AKIA|ASIA|AIDA)[0-9A-Z]{16}\b", "AWS Access Key ID"),
        (r"\bghp_[a-zA-Z0-9]{36}\b", "GitHub Personal Access Token"),
        (r"\bsk-[a-zA-Z0-9]{48}\b", "OpenAI API Key"),
    ]

    SECRET_PATTERNS_HIGH: List[Tuple[str, str]] = [
        (r"password\s*[:=]\s*['\"][^'\"]{8,}['\"]", "password"),
        (r"api[_-]?key\s*[:=]\s*['\"][^'\"]{16,}['\"]", "api_key"),
        (r"secret[_-]?key\s*[:=]\s*['\"][^'\"]{16,}['\"]", "secret_key"),
        (r"aws_secret_access_key\s*[:=]\s*['\"][^'\"]+['\"]", "aws_secret"),
    ]

    SECRET_PATTERNS_MEDIUM: List[Tuple[str, str]] = [
        (r"token\s*[:=]\s*['\"][^'\"]{10,}['\"]", "token"),
        (r"secret\s*[:=]\s*['\"][^'\"]{8,}['\"]", "secret"),
    ]

    GITHUB_ACTIONS_RISKS = [
        (r"pull_request_target:", "pull_request_target event can expose secrets"),
        (r"permissions:\s*write-all", "Overly permissive workflow permissions"),
    ]

    K8S_RISKS = [
        (r"privileged:\s*true", "Container running in privileged mode"),
        (r"hostNetwork:\s*true", "Pod using host network"),
        (r"hostPID:\s*true", "Pod sharing host PID namespace"),
        (r"allowPrivilegeEscalation:\s*true", "Container allows privilege escalation"),
    ]

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """Analyze YAML file for common issues."""
        issues = []
        lines = content.split("\n")

        issues.extend(self._check_syntax(file_path, content, lines))
        issues.extend(self._check_secrets(file_path, lines))
        issues.extend(self._check_indentation(file_path, lines))

        if self._is_github_actions(file_path, content):
            issues.extend(self._check_github_actions(file_path, lines))

        if self._is_kubernetes(content):
            issues.extend(self._check_kubernetes(file_path, lines))

        return issues

    def _strip_inline_comment(self, line: str) -> str:
        """Strip inline comments, handling quoted strings conservatively."""
        in_single = False
        in_double = False
        for i, char in enumerate(line):
            if char == "'" and not in_double:
                in_single = not in_single
            elif char == '"' and not in_single:
                in_double = not in_double
            elif char == "#" and not in_single and not in_double:
                return line[:i]
        return line

    def _check_syntax(self, file_path: str, content: str, lines: List[str]) -> List[AnalysisIssue]:
        """Check for basic YAML syntax issues."""
        issues = []

        if YAML_AVAILABLE and yaml is not None:
            try:
                yaml.safe_load(content)
            except Exception as e:
                line_num = 1
                if hasattr(e, "problem_mark") and e.problem_mark:
                    line_num = e.problem_mark.line + 1
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=line_num,
                        column=0,
                        issue_type=AnalysisIssueType.YAML_SYNTAX_ERROR,
                        severity=AnalysisIssueSeverity.HIGH,
                        message=f"YAML syntax error: {str(e)[:100]}",
                        suggestion="Fix the YAML syntax to ensure valid parsing",
                        engine="internal:yaml_analyzer",
                    )
                )

        for i, line in enumerate(lines, 1):
            if "\t" in line and not line.strip().startswith("#"):
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=i,
                        column=line.index("\t"),
                        issue_type=AnalysisIssueType.YAML_INDENTATION,
                        severity=AnalysisIssueSeverity.MEDIUM,
                        message="Tab character found (YAML requires spaces)",
                        suggestion="Replace tabs with spaces",
                        engine="internal:yaml_analyzer",
                    )
                )

        return issues

    def _check_secrets(self, file_path: str, lines: List[str]) -> List[AnalysisIssue]:
        """Check for potential hardcoded secrets with tiered severity."""
        issues = []

        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue

            check_line = self._strip_inline_comment(line)

            if self._is_template_variable(check_line):
                continue

            for pattern, secret_type in self.SECRET_PATTERNS_CRITICAL:
                if re.search(pattern, check_line):
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=i,
                            column=0,
                            issue_type=AnalysisIssueType.YAML_SECRET_EXPOSURE,
                            severity=AnalysisIssueSeverity.CRITICAL,
                            message=f"Hardcoded {secret_type} detected",
                            suggestion="Remove immediately. Use secrets manager.",
                            engine="internal:yaml_analyzer",
                            source="string_literal",
                            confidence=0.95,
                        )
                    )
                    break

            for pattern, secret_type in self.SECRET_PATTERNS_HIGH:
                if re.search(pattern, check_line, re.IGNORECASE):
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=i,
                            column=0,
                            issue_type=AnalysisIssueType.YAML_SECRET_EXPOSURE,
                            severity=AnalysisIssueSeverity.HIGH,
                            message=f"Potential hardcoded {secret_type}",
                            suggestion="Use environment variables or secrets manager.",
                            engine="internal:yaml_analyzer",
                            source="string_literal",
                            confidence=0.75,
                        )
                    )
                    break

            for pattern, secret_type in self.SECRET_PATTERNS_MEDIUM:
                if re.search(pattern, check_line, re.IGNORECASE):
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=i,
                            column=0,
                            issue_type=AnalysisIssueType.YAML_SECRET_EXPOSURE,
                            severity=AnalysisIssueSeverity.MEDIUM,
                            message=f"Possible hardcoded {secret_type}",
                            suggestion="Consider using secrets manager.",
                            engine="internal:yaml_analyzer",
                            source="string_literal",
                            confidence=0.5,
                        )
                    )
                    break

        return issues

    def _check_indentation(self, file_path: str, lines: List[str]) -> List[AnalysisIssue]:
        """Check for inconsistent indentation."""
        issues = []
        indent_sizes = set()

        for line in lines:
            if not line.strip() or line.strip().startswith("#"):
                continue
            leading = len(line) - len(line.lstrip())
            if leading > 0:
                indent_sizes.add(leading)

        if len(indent_sizes) > 3:
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=1,
                    column=0,
                    issue_type=AnalysisIssueType.YAML_INDENTATION,
                    severity=AnalysisIssueSeverity.LOW,
                    message=f"Inconsistent indentation ({len(indent_sizes)} levels)",
                    suggestion="Use consistent 2-space indentation",
                    engine="internal:yaml_analyzer",
                )
            )

        return issues

    def _check_github_actions(self, file_path: str, lines: List[str]) -> List[AnalysisIssue]:
        """Check GitHub Actions specific issues."""
        issues = []
        content = "\n".join(lines)

        for pattern, description in self.GITHUB_ACTIONS_RISKS:
            for match in re.finditer(pattern, content, re.MULTILINE):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=line_num,
                        column=0,
                        issue_type=AnalysisIssueType.YAML_UNSAFE_COMMAND,
                        severity=AnalysisIssueSeverity.HIGH,
                        message=f"GitHub Actions risk: {description}",
                        suggestion="Review security best practices",
                        engine="internal:yaml_analyzer",
                        confidence=0.85,
                        metadata={"context": "github_actions"},
                    )
                )

        return issues

    def _check_kubernetes(self, file_path: str, lines: List[str]) -> List[AnalysisIssue]:
        """Check Kubernetes manifest specific issues."""
        issues = []
        content = "\n".join(lines)

        for pattern, description in self.K8S_RISKS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[: match.start()].count("\n") + 1
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=line_num,
                        column=0,
                        issue_type=AnalysisIssueType.YAML_UNSAFE_COMMAND,
                        severity=AnalysisIssueSeverity.HIGH,
                        message=f"Kubernetes risk: {description}",
                        suggestion="Apply Pod Security Standards",
                        engine="internal:yaml_analyzer",
                        confidence=0.9,
                        metadata={"context": "kubernetes"},
                    )
                )

        return issues

    def _is_github_actions(self, file_path: str, content: str) -> bool:
        """Detect if file is a GitHub Actions workflow."""
        if ".github/workflows" in file_path:
            return True
        return "on:" in content and "jobs:" in content

    def _is_kubernetes(self, content: str) -> bool:
        """Detect if file is a Kubernetes manifest."""
        return "apiVersion:" in content and "kind:" in content

    def _is_template_variable(self, line: str) -> bool:
        """Check if the line uses template variables."""
        patterns = [r"\$\{\{", r"\$\{[A-Z_]+\}", r"\{\{", r"\$[A-Z_]+"]
        return any(re.search(p, line) for p in patterns)


__all__ = ["YamlAnalyzer"]
