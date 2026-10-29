"""Where the string literals are in Python source.

The line-based SQL and command injection checks use this to tell code from
text that is data inside a string literal (issue #156).
"""

from __future__ import annotations

import io
import re
import tokenize
from typing import List, Optional, Tuple

from hefesto.core.ast.generic_ast import GenericAST

# A literal's (start, end) as tokenize reports them: 1-based rows, 0-based columns.
Span = Tuple[Tuple[int, int], Tuple[int, int]]

_FSTRING_START = getattr(tokenize, "FSTRING_START", None)
_FSTRING_END = getattr(tokenize, "FSTRING_END", None)


def _is_python(tree: Optional[GenericAST], file_path: str) -> bool:
    if tree is not None:
        return tree.language == "python"
    return file_path.endswith((".py", ".pyi"))


def _collect(tokens: List[tokenize.TokenInfo]) -> List[Span]:
    """Turn tokens into literal spans. On Python 3.12+ an f-string is several
    tokens (FSTRING_START ... FSTRING_END); it becomes one span."""
    spans: List[Span] = []
    open_fstrings: List[Tuple[int, int]] = []
    for tok in tokens:
        if _FSTRING_START is not None and tok.type == _FSTRING_START:
            open_fstrings.append(tok.start)
        elif _FSTRING_END is not None and tok.type == _FSTRING_END:
            start = open_fstrings.pop()
            spans.extend([] if open_fstrings else [(start, tok.end)])
        elif tok.type == tokenize.STRING and not open_fstrings:
            spans.append((tok.start, tok.end))
    return spans


def python_string_spans(code: str) -> Optional[List[Span]]:
    """Return the string literal spans in *code*, or None if it does not tokenize."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (tokenize.TokenError, SyntaxError):
        return None
    return _collect(tokens)


def string_spans_for(tree: Optional[GenericAST], file_path: str, code: str) -> Optional[List[Span]]:
    """Literal spans for a Python file; None for other languages or untokenizable code."""
    if not _is_python(tree, file_path):
        return None
    return python_string_spans(code)


def inside_string(spans: List[Span], row: int, col: int) -> bool:
    """True if (row, col) is inside a literal, after its first character."""
    return any(start < (row, col) < end for start, end in spans)


def first_match_outside_strings(
    pattern: "re.Pattern[str]", line: str, row: int, spans: Optional[List[Span]]
) -> Optional["re.Match[str]"]:
    """First match of *pattern* on *line* that does not start inside a literal."""
    for match in pattern.finditer(line):
        if not (spans and inside_string(spans, row, match.start())):
            return match
    return None


def _mask_line(line: str, lo: int, hi: int) -> str:
    hi = min(hi, len(line))
    blank = "".join(c if c in "\r\n" else " " for c in line[lo:hi])
    return line[:lo] + blank + line[hi:]


def mask_strings(lines: List[str], spans: List[Span]) -> List[str]:
    """Blank out literals so text inside them cannot look like a sink or a def."""
    masked = list(lines)
    for (srow, scol), (erow, ecol) in spans:
        for row in range(srow, erow + 1):
            lo = scol if row == srow else 0
            hi = ecol if row == erow else len(masked[row - 1])
            masked[row - 1] = _mask_line(masked[row - 1], lo, hi)
    return masked
