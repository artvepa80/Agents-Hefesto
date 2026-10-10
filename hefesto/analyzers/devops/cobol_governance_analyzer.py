"""
COBOL Governance Analyzer for Hefesto v4.12.0 — Legacy Support Phase 1.

Detects 15 governance issues in COBOL-85 + IBM Enterprise COBOL code.
All 15 rules are FREE (no license required):

1. GOTO_EXCESSIVE: >10 GO TO statements (HIGH severity)
2. HARDCODED_CREDENTIALS: literal MOVEd into a field whose name looks like a
   credential (PASSWORD, TOKEN, ...) (CRITICAL severity)
3. ACCEPT: Unvalidated external input via ACCEPT (MEDIUM severity)
4. REDEFINES_SENSITIVE: a REDEFINES where one side holds packed, binary,
   float, pointer or signed numeric data and the two layouts differ; runs on
   programs and copybooks (HIGH severity). Lives in ``cobol_program_rules``.
5. OCCURS_DEPENDING_ON: one finding per data entry with OCCURS ... DEPENDING
   ON; the CICS ``DEPENDING ON EIBCALEN`` commarea idiom is skipped (MEDIUM)
6. PERFORM_THRU_CHAIN: PERFORM THRU spanning >5 paragraphs (HIGH severity)
7. COPYBOOK_BLAST_RADIUS: reported once on the copybook file when 5 or more
   scanned programs COPY it (MEDIUM; HIGH at 15+ programs or a generic name
   such as COMMON/UTILS/SHARED). Needs a project index (``CobolProjectIndex``);
   vendor copybooks (CICS DFH*, IBM MQ CMQ*, DB2 SQLCA/SQLDA) are skipped.
15. COPYBOOK_NOT_FOUND: a COPY whose copybook is not in the scanned tree
   (LOW), only when the index resolves at least one COPY of the scan.

COBOL008-COBOL014 (VALUE secrets, connection-string secrets, EXEC SQL CONNECT
literal passwords, FILE STATUS missing (grouped per program, LOW)/unchecked,
dead code, unused paragraphs) live in ``cobol_program_rules``.

Source format: a ``>>SOURCE FORMAT IS FREE`` / ``FIXED`` directive (or the
Micro Focus ``$SET SOURCEFORMAT(...)`` form) in the first 50 lines decides the
format. Without a directive, free format is inferred when a division header
(or, in a copybook, a level-01/77 entry) starts before column 8; otherwise
fixed format (columns 7-72) is assumed.

COPY expansion: with a project index, a program is analyzed with each COPY
(and EXEC SQL INCLUDE) replaced by the copybook text, REPLACING applied (see
``cobol_copy_expansion``). Findings on copybook text are reported at the
program's COPY line with ``metadata["expanded_from"]``; COBOL004/008/009 on
an unchanged line of a scanned copybook are left to the copybook file itself.
Copybook files are analyzed as written.

Repeated identical findings are grouped per file: one COBOL006 finding per
``PERFORM X THRU Y`` pair, one COBOL015 finding per missing copybook name and
one COBOL011 finding per program, with the occurrence count and lines in
``metadata``.

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from hefesto.analyzers.devops.cobol_copy_expansion import CopyExpander, Origin
from hefesto.analyzers.devops.cobol_program_rules import (
    occurs_depending,
    run_program_rules,
    split_program_units,
)
from hefesto.analyzers.devops.cobol_project_index import (
    SYSTEM_COPYBOOK_PREFIXES,
    SYSTEM_COPYBOOKS,
    CobolProjectIndex,
    copy_names,
    is_copybook_path,
    is_system_copybook,
    stem_of,
)
from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


@dataclass
class _CobolStructure:
    """
    Internal structural representation of COBOL source.

    Not exported as public API — used only within CobolGovernanceAnalyzer.
    """

    goto_statements: List[int] = field(default_factory=list)
    credential_moves: List[Tuple[int, str, str]] = field(default_factory=list)
    accept_statements: List[int] = field(default_factory=list)
    occurs_depending: List[Tuple[int, str]] = field(default_factory=list)
    perform_thru: List[Tuple[int, str, str]] = field(default_factory=list)
    copy_statements: List[Tuple[int, str]] = field(default_factory=list)
    paragraphs: List[Tuple[str, int]] = field(default_factory=list)
    # (line number, text, starts in Area A) for the program-level rules
    logical_lines: List[Tuple[int, str, bool]] = field(default_factory=list)
    # split_program_units(logical_lines), computed once for all rules
    units: List[Any] = field(default_factory=list)
    # After COPY expansion the line numbers above are positions in the
    # expanded text; origins[n - 1] says where line n really comes from.
    origins: Optional[List[Union[int, Origin]]] = None


class _CobolStructuralExtractor:
    """
    Internal extractor for COBOL structural elements (regex-based).

    Handles fixed-format (columns 7-72) and free-format detection.
    """

    # Fixed-format indicators (column 7)
    COMMENT_INDICATORS = {"*", "/"}
    CONTINUATION_INDICATOR = "-"
    DEBUG_INDICATOR = "D"

    # Credential field name patterns
    CREDENTIAL_PATTERNS = re.compile(
        r"(?:PASSWORD|PASSWD|PWD|SECRET|API[_-]?KEY|APIKEY|TOKEN|CREDENTIAL|AUTH[_-]?KEY)",
        re.IGNORECASE,
    )

    # Fields whose name contains a credential word but that hold a flag, a
    # status, a length or a display label, not the secret itself
    # (e.g. WS-PASSWORD-OK-FLAG, PWD-LEN, PASSWORD-PROMPT).
    NON_SECRET_SUFFIX = re.compile(
        r"-(?:FLAG|FLG|SW|SWITCH|IND|INDICATOR|OK|VALID|STATUS|STAT|LEN|LENGTH"
        r"|MSG|MESSAGE|PROMPT|LABEL|LIT|ERR|ERROR)$",
        re.IGNORECASE,
    )

    # Generic copybook names (raise COBOL007 one severity step). Matched as a
    # whole name part ("CUSTOMER-REC" yes, "ACCOUNTANT" no).
    GENERIC_COPYBOOKS = {"COMMON", "UTILS", "UTIL", "SHARED", "CUSTOMER", "ACCOUNT"}

    # Vendor-supplied copybooks (CICS DFH*, DB2 SQLCA/SQLDA): not user code,
    # so changing them is not a blast-radius risk of the analyzed project.
    SYSTEM_COPYBOOK_PREFIXES = SYSTEM_COPYBOOK_PREFIXES
    SYSTEM_COPYBOOKS = SYSTEM_COPYBOOKS

    FREE_DIRECTIVE = re.compile(
        r">>\s*SOURCE\s+(?:FORMAT\s+)?(?:IS\s+)?FREE\b"
        r"|\$\s*SET\s+.*SOURCEFORMAT\s*\(?\s*[\"']?FREE",
        re.IGNORECASE,
    )
    FIXED_DIRECTIVE = re.compile(
        r">>\s*SOURCE\s+(?:FORMAT\s+)?(?:IS\s+)?FIXED\b"
        r"|\$\s*SET\s+.*SOURCEFORMAT\s*\(?\s*[\"']?FIXED",
        re.IGNORECASE,
    )
    DIVISION_HEADER = re.compile(
        r"^( *)(?:IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b",
        re.IGNORECASE,
    )
    COPYBOOK_ENTRY = re.compile(r"^( *)(?:01|77)\s+[A-Z0-9]", re.IGNORECASE)

    def __init__(self) -> None:
        # How the format of the last extracted source was decided
        # ("directive-free", "directive-fixed", "inferred-free", "default-fixed").
        self.last_format_reason = "default-fixed"

    _GOTO = re.compile(r"\bGO\s+TO\b", re.IGNORECASE)
    _CREDENTIAL_MOVE = re.compile(r"\bMOVE\s+(['\"])(.+?)\1\s+TO\s+([A-Z0-9_-]+)", re.IGNORECASE)
    _ACCEPT = re.compile(r"(?:^|\s)\bACCEPT\s+", re.IGNORECASE)
    _ACCEPT_SYSTEM = re.compile(r"\bFROM\s+(DATE|TIME|DAY|DAY-OF-WEEK)\b", re.IGNORECASE)
    _PERFORM_THRU = re.compile(r"\bPERFORM\s+([A-Z0-9_-]+)\s+THRU\s+([A-Z0-9_-]+)", re.IGNORECASE)
    _PARAGRAPH = re.compile(r"^([A-Z0-9_-]+)\.\s*$", re.IGNORECASE)

    def extract(
        self,
        code: str,
        copy_statements: Optional[List[Tuple[int, str]]] = None,
        expander: Optional[CopyExpander] = None,
        path: str = "",
    ) -> _CobolStructure:
        """Extract structural elements (COPY expanded first with an ``expander``)."""
        structure = _CobolStructure()
        lines = code.split("\n")

        # Detect format
        is_fixed_format = self._detect_fixed_format(lines)

        # Extract logical lines (handle continuations, strip comments)
        logical_lines = self._build_logical_lines(lines, is_fixed_format)
        structure.logical_lines = [
            (num, text, self._starts_in_area_a(lines[num - 1], is_fixed_format))
            for num, text in logical_lines
        ]
        del logical_lines, lines  # bounded memory on huge files
        _expand_copies(structure, expander, path)

        # Extract elements from logical lines (cheap substring tests first)
        for line_num, logical_line, _ in structure.logical_lines:
            upper = logical_line.upper()
            if "GO" in upper:
                self._extract_goto(logical_line, line_num, structure)
            if "MOVE" in upper:
                self._extract_credential_move(logical_line, line_num, structure)
            if "ACCEPT" in upper:
                self._extract_accept(logical_line, line_num, structure)
            if "THRU" in upper:
                self._extract_perform_thru(logical_line, line_num, structure)
            if logical_line.endswith(".") or logical_line.rstrip().endswith("."):
                self._extract_paragraph(logical_line, line_num, structure)

        # COPY and EXEC SQL INCLUDE (INCLUDE can span lines inside EXEC SQL);
        # the project index passes the names it already read for this file.
        structure.copy_statements = (
            copy_statements if copy_statements is not None else copy_names(code, is_fixed_format)
        )

        # OCCURS DEPENDING ON can span lines: read it per data-division entry
        structure.units = split_program_units(structure.logical_lines)
        structure.occurs_depending = occurs_depending(structure.logical_lines, structure.units)

        return structure

    def _detect_fixed_format(self, lines: List[str]) -> bool:
        """Detect if source uses fixed-format (columns 7-72) or free-format.

        1. An explicit directive in the first 50 lines wins.
        2. Otherwise, a division header (or, for copybooks, a level-01/77 entry)
           that starts before column 8 means free format: in fixed format,
           Area A starts at column 8, so such a line could not be valid there.
        3. Otherwise fixed format is assumed.
        """
        for line in lines[:50]:
            if self.FREE_DIRECTIVE.search(line):
                self.last_format_reason = "directive-free"
                return False
            if self.FIXED_DIRECTIVE.search(line):
                self.last_format_reason = "directive-fixed"
                return True

        if self._indent_means_free(lines):
            self.last_format_reason = "inferred-free"
            return False
        self.last_format_reason = "default-fixed"
        return True

    def _indent_means_free(self, lines: List[str]) -> bool:
        """A division header (else a level-01/77 entry) starting before column 8."""
        saw_division = False
        for raw in lines:
            if "ivision" not in raw.lower():
                continue  # cheap filter before the regex
            match = self.DIVISION_HEADER.match(raw.expandtabs(8))
            if match:
                saw_division = True
                if len(match.group(1)) < 7:
                    return True
        if saw_division:
            return False
        for raw in lines:
            match = self.COPYBOOK_ENTRY.match(raw.expandtabs(8))
            if match and len(match.group(1)) < 7:
                return True
        return False

    @staticmethod
    def _starts_in_area_a(line: str, is_fixed_format: bool) -> bool:
        """True if the code starts in Area A (columns 8-11). Unknown in free format."""
        if not is_fixed_format:
            return True
        code = line[7:72]
        if "\t" in code:
            code = code.expandtabs(4)
        stripped = code.lstrip()
        return bool(stripped) and len(code) - len(stripped) < 4

    def logical_lines_of(self, code: str) -> List[Tuple[int, str, bool]]:
        """(line, text, starts in Area A) of a source in its own format."""
        lines = code.split("\n")
        fixed = self._detect_fixed_format(lines)
        return [
            (num, text, self._starts_in_area_a(lines[num - 1], fixed))
            for num, text in self._build_logical_lines(lines, fixed)
        ]

    def _build_logical_lines(
        self, lines: List[str], is_fixed_format: bool
    ) -> List[Tuple[int, str]]:
        """Build logical lines from physical lines (handle continuations, strip comments)."""
        logical_lines = []
        current_line = ""
        current_line_num = 0

        for line_num, line in enumerate(lines, start=1):
            if is_fixed_format:
                if len(line) < 7:
                    continue  # Skip short lines

                indicator = line[6] if len(line) > 6 else " "

                # Skip comment lines
                if indicator in self.COMMENT_INDICATORS:
                    continue

                # Extract code area (columns 7-72)
                code_part = line[6:72] if len(line) > 72 else line[6:]

                if indicator == self.CONTINUATION_INDICATOR:
                    current_line = _join_continuation(current_line, code_part[1:].strip())
                else:
                    # New logical line
                    if current_line:
                        logical_lines.append((current_line_num, current_line))
                    current_line = code_part.strip()
                    current_line_num = line_num
            else:
                # Free-format: strip comments starting with *>
                if line.strip().startswith("*>"):
                    continue
                code_part = line.split("*>")[0].strip()
                if code_part:
                    logical_lines.append((line_num, code_part))

        # Don't forget last logical line
        if current_line:
            logical_lines.append((current_line_num, current_line))

        return logical_lines

    def _extract_goto(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract GO TO statements."""
        if self._GOTO.search(line):
            structure.goto_statements.append(line_num)

    def _extract_credential_move(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract MOVE literal TO credential-field statements."""
        # Pattern: MOVE 'literal' TO FIELD-NAME or MOVE "literal" TO FIELD-NAME
        match = self._CREDENTIAL_MOVE.search(line)
        if match:
            literal_value = match.group(2)
            target_field = match.group(3)

            # Check if target field name suggests credentials
            if self.CREDENTIAL_PATTERNS.search(target_field) and not self.NON_SECRET_SUFFIX.search(
                target_field
            ):
                structure.credential_moves.append((line_num, target_field, literal_value))

    def _extract_accept(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract ACCEPT statements (exclude FROM DATE/TIME/DAY)."""
        # Match ACCEPT statement (must be preceded by whitespace or start of line)
        # Excludes false positives like "PROGRAM-ID. ACCEPT-SAFE"
        if self._ACCEPT.search(line):
            # Exclude system calls - must check for FROM followed by system keywords
            if not self._ACCEPT_SYSTEM.search(line):
                structure.accept_statements.append(line_num)

    def _extract_perform_thru(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract PERFORM THRU statements."""
        match = self._PERFORM_THRU.search(line)
        if match:
            start_para = match.group(1)
            end_para = match.group(2)
            structure.perform_thru.append((line_num, start_para, end_para))

    def _extract_paragraph(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract paragraph names (Area A identifiers ending with period)."""
        # Paragraph names typically start at column 8 (Area A) and end with period
        # For logical lines, we can't rely on column position, so use heuristic:
        # Line starts with identifier and ends with period, no spaces before period
        match = self._PARAGRAPH.match(line)
        if match:
            para_name = match.group(1).upper()
            structure.paragraphs.append((para_name, line_num))


def _expand_copies(structure: _CobolStructure, expander: Optional[CopyExpander], path: str) -> None:
    """Put copybook text in place of COPY (see ``cobol_copy_expansion``).

    Line numbers then become positions in the expanded text;
    ``structure.origins`` maps them back to the program and copybooks.
    """
    if expander is None:
        return
    expanded = expander.expand(path, structure.logical_lines)
    if expanded is not None:
        structure.origins = [origin for origin, _, _ in expanded]
        structure.logical_lines = [
            (num, text, area_a) for num, (_, text, area_a) in enumerate(expanded, start=1)
        ]


def _point_to_program(
    issue: AnalysisIssue, origin: Optional[Origin], program_line: Callable[[int], int]
) -> None:
    """Rewrite an issue's lines (line, message, metadata) to program lines."""
    issue.message = _LINE_REF.sub(lambda m: f"line {program_line(int(m.group(1)))}", issue.message)
    metadata = dict(issue.metadata or {})
    if isinstance(metadata.get("lines"), list):
        metadata["lines"] = sorted({program_line(n) for n in metadata["lines"]})
    if origin is not None:
        metadata["expanded_from"] = {
            "copybook": origin.copybook,
            "file": origin.path,
            "line": origin.line,
            "copy_lines": [line for _, line in origin.via],
            "replaced": origin.replaced,
        }
        issue.message += (
            f" (in copybook {origin.copybook}, line {origin.line}; "
            f"COPY at line {origin.via[0][1]})"
        )
    issue.line = program_line(issue.line)
    if metadata:
        issue.metadata = metadata


def _join_continuation(current: str, text: str) -> str:
    """Append a fixed-format continuation line (indicator '-') to a logical line.

    A continued alphanumeric literal resumes after the quote that opens the
    continuation line, so ``'...PW`` + ``'D=x'`` reads ``'...PWD=x'``. Anything
    else is joined with a space.
    """
    if text[:1] in ("'", '"') and current.count(text[0]) % 2 == 1:
        return current + text[1:]
    return f"{current} {text}" if current else text


class CobolGovernanceAnalyzer:
    """Analyzes COBOL code for governance and risk issues."""

    ENGINE = "internal:cobol_governance"

    # COBOL007: programs that COPY a copybook before it is reported
    BLAST_RADIUS_MEDIUM = 5
    BLAST_RADIUS_HIGH = 15

    def __init__(self, index: Optional[CobolProjectIndex] = None) -> None:
        self._extractor = _CobolStructuralExtractor()
        self._index = index

    @property
    def last_format_reason(self) -> str:
        """How the source format of the last analyzed file was decided."""
        return self._extractor.last_format_reason

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """Analyze COBOL code for governance issues."""
        issues: List[AnalysisIssue] = []

        # Copybooks (.cpy files) contain data definitions, not procedure code:
        # only the data rules (COBOL004, COBOL008, COBOL009), COBOL007 and
        # COBOL015 (a nested COPY that is missing) apply. They are analyzed
        # as written; programs are analyzed with their COPYs expanded.
        is_copybook = (
            self._index.is_copybook_file(file_path)
            if self._index is not None
            else is_copybook_path(file_path)
        )

        # Extract structural elements
        cached = self._index.copy_names_for(file_path) if self._index is not None else None
        expander = None if is_copybook else self._copy_expander()
        structure = self._extractor.extract(content, cached, expander, file_path)

        if not is_copybook:
            # COBOL001-COBOL006 (FREE; procedural rules, not applied to copybooks)
            issues.extend(self._check_goto_excessive(file_path, structure))
            issues.extend(self._check_hardcoded_credentials(file_path, structure))
            issues.extend(self._check_accept_unvalidated(file_path, structure))
            issues.extend(self._check_occurs_depending(file_path, structure))
            issues.extend(self._check_perform_thru_chain(file_path, structure))

        # COBOL004 and COBOL008-COBOL014 (FREE). COBOL004/008/009 also run on copybooks.
        issues.extend(
            run_program_rules(file_path, structure.logical_lines, is_copybook, structure.units)
        )
        if structure.origins is not None:
            issues = self._attribute_expanded(issues, structure.origins)

        # Index rules: their lines are the file's own (not expanded positions)
        if is_copybook:
            issues.extend(self._check_copybook_blast_radius(file_path))
        # COBOL015 also for a nested COPY inside a copybook
        issues.extend(self._check_copybook_not_found(file_path, structure))
        return issues

    def _copy_expander(self) -> Optional[CopyExpander]:
        """One expander per project index (its copybook cache is shared)."""
        index = self._index
        if index is None:
            return None
        if index.expander is None:
            build = _CobolStructuralExtractor().logical_lines_of
            index.expander = CopyExpander(
                index.resolve,
                lambda path: index.copybook_lines(path, build),
                is_system_copybook,
            )
        expander: CopyExpander = index.expander
        return expander

    def _attribute_expanded(
        self, issues: List[AnalysisIssue], origins: List[Union[int, Origin]]
    ) -> List[AnalysisIssue]:
        """Map expanded-text lines back to the program (and the copybook line).

        A finding on a copybook line is reported at the program's COPY
        statement, with the copybook file and line in ``metadata``. Data
        rules that already run on the copybook file itself (COBOL004/008/009)
        are not repeated in every program, unless REPLACING changed that line
        or the copybook is outside the scan (``copybook_paths``).
        """

        def program_line(line: int) -> int:
            origin = origins[line - 1] if 0 < line <= len(origins) else line
            return origin if isinstance(origin, int) else origin.via[0][1]

        out: List[AnalysisIssue] = []
        for issue in issues:
            found = origins[issue.line - 1] if 0 < issue.line <= len(origins) else None
            origin = found if isinstance(found, Origin) else None
            if origin is not None and self._reported_on_copybook(issue, origin):
                continue
            _point_to_program(issue, origin, program_line)
            out.append(issue)
        return out

    def _reported_on_copybook(self, issue: AnalysisIssue, origin: Origin) -> bool:
        """A data finding on an unchanged line of a scanned copybook."""
        return (
            issue.rule_id in _COPYBOOK_RULES
            and not origin.replaced
            and self._index is not None
            and self._index.is_scanned(origin.path)
        )

    def _check_goto_excessive(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 1: GOTO_EXCESSIVE — >10 GO TO statements."""
        issues = []
        goto_count = len(structure.goto_statements)

        if goto_count > 10:
            # Report on first GO TO line
            line = structure.goto_statements[0] if structure.goto_statements else 1

            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line,
                    column=0,
                    issue_type=AnalysisIssueType.COBOL_GOTO_EXCESSIVE,
                    severity=AnalysisIssueSeverity.HIGH,
                    message=f"Excessive GO TO statements: {goto_count} found (threshold: 10). "
                    "Spaghetti control flow is unmaintainable.",
                    suggestion="Refactor to use PERFORM with structured paragraphs.",
                    engine=self.ENGINE,
                    rule_id="COBOL001",
                    confidence=0.95,
                )
            )

        return issues

    def _check_hardcoded_credentials(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 2: HARDCODED_CREDENTIALS — hardcoded passwords/secrets."""
        issues = []

        for line_num, field_name, literal_value in structure.credential_moves:
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=0,
                    issue_type=AnalysisIssueType.COBOL_HARDCODED_CREDENTIALS,
                    severity=AnalysisIssueSeverity.CRITICAL,
                    message=f"Hardcoded credential in MOVE statement to field '{field_name}'. "
                    "Never store secrets in source code.",
                    suggestion="Use environment variables or secure credential stores.",
                    engine=self.ENGINE,
                    rule_id="COBOL002",
                    confidence=0.90,
                    metadata={"cwe": "CWE-798"},
                )
            )

        return issues

    def _check_accept_unvalidated(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 3: ACCEPT — unvalidated external input."""
        issues = []

        for line_num in structure.accept_statements:
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=0,
                    issue_type=AnalysisIssueType.COBOL_ACCEPT_UNVALIDATED,
                    severity=AnalysisIssueSeverity.MEDIUM,
                    message=(
                        "Unvalidated external input via ACCEPT. "
                        "Verify input is sanitized before use."
                    ),
                    suggestion="Add validation logic after ACCEPT statement.",
                    engine=self.ENGINE,
                    rule_id="COBOL003",
                    confidence=0.80,
                    metadata={"cwe": "CWE-20"},
                )
            )

        return issues

    def _check_occurs_depending(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 5: OCCURS_DEPENDING_ON — variable-length tables."""
        issues = []

        for line_num, controlling_var in structure.occurs_depending:
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=0,
                    issue_type=AnalysisIssueType.COBOL_OCCURS_DEPENDING_ON,
                    severity=AnalysisIssueSeverity.MEDIUM,
                    message=(
                        f"Variable-length table with OCCURS DEPENDING ON "
                        f"'{controlling_var}'. Runtime size ambiguity can cause "
                        "memory issues."
                    ),
                    suggestion=(
                        "Validate that controlling variable is properly " "initialized and bounded."
                    ),
                    engine=self.ENGINE,
                    rule_id="COBOL005",
                    confidence=0.90,
                )
            )

        return issues

    def _check_perform_thru_chain(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 6: PERFORM_THRU_CHAIN — PERFORM THRU spanning >5 paragraphs."""
        issues = []

        # Build paragraph index
        paragraph_index = {name: idx for idx, (name, _) in enumerate(structure.paragraphs)}

        for (start_para, end_para), lines in _group_occurrences(
            ((start, end), line) for line, start, end in structure.perform_thru
        ).items():
            line_num = lines[0]
            start_idx = paragraph_index.get(start_para.upper())
            end_idx = paragraph_index.get(end_para.upper())
            repeat = _occurrence_note(lines)

            if start_idx is not None and end_idx is not None:
                para_count = end_idx - start_idx + 1

                if para_count > 5:
                    issues.append(
                        AnalysisIssue(
                            file_path=file_path,
                            line=line_num,
                            column=0,
                            issue_type=AnalysisIssueType.COBOL_PERFORM_THRU_CHAIN,
                            severity=AnalysisIssueSeverity.HIGH,
                            message=f"PERFORM THRU spans {para_count} paragraphs "
                            f"({start_para} THRU {end_para}). Fragile execution chain."
                            f"{repeat}",
                            suggestion="Break into smaller PERFORM blocks or use single PERFORM.",
                            engine=self.ENGINE,
                            rule_id="COBOL006",
                            confidence=0.70,
                            metadata=_occurrence_metadata(lines),
                        )
                    )
            else:
                # Partial detection: can't count paragraphs
                issues.append(
                    AnalysisIssue(
                        file_path=file_path,
                        line=line_num,
                        column=0,
                        issue_type=AnalysisIssueType.COBOL_PERFORM_THRU_CHAIN,
                        severity=AnalysisIssueSeverity.HIGH,
                        message=f"PERFORM THRU from '{start_para}' to '{end_para}' detected. "
                        f"Could not determine paragraph count (partial detection).{repeat}",
                        suggestion="Verify that execution range is not excessive.",
                        engine=self.ENGINE,
                        rule_id="COBOL006",
                        confidence=0.60,
                        metadata=_occurrence_metadata(lines),
                    )
                )

        return issues

    def _check_copybook_blast_radius(self, file_path: str) -> List[AnalysisIssue]:
        """Rule 7: COPYBOOK_BLAST_RADIUS — a copybook COPYed by many scanned programs.

        Reported once, on the copybook file, with the dependent programs. Needs
        the project index; a copybook used by fewer than BLAST_RADIUS_MEDIUM
        programs is not reported.
        """
        name = stem_of(file_path)
        if self._index is None or not name or is_system_copybook(name):
            return []
        programs = self._index.dependent_programs(name)
        if len(programs) < self.BLAST_RADIUS_MEDIUM:
            return []
        high = len(programs) >= self.BLAST_RADIUS_HIGH or _is_generic_copybook(name)
        severity = AnalysisIssueSeverity.HIGH if high else AnalysisIssueSeverity.MEDIUM
        return [
            AnalysisIssue(
                file_path=file_path,
                line=1,
                column=0,
                issue_type=AnalysisIssueType.COBOL_COPYBOOK_BLAST_RADIUS,
                severity=severity,
                message=f"Copybook '{name}' is COPYed by {len(programs)} scanned programs. "
                "A change to it affects all of them.",
                suggestion="Review and test every dependent program before changing this "
                "copybook; consider versioning the layout.",
                engine=self.ENGINE,
                rule_id="COBOL007",
                confidence=0.9,
                metadata={
                    "dependents": len(programs),
                    "programs": [_short_path(p) for p in programs[:_MAX_LINES_IN_METADATA]],
                },
            )
        ]

    def _check_copybook_not_found(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 15: COPYBOOK_NOT_FOUND — COPY of a name that is not in the scanned tree."""
        index = self._index
        if index is None:
            return []
        grouped = _group_occurrences(
            (name, line) for line, name in structure.copy_statements if index.is_missing(name)
        )
        return [
            AnalysisIssue(
                file_path=file_path,
                line=lines[0],
                column=0,
                issue_type=AnalysisIssueType.COBOL_COPYBOOK_NOT_FOUND,
                severity=AnalysisIssueSeverity.LOW,
                message=f"Copybook '{name}' is not in the scanned files, so its data "
                "definitions and code were not analyzed (and the build may fail)."
                f"{_occurrence_note(lines)}",
                suggestion="Add the copybook directory to the scan, or fix the COPY name.",
                engine=self.ENGINE,
                rule_id="COBOL015",
                confidence=0.8,
                metadata=_occurrence_metadata(lines),
            )
            for name, lines in grouped.items()
        ]


_MAX_LINES_IN_METADATA = 50

# Rules that also run on copybook files (see analyze): a finding on an
# unchanged copybook line is reported there, not again in every program.
_COPYBOOK_RULES = {"COBOL004", "COBOL008", "COBOL009"}
_LINE_REF = re.compile(r"\bline (\d+)\b")

_K = TypeVar("_K", bound=Hashable)


def _group_occurrences(pairs: Iterable[Tuple[_K, int]]) -> Dict[_K, List[int]]:
    """Group (key, line) pairs by key, keeping first-seen order and line order."""
    grouped: Dict[_K, List[int]] = {}
    for key, line in pairs:
        grouped.setdefault(key, []).append(line)
    return grouped


def _occurrence_note(lines: List[int]) -> str:
    """Message suffix for a grouped finding (empty for a single occurrence)."""
    if len(lines) < 2:
        return ""
    return f" Occurs {len(lines)} times in this file (first at line {lines[0]})."


def _occurrence_metadata(lines: List[int]) -> Dict[str, Any]:
    return {"occurrences": len(lines), "lines": lines[:_MAX_LINES_IN_METADATA]}


def _is_generic_copybook(name: str) -> bool:
    parts = set(re.split(r"[-_]", name.upper()))
    return bool(parts & _CobolStructuralExtractor.GENERIC_COPYBOOKS)


def _short_path(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[-2:])
