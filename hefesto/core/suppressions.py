"""Line-level suppression comments for Python files.

Syntax, in a Python comment on the line the finding is reported on::

    risky_call()  # hefesto: ignore[TYPE] reason
    other()       # hefesto: ignore[TYPE_A, TYPE_B] reason

Rules:

* Only ``.py`` files are read. Other languages keep every finding.
* The reason is required. A directive without a reason, without ``[TYPE]``,
  or whose TYPE does not match a finding on that line suppresses nothing and
  produces a warning.
* Findings up to HIGH can be suppressed. CRITICAL findings are never
  suppressed; the directive produces a warning instead.
* Suppression runs after analysis: suppressed findings are moved from
  ``FileAnalysisResult.issues`` to ``FileAnalysisResult.suppressed_issues``,
  so they do not count in the summary or for ``--fail-on``.
"""

from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    FileAnalysisResult,
)

_MARKER_RE = re.compile(r"#\s*hefesto\s*:\s*ignore\b(?P<rest>.*)$", re.IGNORECASE)
_TYPES_RE = re.compile(r"^\[(?P<types>[^\]]*)\](?P<reason>.*)$")
_TYPE_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_REASON_STRIP = " \t-:—–"

NEVER_SUPPRESSED = AnalysisIssueSeverity.CRITICAL


@dataclass(frozen=True)
class Suppression:
    """One ``# hefesto: ignore`` directive."""

    line: int
    types: Tuple[str, ...]
    reason: str
    problem: Optional[str] = None
    file: str = ""

    def to_dict(self) -> Dict[str, object]:
        out: Dict[str, object] = {
            "file": self.file,
            "line": self.line,
            "types": list(self.types),
            "reason": self.reason,
        }
        if self.problem:
            out["problem"] = self.problem
        return out


def parse_directive(comment: str, line: int, file: str = "") -> Optional[Suppression]:
    """Parse one comment. ``None`` when it is not a hefesto directive."""
    match = _MARKER_RE.search(comment)
    if not match:
        return None
    rest = match.group("rest").strip()
    typed = _TYPES_RE.match(rest)
    if not typed:
        return Suppression(line, (), "", "missing [TYPE]; use # hefesto: ignore[TYPE] reason", file)
    types = tuple(t.strip().upper() for t in typed.group("types").split(",") if t.strip())
    reason = typed.group("reason").strip(_REASON_STRIP).strip()
    if not types or not all(_TYPE_NAME_RE.match(t) for t in types):
        return Suppression(line, types, reason, "invalid [TYPE] list", file)
    if not reason:
        return Suppression(line, types, "", "missing reason; a reason is required", file)
    return Suppression(line, types, reason, None, file)


def parse_suppressions(source: str, file: str = "") -> List[Suppression]:
    """Directives found in real Python comments (not in strings)."""
    found: List[Suppression] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return found
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        directive = parse_directive(tok.string, tok.start[0], file)
        if directive is not None:
            found.append(directive)
    return found


def _is_python(path: str) -> bool:
    return path.lower().endswith(".py")


def _read(path: str, cache: Optional[Dict[str, str]]) -> Optional[str]:
    if cache and path in cache and isinstance(cache[path], str):
        return cache[path]
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _warning(directive: Suppression, message: str) -> Dict[str, object]:
    return {"file": directive.file, "line": directive.line, "message": message}


def _apply_to_file(
    result: FileAnalysisResult, directives: List[Suppression]
) -> List[Dict[str, object]]:
    warnings: List[Dict[str, object]] = []
    by_line: Dict[int, List[Suppression]] = {}
    for directive in directives:
        if directive.problem:
            warnings.append(_warning(directive, f"suppression ignored: {directive.problem}"))
            continue
        by_line.setdefault(directive.line, []).append(directive)

    kept: List[AnalysisIssue] = []
    used: Dict[Tuple[int, str], bool] = {}
    for issue in result.issues:
        target = _matching(issue, by_line.get(issue.line, []))
        if target is None:
            kept.append(issue)
            continue
        used[(target.line, issue.issue_type.value)] = True
        if issue.severity == NEVER_SUPPRESSED:
            warnings.append(
                _warning(
                    target,
                    f"suppression ignored: {issue.issue_type.value} is CRITICAL "
                    "and CRITICAL findings cannot be suppressed",
                )
            )
            kept.append(issue)
            continue
        issue.suppression_reason = target.reason
        result.suppressed_issues.append(issue)

    for line, line_directives in by_line.items():
        for directive in line_directives:
            for name in directive.types:
                if not used.get((line, name)):
                    warnings.append(
                        _warning(
                            directive,
                            f"suppression ignored: no {name} finding on line {line}",
                        )
                    )
    result.issues = kept
    return warnings


def _matching(issue: AnalysisIssue, directives: Iterable[Suppression]) -> Optional[Suppression]:
    for directive in directives:
        if issue.issue_type.value in directive.types:
            return directive
    return None


def apply_suppressions(
    file_results: List[FileAnalysisResult],
    source_cache: Optional[Dict[str, str]] = None,
) -> List[Dict[str, object]]:
    """Move suppressed findings out of ``issues``. Returns the warnings."""
    warnings: List[Dict[str, object]] = []
    for result in file_results:
        if not _is_python(result.file_path):
            continue
        source = _read(result.file_path, source_cache)
        if source is None:
            continue
        directives = parse_suppressions(source, result.file_path)
        if directives:
            warnings.extend(_apply_to_file(result, directives))
    return warnings


def new_suppressions_in_diff(diff_text: str, root: Optional[Path] = None) -> List[Suppression]:
    """Directives on lines a unified diff adds to ``.py`` files.

    With ``root`` (the checked-out head), a line only counts when the file's
    tokens show a real comment there, so text inside strings is not listed.
    """
    from hefesto.pr_review.diff import parse_unified_diff

    added = _added_lines(diff_text)
    found: List[Suppression] = []
    for file_diff in parse_unified_diff(diff_text):
        path = file_diff.path
        if not path or file_diff.is_deleted_file or not _is_python(path):
            continue
        comment_lines = _comment_directive_lines(root, path)
        for line in sorted(file_diff.changed_lines):
            if comment_lines is not None and line not in comment_lines:
                continue
            text = added.get((path, line))
            if text is None or "#" not in text:
                continue
            directive = parse_directive(text[text.index("#") :], line, path)
            if directive is not None:
                found.append(directive)
    return found


def _comment_directive_lines(root: Optional[Path], path: str) -> Optional[set]:
    if root is None:
        return None
    source = _read(str(Path(root) / path), None)
    if source is None:
        return None
    return {item.line for item in parse_suppressions(source)}


def _added_lines(diff_text: str) -> Dict[Tuple[str, int], str]:
    """(new path, new line) -> text of each added line."""
    out: Dict[Tuple[str, int], str] = {}
    path: Optional[str] = None
    cursor = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            name = raw[4:].strip()
            path = name[2:] if name.startswith("b/") else name
            continue
        hunk = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if hunk:
            cursor = int(hunk.group(1))
            continue
        if path is None or raw.startswith("--- ") or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            out[(path, cursor)] = raw[1:]
            cursor += 1
        elif raw.startswith(" "):
            cursor += 1
    return out


def format_new_suppressions(found: List[Suppression]) -> List[str]:
    """Human-readable lines for logs: ``file:line [TYPES] reason``."""
    lines = []
    for item in found:
        text = f"{item.file}:{item.line} [{', '.join(item.types)}] {item.reason}".rstrip()
        if item.problem:
            text += f" (malformed: {item.problem})"
        lines.append(text)
    return lines


__all__ = [
    "Suppression",
    "apply_suppressions",
    "format_new_suppressions",
    "new_suppressions_in_diff",
    "parse_directive",
    "parse_suppressions",
]
