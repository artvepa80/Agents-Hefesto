"""Where the string literals are in Python source.

The line-based SQL and command injection checks use this to tell code from
text that is data inside a string literal (issue #156).
"""

from __future__ import annotations

import bisect
import io
import re
import tokenize
from typing import List, Optional, Tuple

from hefesto.core.ast.generic_ast import GenericAST
from hefesto.core.safe_parse import safe_parse

# A literal's (start, end) as tokenize reports them: 1-based rows, 0-based columns.
Span = Tuple[Tuple[int, int], Tuple[int, int]]

# Python 3.12+ (PEP 701) tokenizes f-strings, and 3.14+ t-strings, as START,
# MIDDLE (literal text), expression tokens and END.
_MIDDLE_TYPES = {
    t for t in (getattr(tokenize, n, None) for n in ("FSTRING_MIDDLE", "TSTRING_MIDDLE")) if t
}


def _is_python(tree: Optional[GenericAST], file_path: str) -> bool:
    if tree is not None:
        return tree.language == "python"
    return file_path.endswith((".py", ".pyi"))


def _is_formatted(string_token: str) -> bool:
    """True for an f-/t-string STRING token (Python 3.11 and earlier)."""
    prefix = string_token[: len(string_token) - len(string_token.lstrip("rRbBuUfFtT"))]
    return any(c in prefix for c in "fFtT")


def _collect(tokens: List[tokenize.TokenInfo]) -> List[Span]:
    """Turn tokens into literal spans, sorted by start.

    Only literal text is data. On Python 3.12+ that is the MIDDLE parts of an
    f-string and the STRING tokens, including strings nested in a replacement
    field; the expressions in ``{...}`` stay code, so a sink there is still
    seen. On 3.11 and earlier an f-string is one STRING token that also holds
    its expressions, so it is not treated as data at all (same as before #156).
    """
    spans: List[Span] = []
    for tok in tokens:
        if tok.type in _MIDDLE_TYPES:
            spans.append((tok.start, tok.end))
        elif tok.type == tokenize.STRING and not _is_formatted(tok.string):
            spans.append((tok.start, tok.end))
    return spans


def python_string_spans(code: str) -> Optional[List[Span]]:
    """Return the string literal spans in *code*, or None if it does not parse.

    Code this Python cannot parse (for example PEP 701 f-strings on 3.11) may
    still tokenize, but into the wrong literals; it is checked line by line.
    """
    if safe_parse(code).tree is None:
        return None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (tokenize.TokenError, SyntaxError, ValueError):
        return None
    return _collect(tokens)


def string_spans_for(tree: Optional[GenericAST], file_path: str, code: str) -> Optional[List[Span]]:
    """Literal spans for a Python file; None for other languages or untokenizable code."""
    if not _is_python(tree, file_path):
        return None
    return python_string_spans(code)


def inside_string(spans: List[Span], row: int, col: int) -> bool:
    """True if (row, col) is inside a literal, after its first character.

    *spans* are sorted and do not overlap, so a binary search finds the only
    literal that can contain the position (O(log n) per call).
    """
    pos = (row, col)
    i = bisect.bisect_left(spans, pos, key=lambda span: span[0]) - 1
    return i >= 0 and spans[i][0] < pos < spans[i][1]


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
