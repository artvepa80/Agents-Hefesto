"""
COBOL program-level rules (COBOL008-COBOL014).

These rules need more context than a single line: data entries split by
period, SELECT clauses, EXEC SQL blocks, paragraphs and sentences. This module
builds a small regex-based program model from the logical lines that the
structural extractor produces, then runs the rules on it. All rules are FREE.

- COBOL008 HARDCODED_SECRET_VALUE      VALUE literal on a credential-named field (CRITICAL)
- COBOL009 CONNECTION_STRING_SECRET    PASS=/PWD=/PASSWORD= inside a literal (CRITICAL)
- COBOL010 SQL_CONNECT_LITERAL_CREDENTIAL EXEC SQL CONNECT ... USING/IDENTIFIED BY 'literal'
  (CRITICAL)
- COBOL011 FILE_STATUS_MISSING         SELECT without a FILE STATUS clause (MEDIUM)
- COBOL012 FILE_STATUS_UNCHECKED       OPENed file whose status is never referenced (LOW)
- COBOL013 DEAD_CODE_AFTER_STOP        statements after an unconditional STOP RUN /
  GOBACK / EXIT PROGRAM in the same paragraph (MEDIUM)
- COBOL014 UNUSED_PARAGRAPH            paragraph or section that is never referenced
  and cannot be reached by fall-through (LOW)

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

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
_TERMINATOR = re.compile(r"\b(?:STOP\s+RUN|GOBACK|EXIT\s+PROGRAM)\b", re.I)
_GO_TO = re.compile(rf"\bGO\s+TO\s+({_WORD})(?:\s+({_WORD}(?:\s+{_WORD})*)\s+DEPENDING\b)?", re.I)
_UNCONDITIONAL_END = re.compile(
    rf"(?:\bSTOP\s+RUN|\bGOBACK|\bEXIT\s+PROGRAM|\bGO\s+TO\s+{_WORD})\s*$", re.I
)
_ENTRY = re.compile(r"^ENTRY\s+['\"]", re.I)
_ONLY_EXIT = re.compile(r"^\s*EXIT\s*$", re.I)
# "EXIT PROGRAM. STOP RUN." / "GOBACK. EXIT." are idioms, not dead code
_TERMINATOR = r"(?:STOP\s+RUN|GOBACK|EXIT\s+PROGRAM|EXIT)"
_ONLY_TERMINATORS = re.compile(rf"^\s*{_TERMINATOR}(?:\s+{_TERMINATOR})*\s*$", re.I)
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
    r"|\bCONNECT\b.*?(?:\bUSING|\bIDENTIFIED\s+BY)\s+['\"]",
    re.I | re.S,
)
_SELECT = re.compile(rf"\bSELECT\s+(?:OPTIONAL\s+)?({_WORD})", re.I)
_STATUS_CLAUSE = re.compile(rf"\b(?:FILE\s+)?STATUS\s+(?:IS\s+)?({_WORD})", re.I)
_SD = re.compile(rf"(?:^|\s)SD\s+({_WORD})", re.I)
_OPEN = re.compile(r"\bOPEN\s+((?:INPUT|OUTPUT|I-O|EXTEND)\s[^.]*)", re.I)


def mask_literals(text: str) -> str:
    """Blank out the contents of string literals, keeping quotes and length."""
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


def _strip_comments(text: str) -> Optional[str]:
    """Drop '*>' inline comments; None for lines that are comments altogether."""
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


def split_program_units(lines: List[LogicalLine]) -> List[_ProgramUnit]:
    """Split logical lines into program units and divisions."""
    units: List[_ProgramUnit] = []
    unit = _ProgramUnit()
    division = ""
    for line_num, raw, area_a in lines:
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
        _add_line(unit, division, (line_num, text, area_a))
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
        pieces = re.split(r"\.(?=\s|$)", masked)
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
        for match in re.finditer(r"\.(?=\s|$)", masked):
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
    if re.match(r"GO\s+TO\b", match.group(0), re.I) and not include_goto:
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
            if re.match(r"^(?:USING|RETURNING|CHAINING)\b", text, re.I):
                continue
        upper = text.upper().strip()
        if upper.startswith("DECLARATIVES"):
            in_declaratives = True
            continue
        if re.match(r"^END\s+DECLARATIVES\b", upper):
            in_declaratives = False
            continue
        if in_declaratives:
            continue
        # A header starts in Area A; in free format (or badly indented
        # sources) accept it when the previous line closed a sentence.
        header_ok = area_a or at_sentence_start
        at_sentence_start = bool(re.search(r"\.\s*$", mask_literals(text)))
        sec = _SECTION_HEADER.match(text)
        if sec and header_ok:
            section = sec.group(1).upper()
            items.append(_ProcItem(section, line_num, True, section))
            bodies[len(items) - 1] = [(line_num, sec.group(2))] if sec.group(2) else []
            continue
        par = _PARAGRAPH_HEADER.match(text)
        if (
            par
            and header_ok
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
    if re.search(r"\s", value) or value.endswith((":", "=")):
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
    issues = []
    joined: List[str] = []
    offsets: List[Tuple[int, int]] = []  # (char offset, line)
    pos = 0
    for line_num, text, _ in proc:
        offsets.append((pos, line_num))
        joined.append(text)
        pos += len(text) + 1
    code = "\n".join(joined)
    for block in _EXEC_SQL.finditer(code):
        if _SQL_CONNECT_LITERAL.search(block.group(1)):
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


def _words(text: str) -> Set[str]:
    return set(re.findall(rf"(?<![\w-]){_WORD}(?![\w-])", text.upper()))


def _procedure_text(unit: _ProgramUnit) -> str:
    """Whole PROCEDURE DIVISION (DECLARATIVES included), literals masked."""
    return " ".join(mask_literals(text) for _, text, _ in unit.proc)


def check_file_status(file_path: str, unit: _ProgramUnit) -> List[AnalysisIssue]:
    """COBOL011 (no FILE STATUS clause) and COBOL012 (status never referenced)."""
    issues: List[AnalysisIssue] = []
    sort_files = {m.group(1).upper() for _, t in unit.data for m in _SD.finditer(mask_literals(t))}
    proc_text = _procedure_text(unit)
    proc_words = _words(proc_text)
    opened: Set[str] = set()
    for match in _OPEN.finditer(proc_text):
        opened |= _words(match.group(1)) - {"INPUT", "OUTPUT", "I-O", "EXTEND", "REVERSED"}
    proc_has_copy = bool(_COPY.search(proc_text))
    entries: Optional[List[Tuple[int, str]]] = None
    for sentence in split_sentences(unit.env):
        select = _SELECT.search(sentence.text)
        if not select:
            continue
        fname = select.group(1).upper()
        if fname in sort_files:
            continue
        status = _STATUS_CLAUSE.search(sentence.text[select.end() :])
        if not status:
            issues.append(
                _issue(
                    file_path,
                    sentence.line,
                    AnalysisIssueType.COBOL_FILE_STATUS_MISSING,
                    AnalysisIssueSeverity.MEDIUM,
                    f"File '{fname}' has no FILE STATUS clause. I/O errors cannot be "
                    "detected and the program may continue with bad data or abend.",
                    "Add FILE STATUS IS <2-byte field> to the SELECT and check it after "
                    "each OPEN/READ/WRITE/CLOSE.",
                    "COBOL011",
                    0.8,
                )
            )
            continue
        if fname not in opened or proc_has_copy:
            continue
        if entries is None:
            entries = _data_entries(unit)
        related = _related_names(entries, status.group(1).upper())
        if related is None or related & proc_words:
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
                if not _ONLY_TERMINATORS.match(later.text):
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
    referenced: Set[str] = set()
    for line_num, text, _ in unit.proc:
        words = _words(mask_literals(text))
        words.discard(headers.get(line_num, ""))
        referenced |= words
    return referenced


def _goto_targets(proc_text: str) -> Set[str]:
    targets: Set[str] = set()
    for match in _GO_TO.finditer(proc_text):
        targets.add(match.group(1).upper())
        if match.group(2):
            targets |= _words(match.group(2))
    return targets


def _thru_covered(proc_text: str, index: Dict[str, int]) -> Set[int]:
    """Indexes of items inside a THRU range (everything from start to end runs)."""
    covered: Set[int] = set()
    for match in re.finditer(rf"\b({_WORD})\s+(?:THRU|THROUGH)\s+({_WORD})", proc_text, re.I):
        start, end = index.get(match.group(1).upper()), index.get(match.group(2).upper())
        if start is not None and end is not None and start <= end:
            covered.update(range(start, end + 1))
    return covered


def _reachable(items: List[_ProcItem], referenced: Set[str], goto_targets: Set[str]) -> List[bool]:
    """Fall-through reachability from the entry point (and GO TO / ENTRY targets)."""
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
            falls_in = reached[n - 1] and not _ends_paragraph(prev)
        has_entry = any(_ENTRY.match(s.text) for s in item.sentences)
        reached[n] = falls_in or item.name in goto_targets or has_entry
    return reached


def _runs_inside_section(
    items: List[_ProcItem], n: int, index: Dict[str, int], reached: List[bool], referenced: Set[str]
) -> bool:
    """A reached or PERFORMed section runs its paragraphs in order until a terminator."""
    item = items[n]
    sec_idx = index.get(item.section or "")
    if item.is_section or sec_idx is None:
        return False
    if not (reached[sec_idx] or items[sec_idx].name in referenced):
        return False
    return not any(_ends_paragraph(items[k]) for k in range(sec_idx, n))


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
    reached = _reachable(items, referenced, _goto_targets(proc_text))

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
            or _runs_inside_section(items, n, index, reached, referenced)
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


def run_program_rules(
    file_path: str, logical_lines: List[LogicalLine], is_copybook: bool
) -> List[AnalysisIssue]:
    """Run COBOL008-COBOL014 on the logical lines of one file."""
    issues: List[AnalysisIssue] = []
    for unit in split_program_units(logical_lines):
        issues.extend(check_value_secrets(file_path, unit))
        all_lines = [(n, t) for n, t in unit.data + unit.env] + [(n, t) for n, t, _ in unit.proc]
        issues.extend(check_connection_string_secrets(file_path, sorted(all_lines)))
        if is_copybook:
            continue
        issues.extend(check_sql_connect_literal(file_path, unit.proc))
        items = build_procedure(unit.proc)
        issues.extend(check_file_status(file_path, unit))
        if unit.proc:
            issues.extend(check_dead_code(file_path, items))
            issues.extend(check_unused_paragraphs(file_path, unit, items))
    return issues
