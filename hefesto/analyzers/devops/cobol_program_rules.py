"""
COBOL program-level rules (COBOL004, COBOL008-COBOL014).

These rules need more context than a single line: data entries split by
period, SELECT clauses, EXEC SQL blocks, paragraphs and sentences. This module
builds a small regex-based program model from the logical lines that the
structural extractor produces, then runs the rules on it. All rules are FREE.

- COBOL004 REDEFINES_SENSITIVE         REDEFINES over packed/binary/float/pointer/signed
  numeric data with a different layout (HIGH); also runs on copybooks
- COBOL008 HARDCODED_SECRET_VALUE      VALUE literal on a credential-named field (CRITICAL)
- COBOL009 CONNECTION_STRING_SECRET    PASS=/PWD=/PASSWORD= inside a literal (CRITICAL)
- COBOL010 SQL_CONNECT_LITERAL_CREDENTIAL EXEC SQL CONNECT ... USING/IDENTIFIED BY 'literal'
  (CRITICAL)
- COBOL011 FILE_STATUS_MISSING         SELECTs without a FILE STATUS clause, one finding
  per program (LOW)
- COBOL012 FILE_STATUS_UNCHECKED       OPENed file whose status is never referenced (LOW)
- COBOL013 DEAD_CODE_AFTER_STOP        statements after an unconditional STOP RUN /
  GOBACK / EXIT PROGRAM in the same paragraph (MEDIUM)
- COBOL014 UNUSED_PARAGRAPH            paragraph or section that is never referenced
  and cannot be reached by fall-through (LOW)

Copyright 2025 Narapa LLC, Miami, Florida
"""

import itertools
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

ENGINE = "internal:cobol_governance"

LogicalLine = Tuple[int, str, bool]  # (line number, text, starts in Area A)

_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")
_WORD = r"[A-Z0-9][A-Z0-9_-]*"
_DIVISION = re.compile(r"^(IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", re.I)
_END_PROGRAM = re.compile(r"^END\s+PROGRAM\b", re.I)
_SECTION_HEADER = re.compile(rf"^({_WORD})\s+SECTION(?:\s+\d+)?\s*\.\s*(.*)$", re.I)
_PARAGRAPH_HEADER = re.compile(rf"^({_WORD})\s*\.(?:\s+(.*))?$", re.I)
_GO_TO = re.compile(r"\bGO\s+TO\b", re.I)
_WORD_TOKEN = re.compile(_WORD, re.I)
_UNCONDITIONAL_END = re.compile(
    rf"(?:\bSTOP\s+RUN|\bGOBACK|\bEXIT\s+PROGRAM|\bGO\s+TO\s+{_WORD})\s*$", re.I
)
_ENTRY = re.compile(r"^ENTRY\s+['\"]", re.I)
_ONLY_EXIT = re.compile(r"^\s*EXIT\s*$", re.I)
# "EXIT PROGRAM. STOP RUN." / "GOBACK. EXIT." are idioms, not dead code
_CONDITION_PHRASES = re.compile(
    r"\b(?:AT\s+END|AT\s+END-OF-PAGE|AT\s+EOP|INVALID\s+KEY|SIZE\s+ERROR|ON\s+EXCEPTION"
    r"|ON\s+OVERFLOW|WHEN|ELSE|NOT\s+AT|NOT\s+INVALID|NOT\s+ON)\b",
    re.I,
)
_END_SCOPE = re.compile(r"\bEND-[A-Z]+\b", re.I)
_IF = re.compile(r"(?<![\w-])IF(?![\w-])", re.I)
_END_IF = re.compile(r"\bEND-IF\b", re.I)
_EVALUATE = re.compile(r"(?<![\w-])EVALUATE(?![\w-])", re.I)
_END_EVALUATE = re.compile(r"\bEND-EVALUATE\b", re.I)
# Inline PERFORM (closed by END-PERFORM): PERFORM UNTIL/VARYING/WITH TEST/n TIMES
_INLINE_PERFORM = re.compile(
    rf"(?<![\w-])PERFORM\s+(?:UNTIL|VARYING|WITH\s+TEST|{_WORD}\s+TIMES)\b", re.I
)
_END_PERFORM = re.compile(r"\bEND-PERFORM\b", re.I)
_COPY = re.compile(r"(?<![\w-])COPY\s+", re.I)
_SCOPE_TERMINATOR = re.compile(
    r"^END-(?:IF|EVALUATE|PERFORM|READ|WRITE|REWRITE|DELETE|START|RETURN|SEARCH|CALL"
    r"|COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|STRING|UNSTRING|ACCEPT|DISPLAY|EXEC|INVOKE"
    r"|RECEIVE|SEND|XML|JSON)$",
    re.I,
)

# Statements alone on a line that look like a paragraph header ("EXIT.").
_RESERVED_NOT_PARAGRAPH = {
    "EJECT",
    "SKIP1",
    "SKIP2",
    "SKIP3",
    "EXIT",
    "GOBACK",
    "CONTINUE",
    "ELSE",
    "STOP",
    "NEXT",
    "END",
    "DECLARATIVES",
}

_CREDENTIAL_NAME = re.compile(
    r"(?:PASSWORD|PASSWD|PWD|SECRET|API[_-]?KEY|APIKEY|TOKEN|CREDENTIAL|AUTH[_-]?KEY)", re.I
)
_NON_SECRET_SUFFIX = re.compile(
    r"-(?:FLAG|FLG|SW|SWITCH|IND|INDICATOR|OK|VALID|STATUS|STAT|LEN|LENGTH"
    r"|MSG|MESSAGE|PROMPT|LABEL|LIT|ERR|ERROR)$",
    re.I,
)
_DATA_ENTRY = re.compile(rf"^(\d{{1,2}})\s+({_WORD})\b(.*)$", re.I | re.S)
_VALUE_LITERAL = re.compile(r"\bVALUES?\s+(?:IS\s+|ARE\s+)?(['\"])(.*?)\1", re.I | re.S)
_CONN_SECRET = re.compile(r"(?:^|[;,\s(])(?:PASS|PWD|PASSWORD|PASSWD)\s*=\s*([^;,\s'\")]+)", re.I)
_EXEC_SQL = re.compile(r"\bEXEC\s+SQL\b(.*?)\bEND-EXEC\b", re.I | re.S)
_SQL_CONNECT_LITERAL = re.compile(
    r"\bCONNECT\s+['\"][^'\"]*/"  # Oracle 'user/password'
    r"|\bCONNECT\b",
    re.I,
)
_SQL_LITERAL_PASSWORD = re.compile(r"(?:\bUSING|\bIDENTIFIED\s+BY)\s+['\"]", re.I)
_SELECT = re.compile(rf"\bSELECT\s+(?:OPTIONAL\s+)?({_WORD})", re.I)
_STATUS_CLAUSE = re.compile(rf"\b(?:FILE\s+)?STATUS\s+(?:IS\s+)?({_WORD})", re.I)
_SD = re.compile(rf"(?:^|\s)SD\s+({_WORD})", re.I)
_OPEN = re.compile(r"\bOPEN\b", re.I)
_OPEN_MODES = {"INPUT", "OUTPUT", "I-O", "EXTEND"}


_TERMINATOR_WORDS = {"GOBACK", "EXIT"}
_TERMINATOR_PAIRS = {("STOP", "RUN"), ("EXIT", "PROGRAM")}


def only_terminators(text: str) -> bool:
    """True when ``text`` is only STOP RUN / GOBACK / EXIT PROGRAM / EXIT tokens.

    Token loop instead of a repeated regex group (avoids ReDoS backtracking).
    """
    tokens = text.upper().split()
    if not tokens:
        return False
    i = 0
    while i < len(tokens):
        if tuple(tokens[i : i + 2]) in _TERMINATOR_PAIRS:
            i += 2
        elif tokens[i] in _TERMINATOR_WORDS:
            i += 1
        else:
            return False
    return True


def _open_operands(text: str, start: int) -> Set[str]:
    """File names after an OPEN verb, up to the end of the sentence."""
    stop = text.find(".", start)
    tokens = [t.upper() for t in _WORD_TOKEN.findall(text[start : stop if stop >= 0 else None])]
    if not tokens or tokens[0] not in _OPEN_MODES:
        return set()
    return set(tokens) - _OPEN_MODES - {"REVERSED", "WITH", "NO", "REWIND"}


def _connect_has_literal_password(sql: str) -> bool:
    """Oracle CONNECT 'user/pass', or CONNECT ... USING/IDENTIFIED BY '<literal>'."""
    match = _SQL_CONNECT_LITERAL.search(sql)
    if not match:
        return False
    if match.group(0).upper() != "CONNECT":
        return True
    return bool(_SQL_LITERAL_PASSWORD.search(sql, match.end()))


def mask_literals(text: str) -> str:
    """Blank out the contents of string literals, keeping quotes and length."""
    if "'" not in text and '"' not in text:
        return text  # fast path: most lines have no literal
    return _LITERAL.sub(
        lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], text
    )


@dataclass
class _Sentence:
    line: int
    text: str  # literals masked


@dataclass
class _ProcItem:
    """A paragraph or section in the PROCEDURE DIVISION."""

    name: str
    line: int
    is_section: bool
    section: Optional[str]
    sentences: List[_Sentence] = field(default_factory=list)


@dataclass
class _ProgramUnit:
    data: List[Tuple[int, str]] = field(default_factory=list)  # (line, raw text)
    env: List[Tuple[int, str]] = field(default_factory=list)
    proc: List[LogicalLine] = field(default_factory=list)
    _proc_text: Optional[str] = field(default=None, repr=False, compare=False)


def _strip_comments(text: str) -> Optional[str]:
    """Drop '*>' inline comments; None for lines that are comments altogether."""
    if "*" not in text:
        return text  # fast path
    masked = mask_literals(text)
    if masked.lstrip().startswith("*"):
        return None  # '*>' comment line, or a misplaced '*' comment
    cut = masked.find("*>")
    return text[:cut].rstrip() if cut >= 0 else text


def _add_line(unit: _ProgramUnit, division: str, line: LogicalLine) -> None:
    line_num, text, _ = line
    if division == "ENVIRONMENT":
        unit.env.append((line_num, text))
    elif division == "PROCEDURE":
        unit.proc.append(line)
    elif division in ("DATA", ""):
        # no division header at all: copybook or fragment, treated as data
        unit.data.append((line_num, text))


_PERIOD_SPLIT = re.compile(r"\.(?=\s|$)")
_GO_TO_START = re.compile(r"GO\s+TO\b", re.I)
_PROC_HEADER_REST = re.compile(r"^(?:USING|RETURNING|CHAINING)\b", re.I)
_END_DECLARATIVES = re.compile(r"^END\s+DECLARATIVES\b")
_WHITESPACE = re.compile(r"\s")


def split_program_units(lines: List[LogicalLine]) -> List[_ProgramUnit]:
    """Split logical lines into program units and divisions."""
    units: List[_ProgramUnit] = []
    unit = _ProgramUnit()
    division = ""
    for line in lines:
        line_num, raw, area_a = line
        text = _strip_comments(raw)
        if text is None:
            continue
        if _END_PROGRAM.match(text):
            division = "END"
            continue
        match = _DIVISION.match(text)
        if match:
            name = match.group(1).upper()
            if name in ("IDENTIFICATION", "ID") and (unit.proc or unit.data or unit.env):
                units.append(unit)
                unit = _ProgramUnit()
            division = "IDENTIFICATION" if name == "ID" else name
            if division == "PROCEDURE":
                continue
        # reuse the caller's tuple when nothing was stripped (memory)
        _add_line(unit, division, line if text is raw else (line_num, text, area_a))
    if unit.proc or unit.data or unit.env:
        units.append(unit)
    return units


def split_sentences(lines: List[Tuple[int, str]]) -> List[_Sentence]:
    """Join lines and split on periods outside literals (literals masked)."""
    sentences: List[_Sentence] = []
    buf: List[str] = []
    start: Optional[int] = None
    for line_num, raw in lines:
        masked = mask_literals(raw)
        if start is None and masked.strip():
            start = line_num
        pieces = _PERIOD_SPLIT.split(masked) if "." in masked else [masked]
        for i, piece in enumerate(pieces):
            if i > 0:
                text = " ".join(buf).strip()
                if text and start is not None:
                    sentences.append(_Sentence(start, text))
                buf = []
                start = line_num if piece.strip() else None
            if piece.strip():
                if start is None:
                    start = line_num
                buf.append(piece.strip())
    text = " ".join(buf).strip()
    if text and start is not None:
        sentences.append(_Sentence(start, text))
    return sentences


def _raw_sentences(lines: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """Like split_sentences but keeps literal contents (split on masked periods)."""
    out: List[Tuple[int, str]] = []
    buf: List[str] = []
    start: Optional[int] = None
    for line_num, raw in lines:
        masked = mask_literals(raw)
        cut = 0
        for match in _PERIOD_SPLIT.finditer(masked):
            piece = raw[cut : match.start()]
            if piece.strip():
                buf.append(piece.strip())
                start = line_num if start is None else start
            if buf and start is not None:
                out.append((start, " ".join(buf)))
            buf, start, cut = [], None, match.end()
        rest = raw[cut:]
        if rest.strip():
            buf.append(rest.strip())
            start = line_num if start is None else start
    if buf and start is not None:
        out.append((start, " ".join(buf)))
    return out


def _is_conditional(prefix: str) -> bool:
    """True when the end of ``prefix`` is still inside a conditional scope."""
    if len(_IF.findall(prefix)) > len(_END_IF.findall(prefix)):
        return True
    if len(_EVALUATE.findall(prefix)) > len(_END_EVALUATE.findall(prefix)):
        return True
    if len(_INLINE_PERFORM.findall(prefix)) > len(_END_PERFORM.findall(prefix)):
        return True
    last_phrase = None
    for last_phrase in _CONDITION_PHRASES.finditer(prefix):
        pass
    if last_phrase is None:
        return False
    last_end = None
    for last_end in _END_SCOPE.finditer(prefix):
        pass
    return last_end is None or last_end.start() < last_phrase.start()


def ends_unconditionally(sentence: str, include_goto: bool) -> bool:
    """True if the sentence ends with an unconditional STOP RUN/GOBACK/EXIT PROGRAM
    (or GO TO, when include_goto)."""
    match = _UNCONDITIONAL_END.search(sentence)
    if not match:
        return False
    if not include_goto and _GO_TO_START.match(match.group(0)):
        return False
    return not _is_conditional(sentence[: match.start()])


def build_procedure(proc: List[LogicalLine]) -> List[_ProcItem]:
    """Group procedure lines into paragraphs/sections with their sentences.

    Items inside DECLARATIVES are dropped. The first item is a synthetic entry
    (name "") for code before any paragraph or section header.
    """
    items: List[_ProcItem] = [_ProcItem("", proc[0][0] if proc else 1, False, None)]
    bodies: Dict[int, List[Tuple[int, str]]] = {0: []}
    in_declaratives = False
    section: Optional[str] = None
    first = True
    at_sentence_start = True
    for line_num, text, area_a in proc:
        if first:
            first = False
            # "PROCEDURE DIVISION [USING ...]." header remainder
            if _PROC_HEADER_REST.match(text):
                continue
        upper = text.upper().strip()
        if upper.startswith("DECLARATIVES"):
            in_declaratives = True
            continue
        if upper.startswith("END") and _END_DECLARATIVES.match(upper):
            in_declaratives = False
            continue
        if in_declaratives:
            continue
        # A header starts in Area A; in free format (or badly indented
        # sources) accept it when the previous line closed a sentence.
        header_ok = area_a or at_sentence_start
        at_sentence_start = mask_literals(text).rstrip().endswith(".")
        sec = _SECTION_HEADER.match(text) if header_ok and "." in text else None
        if sec:
            section = sec.group(1).upper()
            items.append(_ProcItem(section, line_num, True, section))
            bodies[len(items) - 1] = [(line_num, sec.group(2))] if sec.group(2) else []
            continue
        par = _PARAGRAPH_HEADER.match(text) if header_ok and "." in text else None
        if (
            par
            and par.group(1).upper() not in _RESERVED_NOT_PARAGRAPH
            and not _SCOPE_TERMINATOR.match(par.group(1))
        ):
            items.append(_ProcItem(par.group(1).upper(), line_num, False, section))
            bodies[len(items) - 1] = [(line_num, par.group(2))] if par.group(2) else []
            continue
        bodies[len(items) - 1].append((line_num, text))
    for idx, item in enumerate(items):
        item.sentences = split_sentences(bodies.get(idx, []))
    return items


def _issue(
    file_path: str,
    line: int,
    issue_type: AnalysisIssueType,
    severity: AnalysisIssueSeverity,
    message: str,
    suggestion: str,
    rule_id: str,
    confidence: float,
) -> AnalysisIssue:
    return AnalysisIssue(
        file_path=file_path,
        line=line,
        column=0,
        issue_type=issue_type,
        severity=severity,
        message=message,
        suggestion=suggestion,
        engine=ENGINE,
        rule_id=rule_id,
        confidence=confidence,
    )


_PLACEHOLDER_VALUES = {
    "UNDEFINED",
    "UNKNOWN",
    "NONE",
    "NULL",
    "DUMMY",
    "N/A",
    "NA",
    "TBD",
    "NOTSET",
    "NOT-SET",
    "PLACEHOLDER",
    "SPACES",
    "LOW-VALUES",
    "HIGH-VALUES",
}


_BARE_CREDENTIAL_WORDS = {"PASSWORD", "PASSWD", "PWD", "SECRET", "TOKEN"}
# Extra name suffixes for COBOL008 only: these fields describe the credential.
_NON_SECRET_VALUE_SUFFIX = re.compile(
    r"-(?:USER|USERNAME|USERID|NAME|URL|URI|TYPE|PARMS|PARAMS|HEADERS|EXPIRY|EXPIRES"
    r"|TIME|DATE|COUNT|CNT)$",
    re.I,
)


def _is_placeholder(value: str) -> bool:
    value = value.strip()
    return (
        len(value) < 2
        or len(set(value.upper())) == 1  # 'XXXXXXXX', '********'
        or value.upper() in _PLACEHOLDER_VALUES
        or not value[0].isalnum()  # '[', '?', '%s', '${VAR}', ':HOST-VAR'
    )


def _looks_like_secret(literal: str) -> bool:
    value = literal.strip()
    if _is_placeholder(value):
        return False
    if _WHITESPACE.search(value) or value.endswith((":", "=")):
        return False  # display labels such as 'ENTER PASSWORD:'
    if _CREDENTIAL_NAME.search(value) and value.upper() not in _BARE_CREDENTIAL_WORDS:
        return False  # key/variable names such as 'BAQHAPI-Token-Password'

    return True


def check_value_secrets(file_path: str, unit: _ProgramUnit) -> List[AnalysisIssue]:
    """COBOL008: VALUE 'literal' on a credential-named data item."""
    issues = []
    for line, entry in _raw_sentences(unit.data):
        match = _DATA_ENTRY.match(entry.strip())
        if not match or match.group(1) == "88":
            continue
        name = match.group(2)
        if (
            not _CREDENTIAL_NAME.search(name)
            or _NON_SECRET_SUFFIX.search(name)
            or _NON_SECRET_VALUE_SUFFIX.search(name)
        ):
            continue
        value = _VALUE_LITERAL.search(match.group(3))
        if value and _looks_like_secret(value.group(2)):
            issues.append(
                _issue(
                    file_path,
                    line,
                    AnalysisIssueType.COBOL_HARDCODED_SECRET_VALUE,
                    AnalysisIssueSeverity.CRITICAL,
                    f"Hardcoded credential in VALUE clause of field '{name}'. "
                    "Never store secrets in source code.",
                    "Load the secret at run time (RACF/vault/parameter file) instead "
                    "of a VALUE literal.",
                    "COBOL008",
                    0.85,
                )
            )
    return issues


def check_connection_string_secrets(
    file_path: str, lines: List[Tuple[int, str]]
) -> List[AnalysisIssue]:
    """COBOL009: PASS=/PWD=/PASSWORD= with a value inside a string literal."""
    issues = []
    for line, text in lines:
        for literal in _LITERAL.finditer(text):
            match = _CONN_SECRET.search(literal.group(0)[1:-1])
            if match and not _is_placeholder(match.group(1)):
                issues.append(
                    _issue(
                        file_path,
                        line,
                        AnalysisIssueType.COBOL_CONNECTION_STRING_SECRET,
                        AnalysisIssueSeverity.CRITICAL,
                        "Password embedded in a connection-string literal "
                        "(PASS=/PWD=/PASSWORD=).",
                        "Build the connection string at run time from a protected "
                        "source; do not hardcode the password.",
                        "COBOL009",
                        0.85,
                    )
                )
                break
    return issues


def check_sql_connect_literal(file_path: str, proc: List[LogicalLine]) -> List[AnalysisIssue]:
    """COBOL010: EXEC SQL CONNECT ... USING/IDENTIFIED BY with a literal password."""
    issues: List[AnalysisIssue] = []
    if not any("CONNECT" in text.upper() for _, text, _ in proc):
        return issues
    joined: List[str] = []
    offsets: List[Tuple[int, int]] = []  # (char offset, line)
    pos = 0
    for line_num, text, _ in proc:
        offsets.append((pos, line_num))
        joined.append(text)
        pos += len(text) + 1
    code = "\n".join(joined)
    for block in _EXEC_SQL.finditer(code):
        if _connect_has_literal_password(block.group(1)):
            line = max((ln for off, ln in offsets if off <= block.start()), default=1)
            issues.append(
                _issue(
                    file_path,
                    line,
                    AnalysisIssueType.COBOL_SQL_CONNECT_LITERAL_CREDENTIAL,
                    AnalysisIssueSeverity.CRITICAL,
                    "EXEC SQL CONNECT uses a literal password " "(USING/IDENTIFIED BY 'literal').",
                    "Pass the password in a host variable loaded at run time.",
                    "COBOL010",
                    0.9,
                )
            )
    return issues


def _data_entries(unit: _ProgramUnit) -> List[Tuple[int, str]]:
    """(level, NAME) for every data entry in the unit, in order."""
    out = []
    for sentence in split_sentences(unit.data):
        match = _DATA_ENTRY.match(sentence.text)
        if match:
            out.append((int(match.group(1)), match.group(2).upper()))
    return out


def _related_names(entries: List[Tuple[int, str]], name: str) -> Optional[Set[str]]:
    """The item, its subordinates (incl. 88s) and its ancestors; None if undefined."""
    for idx, (level, entry_name) in enumerate(entries):
        if entry_name != name:
            continue
        names = {name}
        for sub_level, sub_name in entries[idx + 1 :]:
            if sub_level == 88:
                names.add(sub_name)
                continue
            if level == 77 or sub_level <= level or sub_level == 77:
                break
            names.add(sub_name)
        current = level
        for anc_level, anc_name in reversed(entries[:idx]):
            if anc_level == 88:
                continue
            if anc_level < current:
                names.add(anc_name)
                current = anc_level
            if current == 1:
                break
        return names
    return None


_WORDS = re.compile(rf"(?<![\w-]){_WORD}(?![\w-])")
# "<word> THRU <word>": find the keyword first, then the word right before it
# (a pattern starting with the first word is tried at every position: slow).
_THRU_KEYWORD = re.compile(rf"(?<=\s)(?:THRU|THROUGH)\s+({_WORD})")
_WORD_BEFORE = re.compile(rf"({_WORD})\s+$")
_WORDS_CHUNK = 2000  # lines joined per word scan in _referenced_words


def _words(text: str) -> Set[str]:
    if len(text) < 65536:
        return set(_WORDS.findall(text.upper()))
    # big text: no list of every word occurrence (bounded memory)
    return {m.group(0) for m in _WORDS.finditer(text.upper())}


def _procedure_text(unit: _ProgramUnit) -> str:
    """Whole PROCEDURE DIVISION (DECLARATIVES included), literals masked (cached)."""
    if unit._proc_text is None:
        unit._proc_text = " ".join(mask_literals(text) for _, text, _ in unit.proc)
    return unit._proc_text


_REDEFINES = re.compile(rf"\bREDEFINES\s+({_WORD})", re.I)
_PIC = re.compile(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)", re.I)
# USAGE words, not parts of data names (``REDEFINES TWO-BYTES-BINARY``, ``WS-COMP-3``).
_USAGE_PACKED = re.compile(r"(?<![\w-])(?:COMP(?:UTATIONAL)?-3|PACKED-DECIMAL)(?![\w-])", re.I)
_USAGE_FLOAT = re.compile(r"(?<![\w-])COMP(?:UTATIONAL)?-[12](?![\w-])", re.I)
_USAGE_BINARY = re.compile(r"(?<![\w-])(?:COMP(?:UTATIONAL)?(?:-[45])?|BINARY)(?![\w-])", re.I)
_USAGE_OTHER = re.compile(
    r"(?<![\w-])(?:INDEX|POINTER|PROCEDURE-POINTER|FUNCTION-POINTER)(?![\w-])", re.I
)
_NUMERIC_PIC = re.compile(r"^[S9VP()0-9]+$", re.I)
_SENSITIVE = {"packed", "binary", "signed", "float", "pointer"}
_CLASS_LABEL = {
    "packed": "packed-decimal (COMP-3)",
    "binary": "binary (COMP)",
    "signed": "signed numeric",
    "float": "floating point",
    "pointer": "index/pointer",
}


@dataclass
class _DataItem:
    line: int
    level: int
    name: str
    clause: str  # text after the name, literals masked


def _data_items(unit: _ProgramUnit) -> List[_DataItem]:
    items = []
    for sentence in split_sentences(unit.data):
        match = _DATA_ENTRY.match(sentence.text.strip())
        if not match:
            continue
        name, clause = match.group(2).upper(), match.group(3)
        if name in ("PIC", "PICTURE", "VALUE", "USAGE", "COMP", "COMP-3", "OCCURS"):
            name, clause = "FILLER", f"{name} {clause}"  # anonymous FILLER item
        items.append(_DataItem(sentence.line, int(match.group(1)), name, clause))
    return items


def _usage_class(clause: str) -> Optional[str]:
    if _USAGE_PACKED.search(clause):
        return "packed"
    if _USAGE_FLOAT.search(clause):
        return "float"
    if _USAGE_BINARY.search(clause):
        return "binary"
    if _USAGE_OTHER.search(clause):
        return "pointer"
    return None


def _elementary_class(pic: Optional[str], usage: Optional[str]) -> str:
    if usage:
        return usage
    if pic and _NUMERIC_PIC.match(pic):
        return "signed" if pic.upper().startswith("S") else "numeric"
    return "alphanumeric"


def _members(items: List[_DataItem], idx: int) -> List[_DataItem]:
    """``items[idx]`` and every item below it (66/88 entries skipped)."""
    root = items[idx]
    members = [root]
    for item in items[idx + 1 :]:
        if item.level in (66, 88):
            continue
        if root.level == 77 or item.level <= root.level or item.level == 77:
            break
        members.append(item)
    return members


def _layout(items: List[_DataItem], idx: int) -> Tuple[Tuple[str, str], ...]:
    """(class, PIC) of every elementary item under ``items[idx]`` (or itself)."""
    members = _members(items, idx)
    out = []
    stack: List[Tuple[int, Optional[str]]] = []  # (level, own usage) of open groups
    for pos, item in enumerate(members):
        while stack and stack[-1][0] >= item.level:
            stack.pop()
        own = _usage_class(item.clause)
        inherited = next((usage for _, usage in reversed(stack) if usage), None)
        stack.append((item.level, own))
        if pos + 1 < len(members) and members[pos + 1].level > item.level:
            continue  # group item: its children carry the layout
        pic = _PIC.search(item.clause)
        pic_text = pic.group(1).rstrip(".").upper() if pic else ""
        out.append((_elementary_class(pic_text or None, own or inherited), pic_text))
    return tuple(out)


_PIC_SYMBOL_RUN = re.compile(r"([9X])(?:\((\d+)\))?", re.IGNORECASE)


def _pic_count(pic: str, symbol: str) -> Optional[int]:
    """Number of ``symbol`` positions in a PIC made only of that symbol, else None."""
    text = pic.upper()
    total, pos = 0, 0
    for match in _PIC_SYMBOL_RUN.finditer(text):
        if match.start() != pos or match.group(1) != symbol:
            return None
        total += int(match.group(2) or 1)
        pos = match.end()
    return total if pos == len(text) and total else None


def _binary_bytes(digits: int) -> Optional[int]:
    """Storage of an unsigned binary PIC 9(n) (COMP/BINARY/COMP-4/COMP-5)."""
    for limit, size in ((4, 2), (9, 4), (18, 8)):
        if digits <= limit:
            return size
    return None


def _is_byte_view(one: Tuple[Tuple[str, str], ...], other: Tuple[Tuple[str, str], ...]) -> bool:
    """Binary integer (signed or not) overlaid by PIC X bytes of exactly its storage size.

    The CardDemo idiom ``01 TWO-BYTES-BINARY PIC 9(4) BINARY`` +
    ``01 TWO-BYTES-ALPHA REDEFINES ... 05 PIC X. 05 PIC X.`` reads the bytes of
    a binary field (e.g. to decode a VSAM file status). No digit is ever
    reinterpreted, so it is not the corruption risk COBOL004 is about. The same
    holds for signed binary (``PIC S9(4) COMP`` read byte by byte to print it in
    hex): the sign is a bit of those bytes, not a separate encoding. A size
    mismatch or any non-PIC X byte still counts as a finding.
    """
    if len(one) != 1 or one[0][0] != "binary":
        return False
    digits = _pic_count(one[0][1][1:] if one[0][1].startswith("S") else one[0][1], "9")
    size = _binary_bytes(digits) if digits else None
    if size is None or not other:
        return False
    widths = [_pic_count(pic, "X") if cls == "alphanumeric" else None for cls, pic in other]
    return all(widths) and sum(w for w in widths if w) == size


_ZONED_PIC = re.compile(r"^(S?)((?:9(?:\(\d+\))?|V)+)$", re.IGNORECASE)
_ZONED_RUN = re.compile(r"9(?:\((\d+)\))?", re.IGNORECASE)
_SIGN_CLAUSE = re.compile(r"(?<![\w-])(?:SIGN|LEADING|TRAILING|SEPARATE)(?![\w-])", re.I)


def _zoned(entry: Tuple[str, str]) -> Optional[Tuple[bool, int]]:
    """(signed, digits) of a zoned decimal (USAGE DISPLAY numeric) PIC, else None."""
    cls, pic = entry
    match = _ZONED_PIC.match(pic) if cls in ("signed", "numeric") else None
    if not match:
        return None
    digits = sum(int(run.group(1) or 1) for run in _ZONED_RUN.finditer(match.group(2)))
    return bool(match.group(1)), digits


def _is_zoned_split(
    whole: Tuple[Tuple[str, str], ...],
    parts: Tuple[Tuple[str, str], ...],
    clauses: List[str],
) -> bool:
    """A signed zoned number split into digit groups, sign on the last group.

    ``PIC S9(10)`` redefined as ``9(9)`` + ``S9``: zoned decimal stores one
    digit per byte with the sign in the zone of the last byte, so both views
    hold the same digits in the same bytes and the sign stays where it was. A
    SIGN clause (leading or separate sign) changes where the sign lives and is
    still reported, as is any other split.
    """
    if len(whole) != 1 or len(parts) < 2 or any(_SIGN_CLAUSE.search(c) for c in clauses):
        return False
    one = _zoned(whole[0])
    split = [_zoned(entry) for entry in parts]
    if one is None or not one[0] or any(s is None for s in split):
        return False
    signs = [s[0] for s in split if s]
    return sum(s[1] for s in split if s) == one[1] and signs[-1] and not any(signs[:-1])


_POINTER_USAGE = re.compile(r"(?<![\w-])(?:PROCEDURE-|FUNCTION-)?POINTER(?![\w-])", re.I)
_ADDRESS_SIZES = (4, 8)  # 31/32-bit and 64-bit addressing


def _is_pointer_view(
    pointer: List[_DataItem],
    pointer_layout: Tuple[Tuple[str, str], ...],
    view_layout: Tuple[Tuple[str, str], ...],
) -> bool:
    """A pointer and one address-sized elementary view of the same storage.

    ``USAGE POINTER`` overlaid by ``PIC X(8)``, ``PIC X(4)`` or an unsigned
    binary of 4 or 8 bytes (``PIC 9(9) COMP``) is how programs print, compare
    or pass an address; no numeric value is reinterpreted. Signed, display,
    group or other-sized views are still reported, and INDEX is not a pointer.
    """
    if len(pointer) != 1 or len(pointer_layout) != 1 or len(view_layout) != 1:
        return False
    if pointer_layout[0][0] != "pointer" or not _POINTER_USAGE.search(pointer[0].clause):
        return False
    cls, pic = view_layout[0]
    if cls == "alphanumeric":
        return _pic_count(pic, "X") in _ADDRESS_SIZES
    digits = _pic_count(pic, "9") if cls == "binary" else None
    return digits is not None and _binary_bytes(digits) in _ADDRESS_SIZES


_OCCURS_FIXED = re.compile(r"(?<![\w-])OCCURS\s+(\d+)(?:\s+TIMES)?(?:\s+(TO)\b)?", re.I)
_OCCURS_WORD = re.compile(r"(?<![\w-])OCCURS(?![\w-])", re.I)
_PIC_EXPAND = re.compile(r"(.)\((\d+)\)")


class _VariableTable(Exception):
    """OCCURS ... DEPENDING ON (or an unreadable OCCURS): no fixed layout."""


def _occurs_count(clause: str) -> int:
    if not _OCCURS_WORD.search(clause):
        return 1
    match = _OCCURS_FIXED.search(clause)
    if not match or match.group(2) or re.search(r"\bDEPENDING\b", clause, re.I):
        raise _VariableTable
    return int(match.group(1))


def _storage_layout(items: List[_DataItem], idx: int) -> Optional[Tuple[Tuple[str, str], ...]]:
    """Elementary (class, PIC) sequence of the storage, OCCURS expanded.

    PICs are spelled out (``S9(02)`` and ``S99`` compare equal) and adjacent
    PIC X fields are merged into one byte string (``X(34)`` + ``X(6)`` is
    ``X(40)``). None for variable-length tables.
    """
    members = _members(items, idx)

    def node(pos: int, inherited: Optional[str]) -> Tuple[List[Tuple[str, str]], int]:
        item = members[pos]
        usage = _usage_class(item.clause) or inherited
        count = _occurs_count(item.clause)
        out: List[Tuple[str, str]] = []
        nxt = pos + 1
        while nxt < len(members) and members[nxt].level > item.level:
            child, nxt = node(nxt, usage)
            out.extend(child)
        if nxt == pos + 1:
            pic = _PIC.search(item.clause)
            pic_text = pic.group(1).rstrip(".").upper() if pic else ""
            spelled = _PIC_EXPAND.sub(lambda m: m.group(1) * int(m.group(2)), pic_text)
            out = [(_elementary_class(pic_text or None, usage), spelled)]
        return out * count, nxt

    try:
        flat, _ = node(0, None)
    except _VariableTable:
        return None
    merged: List[Tuple[str, str]] = []
    for cls, pic in flat:
        if (
            merged
            and cls == "alphanumeric" == merged[-1][0]
            and set(pic) == {"X"} == set(merged[-1][1])
        ):
            merged[-1] = (cls, merged[-1][1] + pic)
        else:
            merged.append((cls, pic))
    return tuple(merged)


def _is_intended_overlay(items: List[_DataItem], orig_idx: int, idx: int) -> bool:
    """REDEFINES idioms that keep every value's bytes and meaning (not reported)."""
    original, redefined = _layout(items, orig_idx), _layout(items, idx)
    if _is_byte_view(original, redefined) or _is_byte_view(redefined, original):
        return True
    orig_members, redef_members = _members(items, orig_idx), _members(items, idx)
    clauses = [m.clause for m in orig_members + redef_members]
    if _is_zoned_split(original, redefined, clauses) or _is_zoned_split(
        redefined, original, clauses
    ):
        return True
    if _is_pointer_view(orig_members, original, redefined) or _is_pointer_view(
        redef_members, redefined, original
    ):
        return True
    storage = _storage_layout(items, orig_idx)
    return storage is not None and storage == _storage_layout(items, idx)


def _is_bms_output_map(name: str, target: str) -> bool:
    """CICS BMS symbolic map: ``01 xxxO REDEFINES xxxI`` is generated, not user code."""
    return (
        len(name) == len(target)
        and name.endswith("O")
        and target.endswith("I")
        and name[:-1] == target[:-1]
    )


def _is_bms_input_map(items: List[_DataItem], idx: int) -> bool:
    """A CICS BMS symbolic input map: every binary field is a ``xxxL`` length
    field with its ``xxxI`` data field in the same group (generated layout).

    Programs overlay these maps to index repeated screen rows (CardDemo
    ``01 FILLER REDEFINES CTRTLIAI``); the overlay follows the generated
    layout, so it is not reported. Seen once COPY expansion put the map
    copybook in the program.
    """
    root = items[idx]
    names: Set[str] = set()
    lengths: List[str] = []
    for item in items[idx + 1 :]:
        if item.level <= root.level or item.level in (66, 77):
            break
        names.add(item.name)
        if _usage_class(item.clause) == "binary":
            if not item.name.endswith("L"):
                return False
            lengths.append(item.name)
    return bool(lengths) and all(f"{name[:-1]}I" in names for name in lengths)


def check_redefines(file_path: str, unit: _ProgramUnit) -> List[AnalysisIssue]:
    """COBOL004: REDEFINES that reinterprets packed/binary/signed numeric data.

    Flagged only when one side holds COMP-3, binary, floating-point, pointer or
    signed numeric data and the two layouts differ. REDEFINES between
    alphanumeric/unsigned display fields (e.g. a PIC X split into parts) and
    REDEFINES of items defined elsewhere (copybooks) are not flagged.
    """
    issues = []
    items = _data_items(unit)
    for idx, item in enumerate(items):
        match = _REDEFINES.search(item.clause)
        if not match:
            continue
        target = match.group(1).upper()
        if _is_bms_output_map(item.name, target):
            continue
        orig_idx = next(
            (
                j
                for j in range(idx - 1, -1, -1)
                if items[j].name == target and items[j].level == item.level
            ),
            None,
        )
        if orig_idx is None or _is_bms_input_map(items, orig_idx):
            continue
        original, redefined = _layout(items, orig_idx), _layout(items, idx)
        sensitive = sorted({c for c, _ in original + redefined if c in _SENSITIVE})
        if not sensitive or original == redefined:
            continue
        if _is_intended_overlay(items, orig_idx, idx):
            continue
        kinds = ", ".join(_CLASS_LABEL[c] for c in sensitive)
        issues.append(
            _issue(
                file_path,
                item.line,
                AnalysisIssueType.COBOL_REDEFINES_SENSITIVE,
                AnalysisIssueSeverity.HIGH,
                f"'{item.name}' REDEFINES '{target}' with a different layout over "
                f"{kinds} data. Reading or moving through the other view can corrupt "
                "values or raise data exceptions (S0C7).",
                "Use a single numeric view, or convert explicitly (MOVE to a display "
                "field) instead of overlaying the storage.",
                "COBOL004",
                0.85,
            )
        )
    return issues


def _file_status_missing(file_path: str, missing: List[Tuple[int, str]]) -> AnalysisIssue:
    """COBOL011, one finding per program listing every file without FILE STATUS."""
    names = [name for _, name in missing]
    shown = ", ".join(f"'{n}'" for n in names[:10]) + (" ..." if len(names) > 10 else "")
    issue = _issue(
        file_path,
        missing[0][0],
        AnalysisIssueType.COBOL_FILE_STATUS_MISSING,
        AnalysisIssueSeverity.LOW,
        f"{len(names)} file(s) without a FILE STATUS clause: {shown}. I/O errors cannot "
        "be detected and the program may continue with bad data or abend.",
        "Add FILE STATUS IS <2-byte field> to each SELECT and check it after "
        "each OPEN/READ/WRITE/CLOSE.",
        "COBOL011",
        0.8,
    )
    issue.metadata = {
        "occurrences": len(names),
        "files": names[:50],
        "lines": [line for line, _ in missing][:50],
    }
    return issue


_OCCURS = re.compile(r"\bOCCURS\b", re.I)
_DEPENDING_ON = re.compile(rf"\bDEPENDING\s+ON\s+({_WORD})", re.I)
# CICS commarea idiom: LK-COMMAREA OCCURS 1 TO 32767 DEPENDING ON EIBCALEN is
# sized by CICS itself, not by program data.
_ODO_SAFE_CONTROLS = {"EIBCALEN"}


def occurs_depending(
    logical_lines: List[LogicalLine], units: Optional[List[_ProgramUnit]] = None
) -> List[Tuple[int, str]]:
    """(line, controlling item) of each OCCURS ... DEPENDING ON data entry (COBOL005)."""
    out: List[Tuple[int, str]] = []
    for unit in split_program_units(logical_lines) if units is None else units:
        for sentence in split_sentences(unit.data):
            occurs = _OCCURS.search(sentence.text)
            if not occurs:
                continue
            control = _DEPENDING_ON.search(sentence.text, occurs.end())
            if control and control.group(1).upper() not in _ODO_SAFE_CONTROLS:
                out.append((sentence.line, control.group(1)))
    return out


def _status_referenced(unit: _ProgramUnit, proc_text: str, name: str, lazy: Dict[str, Any]) -> bool:
    """True if the status field (or a subordinate/88/ancestor) is used, or undefined."""
    if "entries" not in lazy:
        lazy["entries"] = _data_entries(unit)
    related = _related_names(lazy["entries"], name)
    if related is None:
        return True  # defined in a copybook or elsewhere: do not report
    if "words" not in lazy:
        lazy["words"] = _words(proc_text)
    return bool(related & lazy["words"])


def check_file_status(file_path: str, unit: _ProgramUnit) -> List[AnalysisIssue]:
    """COBOL011 (no FILE STATUS clause) and COBOL012 (status never referenced)."""
    issues: List[AnalysisIssue] = []
    sort_files = {m.group(1).upper() for _, t in unit.data for m in _SD.finditer(mask_literals(t))}
    proc_text = _procedure_text(unit)
    lazy: Dict[str, Any] = {}  # data entries / procedure words, built on first use
    opened: Set[str] = set()
    for match in _OPEN.finditer(proc_text):
        opened |= _open_operands(proc_text, match.end())
    proc_has_copy = bool(_COPY.search(proc_text))
    missing: List[Tuple[int, str]] = []
    for sentence in split_sentences(unit.env):
        select = _SELECT.search(sentence.text)
        if not select:
            continue
        fname = select.group(1).upper()
        if fname in sort_files:
            continue
        status = _STATUS_CLAUSE.search(sentence.text[select.end() :])
        if not status:
            missing.append((sentence.line, fname))
            continue
        if (
            fname not in opened
            or proc_has_copy
            or _status_referenced(unit, proc_text, status.group(1).upper(), lazy)
        ):
            continue
        issues.append(
            _issue(
                file_path,
                sentence.line,
                AnalysisIssueType.COBOL_FILE_STATUS_UNCHECKED,
                AnalysisIssueSeverity.LOW,
                f"File '{fname}' is OPENed but its status field '{status.group(1)}' "
                "(and its 88-levels) is never referenced in the PROCEDURE DIVISION.",
                "Check the file status after OPEN/READ/WRITE/CLOSE.",
                "COBOL012",
                0.7,
            )
        )
    if missing:
        issues.insert(0, _file_status_missing(file_path, missing))
    return issues


def check_dead_code(file_path: str, items: List[_ProcItem]) -> List[AnalysisIssue]:
    """COBOL013: statements after an unconditional STOP RUN/GOBACK/EXIT PROGRAM."""
    issues = []
    for item in items:
        sentences = item.sentences
        for idx, sentence in enumerate(sentences[:-1]):
            if not ends_unconditionally(sentence.text, include_goto=False):
                continue
            rest = []
            for later in sentences[idx + 1 :]:
                if _ENTRY.match(later.text):
                    break  # alternate entry point: code below is reachable
                if not only_terminators(later.text):
                    rest.append(later)
            if rest:
                where = f"paragraph '{item.name}'" if item.name else "the PROCEDURE DIVISION"
                issues.append(
                    _issue(
                        file_path,
                        rest[0].line,
                        AnalysisIssueType.COBOL_DEAD_CODE,
                        AnalysisIssueSeverity.MEDIUM,
                        f"Unreachable code in {where}: it follows an unconditional "
                        f"STOP RUN/GOBACK/EXIT PROGRAM (line {sentence.line}).",
                        "Remove the dead statements or move them before the terminator.",
                        "COBOL013",
                        0.85,
                    )
                )
            break
    return issues


def _ends_paragraph(item: _ProcItem) -> bool:
    """True if control never falls out of the paragraph's end (any sentence ends
    with an unconditional STOP RUN/GOBACK/EXIT PROGRAM/GO TO; later ones are dead)."""
    return any(ends_unconditionally(s.text, include_goto=True) for s in item.sentences)


def _referenced_words(unit: _ProgramUnit, items: List[_ProcItem]) -> Set[str]:
    """Every word in the procedure text except the paragraph/section headers."""
    headers: Dict[int, str] = {item.line: item.name for item in items if item.name}
    body: List[str] = []
    referenced: Set[str] = set()
    for line_num, text, _ in unit.proc:
        header = headers.get(line_num)
        if header is None:
            body.append(mask_literals(text))
            if len(body) >= _WORDS_CHUNK:  # bounded memory on huge programs
                referenced |= _words(" ".join(body))
                body.clear()
            continue
        words = _words(mask_literals(text))
        words.discard(header)
        referenced |= words
    return referenced | _words(" ".join(body))


def _goto_targets(proc_text: str) -> Set[str]:
    targets: Set[str] = set()
    starts = [m.end() for m in _GO_TO.finditer(proc_text)]
    for pos, start in enumerate(starts):
        stop = proc_text.find(".", start)
        if pos + 1 < len(starts) and (stop < 0 or starts[pos + 1] < stop):
            stop = starts[pos + 1]
        tokens = [
            t.upper() for t in _WORD_TOKEN.findall(proc_text[start : stop if stop >= 0 else None])
        ]
        if not tokens:
            continue
        if "DEPENDING" in tokens:
            targets.update(tokens[: tokens.index("DEPENDING")])
        else:
            targets.add(tokens[0])
    return targets


def _thru_covered(proc_text: str, index: Dict[str, int]) -> Set[int]:
    """Indexes of items inside a THRU range (everything from start to end runs)."""
    covered: Set[int] = set()
    upper = proc_text.upper()
    if "THRU" not in upper and "THROUGH" not in upper:
        return covered
    for match in _THRU_KEYWORD.finditer(upper):
        before = _WORD_BEFORE.search(upper, max(0, match.start() - 64), match.start())
        if before is None:
            continue
        start, end = index.get(before.group(1)), index.get(match.group(1))
        if start is not None and end is not None and start <= end:
            covered.update(range(start, end + 1))
    return covered


def _reachable(
    items: List[_ProcItem],
    referenced: Set[str],
    goto_targets: Set[str],
    ends: Optional[List[bool]] = None,
) -> List[bool]:
    """Fall-through reachability from the entry point (and GO TO / ENTRY targets).

    ``ends[k]`` is ``_ends_paragraph(items[k])`` when the caller computed it."""
    if ends is None:
        ends = [_ends_paragraph(item) for item in items]
    reached = [False] * len(items)
    reached[0] = bool(items[0].sentences)
    for n in range(1, len(items)):
        item, prev = items[n], items[n - 1]
        if n == 1 and not reached[0]:
            reached[n] = True  # first paragraph/section is the entry point
            continue
        if prev.is_section and not prev.sentences:
            falls_in = reached[n - 1] or prev.name in referenced
        else:
            falls_in = reached[n - 1] and not ends[n - 1]
        has_entry = any(_ENTRY.match(s.text) for s in item.sentences)
        reached[n] = falls_in or item.name in goto_targets or has_entry
    return reached


def _runs_inside_section(
    items: List[_ProcItem],
    n: int,
    index: Dict[str, int],
    reached: List[bool],
    referenced: Set[str],
    ends_before: List[int],
) -> bool:
    """A reached or PERFORMed section runs its paragraphs in order until a terminator.

    ``ends_before[k]`` counts the items before ``k`` that end unconditionally,
    so "no terminator between the section header and item n" is O(1).
    """
    item = items[n]
    sec_idx = index.get(item.section or "")
    if item.is_section or sec_idx is None:
        return False
    if not (reached[sec_idx] or items[sec_idx].name in referenced):
        return False
    return ends_before[n] == ends_before[sec_idx]


def check_unused_paragraphs(
    file_path: str, unit: _ProgramUnit, items: List[_ProcItem]
) -> List[AnalysisIssue]:
    """COBOL014: paragraphs/sections never referenced and not reached by fall-through."""
    if not any(i.name for i in items):
        return []
    proc_text = _procedure_text(unit)
    if _COPY.search(proc_text):
        return []  # a procedure copybook may PERFORM them
    referenced = _referenced_words(unit, items)
    index = {item.name: n for n, item in enumerate(items) if item.name}
    covered = _thru_covered(proc_text, index)
    ends = [_ends_paragraph(item) for item in items]
    reached = _reachable(items, referenced, _goto_targets(proc_text), ends)
    ends_before = [0]
    for end in ends:
        ends_before.append(ends_before[-1] + end)

    issues = []
    reported_sections: Set[str] = set()
    for n, item in enumerate(items):
        skip = (
            not item.name
            or reached[n]
            or n in covered
            or item.name in referenced  # PERFORM, GO TO, ALTER, SORT ... PROCEDURE
            or (not item.is_section and item.section in reported_sections)
            or (item.sentences and all(_ONLY_EXIT.match(s.text) for s in item.sentences))
            or _runs_inside_section(items, n, index, reached, referenced, ends_before)
        )
        if skip:
            continue
        if item.is_section:
            reported_sections.add(item.name)
        kind = "Section" if item.is_section else "Paragraph"
        issues.append(
            _issue(
                file_path,
                item.line,
                AnalysisIssueType.COBOL_UNUSED_PARAGRAPH,
                AnalysisIssueSeverity.LOW,
                f"{kind} '{item.name}' is never PERFORMed or GO TO'd and is not reached "
                "by fall-through. It looks like dead code.",
                "Remove it or wire it in; if it is called from a copybook, ignore this.",
                "COBOL014",
                0.7,
            )
        )
    return issues


def _has_quote(text: str) -> bool:
    return '"' in text or "'" in text


def run_program_rules(
    file_path: str,
    logical_lines: List[LogicalLine],
    is_copybook: bool,
    units: Optional[List[_ProgramUnit]] = None,
) -> List[AnalysisIssue]:
    """Run COBOL004 and COBOL008-COBOL014 on the logical lines of one file.

    ``units`` lets the caller pass ``split_program_units(logical_lines)`` it
    already computed.
    """
    issues: List[AnalysisIssue] = []
    for unit in split_program_units(logical_lines) if units is None else units:
        issues.extend(check_redefines(file_path, unit))
        issues.extend(check_value_secrets(file_path, unit))
        # COBOL009 only looks inside literals: skip lines without a quote
        quoted = [(n, t) for n, t in itertools.chain(unit.data, unit.env) if _has_quote(t)]
        quoted += [(n, t) for n, t, _ in unit.proc if _has_quote(t)]
        issues.extend(check_connection_string_secrets(file_path, sorted(quoted)))
        if is_copybook:
            continue
        issues.extend(check_sql_connect_literal(file_path, unit.proc))
        items = build_procedure(unit.proc)
        issues.extend(check_file_status(file_path, unit))
        if unit.proc:
            issues.extend(check_dead_code(file_path, items))
            issues.extend(check_unused_paragraphs(file_path, unit, items))
    return issues
