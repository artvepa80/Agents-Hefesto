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

Repeated identical findings are grouped per file: one COBOL006 finding per
``PERFORM X THRU Y`` pair, one COBOL015 finding per missing copybook name and
one COBOL011 finding per program, with the occurrence count and lines in
``metadata``.

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, Iterable, List, Optional, Tuple, TypeVar

from hefesto.analyzers.devops.cobol_program_rules import occurs_depending, run_program_rules
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

    def extract(self, code: str) -> _CobolStructure:
        """Extract structural elements from COBOL source."""
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

        # Extract elements from logical lines
        for line_num, logical_line in logical_lines:
            self._extract_goto(logical_line, line_num, structure)
            self._extract_credential_move(logical_line, line_num, structure)
            self._extract_accept(logical_line, line_num, structure)
            self._extract_perform_thru(logical_line, line_num, structure)
            self._extract_copy(logical_line, line_num, structure)
            self._extract_paragraph(logical_line, line_num, structure)

        # OCCURS DEPENDING ON can span lines: read it per data-division entry
        structure.occurs_depending = occurs_depending(structure.logical_lines)

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

        saw_division = False
        for raw in lines:
            line = raw.expandtabs(8)
            match = self.DIVISION_HEADER.match(line)
            if match:
                saw_division = True
                if len(match.group(1)) < 7:
                    self.last_format_reason = "inferred-free"
                    return False
        if not saw_division:
            for raw in lines:
                match = self.COPYBOOK_ENTRY.match(raw.expandtabs(8))
                if match and len(match.group(1)) < 7:
                    self.last_format_reason = "inferred-free"
                    return False

        self.last_format_reason = "default-fixed"
        return True

    @staticmethod
    def _starts_in_area_a(line: str, is_fixed_format: bool) -> bool:
        """True if the code starts in Area A (columns 8-11). Unknown in free format."""
        if not is_fixed_format:
            return True
        code = line[7:72].expandtabs(4)
        return bool(code.strip()) and len(code) - len(code.lstrip()) < 4

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
                    # Continuation line
                    current_line += " " + code_part.strip()
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
        if re.search(r"\bGO\s+TO\b", line, re.IGNORECASE):
            structure.goto_statements.append(line_num)

    def _extract_credential_move(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract MOVE literal TO credential-field statements."""
        # Pattern: MOVE 'literal' TO FIELD-NAME or MOVE "literal" TO FIELD-NAME
        match = re.search(r"\bMOVE\s+(['\"])(.+?)\1\s+TO\s+([A-Z0-9_-]+)", line, re.IGNORECASE)
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
        if re.search(r"(?:^|\s)\bACCEPT\s+", line, re.IGNORECASE):
            # Exclude system calls - must check for FROM followed by system keywords
            if not re.search(r"\bFROM\s+(DATE|TIME|DAY|DAY-OF-WEEK)\b", line, re.IGNORECASE):
                structure.accept_statements.append(line_num)

    def _extract_perform_thru(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract PERFORM THRU statements."""
        match = re.search(r"\bPERFORM\s+([A-Z0-9_-]+)\s+THRU\s+([A-Z0-9_-]+)", line, re.IGNORECASE)
        if match:
            start_para = match.group(1)
            end_para = match.group(2)
            structure.perform_thru.append((line_num, start_para, end_para))

    def _extract_copy(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract COPY statements (outside literals; quoted names allowed)."""
        for _, name in copy_names(line):
            structure.copy_statements.append((line_num, name))

    def _extract_paragraph(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract paragraph names (Area A identifiers ending with period)."""
        # Paragraph names typically start at column 8 (Area A) and end with period
        # For logical lines, we can't rely on column position, so use heuristic:
        # Line starts with identifier and ends with period, no spaces before period
        match = re.match(r"^([A-Z0-9_-]+)\.\s*$", line, re.IGNORECASE)
        if match:
            para_name = match.group(1).upper()
            structure.paragraphs.append((para_name, line_num))


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

        # Extract structural elements
        structure = self._extractor.extract(content)

        # Copybooks (.cpy files) contain data definitions, not procedure code:
        # only the data rules (COBOL004, COBOL008, COBOL009) and COBOL007 apply.
        is_copybook = is_copybook_path(file_path)

        if not is_copybook:
            # COBOL001-COBOL006 (FREE; procedural rules, not applied to copybooks)
            issues.extend(self._check_goto_excessive(file_path, structure))
            issues.extend(self._check_hardcoded_credentials(file_path, structure))
            issues.extend(self._check_accept_unvalidated(file_path, structure))
            issues.extend(self._check_occurs_depending(file_path, structure))
            issues.extend(self._check_perform_thru_chain(file_path, structure))
            issues.extend(self._check_copybook_not_found(file_path, structure))
        else:
            issues.extend(self._check_copybook_blast_radius(file_path))

        # COBOL004 and COBOL008-COBOL014 (FREE). COBOL004/008/009 also run on copybooks.
        issues.extend(run_program_rules(file_path, structure.logical_lines, is_copybook))

        return issues

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
