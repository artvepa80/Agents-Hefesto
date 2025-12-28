"""
Shell Script Analyzer for Hefesto.

Detects security issues and anti-patterns in Bash/Shell scripts:
- Remote code execution (curl|sh, wget|bash)
- Dangerous eval usage
- Destructive commands (rm -rf /)
- Missing safety flags (set -euo pipefail)
- Unquoted variables in dangerous contexts

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from typing import List, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class ShellAnalyzer:
    """Analyzes shell scripts for security issues and anti-patterns."""

    ENGINE = "internal:shell_analyzer"

    RCE_PATTERNS: List[Tuple[str, str, float]] = [
        (r"curl\s+[^|]*\|\s*(ba)?sh", "curl piped to shell (RCE risk)", 0.95),
        (r"wget\s+[^|]*\|\s*(ba)?sh", "wget piped to shell (RCE risk)", 0.95),
        (r"curl\s+[^|]*\|\s*sudo\s+(ba)?sh", "curl piped to sudo shell", 0.98),
        (r"wget\s+[^|]*\|\s*sudo\s+(ba)?sh", "wget piped to sudo shell", 0.98),
    ]

    EVAL_PATTERNS: List[Tuple[str, str, float]] = [
        (r'\beval\s+"\$\([^)]+\)"', "eval with command substitution", 0.85),
        (r'\beval\s+"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"', "eval with variable", 0.80),
        (r"\beval\s+\$[A-Za-z_]", "eval with unquoted variable", 0.85),
    ]

    DESTRUCTIVE_PATTERNS: List[Tuple[str, str, float]] = [
        (r"\brm\b(?=[^\n]*\s-[^\s]*r)(?=[^\n]*\s-[^\s]*f)[^\n]*\s+/(?:\s|$|;|&&|\|\|)",
         "rm -rf /", 0.98),
        (r"\brm\b(?=[^\n]*\s-[^\s]*r)(?=[^\n]*\s-[^\s]*f)[^\n]*\s+/\*",
         "rm -rf /*", 0.95),
        (r'rm\s+-rf\s+"\$\{?[^}]*:-/\}?"', "rm -rf with default /", 0.90),
        (r":\s*>\s*/etc/passwd", "truncating /etc/passwd", 0.98),
        (r"mkfs\s+/dev/sd[a-z]", "formatting disk", 0.85),
        (r"dd\s+.*of=/dev/sd[a-z]", "dd to disk", 0.80),
    ]

    def analyze(self, file_path: str, code: str) -> List[AnalysisIssue]:
        """Analyze shell script for security issues."""
        issues: List[AnalysisIssue] = []
        lines = code.split("\n")

        issues.extend(self._check_safety_flags(file_path, code, lines))

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            code_part = self._strip_inline_comment(line)

            for pattern, desc, conf in self.RCE_PATTERNS:
                if re.search(pattern, code_part, re.IGNORECASE):
                    issues.append(self._create_issue(
                        file_path, line_num, line,
                        AnalysisIssueType.SHELL_COMMAND_INJECTION,
                        AnalysisIssueSeverity.CRITICAL,
                        f"Remote code execution: {desc}",
                        "Never pipe untrusted remote content to shell.",
                        conf, "rce-pipe",
                    ))
                    break

            for pattern, desc, conf in self.EVAL_PATTERNS:
                if re.search(pattern, code_part):
                    issues.append(self._create_issue(
                        file_path, line_num, line,
                        AnalysisIssueType.SHELL_COMMAND_INJECTION,
                        AnalysisIssueSeverity.HIGH,
                        f"Dangerous eval: {desc}",
                        "Avoid eval with dynamic content.",
                        conf, "eval-dynamic",
                    ))
                    break

            for pattern, desc, conf in self.DESTRUCTIVE_PATTERNS:
                if re.search(pattern, code_part, re.IGNORECASE):
                    severity = (AnalysisIssueSeverity.CRITICAL
                               if conf >= 0.95
                               else AnalysisIssueSeverity.HIGH)
                    issues.append(self._create_issue(
                        file_path, line_num, line,
                        AnalysisIssueType.SHELL_UNSAFE_COMMAND,
                        severity,
                        f"Destructive command: {desc}",
                        "Add safety checks before destructive operations.",
                        conf, "destructive",
                    ))
                    break

            issues.extend(self._check_unquoted_vars(file_path, line_num, code_part))

        return issues

    def _check_safety_flags(
        self, file_path: str, code: str, lines: List[str]
    ) -> List[AnalysisIssue]:
        """Check for recommended safety flags."""
        issues: List[AnalysisIssue] = []

        has_shebang = lines and lines[0].startswith("#!")
        is_bash = has_shebang and (
            ("bash" in lines[0]) or lines[0].rstrip().endswith("sh")
        )

        if not is_bash:
            return issues

        has_safety = False
        for line in lines[:20]:
            if re.search(r"set\s+-[euo]+", line):
                has_safety = True
                break
            if re.search(r"set\s+-o\s+(errexit|nounset|pipefail)", line):
                has_safety = True
                break

        if not has_safety and len(lines) > 10:
            issues.append(self._create_issue(
                file_path, 1, lines[0] if lines else "",
                AnalysisIssueType.SHELL_MISSING_SAFETY,
                AnalysisIssueSeverity.MEDIUM,
                "Missing safety flags (set -euo pipefail)",
                "Add set -euo pipefail for safer scripts.",
                0.70, "missing-safety",
            ))

        return issues

    def _check_unquoted_vars(
        self, file_path: str, line_num: int, line: str
    ) -> List[AnalysisIssue]:
        """Check for unquoted variables in dangerous contexts."""
        issues: List[AnalysisIssue] = []

        dangerous = [
            (r"\[\s+-[a-z]\s+\$[A-Za-z_]", "test with unquoted var"),
            (r"rm\s+.*\$[A-Za-z_][A-Za-z0-9_]*[^\"'\s]", "rm with unquoted var"),
            (r"cd\s+\$[A-Za-z_][A-Za-z0-9_]*\s", "cd with unquoted var"),
        ]

        for pattern, desc in dangerous:
            if re.search(pattern, line):
                issues.append(self._create_issue(
                    file_path, line_num, line,
                    AnalysisIssueType.SHELL_UNQUOTED_VARIABLE,
                    AnalysisIssueSeverity.MEDIUM,
                    f"Unquoted variable: {desc}",
                    'Quote variables: "$var" instead of $var.',
                    0.65, "unquoted-var",
                ))
                break

        return issues

    def _strip_inline_comment(self, line: str) -> str:
        """Remove inline comments, preserving strings."""
        in_single = False
        in_double = False
        result = []

        for char in line:
            if char == "'" and not in_double:
                in_single = not in_single
            elif char == '"' and not in_single:
                in_double = not in_double
            elif char == "#" and not in_single and not in_double:
                break
            result.append(char)

        return "".join(result)

    def _create_issue(
        self, file_path: str, line: int, line_content: str,
        issue_type: AnalysisIssueType, severity: AnalysisIssueSeverity,
        message: str, suggestion: str, confidence: float, rule_id: str,
    ) -> AnalysisIssue:
        """Create an AnalysisIssue with enterprise fields."""
        return AnalysisIssue(
            file_path=file_path,
            line=line,
            column=0,
            issue_type=issue_type,
            severity=severity,
            message=message,
            suggestion=suggestion,
            engine=self.ENGINE,
            confidence=confidence,
            rule_id=rule_id,
            metadata={"line_content": line_content.strip()[:100]},
        )


__all__ = ["ShellAnalyzer"]