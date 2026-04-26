"""
COBOL Governance Analyzer for Hefesto v4.12.0 — Legacy Support Phase 1.

Detects 7 governance issues in COBOL-85 + IBM Enterprise COBOL code:

FREE Tier (3 rules):
1. GOTO_EXCESSIVE: >10 GO TO statements (HIGH severity)
2. HARDCODED_CREDENTIALS: Hardcoded passwords/secrets in MOVE (CRITICAL severity)
3. ACCEPT: Unvalidated external input via ACCEPT (MEDIUM severity)

PRO Tier (4 rules):
4. REDEFINES_SENSITIVE: REDEFINES on packed decimal/signed fields (HIGH severity)
5. OCCURS_DEPENDING_ON: Variable-length tables (MEDIUM severity)
6. PERFORM_THRU_CHAIN: PERFORM THRU spanning >5 paragraphs (HIGH severity)
7. COPYBOOK_BLAST_RADIUS: Shared copybook usage (CRITICAL/HIGH severity)

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple

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
    redefines_clauses: List[Tuple[int, str, str, bool]] = field(default_factory=list)
    occurs_depending: List[Tuple[int, str]] = field(default_factory=list)
    perform_thru: List[Tuple[int, str, str]] = field(default_factory=list)
    copy_statements: List[Tuple[int, str]] = field(default_factory=list)
    paragraphs: List[Tuple[str, int]] = field(default_factory=list)


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

    # Packed decimal pattern
    COMP3_PATTERN = re.compile(r"PIC\s+S9.*COMP-3", re.IGNORECASE)
    SIGNED_PATTERN = re.compile(r"PIC\s+S9", re.IGNORECASE)

    # Generic copybook names (high blast radius) - exact match only
    GENERIC_COPYBOOKS = {"COMMON", "UTILS", "SHARED", "CUSTOMER", "ACCOUNT"}

    def extract(self, code: str) -> _CobolStructure:
        """Extract structural elements from COBOL source."""
        structure = _CobolStructure()
        lines = code.split("\n")

        # Detect format
        is_fixed_format = self._detect_fixed_format(lines)

        # Extract logical lines (handle continuations, strip comments)
        logical_lines = self._build_logical_lines(lines, is_fixed_format)

        # Extract elements from logical lines
        for line_num, logical_line in logical_lines:
            self._extract_goto(logical_line, line_num, structure)
            self._extract_credential_move(logical_line, line_num, structure)
            self._extract_accept(logical_line, line_num, structure)
            self._extract_redefines(logical_line, line_num, structure)
            self._extract_perform_thru(logical_line, line_num, structure)
            self._extract_copy(logical_line, line_num, structure)
            self._extract_paragraph(logical_line, line_num, structure)

        # OCCURS DEPENDING ON can span lines - search in full code
        self._extract_occurs_depending_multiline(code, structure)

        return structure

    def _detect_fixed_format(self, lines: List[str]) -> bool:
        """Detect if source uses fixed-format (columns 7-72) or free-format."""
        for line in lines[:20]:  # Sample first 20 lines
            if ">>SOURCE FORMAT IS FREE" in line.upper():
                return False
            # Fixed-format typically has sequence numbers in cols 1-6
            if len(line) > 6 and line[6] in self.COMMENT_INDICATORS:
                return True
        return True  # Default to fixed-format

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
        match = re.search(
            r"\bMOVE\s+(['\"])(.+?)\1\s+TO\s+([A-Z0-9_-]+)", line, re.IGNORECASE
        )
        if match:
            literal_value = match.group(2)
            target_field = match.group(3)

            # Check if target field name suggests credentials
            if self.CREDENTIAL_PATTERNS.search(target_field):
                structure.credential_moves.append((line_num, target_field, literal_value))

    def _extract_accept(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract ACCEPT statements (exclude FROM DATE/TIME/DAY)."""
        # Match ACCEPT statement (must be preceded by whitespace or start of line)
        # Excludes false positives like "PROGRAM-ID. ACCEPT-SAFE"
        if re.search(r"(?:^|\s)\bACCEPT\s+", line, re.IGNORECASE):
            # Exclude system calls - must check for FROM followed by system keywords
            if not re.search(r"\bFROM\s+(DATE|TIME|DAY|DAY-OF-WEEK)\b", line, re.IGNORECASE):
                structure.accept_statements.append(line_num)

    def _extract_redefines(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract REDEFINES clauses on packed decimal/signed fields."""
        # Pattern: NN FIELD-NAME REDEFINES ORIGINAL-FIELD
        match = re.search(
            r"\b(\d{2})\s+([A-Z0-9_-]+)\s+REDEFINES\s+([A-Z0-9_-]+)", line, re.IGNORECASE
        )
        if match:
            redefining_field = match.group(2)
            original_field = match.group(3)

            # Check if this is sensitive (need to look at previous lines for PIC COMP-3)
            # For Phase 1, we'll flag all REDEFINES as potentially sensitive
            # and rely on context to determine if it's on COMP-3
            is_sensitive = bool(self.COMP3_PATTERN.search(line) or self.SIGNED_PATTERN.search(line))

            structure.redefines_clauses.append(
                (line_num, original_field, redefining_field, is_sensitive)
            )

    def _extract_occurs_depending_multiline(self, code: str, structure: _CobolStructure):
        """Extract OCCURS DEPENDING ON clauses (multi-line aware)."""
        # Strip comments first
        clean_lines = []
        for line in code.split("\n"):
            if len(line) > 6 and line[6] in self.COMMENT_INDICATORS:
                continue
            # Get code area (columns 7-72)
            code_part = line[6:72] if len(line) > 72 else line[6:]
            clean_lines.append(code_part)

        # Join lines and search for pattern
        clean_code = " ".join(clean_lines)

        # Find all OCCURS ... DEPENDING ON patterns
        pattern = r"\bOCCURS\b.*?\bDEPENDING\s+ON\s+([A-Z0-9_-]+)"
        for match in re.finditer(pattern, clean_code, re.IGNORECASE):
            controlling_var = match.group(1)
            # Approximate line number (use 1 as placeholder - could improve)
            structure.occurs_depending.append((1, controlling_var))

    def _extract_perform_thru(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract PERFORM THRU statements."""
        match = re.search(
            r"\bPERFORM\s+([A-Z0-9_-]+)\s+THRU\s+([A-Z0-9_-]+)", line, re.IGNORECASE
        )
        if match:
            start_para = match.group(1)
            end_para = match.group(2)
            structure.perform_thru.append((line_num, start_para, end_para))

    def _extract_copy(self, line: str, line_num: int, structure: _CobolStructure):
        """Extract COPY statements."""
        match = re.search(r"\bCOPY\s+([A-Z0-9_-]+)", line, re.IGNORECASE)
        if match:
            copybook_name = match.group(1).upper()
            structure.copy_statements.append((line_num, copybook_name))

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

    def __init__(self):
        self._extractor = _CobolStructuralExtractor()

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        """Analyze COBOL code for governance issues."""
        issues: List[AnalysisIssue] = []

        # Extract structural elements
        structure = self._extractor.extract(content)

        # Copybooks (.cpy files) contain data definitions, not procedure code
        # Skip procedural rules for copybooks
        is_copybook = file_path.lower().endswith(".cpy")

        if not is_copybook:
            # Apply FREE tier rules (procedural)
            issues.extend(self._check_goto_excessive(file_path, structure))
            issues.extend(self._check_hardcoded_credentials(file_path, structure))
            issues.extend(self._check_accept_unvalidated(file_path, structure))

            # Apply PRO tier rules (gated)
            if self._is_pro_tier_available():
                issues.extend(self._check_redefines_sensitive(file_path, structure))
                issues.extend(self._check_occurs_depending(file_path, structure))
                issues.extend(self._check_perform_thru_chain(file_path, structure))
                issues.extend(self._check_copybook_blast_radius(file_path, structure))

        return issues

    def _is_pro_tier_available(self) -> bool:
        """Check if PRO tier is available.

        TODO: Replace with real tier detection from license key.
        For MVP/investor demo, allow all rules.
        """
        return True

    def _check_goto_excessive(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 1 (FREE): GOTO_EXCESSIVE — >10 GO TO statements."""
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
        """Rule 2 (FREE): HARDCODED_CREDENTIALS — hardcoded passwords/secrets."""
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
        """Rule 3 (FREE): ACCEPT — unvalidated external input."""
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

    def _check_redefines_sensitive(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 4 (PRO): REDEFINES_SENSITIVE — REDEFINES on packed decimal/signed fields."""
        issues = []

        for line_num, original_field, redefining_field, is_sensitive in structure.redefines_clauses:
            # For Phase 1, we flag all REDEFINES as potentially sensitive
            # In Phase 2, we would track field definitions to verify COMP-3
            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=0,
                    issue_type=AnalysisIssueType.COBOL_REDEFINES_SENSITIVE,
                    severity=AnalysisIssueSeverity.HIGH,
                    message=(
                        f"REDEFINES clause reinterprets '{original_field}' as "
                        f"'{redefining_field}'. Data integrity risk if original "
                        "field is packed decimal (COMP-3)."
                    ),
                    suggestion="Verify that both fields have compatible PIC clauses.",
                    engine=self.ENGINE,
                    rule_id="COBOL004",
                    confidence=0.85,
                )
            )

        return issues

    def _check_occurs_depending(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 5 (PRO): OCCURS_DEPENDING_ON — variable-length tables."""
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
                        "Validate that controlling variable is properly "
                        "initialized and bounded."
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
        """Rule 6 (PRO): PERFORM_THRU_CHAIN — PERFORM THRU spanning >5 paragraphs."""
        issues = []

        # Build paragraph index
        paragraph_index = {name: idx for idx, (name, _) in enumerate(structure.paragraphs)}

        for line_num, start_para, end_para in structure.perform_thru:
            start_idx = paragraph_index.get(start_para)
            end_idx = paragraph_index.get(end_para)

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
                            f"({start_para} THRU {end_para}). Fragile execution chain.",
                            suggestion="Break into smaller PERFORM blocks or use single PERFORM.",
                            engine=self.ENGINE,
                            rule_id="COBOL006",
                            confidence=0.70,
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
                        "Could not determine paragraph count (partial detection).",
                        suggestion="Verify that execution range is not excessive.",
                        engine=self.ENGINE,
                        rule_id="COBOL006",
                        confidence=0.60,
                    )
                )

        return issues

    def _check_copybook_blast_radius(
        self, file_path: str, structure: _CobolStructure
    ) -> List[AnalysisIssue]:
        """Rule 7 (PRO): COPYBOOK_BLAST_RADIUS — shared copybook usage."""
        issues = []

        for line_num, copybook_name in structure.copy_statements:
            # Determine severity based on copybook name
            is_generic = any(
                generic in copybook_name for generic in _CobolStructuralExtractor.GENERIC_COPYBOOKS
            )

            severity = AnalysisIssueSeverity.CRITICAL if is_generic else AnalysisIssueSeverity.HIGH
            confidence = 0.60  # Phase 1 can't count cross-project references

            issues.append(
                AnalysisIssue(
                    file_path=file_path,
                    line=line_num,
                    column=0,
                    issue_type=AnalysisIssueType.COBOL_COPYBOOK_BLAST_RADIUS,
                    severity=severity,
                    message=f"Copybook '{copybook_name}' referenced. "
                    "Changes to shared copybooks affect all dependent programs. "
                    "Phase 2 will provide cross-project reference counts.",
                    suggestion="Document copybook dependencies and assess impact before modifying.",
                    engine=self.ENGINE,
                    rule_id="COBOL007",
                    confidence=confidence,
                )
            )

        return issues
