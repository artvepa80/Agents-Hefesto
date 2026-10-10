"""
COBOL smoke regression tests (Phase 1 of the COBOL test plan).

Fixtures in tests/fixtures/cobol/smoke/ are small synthetic programs written for
these tests:

- bad_fixed.cbl: fixed format, with known problems.
- bad_free_directive.cbl / bad_free_nodirective.cbl: the same program in free
  format, with and without ``>>SOURCE FORMAT IS FREE``.
- clean.cbl: a well-behaved program (must produce no findings).
- false_positives.cbl: benign code that used to produce findings.

Tests marked xfail(strict=True) document known misses and false positives that
need new rules or tuning (Phase 3). When a rule starts catching them, the
xfail turns into XPASS and fails, so the marker must be removed on purpose.
"""

from pathlib import Path

import pytest

from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer
from hefesto.core.language_detector import LanguageDetector
from hefesto.core.languages.specs import Language

SMOKE_DIR = Path(__file__).parent / "fixtures" / "cobol" / "smoke"

BAD_EXPECTED = {
    ("COBOL001", 28),  # 11 GO TO statements
    ("COBOL002", 23),  # MOVE 'hunter2' TO WS-USER-PWD
    ("COBOL002", 24),  # MOVE "tok_live_..." TO WS-API-TOKEN
    ("COBOL004", 17),  # REDEFINES on a COMP-3 field
    ("COBOL007", 20),  # COPY MISSINGBK
}


def _analyze(name: str, content: str = None, filename: str = None):
    analyzer = CobolGovernanceAnalyzer()
    path = SMOKE_DIR / name
    text = content if content is not None else path.read_text()
    issues = analyzer.analyze(str(filename or path), text)
    return analyzer, issues


def _findings(issues):
    return {(i.rule_id, i.line) for i in issues}


class TestDetected:
    def test_bad_fixed_format(self):
        _, issues = _analyze("bad_fixed.cbl")
        assert _findings(issues) == BAD_EXPECTED

    def test_bad_free_with_directive(self):
        analyzer, issues = _analyze("bad_free_directive.cbl")
        assert analyzer.last_format_reason == "directive-free"
        assert {r for r, _ in _findings(issues)} == {r for r, _ in BAD_EXPECTED}

    def test_lowercase_source_same_findings(self):
        text = (SMOKE_DIR / "bad_fixed.cbl").read_text().lower()
        _, issues = _analyze("bad_fixed.cbl", content=text, filename="bad_lower.cob")
        assert {r for r, _ in _findings(issues)} == {r for r, _ in BAD_EXPECTED}

    def test_clean_program_has_no_findings(self):
        _, issues = _analyze("clean.cbl")
        assert issues == []

    def test_accept_from_console_is_flagged(self):
        _, issues = _analyze("false_positives.cbl")
        assert ("COBOL003", 20) in _findings(issues)


class TestFreeFormatDetection:
    def test_free_format_without_directive_is_inferred(self):
        analyzer, issues = _analyze("bad_free_nodirective.cbl")
        assert analyzer.last_format_reason == "inferred-free"
        assert {r for r, _ in _findings(issues)} == {r for r, _ in BAD_EXPECTED}

    def test_fixed_format_with_sequence_numbers_stays_fixed(self):
        analyzer, _ = _analyze("bad_fixed.cbl")
        assert analyzer.last_format_reason == "default-fixed"

    def test_fixed_format_without_sequence_numbers_stays_fixed(self):
        text = "\n".join(
            "      " + line[6:] for line in (SMOKE_DIR / "bad_fixed.cbl").read_text().splitlines()
        )
        analyzer, issues = _analyze("bad_fixed.cbl", content=text)
        assert analyzer.last_format_reason == "default-fixed"
        assert _findings(issues) == BAD_EXPECTED

    def test_tab_indented_fixed_format_stays_fixed(self):
        text = "\tIDENTIFICATION DIVISION.\n\tPROGRAM-ID. T.\n\tPROCEDURE DIVISION.\n"
        analyzer, _ = _analyze("t.cbl", content=text)
        assert analyzer.last_format_reason == "default-fixed"

    def test_explicit_fixed_directive_wins(self):
        text = "      >>SOURCE FORMAT IS FIXED\nIDENTIFICATION DIVISION.\n"
        analyzer, _ = _analyze("t.cbl", content=text)
        assert analyzer.last_format_reason == "directive-fixed"

    @pytest.mark.parametrize(
        "directive",
        [
            ">>SOURCE FORMAT IS FREE",
            ">>SOURCE FREE",
            "$SET SOURCEFORMAT(FREE)",
            ">>source format free",
        ],
    )
    def test_free_directive_variants(self, directive):
        analyzer, _ = _analyze("t.cbl", content=f"{directive}\nIDENTIFICATION DIVISION.\n")
        assert analyzer.last_format_reason == "directive-free"

    def test_free_format_copybook_is_inferred(self):
        analyzer, _ = _analyze("t.cpy", content="01 CUST-REC.\n   05 CUST-ID PIC 9(6).\n")
        assert analyzer.last_format_reason == "inferred-free"


class TestExtensions:
    @pytest.mark.parametrize(
        "name",
        ["P.cbl", "P.CBL", "P.cob", "P.COB", "P.cobol", "P.COBOL", "P.pco", "P.PCO", "P.cpy"],
    )
    def test_extension_detected_as_cobol(self, name):
        assert LanguageDetector.detect(Path(name)) == Language.COBOL

    @pytest.mark.parametrize("name", ["P.cobol", "P.PCO", "P.COBOL"])
    def test_extension_is_discovered_in_directories(self, tmp_path, name):
        from hefesto.core.analyzer_engine import AnalyzerEngine

        src = tmp_path / name
        src.write_text((SMOKE_DIR / "bad_fixed.cbl").read_text())
        engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
        found = engine._find_files(tmp_path, [])
        assert [p.name for p in found] == [name]


class TestFalsePositiveFixes:
    def test_flag_field_with_credential_word_not_flagged(self):
        _, issues = _analyze("false_positives.cbl")
        assert not [i for i in issues if i.rule_id == "COBOL002"]

    @pytest.mark.parametrize(
        "field", ["WS-PASSWORD-OK", "PWD-LEN", "PASSWORD-PROMPT", "WS-TOKEN-SW", "WS-PASSWD-STATUS"]
    )
    def test_non_secret_suffixes(self, field):
        text = f"       PROCEDURE DIVISION.\n       MAIN.\n           MOVE 'N' TO {field}.\n"
        _, issues = _analyze("t.cbl", content=text)
        assert issues == []

    def test_real_secret_still_flagged(self):
        text = "       PROCEDURE DIVISION.\n       MAIN.\n           MOVE 'x9!' TO WS-PASSWORD.\n"
        _, issues = _analyze("t.cbl", content=text)
        assert [i.rule_id for i in issues] == ["COBOL002"]

    def test_cics_and_db2_system_copybooks_not_flagged(self):
        text = (
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "           COPY DFHAID.\n"
            "           COPY DFHBMSCA.\n"
            "           COPY SQLCA.\n"
            "           COPY CUSTREC.\n"
        )
        _, issues = _analyze("t.cbl", content=text)
        assert [(i.rule_id, i.line) for i in issues] == [("COBOL007", 6)]


class TestGrouping:
    def _perform_program(self, n: int) -> str:
        paras = "".join(f"       P{k}.\n           DISPLAY 'X'.\n" for k in range(1, 10))
        calls = "".join("           PERFORM P1 THRU P9\n" for _ in range(n))
        return (
            f"       PROCEDURE DIVISION.\n       MAIN-PARA.\n{calls}           STOP RUN.\n{paras}"
        )

    def test_identical_perform_thru_grouped(self):
        _, issues = _analyze("t.cbl", content=self._perform_program(200))
        cobol006 = [i for i in issues if i.rule_id == "COBOL006"]
        assert len(cobol006) == 1
        assert cobol006[0].line == 3
        assert cobol006[0].metadata["occurrences"] == 200
        assert len(cobol006[0].metadata["lines"]) == 50
        assert "Occurs 200 times" in cobol006[0].message

    def test_distinct_perform_thru_pairs_not_grouped(self):
        text = self._perform_program(1).replace(
            "           STOP RUN.", "           PERFORM P2 THRU P9\n           STOP RUN."
        )
        _, issues = _analyze("t.cbl", content=text)
        assert len([i for i in issues if i.rule_id == "COBOL006"]) == 2

    def test_single_perform_thru_message_unchanged(self):
        _, issues = _analyze("t.cbl", content=self._perform_program(1))
        (issue,) = [i for i in issues if i.rule_id == "COBOL006"]
        assert "Occurs" not in issue.message
        assert issue.metadata["occurrences"] == 1

    def test_repeated_copy_grouped_per_copybook(self):
        text = (
            "       DATA DIVISION.\n"
            + "           COPY CSSETATY.\n" * 5
            + "           COPY OTHER.\n"
        )
        _, issues = _analyze("t.cbl", content=text)
        assert [(i.line, i.metadata["occurrences"]) for i in issues] == [(2, 5), (7, 1)]

    def test_lowercase_perform_thru_counts_paragraphs(self):
        _, issues = _analyze("t.cbl", content=self._perform_program(1).lower())
        (issue,) = [i for i in issues if i.rule_id == "COBOL006"]
        assert "spans 9 paragraphs" in issue.message


class TestKnownMissesPhase3:
    """Known gaps. Phase 3 of the COBOL plan adds the rules/tuning."""

    @pytest.mark.xfail(strict=True, reason="Phase 3: VALUE clause secrets not scanned")
    def test_value_clause_secret(self):
        _, issues = _analyze("bad_fixed.cbl")
        assert ("COBOL002", 12) in _findings(issues)

    @pytest.mark.xfail(strict=True, reason="Phase 3: connection-string secrets in neutral fields")
    def test_connection_string_secret(self):
        _, issues = _analyze("bad_fixed.cbl")
        assert ("COBOL002", 25) in _findings(issues)

    @pytest.mark.xfail(strict=True, reason="Phase 3: EXEC SQL CONNECT ... USING literal")
    def test_exec_sql_connect_password_literal(self):
        _, issues = _analyze("false_positives.cbl")
        assert ("COBOL002", 19) in _findings(issues)

    @pytest.mark.xfail(strict=True, reason="Phase 3: no FILE STATUS rule yet")
    def test_open_without_file_status(self):
        _, issues = _analyze("bad_fixed.cbl")
        assert any(i.line == 26 for i in issues)

    @pytest.mark.xfail(strict=True, reason="Phase 3: no dead-code rule yet")
    def test_code_after_stop_run(self):
        _, issues = _analyze("bad_fixed.cbl")
        assert any(i.line in (51, 52) for i in issues)

    @pytest.mark.xfail(strict=True, reason="Phase 3: COBOL004 flags every REDEFINES (PIC X too)")
    def test_redefines_of_alphanumeric_not_flagged(self):
        _, issues = _analyze("false_positives.cbl")
        assert not [i for i in issues if i.rule_id == "COBOL004"]
