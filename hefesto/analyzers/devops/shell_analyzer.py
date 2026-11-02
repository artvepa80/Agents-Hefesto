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
from typing import List, Optional, Tuple

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
        (
            r"\brm\b(?=[^\n]*\s-[^\s]*r)(?=[^\n]*\s-[^\s]*f)[^\n]*\s+/(?:\s|$|;|&&|\|\|)",
            "rm -rf /",
            0.98,
        ),
        (r"\brm\b(?=[^\n]*\s-[^\s]*r)(?=[^\n]*\s-[^\s]*f)[^\n]*\s+/\*", "rm -rf /*", 0.95),
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
                    issues.append(
                        self._create_issue(
                            file_path,
                            line_num,
                            line,
                            AnalysisIssueType.SHELL_COMMAND_INJECTION,
                            AnalysisIssueSeverity.CRITICAL,
                            f"Remote code execution: {desc}",
                            "Never pipe untrusted remote content to shell.",
                            conf,
                            "rce-pipe",
                        )
                    )
                    break

            for pattern, desc, conf in self.EVAL_PATTERNS:
                if re.search(pattern, code_part):
                    issues.append(
                        self._create_issue(
                            file_path,
                            line_num,
                            line,
                            AnalysisIssueType.SHELL_COMMAND_INJECTION,
                            AnalysisIssueSeverity.HIGH,
                            f"Dangerous eval: {desc}",
                            "Avoid eval with dynamic content.",
                            conf,
                            "eval-dynamic",
                        )
                    )
                    break

            for pattern, desc, conf in self.DESTRUCTIVE_PATTERNS:
                if re.search(pattern, code_part, re.IGNORECASE):
                    severity = (
                        AnalysisIssueSeverity.CRITICAL
                        if conf >= 0.95
                        else AnalysisIssueSeverity.HIGH
                    )
                    issues.append(
                        self._create_issue(
                            file_path,
                            line_num,
                            line,
                            AnalysisIssueType.SHELL_UNSAFE_COMMAND,
                            severity,
                            f"Destructive command: {desc}",
                            "Add safety checks before destructive operations.",
                            conf,
                            "destructive",
                        )
                    )
                    break

            issues.extend(self._check_unquoted_vars(file_path, line_num, code_part))

        return issues

    def _check_safety_flags(
        self, file_path: str, code: str, lines: List[str]
    ) -> List[AnalysisIssue]:
        """Check for recommended safety flags."""
        issues: List[AnalysisIssue] = []

        has_shebang = lines and lines[0].startswith("#!")
        is_bash = has_shebang and (("bash" in lines[0]) or lines[0].rstrip().endswith("sh"))

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
            issues.append(
                self._create_issue(
                    file_path,
                    1,
                    lines[0] if lines else "",
                    AnalysisIssueType.SHELL_MISSING_SAFETY,
                    AnalysisIssueSeverity.MEDIUM,
                    "Missing safety flags (set -euo pipefail)",
                    "Add set -euo pipefail for safer scripts.",
                    0.70,
                    "missing-safety",
                )
            )

        return issues

    # Single-bracket test with an unquoted variable; [[ ]] does not split words.
    _UNQUOTED_TEST = re.compile(r"(?<!\[)\[\s+-[a-z]\s+\$[A-Za-z_]")
    # rm / cd as a word (not "perform", not "docker run --rm"); see _is_command.
    _RM_OR_CD = re.compile(r"(?:^|(?<=[\s;&|(`]))(rm|cd)\s")
    # Words after which the next word is still a command, not an argument.
    _COMMAND_PREFIXES = frozenset(
        {"sudo", "then", "do", "else", "exec", "command", "nohup", "!", "{"}
    )
    _VAR_NAME = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")

    @staticmethod
    def _scan_quotes(text: str) -> Tuple[List[int], bool]:
        """Indexes of the characters of ``text`` outside quotes, and whether it ends inside quotes.

        Backslash escapes are skipped, and so is a ``$( ... )`` body: its inner
        quotes are its own (``rm -rf "$(path "$v")"`` is quoted).
        """
        unquoted: List[int] = []
        quote = ""
        i = 0
        while i < len(text):
            char = text[i]
            if quote != "'" and (char == "\\" or text.startswith("$(", i)):
                i = ShellAnalyzer._skip_escape_or_substitution(text, i)
                continue
            if char in "'\"" and quote in ("", char):
                quote = "" if quote else char
            elif not quote:
                unquoted.append(i)
            i += 1
        return unquoted, bool(quote)

    def _has_unquoted_var(self, args: str) -> bool:
        """True if ``args`` (up to the next command separator) expands an unquoted $NAME."""
        for i in self._scan_quotes(args)[0]:
            if args[i] in ";&|":
                return False
            if args[i] == "$" and self._VAR_NAME.match(args, i):
                return True
        return False

    @staticmethod
    def _skip_escape_or_substitution(text: str, i: int) -> int:
        """Index after the ``\\x`` escape or the ``$( ... )`` that starts at ``i``."""
        if text[i] == "\\":
            return i + 2
        return ShellAnalyzer._skip_command_substitution(text, i + 2)

    @staticmethod
    def _skip_command_substitution(text: str, start: int) -> int:
        """Index just after the ``)`` closing a ``$(`` whose body starts at ``start``."""
        depth = 1
        i = start
        while i < len(text) and depth:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        return i

    @classmethod
    def _is_command(cls, prefix: str) -> bool:
        """True if a word right after ``prefix`` is in command position."""
        words = prefix.split()
        if not words:
            return True
        last = words[-1]
        return last[-1] in ";&|(`" or last in cls._COMMAND_PREFIXES

    def _rm_or_cd_with_unquoted_var(self, line: str) -> Optional[str]:
        """``"rm"`` or ``"cd"`` if that command gets an unquoted variable on this line."""
        for match in self._RM_OR_CD.finditer(line):
            prefix = line[: match.start()]
            # Skip text inside a string (echo "run: rm $X") and subcommands
            # (docker image rm $ID, git rm $FILE).
            if self._scan_quotes(prefix)[1] or not self._is_command(prefix):
                continue
            if self._has_unquoted_var(line[match.end() :]):
                return match.group(1)
        return None

    def _check_unquoted_vars(self, file_path: str, line_num: int, line: str) -> List[AnalysisIssue]:
        """Check for unquoted variables in dangerous contexts."""
        desc = None
        if self._UNQUOTED_TEST.search(line):
            desc = "test with unquoted var"
        else:
            command = self._rm_or_cd_with_unquoted_var(line)
            if command:
                desc = f"{command} with unquoted var"
        if desc is None:
            return []
        return [
            self._create_issue(
                file_path,
                line_num,
                line,
                AnalysisIssueType.SHELL_UNQUOTED_VARIABLE,
                AnalysisIssueSeverity.MEDIUM,
                f"Unquoted variable: {desc}",
                'Quote variables: "$var" instead of $var.',
                0.65,
                "unquoted-var",
            )
        ]

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
        self,
        file_path: str,
        line: int,
        line_content: str,
        issue_type: AnalysisIssueType,
        severity: AnalysisIssueSeverity,
        message: str,
        suggestion: str,
        confidence: float,
        rule_id: str,
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
