"""Parse analyzed Python source with ``ast.parse`` and no process side effects.

Every ``ast.parse`` call on analyzed code goes through :func:`safe_parse`.

Python's compiler reports some problems in the analyzed code as warnings
(``SyntaxWarning`` for an invalid escape sequence such as ``"\\d"`` on 3.12+,
``DeprecationWarning`` on earlier versions). Left alone, those warnings are
printed to stderr, and under ``PYTHONWARNINGS=error`` or ``-W error`` the
compiler turns them into ``SyntaxError``: the same file then parses in one
environment and fails in another, and the analyzers return no findings for
it. Here the warnings are recorded on the result instead, with the action
forced to ``always`` for the duration of the call, so the parse outcome does
not depend on the warning filters of the process.

Failures are classified:

* ``syntax``: ``SyntaxError`` (including ``IndentationError`` and ``TabError``).
* ``invalid_source``: ``ValueError``. Null bytes raise it on Python 3.10 to
  3.11.3; later versions raise ``SyntaxError`` for the same input.
* ``too_complex``: ``RecursionError`` or ``MemoryError`` (deeply nested code).

Any other exception propagates.

``warnings.catch_warnings`` swaps the process-wide filter list, so calls are
serialized with a module-level lock.
"""

from __future__ import annotations

import ast
import codecs
import re
import threading
import warnings
from dataclasses import dataclass
from typing import List, NoReturn, Optional, Tuple, Union

__all__ = [
    "INVALID_SOURCE",
    "SYNTAX",
    "TOO_COMPLEX",
    "ParseResult",
    "ParseWarning",
    "parse_or_none",
    "safe_parse",
]

SYNTAX = "syntax"
INVALID_SOURCE = "invalid_source"
TOO_COMPLEX = "too_complex"

_LOCK = threading.Lock()
_RECORDED_CATEGORIES = (SyntaxWarning, DeprecationWarning)
# PEP 263 encoding declaration; it is only honoured on the first two lines.
_CODING_RE = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")


@dataclass(frozen=True)
class ParseWarning:
    """A warning the compiler emitted for the analyzed code."""

    category: str
    message: str
    lineno: int


@dataclass(frozen=True)
class ParseResult:
    """Outcome of :func:`safe_parse`.

    ``tree`` is ``None`` exactly when ``error`` is set. ``exception`` is the
    original exception, kept so a caller can re-raise it.
    """

    tree: Optional[ast.Module]
    error: Optional[str] = None
    exception: Optional[BaseException] = None
    warnings: Tuple[ParseWarning, ...] = ()

    @property
    def error_type(self) -> str:
        return type(self.exception).__name__ if self.exception is not None else ""

    @property
    def error_message(self) -> str:
        return str(self.exception) if self.exception is not None else ""

    def reraise(self) -> NoReturn:
        """Raise the original exception (for callers that propagated it)."""
        if self.exception is None:
            raise RuntimeError("parse succeeded; there is no exception to re-raise")
        raise self.exception


def _declares_encoding(source: bytes) -> bool:
    if source.startswith(codecs.BOM_UTF8):
        return True
    return any(_CODING_RE.match(line) for line in source.splitlines()[:2])


def _select_source(source: Union[str, bytes], fallback_text: Optional[str]) -> Union[str, bytes]:
    """Bytes are parsed as bytes so ``ast.parse`` honours BOMs and encoding
    declarations. Bytes that are not UTF-8 and declare no encoding cannot be
    parsed that way; ``fallback_text`` (the source as already decoded by the
    caller) is parsed instead when it is given.
    """
    if isinstance(source, str) or fallback_text is None or _declares_encoding(source):
        return source
    try:
        source.decode("utf-8")
    except UnicodeDecodeError:
        return fallback_text
    return source


def _recorded(caught: List[warnings.WarningMessage]) -> Tuple[ParseWarning, ...]:
    return tuple(
        ParseWarning(
            category=w.category.__name__,
            message=str(w.message),
            lineno=int(w.lineno or 0),
        )
        for w in caught
        if issubclass(w.category, _RECORDED_CATEGORIES)
    )


def safe_parse(
    source: Union[str, bytes],
    filename: str = "<unknown>",
    *,
    fallback_text: Optional[str] = None,
) -> ParseResult:
    """Parse ``source`` like ``ast.parse(source, filename=filename)``.

    Never prints warnings and never changes ``warnings.filters``. Returns a
    :class:`ParseResult` instead of raising for source that is not valid
    Python.
    """
    to_parse = _select_source(source, fallback_text)
    with _LOCK, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        error: Optional[str] = None
        exception: Optional[BaseException] = None
        tree: Optional[ast.Module] = None
        try:
            tree = ast.parse(to_parse, filename=filename)
        except SyntaxError as exc:
            error, exception = SYNTAX, exc
        except ValueError as exc:
            error, exception = INVALID_SOURCE, exc
        except (RecursionError, MemoryError) as exc:
            error, exception = TOO_COMPLEX, exc
        recorded = _recorded(caught)
    return ParseResult(tree=tree, error=error, exception=exception, warnings=recorded)


def parse_or_none(
    source: Union[str, bytes],
    filename: str = "<unknown>",
    *,
    fallback_text: Optional[str] = None,
) -> Optional[ast.Module]:
    """Tree for ``source``, or ``None`` when it has a syntax error.

    For callers that used to catch only ``SyntaxError``: any other parse
    failure re-raises the original exception, as a direct ``ast.parse`` did.
    """
    result = safe_parse(source, filename, fallback_text=fallback_text)
    if result.tree is not None:
        return result.tree
    if result.error == SYNTAX:
        return None
    result.reraise()
