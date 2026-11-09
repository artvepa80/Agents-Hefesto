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

import bisect
import re
from typing import List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class _ScanFrame:
    """One command context: the outer line, or one ``$(...)`` / backtick body."""

    __slots__ = ("fid", "outside", "quote", "kind", "depth", "word", "cases", "command")

    def __init__(self, fid: int, kind: str) -> None:
        self.fid = fid
        self.outside: List[int] = []
        self.quote = ""
        self.kind = kind
        self.depth = 1 if kind == "d" else 0
        self.word: List[str] = []
        self.cases = 0
        self.command = True


def _is_command_substitution(text: str, i: int) -> bool:
    """True for ``$(`` but not arithmetic ``$((``."""
    return text.startswith("$(", i) and not text.startswith("$((", i)


def _scan_line(text: str) -> Tuple[List[List[int]], List[int]]:
    """Outside-quote indexes for every command context, and each index's context."""
    outer = _ScanFrame(0, "o")
    frames = [outer]
    stack = [0]
    context_at = [0] * len(text)
    index = 0
    while index < len(text):
        index = _scan_step(text, index, frames, stack, context_at)
    return [frame.outside for frame in frames], context_at


def _scan_step(
    text: str, i: int, frames: List[_ScanFrame], stack: List[int], context_at: List[int]
) -> int:
    frame = frames[stack[-1]]
    jumped = _escape_or_open(text, i, frame, frames, stack, context_at)
    if jumped is not None:
        return jumped
    return _scan_plain(text, i, frame, stack, context_at)


def _escape_or_open(
    text: str,
    i: int,
    frame: _ScanFrame,
    frames: List[_ScanFrame],
    stack: List[int],
    context_at: List[int],
) -> Optional[int]:
    escaped = _mark_escape(text, i, frame, context_at)
    if escaped is not None:
        return escaped
    return _mark_open(text, i, frame, frames, stack, context_at)


def _mark_escape(text: str, i: int, frame: _ScanFrame, context_at: List[int]) -> Optional[int]:
    if frame.quote == "'" or text[i] != "\\":
        return None
    _note_outside(frame.quote, i, frame.outside)
    context_at[i] = frame.fid
    if i + 1 < len(context_at):
        context_at[i + 1] = frame.fid
    return i + 2


def _mark_open(
    text: str,
    i: int,
    frame: _ScanFrame,
    frames: List[_ScanFrame],
    stack: List[int],
    context_at: List[int],
) -> Optional[int]:
    if not _starts_body(frame, text, i):
        return None
    _flush_word(frame)
    _note_outside(frame.quote, i, frame.outside)
    context_at[i] = frame.fid
    kind = "b"
    if text[i] == "$":
        kind = "d"
        if i + 1 < len(context_at):
            context_at[i + 1] = frame.fid
    opened = _ScanFrame(len(frames), kind)
    frames.append(opened)
    stack.append(opened.fid)
    return i + (2 if kind == "d" else 1)


def _starts_body(frame: _ScanFrame, text: str, i: int) -> bool:
    if frame.quote == "'":
        return False
    if text[i] == "`":
        return not (frame.kind == "b" and frame.quote == "")
    return _is_command_substitution(text, i)


def _close_frame(
    text: str, i: int, frame: _ScanFrame, stack: List[int], context_at: List[int]
) -> bool:
    if not _is_frame_closer(frame, text, i):
        return False
    stack.pop()
    context_at[i] = stack[-1]
    return True


def _is_frame_closer(frame: _ScanFrame, text: str, i: int) -> bool:
    if frame.kind == "b":
        return frame.quote == "" and text[i] == "`"
    if frame.kind != "d":
        return False
    if frame.quote or text[i] != ")" or frame.depth != 1:
        return False
    return frame.cases == 0


def _scan_plain(
    text: str, i: int, frame: _ScanFrame, stack: List[int], context_at: List[int]
) -> int:
    _break_word(text, i, frame)
    if _close_frame(text, i, frame, stack, context_at):
        return i + 1
    if _mark_case_paren(text, i, frame, context_at):
        return i + 1
    _scan_ordinary(text, i, frame, context_at)
    return i + 1


def _break_word(text: str, i: int, frame: _ScanFrame) -> None:
    if frame.quote:
        return
    if text[i] in " \t":
        _flush_word(frame)
    elif text[i] in ";&|()`\n":
        _flush_word(frame)
        frame.command = True


def _flush_word(frame: _ScanFrame) -> None:
    if not frame.word:
        return
    word = "".join(frame.word)
    frame.word.clear()
    if frame.command and word == "case":
        frame.cases += 1
    elif frame.command and word == "esac" and frame.cases:
        frame.cases -= 1
    frame.command = word in ShellAnalyzer._COMMAND_PREFIXES


def _mark_case_paren(text: str, i: int, frame: _ScanFrame, context_at: List[int]) -> bool:
    if not _is_case_paren(frame, text, i):
        return False
    context_at[i] = frame.fid
    frame.outside.append(i)
    frame.command = True
    return True


def _is_case_paren(frame: _ScanFrame, text: str, i: int) -> bool:
    if frame.kind != "d" or frame.cases == 0:
        return False
    return frame.quote == "" and text[i] == ")" and frame.depth == 1


def _scan_ordinary(text: str, i: int, frame: _ScanFrame, context_at: List[int]) -> None:
    context_at[i] = frame.fid
    if _toggle_quote(frame, text[i]):
        _flush_word(frame)
        return
    if frame.quote:
        return
    frame.outside.append(i)
    _note_word_char(frame, text[i])
    _track_bare_paren(frame, text[i])


def _note_word_char(frame: _ScanFrame, char: str) -> None:
    if char not in " \t;&|()`\n":
        frame.word.append(char)


def _toggle_quote(frame: _ScanFrame, char: str) -> bool:
    if char in "'\"" and frame.quote in ("", char):
        frame.quote = "" if frame.quote else char
        return True
    return False


def _track_bare_paren(frame: _ScanFrame, char: str) -> None:
    if frame.kind != "d":
        return
    if char == "(":
        frame.depth += 1
    elif char == ")":
        frame.depth -= 1


def _note_outside(quote: str, i: int, unquoted: List[int]) -> None:
    """Record an introducer that sits outside quotes (backslash, backtick, or ``$(``)."""
    if not quote:
        unquoted.append(i)


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
    # rm / cd as the command word: optional path (/bin/rm, ./rm) and an
    # unquoted backslash (\rm). Not a substring (--rm, perform, rmdir).
    # A path part may be a name or an unquoted $NAME / ${NAME} ($HOME/bin/rm).
    _PATH_PART = r"(?:\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*|[\w.+-]+)"
    _RM_OR_CD = re.compile(
        r"(?:^|(?<=[\s;&|(`)]))" r"\\?" r"(?:(?:" + _PATH_PART + r")?/)*" r"(rm|cd)(?=\s)"
    )
    # Words after which the next word is still a command, not an argument.
    _COMMAND_PREFIXES = frozenset(
        {
            "sudo",
            "then",
            "do",
            "else",
            "exec",
            "command",
            "nohup",
            "!",
            "{",
            "if",
            "elif",
            "while",
            "until",
            "time",
            "xargs",
        }
    )
    _VAR_NAME = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")

    @staticmethod
    def _scan_quotes(text: str) -> Tuple[List[List[int]], List[int]]:
        """Outside-quote indexes for every command context, and each index's context.

        One left-to-right pass. A ``$(...)`` or backtick body is its own context
        and starts with empty quotes, so quotes around the substitution do not
        quote the body. ``$((`` is arithmetic and does not open a context. The
        ``$`` or backtick that is itself outside quotes stays in the parent: an
        unquoted result still field-splits there.
        """
        return _scan_line(text)

    def _starts_unquoted_expansion(self, args: str, i: int) -> bool:
        return bool(
            args[i] == "`" or self._VAR_NAME.match(args, i) or _is_command_substitution(args, i)
        )

    @classmethod
    def _is_command(cls, prefix: str) -> bool:
        """True if a word right after ``prefix`` is in command position."""
        words = prefix.split()
        if not words:
            return True
        last = words[-1]
        # ")" closes a case pattern (`*)`, `start)`); the next word is a command.
        return last[-1] in ";&|()`" or last in cls._COMMAND_PREFIXES

    def _rm_or_cd_with_unquoted_var(self, line: str) -> Optional[str]:
        """``"rm"`` or ``"cd"`` if that command gets an unquoted expansion on this line.

        The quote scan runs once and keeps each substitution body separate.
        Each context's argument scan is tabulated once; a match does not
        walk the suffix again.
        """
        contexts, context_at = self._scan_quotes(line)
        outside_sets = [set(indexes) for indexes in contexts]
        reaches = [self._argument_reaches_expansion(line, indexes) for indexes in contexts]
        for match in self._RM_OR_CD.finditer(line):
            context = context_at[match.start()] if context_at else 0
            if self._rm_match_reports(
                line, match, contexts[context], outside_sets[context], reaches[context]
            ):
                return match.group(1)
        return None

    def _rm_match_reports(
        self,
        line: str,
        match: re.Match,
        outside: List[int],
        outside_set: set,
        reaches: List[bool],
    ) -> bool:
        if match.start() not in outside_set:
            return False
        if not self._command_boundary(line, match.start(), outside_set):
            return False
        return self._expansion_from(match.end(), outside, reaches)

    # POSIX operators and newline. ")" is handled apart from this string: only a
    # ")" that is outside quotes and substitutions ends a word. Space and tab are
    # blanks, not operators. Other str.isspace() characters are not separators.
    _BEFORE_SEPARATORS = ";&|(`\n"
    _BLANKS = " \t"

    @classmethod
    def _command_boundary(cls, line: str, start: int, outside: set) -> bool:
        """True when the command word at ``start`` is not an argument of another word."""
        if cls._char_introduces_command(line, start, outside):
            return True
        if line[start - 1] not in cls._BLANKS:
            return False
        return cls._blank_separated_word_introduces(line, start, outside)

    @staticmethod
    def _char_introduces_command(line: str, start: int, outside: set) -> bool:
        """True when the character immediately before ``start`` begins a command."""
        if start == 0:
            return True
        prev = line[start - 1]
        if prev in ShellAnalyzer._BEFORE_SEPARATORS:
            return True
        return prev == ")" and (start - 1) in outside

    @classmethod
    def _blank_separated_word_introduces(cls, line: str, start: int, outside: set) -> bool:
        """True when the word before the blanks at ``start`` introduces a command.

        The word is never empty. No blank-separated word means the command is
        at the start of the line once the blanks are skipped.
        """
        word = cls._previous_word(line, start)
        if not word:
            return True
        last = cls._last_word_index(line, start)
        if word[-1] == ")":
            return last in outside
        return word[-1] in cls._BEFORE_SEPARATORS or word in cls._COMMAND_PREFIXES

    @staticmethod
    def _last_word_index(line: str, start: int) -> int:
        last = start - 1
        while last > 0 and line[last] in ShellAnalyzer._BLANKS:
            last -= 1
        return last

    @staticmethod
    def _previous_word(line: str, start: int) -> Optional[str]:
        """Blank-separated word before ``start``, or None when there is none.

        Only space and tab are blanks. The result is never an empty string.
        """
        if start == 0 or line[start - 1] not in ShellAnalyzer._BLANKS:
            return None
        k = start - 1
        while k >= 0 and line[k] in ShellAnalyzer._BLANKS:
            k -= 1
        if k < 0:
            return None
        end = k + 1
        while k >= 0 and line[k] not in ShellAnalyzer._BLANKS:
            k -= 1
        return line[k + 1 : end]

    def _argument_reaches_expansion(self, line: str, outside: List[int]) -> List[bool]:
        """Whether each outside index sees an expansion before ``;``, ``&`` or ``|``.

        Computed once from the end of the context. A later match only looks up
        the first index at or after its arguments.
        """
        reaches = [False] * len(outside)
        later = False
        for pos in range(len(outside) - 1, -1, -1):
            index = outside[pos]
            if line[index] in ";&|":
                later = False
            elif self._index_is_expansion(line, index):
                later = True
            reaches[pos] = later
        return reaches

    def _expansion_from(self, start: int, outside: List[int], reaches: List[bool]) -> bool:
        pos = bisect.bisect_left(outside, start)
        if pos >= len(outside):
            return False
        return reaches[pos]

    def _index_is_expansion(self, line: str, i: int) -> bool:
        if line[i] == "`":
            return True
        return line[i] == "$" and self._starts_unquoted_expansion(line, i)

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
