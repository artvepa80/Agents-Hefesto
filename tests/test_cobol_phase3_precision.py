"""
Phase 3 precision tuning: COBOL004 (REDEFINES over packed/binary/signed data),
COBOL005 (per-entry OCCURS DEPENDING ON), COBOL007 (project-level blast radius),
COBOL011 grouping and the new COBOL015 (copybook not found).
"""

import time

import pytest

from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer
from hefesto.analyzers.devops.cobol_project_index import CobolProjectIndex, copy_names
from hefesto.core.analysis_models import AnalysisIssueSeverity
from hefesto.core.analyzer_engine import AnalyzerEngine


def _fixed(lines):
    """Area A lines start with '@', Area B lines with spaces; returns fixed format."""
    out = []
    for line in lines:
        out.append(("       " + line[1:]) if line.startswith("@") else ("           " + line))
    return "\n".join(out) + "\n"


def _data(*entries, name="T.cbl", index=None):
    code = _fixed(
        ["@IDENTIFICATION DIVISION.", "@PROGRAM-ID. T.", "@DATA DIVISION."]
        + ["@WORKING-STORAGE SECTION."]
        + list(entries)
        + ["@PROCEDURE DIVISION.", "@MAIN-PARA.", "STOP RUN."]
    )
    return CobolGovernanceAnalyzer(index=index).analyze(name, code)


def _lines(issues, rule):
    return [i.line for i in issues if i.rule_id == rule]


class TestCobol004Redefines:
    @pytest.mark.parametrize(
        "entries",
        [
            ["@01  AMT      PIC S9(7)V99 COMP-3.", "@01  AMT-X    REDEFINES AMT PIC X(5)."],
            ["@01  AMT      PIC S9(7)V99 PACKED-DECIMAL.", "@01  AMT-X REDEFINES AMT PIC X(5)."],
            ["@01  CNT      PIC S9(4) COMP.", "@01  CNT-X    REDEFINES CNT PIC XX."],
            # unsigned PIC 9(4) BINARY viewed as PIC XX is the byte-view idiom:
            # see tests/test_cobol_phase3_leftovers.py::test_byte_view_idiom
            ["@01  CNT      PIC 9(4) BINARY.", "@01  CNT-X    REDEFINES CNT PIC XXX."],
            ["@01  BAL      PIC X(12).", "@01  BAL-N    REDEFINES BAL PIC S9(10)V99."],
            ["@01  P        PIC S9(8) BINARY.", "@01  P-PTR    REDEFINES P POINTER."],
            [
                "@01  REC.",
                "05  AMT   PIC S9(7) COMP-3.",
                "05  NAME  PIC X(10).",
                "@01  REC-X REDEFINES REC PIC X(14).",
            ],
            [
                "@01  REC   USAGE COMP-3.",
                "05  A     PIC S9(5).",
                "05  B     PIC S9(5).",
                "@01  REC-X REDEFINES REC PIC X(6).",
            ],
        ],
    )
    def test_sensitive_overlay_flagged(self, entries):
        issues = _data(*entries)
        assert len(_lines(issues, "COBOL004")) == 1
        issue = next(i for i in issues if i.rule_id == "COBOL004")
        assert issue.severity == AnalysisIssueSeverity.HIGH

    @pytest.mark.parametrize(
        "entries",
        [
            # alphanumeric split into parts (the old Phase 3 xfail)
            [
                "@01  NAME     PIC X(10).",
                "@01  NAME-R   REDEFINES NAME.",
                "05 FIRST  PIC X(5).",
                "05 LAST   PIC X(5).",
            ],
            # unsigned display date split into YYYY/MM/DD
            [
                "@01  DT       PIC 9(8).",
                "@01  DT-R     REDEFINES DT.",
                "05 YYYY   PIC 9(4).",
                "05 MM     PIC 99.",
                "05 DD     PIC 99.",
            ],
            # identical layout
            ["@01  A        PIC S9(4) COMP.", "@01  B        REDEFINES A PIC S9(4) COMP."],
            # CICS BMS symbolic map (generated)
            [
                "@01  MAPAI.",
                "02 FILLER PIC X(12).",
                "02 FLDL   PIC S9(4) COMP.",
                "02 FLDI   PIC X(10).",
                "@01  MAPAO REDEFINES MAPAI.",
                "02 FILLER PIC X(12).",
                "02 FILLER PIC X(3).",
                "02 FLDO   PIC X(10).",
            ],
            # redefined item defined elsewhere (copybook): cannot verify
            ["@01  LOCAL-X  REDEFINES FROM-COPYBOOK PIC X(5)."],
        ],
    )
    def test_safe_or_unknown_overlay_not_flagged(self, entries):
        assert _lines(_data(*entries), "COBOL004") == []

    def test_redefines_in_copybook_is_checked(self):
        code = (
            "       01  AMT      PIC S9(7) COMP-3.\n       01  AMT-X    REDEFINES AMT PIC X(4).\n"
        )
        issues = CobolGovernanceAnalyzer().analyze("REC.cpy", code)
        assert [(i.rule_id, i.line) for i in issues] == [("COBOL004", 2)]

    def test_88_levels_do_not_end_the_group(self):
        issues = _data(
            "@01  REC.",
            "05  CODE  PIC X.",
            "88 CODE-OK VALUE 'Y'.",
            "05  AMT   PIC S9(5) COMP-3.",
            "@01  REC-X REDEFINES REC PIC X(4).",
        )
        assert len(_lines(issues, "COBOL004")) == 1


class TestCobol005OccursDepending:
    def test_cics_commarea_idiom_skipped(self):
        issues = _data(
            "@01  LK.",
            "05  LK-COMMAREA PIC X OCCURS 1 TO 32767 TIMES",
            "DEPENDING ON EIBCALEN.",
        )
        assert _lines(issues, "COBOL005") == []

    def test_each_odo_reported_on_its_own_line(self):
        issues = _data(
            "@01  T1.",
            "05  N1  PIC S9(4) BINARY.",
            "05  C1  PIC X OCCURS 0 TO 9 TIMES",
            "DEPENDING ON N1.",
            "@01  T2.",
            "05  N2  PIC S9(4) BINARY.",
            "05  C2  PIC X OCCURS 0 TO 9 TIMES DEPENDING ON N2.",
        )
        assert _lines(issues, "COBOL005") == [7, 11]

    def test_record_varying_depending_is_not_odo(self):
        code = _fixed(
            [
                "@IDENTIFICATION DIVISION.",
                "@PROGRAM-ID. T.",
                "@DATA DIVISION.",
                "@FILE SECTION.",
                "@FD  F1 RECORD IS VARYING IN SIZE FROM 10 TO 80",
                "DEPENDING ON WS-LEN.",
                "@01  F1-REC PIC X(80).",
                "@WORKING-STORAGE SECTION.",
                "@01  T.",
                "05  X PIC X OCCURS 3 TIMES.",
            ]
        )
        assert _lines(CobolGovernanceAnalyzer().analyze("T.cbl", code), "COBOL005") == []


def _index(name, programs, available=None):
    return CobolProjectIndex(
        available=set(available or {name}),
        dependents={name: {f"P{n}.cbl" for n in range(programs)}},
    )


class TestCobol007BlastRadius:
    CPY = "       01  REC.\n           05  F  PIC X(5).\n"

    def _run(self, name, programs, available=None):
        index = _index(name, programs, available)
        return [
            i
            for i in CobolGovernanceAnalyzer(index=index).analyze(f"{name}.cpy", self.CPY)
            if i.rule_id == "COBOL007"
        ]

    @pytest.mark.parametrize(
        "name,programs,severity",
        [
            ("ACCTREC", 4, None),
            ("ACCTREC", 5, AnalysisIssueSeverity.MEDIUM),
            ("ACCTREC", 15, AnalysisIssueSeverity.HIGH),
            ("CUSTOMER-REC", 5, AnalysisIssueSeverity.HIGH),  # generic name part
            ("ACCOUNTANT", 5, AnalysisIssueSeverity.MEDIUM),  # not "ACCOUNT"
            ("DFHAID", 50, None),  # vendor copybook
        ],
    )
    def test_thresholds_and_generic_names(self, name, programs, severity):
        issues = self._run(name, programs)
        assert [i.severity for i in issues] == ([severity] if severity else [])

    def test_no_index_no_finding(self):
        issues = CobolGovernanceAnalyzer().analyze("ACCTREC.cpy", self.CPY)
        assert [i for i in issues if i.rule_id == "COBOL007"] == []

    def test_programs_never_get_cobol007(self):
        issues = _data("@01  X PIC X.", index=_index("T", 20))
        assert _lines(issues, "COBOL007") == []


class TestCobol015CopybookNotFound:
    PROG = (
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "           COPY FOUNDBK.\n"
        "           COPY MISSBK.\n"
        "           COPY DFHAID.\n"
        "           COPY CMQV.\n"
    )

    def test_missing_copybook_reported_when_others_resolve(self):
        index = CobolProjectIndex(available={"FOUNDBK"}, dependents={"FOUNDBK": {"T.cbl"}})
        issues = CobolGovernanceAnalyzer(index=index).analyze("T.cbl", self.PROG)
        assert [(i.rule_id, i.line, i.severity) for i in issues] == [
            ("COBOL015", 4, AnalysisIssueSeverity.LOW)
        ]

    def test_not_reported_when_no_copybook_was_scanned(self):
        index = CobolProjectIndex(available={"T"}, dependents={"MISSBK": {"T.cbl"}})
        issues = CobolGovernanceAnalyzer(index=index).analyze("T.cbl", self.PROG)
        assert [i for i in issues if i.rule_id == "COBOL015"] == []

    def test_no_index_no_finding(self):
        assert CobolGovernanceAnalyzer().analyze("T.cbl", self.PROG) == []


class TestCopyNames:
    def test_comments_literals_and_quoted_names(self):
        text = (
            "       COPY ALPHA.\n"
            "      *    COPY COMMENTED.\n"
            "           DISPLAY 'COPY NOTME'.\n"
            '           COPY "beta.cpy".\n'
            "           copy gamma of lib.\n"
            "           MOVE X TO Y *> COPY INLINE\n"
        )
        assert copy_names(text) == [(1, "ALPHA"), (4, "BETA"), (5, "GAMMA")]

    def test_index_from_sources(self):
        index = CobolProjectIndex.from_sources(
            [
                ("a/P1.cbl", "       COPY REC.\n       COPY GONE.\n"),
                ("a/P2.cbl", "       COPY REC.\n"),
                ("c/REC.cpy", "       COPY NESTED.\n"),
            ]
        )
        assert index.dependent_programs("REC") == ["a/P1.cbl", "a/P2.cbl"]
        # nested COPY: the programs that COPY REC also depend on NESTED (Phase 4);
        # the copybook itself is never counted as a dependent program
        assert index.dependent_programs("NESTED") == ["a/P1.cbl", "a/P2.cbl"]
        assert index.resolves_any
        assert index.is_missing("GONE") and not index.is_missing("REC")

    def test_long_adversarial_line_is_fast(self):
        text = "       " + "COPY " * 20000 + "\n" + "      " + "'" * 40001 + "\n"
        start = time.perf_counter()
        copy_names(text)
        assert time.perf_counter() - start < 1.0


class TestEngineIntegration:
    def _tree(self, tmp_path, programs=5):
        (tmp_path / "cpy").mkdir()
        (tmp_path / "cbl").mkdir()
        (tmp_path / "cpy" / "SHAREDREC.cpy").write_text("       01  REC.\n           05 F PIC X.\n")
        for n in range(programs):
            (tmp_path / "cbl" / f"P{n}.cbl").write_text(
                "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"
                "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
                "           COPY SHAREDREC.\n           COPY NOWHERE.\n"
            )

    def _found(self, report):
        return sorted(
            (fr.file_path.rsplit("/", 1)[-1], i.rule_id, i.line)
            for fr in report.file_results
            for i in fr.issues
            if i.rule_id in ("COBOL007", "COBOL015")
        )

    def test_directory_scan_builds_index(self, tmp_path):
        self._tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW")
        found = self._found(engine.analyze_path(str(tmp_path)))
        assert ("SHAREDREC.cpy", "COBOL007", 1) in found
        assert [f for f in found if f[1] == "COBOL015"] == [
            (f"P{n}.cbl", "COBOL015", 6) for n in range(5)
        ]

    def test_prepared_index_spans_several_paths(self, tmp_path):
        self._tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW")
        paths = [str(tmp_path / "cpy"), str(tmp_path / "cbl")]
        engine.prepare_cobol_index(paths, [])
        found = []
        for path in paths:
            found += self._found(engine.analyze_path(path))
        assert ("SHAREDREC.cpy", "COBOL007", 1) in found
        assert len([f for f in found if f[1] == "COBOL015"]) == 5

    def test_prepared_index_uses_engine_discovery(self, tmp_path):
        """prepare_cobol_index walks paths like analyze_path: excludes and missing paths."""
        self._tree(tmp_path)
        engine = AnalyzerEngine(severity_threshold="LOW")
        engine.prepare_cobol_index([str(tmp_path / "missing"), str(tmp_path / "cbl")], ["cbl"])
        assert engine._cobol_index is None
        engine.prepare_cobol_index([str(tmp_path / "cbl"), str(tmp_path / "cpy")], [])
        assert "SHAREDREC" in engine._cobol_index.available
        assert len(engine._cobol_index.dependent_programs("SHAREDREC")) == 5
