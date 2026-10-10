"""COPY ... REPLACING expansion for the COBOL analyzer.

A program is analyzed with the text of the copybooks it COPYs (and the DB2
members it ``EXEC SQL INCLUDE``s) put in place of the statement, the way the
compiler sees it, so the data and procedure rules see copybook definitions in
the context of the including program.

Supported (IBM Enterprise COBOL / COBOL 2002 rules):

* ``COPY name [OF|IN library] [SUPPRESS] [REPLACING ...] .`` and
  ``EXEC SQL INCLUDE name END-EXEC`` (SQLCA/SQLDA and vendor members are not
  expanded).
* REPLACING operands: ``==pseudo-text==`` (also empty ``====`` as the
  replacement), literals, COBOL words and identifiers (``A OF B``, ``T(1)``),
  and ``LEADING`` / ``TRAILING`` partial words. Matching is done on text words:
  case-insensitive for words, exact for literals; commas, semicolons and
  spaces are separators; the colon and parentheses are separate text words, so
  the ``==:TAG:==`` idiom replaces ``:TAG:`` inside ``:TAG:-NAME``. Pairs are
  tried in order at each text word, the first match wins, and replaced text is
  not scanned again.
* Nested COPY: the REPLACING of an outer COPY also applies to the text of the
  copybooks nested under it (IBM allows one REPLACING per nested chain; if
  several are present they are applied innermost first).
* Guards: a copybook already active in the chain is not expanded again
  (recursion), nesting stops at ``MAX_DEPTH``, and a program stops expanding
  once ``MAX_EXPANDED_LINES`` copybook lines were added. A COPY that is not
  expanded is left in the text, as before.

Not supported: the ``REPLACE`` statement, compiler-directing statements other
than COPY, and library names (``OF lib``) are read but not used to pick a file.

Every expanded line keeps an :class:`Origin` (file, physical line, COPY
chain) so findings are reported at the program's COPY line with the copybook
line in the metadata.
"""

import re
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

MAX_DEPTH = 16
MAX_EXPANDED_LINES = 250_000

LogicalLine = Tuple[int, str, bool]  # (line number, text, starts in Area A)


@dataclass(frozen=True)
class Origin:
    """Where an expanded line comes from."""

    path: str  # file holding the line
    line: int  # physical line in that file
    # COPY statements that brought it in, outermost first: (file, line)
    via: Tuple[Tuple[str, int], ...] = ()
    replaced: bool = False  # REPLACING changed something on this line
    copybook: str = ""  # copybook name (empty for the program's own lines)


# (origin, text, starts in Area A). The program's own lines keep their line
# number as origin (an int), so a program without COPY costs nothing extra.
ExpLine = Tuple[Union[int, Origin], str, bool]

# ---------------------------------------------------------------- tokens

_TOKEN = re.compile(
    r"""
    (?P<ws>[\s,;]+(?=\s|$)|\s+)                     # separators (comma/semicolon + space)
   |(?P<lit>(?:N|X|NX|G|Z|B)?(?:'(?:[^']|'')*'?|"(?:[^"]|"")*"?))
   |(?P<pseudo>==)
   |(?P<word>[A-Za-z0-9_-]+(?:\.[0-9]+)?)
   |(?P<other>\S)
    """,
    re.X | re.I,
)


@dataclass
class _Tok:
    kind: str  # ws, lit, pseudo, word, other, nl
    text: str
    line: int  # index of the expanded line it belongs to
    pre: str = ""  # whitespace before it (significant tokens of a statement)


def _tokenize(text: str, line: int) -> List[_Tok]:
    return [_Tok(m.lastgroup or "other", m.group(0), line) for m in _TOKEN.finditer(text)]


def significant(tokens: Sequence[_Tok]) -> List[_Tok]:
    """Tokens without whitespace, each remembering the whitespace before it."""
    out: List[_Tok] = []
    pre = ""
    for tok in tokens:
        if tok.kind == "ws":
            pre += tok.text
            continue
        tok.pre = " " if pre else ""
        out.append(tok)
        pre = ""
    return out


def _key(tok: _Tok) -> str:
    return tok.text.upper() if tok.kind == "word" else tok.text


def _keys(text: str) -> List[str]:
    return [_key(t) for t in _tokenize(text, 0) if t.kind != "ws"]


# ---------------------------------------------------------------- REPLACING


@dataclass(frozen=True)
class Replacement:
    pattern: Tuple[str, ...]  # text-word keys (one key for LEADING/TRAILING)
    by: str
    mode: str = "text"  # text, leading, trailing


def parse_replacing(tokens: Sequence[_Tok]) -> List[Replacement]:
    """REPLACING pairs from the significant tokens after the REPLACING keyword."""
    reps: List[Replacement] = []
    pos = 0
    while pos < len(tokens):
        mode = "text"
        word = tokens[pos].text.upper() if tokens[pos].kind == "word" else ""
        if word in ("LEADING", "TRAILING"):
            mode, pos = word.lower(), pos + 1
        first, pos = _operand(tokens, pos)
        if first is None or pos >= len(tokens) or tokens[pos].text.upper() != "BY":
            break
        second, pos = _operand(tokens, pos + 1)
        if second is None:
            break
        pattern = tuple(_keys(first))
        if not pattern:
            continue  # empty pseudo-text-1 is not valid
        if mode != "text":
            if len(pattern) != 1:
                continue  # partial word must be one text word
            pattern = (pattern[0].upper(),)
        reps.append(Replacement(pattern, " ".join(second.split()), mode))
    return reps


def _operand(tokens: Sequence[_Tok], pos: int) -> Tuple[Optional[str], int]:
    """One REPLACING operand: pseudo-text, literal, word or identifier."""
    if pos >= len(tokens):
        return None, pos
    tok = tokens[pos]
    if tok.kind == "pseudo":
        return _pseudo_text(tokens, pos)
    if tok.kind == "lit":
        return tok.text, pos + 1
    if tok.kind != "word" or tok.text.upper() == "BY":
        return None, pos
    return _identifier(tokens, pos)


def _pseudo_text(tokens: Sequence[_Tok], pos: int) -> Tuple[Optional[str], int]:
    """Text between ``==`` delimiters (``pos`` is the opening one)."""
    end = pos + 1
    while end < len(tokens) and tokens[end].kind != "pseudo":
        end += 1
    if end >= len(tokens):
        return None, end
    inner = tokens[pos + 1 : end]
    return "".join((t.pre if i else "") + t.text for i, t in enumerate(inner)), end + 1


def _identifier(tokens: Sequence[_Tok], pos: int) -> Tuple[str, int]:
    """A word with optional ``OF/IN`` qualifiers and parenthesized subscripts."""
    parts = [tokens[pos].text]
    pos += 1
    while pos < len(tokens):
        if _is_qualifier(tokens, pos):
            parts += [tokens[pos].text, tokens[pos + 1].text]
            pos += 2
        elif tokens[pos].text == "(":
            end = _closing_paren(tokens, pos)
            parts[-1] += "".join(t.text for t in tokens[pos:end])
            pos = end
        else:
            break
    return " ".join(parts), pos


def _is_qualifier(tokens: Sequence[_Tok], pos: int) -> bool:
    return (
        tokens[pos].kind == "word"
        and tokens[pos].text.upper() in ("OF", "IN")
        and pos + 1 < len(tokens)
        and tokens[pos + 1].kind == "word"
    )


def _closing_paren(tokens: Sequence[_Tok], pos: int) -> int:
    """Index just after the parenthesis that closes the one at ``pos``."""
    depth = 0
    while pos < len(tokens):
        depth += {"(": 1, ")": -1}.get(tokens[pos].text, 0)
        pos += 1
        if depth == 0:
            break
    return pos


def apply_replacing(lines: List[ExpLine], reps: Sequence[Replacement]) -> List[ExpLine]:
    """Apply REPLACING pairs to expanded lines (a match may span lines)."""
    if not reps:
        return lines
    tokens: List[_Tok] = []
    for idx, (_, text, _) in enumerate(lines):
        tokens.extend(_tokenize(text, idx))
        tokens.append(_Tok("nl", "\n", idx))
    sig = [i for i, t in enumerate(tokens) if t.kind not in ("ws", "nl")]
    keys = [_key(tokens[i]) for i in sig]
    texts: List[List[str]] = [[] for _ in lines]
    changed: Set[int] = set()
    emitted = 0  # tokens before this index were already copied to ``texts``
    s = 0
    while s < len(sig):
        hit = _match(reps, keys, s, tokens[sig[s]])
        if hit is None:
            s += 1
            continue
        rep, width = hit
        start = sig[s]
        _copy_tokens(tokens, emitted, start, texts)
        line = tokens[start].line
        texts[line].append(_replaced(rep, tokens[start].text))
        changed.add(line)
        emitted = sig[s + width - 1] + 1  # drop the matched tokens (keep line breaks)
        s += width
    _copy_tokens(tokens, emitted, len(tokens), texts)
    return _rebuild(lines, texts, changed)


def _copy_tokens(tokens: List[_Tok], start: int, stop: int, texts: List[List[str]]) -> None:
    for tok in tokens[start:stop]:
        if tok.kind != "nl":
            texts[tok.line].append(tok.text)


def _replaced(rep: Replacement, word: str) -> str:
    """Replacement text for a match starting at ``word``."""
    if rep.mode == "text":
        return rep.by
    cut = len(rep.pattern[0])
    return rep.by + word[cut:] if rep.mode == "leading" else word[:-cut] + rep.by


def _rebuild(lines: List[ExpLine], texts: List[List[str]], changed: Set[int]) -> List[ExpLine]:
    out: List[ExpLine] = []
    for idx, (origin, _, area_a) in enumerate(lines):
        text = "".join(texts[idx]).strip()
        if idx in changed and isinstance(origin, Origin):
            origin = Origin(origin.path, origin.line, origin.via, True, origin.copybook)
        if text:
            out.append((origin, text, area_a))
    return out


def _match(reps: Sequence[Replacement], keys: List[str], s: int, tok: _Tok):
    for rep in reps:
        if rep.mode == "text":
            width = len(rep.pattern)
            if tuple(keys[s : s + width]) == rep.pattern:
                return rep, width
        elif tok.kind == "word":
            word = keys[s]
            part = rep.pattern[0]
            if len(word) >= len(part) and (
                word.startswith(part) if rep.mode == "leading" else word.endswith(part)
            ):
                return rep, 1
    return None


# ---------------------------------------------------------------- statements

_COPY_START = re.compile(r"(?<![\w-])COPY(?=\s|$)", re.I)
_EXEC_SQL_START = re.compile(r"(?<![\w-])EXEC\s+SQL(?=\s|$)", re.I)
_STATEMENT_MAX_LINES = 50


@dataclass
class CopyStatement:
    name: str
    first: int  # index of the first line
    start: int  # offset of COPY / EXEC on the first line
    last: int  # index of the line holding the terminator
    end: int  # offset just after the terminator on that line
    replacing: List[Replacement] = field(default_factory=list)


def _mask_literals(text: str) -> str:
    if "'" not in text and '"' not in text:
        return text
    return "".join(
        t.text if t.kind != "lit" else t.text[0] + " " * (len(t.text) - 1)
        for t in _tokenize(text, 0)
    )


def find_statement(lines: Sequence[ExpLine], idx: int) -> Optional[CopyStatement]:
    """First COPY or EXEC SQL INCLUDE starting on line ``idx`` (None if none)."""
    text = lines[idx][1]
    upper = text.upper()
    if "COPY" not in upper and "EXEC" not in upper and "INCLUDE" not in upper:
        return None
    masked = _mask_literals(text)
    copy = _COPY_START.search(masked)
    sql = _EXEC_SQL_START.search(masked)
    if copy and (not sql or copy.start() < sql.start()):
        return _parse_copy(lines, idx, copy.start())
    if sql:
        return _parse_include(lines, idx, sql.start())
    return None


def _statement_tokens(lines: Sequence[ExpLine], idx: int, start: int):
    """(line index, token, end offset) from ``start`` on line ``idx`` onward."""
    pre = ""
    for n in range(idx, min(len(lines), idx + _STATEMENT_MAX_LINES)):
        text = lines[n][1]
        base = start if n == idx else 0
        pre = " " if n > idx else ""
        for m in _TOKEN.finditer(text, base):
            kind = m.lastgroup or "other"
            if kind == "ws":
                pre = " "
                continue
            yield n, _Tok(kind, m.group(0), n, pre), m.end()
            pre = ""


def _parse_copy(lines: Sequence[ExpLine], idx: int, start: int) -> Optional[CopyStatement]:
    toks: List[Tuple[int, _Tok, int]] = []
    in_pseudo = False
    for item in _statement_tokens(lines, idx, start):
        toks.append(item)
        tok = item[1]
        if tok.kind == "pseudo":
            in_pseudo = not in_pseudo
        elif tok.text == "." and not in_pseudo:
            break
    else:
        return None  # no terminating period
    if len(toks) < 3 or toks[1][1].kind not in ("word", "lit"):
        return None
    name = toks[1][1].text.strip("'\"").upper()
    if not name:
        return None
    body = [t for _, t, _ in toks[2:-1]]
    reps: List[Replacement] = []
    for pos, tok in enumerate(body):
        if tok.kind == "word" and tok.text.upper() == "REPLACING":
            reps = parse_replacing(body[pos + 1 :])
            break
    last, _, end = toks[-1]
    return CopyStatement(name, idx, start, last, end, reps)


def _parse_include(lines: Sequence[ExpLine], idx: int, start: int) -> Optional[CopyStatement]:
    words: List[Tuple[int, _Tok, int]] = []
    for item in _statement_tokens(lines, idx, start):
        words.append(item)
        if item[1].text.upper() == "END-EXEC" or len(words) > 8:
            break
    texts = [t.text.upper() for _, t, _ in words]
    if len(texts) < 5 or texts[2] != "INCLUDE" or texts[-1] != "END-EXEC" or len(texts) != 5:
        return None
    name = words[3][1].text.strip("'\"").upper()
    last, _, end = words[-1]
    return CopyStatement(name, idx, start, last, end)


# ---------------------------------------------------------------- expander


Resolver = Callable[[str, str], Optional[str]]  # (NAME, including file) -> path
Loader = Callable[[str], Optional[List[LogicalLine]]]  # path -> logical lines


class CopyExpander:
    """Expands COPY / EXEC SQL INCLUDE in a program's logical lines."""

    def __init__(
        self,
        resolve: Resolver,
        load: Loader,
        skip: Callable[[str], bool] = lambda name: False,
        max_depth: int = MAX_DEPTH,
        max_lines: int = MAX_EXPANDED_LINES,
    ) -> None:
        self._resolve = resolve
        self._load = load
        self._skip = skip
        self.max_depth = max_depth
        self.max_lines = max_lines
        self._path = ""
        # what the last expand() call did, for notices and tests
        self.expanded: List[str] = []
        self.not_expanded: Dict[str, str] = {}  # NAME -> reason

    def expand(self, path: str, lines: List[LogicalLine]) -> Optional[List[ExpLine]]:
        """Expanded lines (origin, text, Area A), or None when nothing was expanded.

        ``lines`` are the program's (line number, text, Area A) logical lines;
        its own lines keep their number as origin.
        """
        self.expanded, self.not_expanded, self._path = [], {}, path
        out = self._expand(list(lines), (), 0, [self.max_lines])
        return out if self.expanded else None

    def _expand(
        self, work: List[ExpLine], active: Tuple[str, ...], depth: int, budget: List[int]
    ) -> List[ExpLine]:
        candidates = sorted(_candidate_lines(work))
        if not candidates:
            return work
        out: List[ExpLine] = []
        i, again = 0, -1  # again: a line whose rest must be looked at again
        while i < len(work):
            if i != again:
                pos = bisect_left(candidates, i)
                nxt = candidates[pos] if pos < len(candidates) else len(work)
                if nxt > i:
                    out.extend(work[i:nxt])
                    i = nxt
                    continue
            stmt = find_statement(work, i)
            body = self._copybook_lines(stmt, work[i][0], active, depth, budget) if stmt else None
            if stmt is None or body is None:
                out.append(work[i])
                i += 1
                continue
            origin, text, area_a = work[i]
            before = text[: stmt.start].rstrip()
            if before:
                out.append((origin, before, area_a))
            out.extend(body)
            after_origin, after_text, _ = work[stmt.last]
            after = after_text[stmt.end :].strip()
            if after:
                work[stmt.last] = (after_origin, after, False)
                i = again = stmt.last  # the rest of the line may hold another COPY
            else:
                i = stmt.last + 1
        return out

    def _origin(self, origin: Union[int, Origin]) -> Origin:
        return Origin(self._path, origin) if isinstance(origin, int) else origin

    def _copybook_lines(
        self,
        stmt: CopyStatement,
        where: Union[int, Origin],
        active: Tuple[str, ...],
        depth: int,
        budget: List[int],
    ) -> Optional[List[ExpLine]]:
        origin = self._origin(where)
        name = stmt.name
        reason = ""
        target = None
        if self._skip(name):
            reason = "system"
        elif name in active:
            reason = "recursive"
        elif depth >= self.max_depth:
            reason = "too deep"
        elif budget[0] <= 0:
            reason = "size limit"
        else:
            target = self._resolve(name, origin.path)
            reason = "" if target else "not found"
        lines = self._load(target) if target else None
        if lines is None:
            self.not_expanded.setdefault(name, reason or "unreadable")
            return None
        budget[0] -= len(lines)
        via = origin.via + ((origin.path, origin.line),)
        body: List[ExpLine] = [
            (Origin(target or "", num, via, False, name), text, area) for num, text, area in lines
        ]
        body = self._expand(body, active + (name,), depth + 1, budget)
        self.expanded.append(name)
        return apply_replacing(body, stmt.replacing)


def _candidate_lines(lines: Sequence[ExpLine]) -> Set[int]:
    """Indexes of lines where a COPY or EXEC SQL INCLUDE may start.

    A substring search over the joined text instead of a test per line. An
    INCLUDE line also marks the two lines before it (``EXEC SQL`` is often
    on its own line).
    """
    blob = "\n".join(text for _, text, _ in lines).upper()
    hits: List[Tuple[int, bool]] = []
    for needle in ("COPY", "INCLUDE"):
        pos = blob.find(needle)
        while pos >= 0:
            hits.append((pos, needle == "INCLUDE"))
            pos = blob.find(needle, pos + 1)
    out: Set[int] = set()
    line, last = 0, 0
    for pos, include in sorted(hits):
        line += blob.count("\n", last, pos)
        last = pos
        out.add(line)
        if include:
            out.update((line - 1, line - 2))
    out.discard(-1)
    out.discard(-2)
    return out
