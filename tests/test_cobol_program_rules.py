"""
Tests for the program-level COBOL rules COBOL008-COBOL014 (all FREE).

Each rule has positive cases and negative (false-positive) cases. Programs are
written in fixed format with an empty sequence area, built by ``_prog``.
"""

import pytest

from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer
from hefesto.core.analysis_models import AnalysisIssueSeverity


def _fixed(lines):
    """Area A lines start with '@', Area B lines with spaces; returns fixed format."""
    out = []
    for line in lines:
        if line.startswith("@"):
            out.append("       " + line[1:])
        else:
            out.append("           " + line.lstrip())
    return "\n".join(out) + "\n"


def _prog(env=(), data=(), proc=()):
    lines = ["@IDENTIFICATION DIVISION.", "@PROGRAM-ID. T."]
    if env:
        lines += ["@ENVIRONMENT DIVISION.", "@INPUT-OUTPUT SECTION.", "@FILE-CONTROL."]
        lines += list(env)
    lines += ["@DATA DIVISION."] + list(data)
    lines += ["@PROCEDURE DIVISION."] + list(proc)
    return _fixed(lines)


def _rules(code, name="T.cbl", rule=None):
    issues = CobolGovernanceAnalyzer().analyze(name, code)
    found = [(i.rule_id, i.line) for i in issues]
    if rule:
        return [line for rid, line in found if rid == rule]
    return found


def _issues(code, rule, name="T.cbl"):
    return [i for i in CobolGovernanceAnalyzer().analyze(name, code) if i.rule_id == rule]


WS = ["@WORKING-STORAGE SECTION."]


class TestCobol008ValueSecret:
    @pytest.mark.parametrize(
        "entry",
        [
            "@01  WS-DB-PASSWORD  PIC X(12) VALUE 'Sup3rS3cr3t!'.",
            '@01  WS-API-TOKEN    PIC X(20) VALUE "tok_live_abc123".',
            "@77  DB-PASSWORD     PIC X(20) VALUE 'ROOT'.",
            "@77  WS-PASSWORD     PIC X(20) VALUE IS 'password'.",
        ],
    )
    def test_flags_literal(self, entry):
        code = _prog(data=WS + [entry], proc=["@MAIN-PARA.", "STOP RUN."])
        issues = _issues(code, "COBOL008")
        assert [i.line for i in issues] == [5]
        assert issues[0].severity == AnalysisIssueSeverity.CRITICAL

    def test_value_on_next_line(self):
        code = _prog(
            data=WS + ["@01  WS-SECRET  PIC X(10)", "VALUE 'k9!Lq2'."],
            proc=["@MAIN-PARA.", "STOP RUN."],
        )
        assert _rules(code, rule="COBOL008") == [5]

    def test_runs_on_copybooks(self):
        code = _fixed(["@01  DB-CONN.", "05 DB-PASSWORD PIC X(20) VALUE 'ROOT'."])
        assert _rules(code, name="DBCONN.cpy", rule="COBOL008") == [2]

    @pytest.mark.parametrize(
        "entry",
        [
            "@01  WS-PASSWORD-OK-FLAG PIC X VALUE 'N'.",
            "@01  WS-PASSWORD   PIC X(8) VALUE SPACES.",
            "@01  WS-PASSWORD   PIC X(8) VALUE 'Y'.",
            "@01  WS-PASSWORD   PIC X(8) VALUE 'XXXXXXXX'.",
            "@01  WS-PASSWORD   PIC X(8) VALUE '********'.",
            "@01  WS-PASSWORD   PIC X(9) VALUE 'UNDEFINED'.",
            "@01  WS-PWD-TXT    PIC X(16) VALUE 'ENTER PASSWORD:'.",
            "@01  WS-PASSWORD-PROMPT PIC X(9) VALUE 'Password:'.",
            "@77  BAQR-TOKEN-PASSWORD PIC X(22) VALUE 'BAQHAPI-Token-Password'.",
            "@77  BAQR-TOKEN-USERNAME PIC X(22) VALUE 'svc-user'.",
            "@01  WS-USER       PIC X(8) VALUE 'admin'.",
        ],
    )
    def test_not_flagged(self, entry):
        code = _prog(data=WS + [entry], proc=["@MAIN-PARA.", "STOP RUN."])
        assert _rules(code, rule="COBOL008") == []

    def test_88_level_not_flagged(self):
        code = _prog(
            data=WS + ["@01  WS-PWD-SW PIC X.", "88 PASSWORD-SET VALUE 'Y1'."],
            proc=["@MAIN-PARA.", "STOP RUN."],
        )
        assert _rules(code, rule="COBOL008") == []


class TestCobol009ConnectionString:
    @pytest.mark.parametrize(
        "literal",
        [
            "'DSN=cobol;UID=root;PWD=tata;'",
            "'UID=db2inst1;PWD=password;PROTOCOL=TCPIP;'",
            '"SERVER=x;PASSWORD=Hunter2;"',
            "'user=app passwd=s3cret'",
        ],
    )
    def test_flags_literal(self, literal):
        code = _prog(
            data=WS + ["@01  WS-CONN PIC X(80)."],
            proc=["@MAIN-PARA.", f"MOVE {literal} TO WS-CONN", "STOP RUN."],
        )
        issues = _issues(code, "COBOL009")
        assert [i.line for i in issues] == [8]
        assert issues[0].severity == AnalysisIssueSeverity.CRITICAL

    @pytest.mark.parametrize(
        "literal",
        [
            "'PWD='",
            "'PASSWORD=?'",
            "'   Password = ['",
            "'password=XXXXXXX'",
            "'PWD=:WS-PWD'",
            "'PWD=%s'",
            "'USER=DUMMY,PASSWORD=DUMMY'",
            "'ENTER PASSWORD'",
        ],
    )
    def test_not_flagged(self, literal):
        code = _prog(
            data=WS + ["@01  WS-CONN PIC X(80)."],
            proc=["@MAIN-PARA.", f"MOVE {literal} TO WS-CONN", "STOP RUN."],
        )
        assert _rules(code, rule="COBOL009") == []


class TestCobol010SqlConnect:
    @pytest.mark.parametrize(
        "stmt",
        [
            ["EXEC SQL CONNECT TO DB2P USER 'DBA' USING 'Pa55w0rd' END-EXEC"],
            ["EXEC SQL", 'CONNECT :USERNAME IDENTIFIED BY "SECRETPWD"', "END-EXEC"],
            ["EXEC SQL CONNECT 'scott/tiger' END-EXEC"],
        ],
    )
    def test_flags_literal_password(self, stmt):
        code = _prog(proc=["@MAIN-PARA."] + stmt + ["STOP RUN."])
        issues = _issues(code, "COBOL010")
        assert [i.line for i in issues] == [6]
        assert issues[0].severity == AnalysisIssueSeverity.CRITICAL

    @pytest.mark.parametrize(
        "stmt",
        [
            "EXEC SQL CONNECT TO :DB USER :WS-USER USING :WS-PWD END-EXEC",
            "EXEC SQL CONNECT :WS-USER IDENTIFIED BY :WS-PWD END-EXEC",
            "EXEC SQL CONNECT RESET END-EXEC",
            "EXEC SQL SELECT A INTO :B FROM T WHERE C = 'USING' END-EXEC",
        ],
    )
    def test_not_flagged(self, stmt):
        code = _prog(proc=["@MAIN-PARA.", stmt, "STOP RUN."])
        assert _rules(code, rule="COBOL010") == []


FD_DATA = ["@FILE SECTION.", "@FD  IN-FILE.", "@01  IN-REC PIC X(80)."]


class TestCobol011FileStatusMissing:
    def test_select_without_status(self):
        code = _prog(
            env=["SELECT IN-FILE ASSIGN TO INDD", "ORGANIZATION IS SEQUENTIAL."],
            data=FD_DATA,
            proc=["@MAIN-PARA.", "OPEN INPUT IN-FILE", "STOP RUN."],
        )
        issues = _issues(code, "COBOL011")
        assert [i.line for i in issues] == [6]
        assert issues[0].severity == AnalysisIssueSeverity.LOW
        assert issues[0].metadata["files"] == ["IN-FILE"]

    def test_files_without_status_grouped_per_program(self):
        code = _prog(
            env=["SELECT A-FILE ASSIGN TO ADD.", "SELECT B-FILE ASSIGN TO BDD."],
            data=FD_DATA,
            proc=["@MAIN-PARA.", "STOP RUN."],
        )
        issues = _issues(code, "COBOL011")
        assert len(issues) == 1
        assert issues[0].metadata["files"] == ["A-FILE", "B-FILE"]
        assert issues[0].metadata["occurrences"] == 2
        assert "2 file(s)" in issues[0].message

    @pytest.mark.parametrize(
        "status", ["FILE STATUS IS WS-FS.", "STATUS WS-FS.", "FILE STATUS WS-FS."]
    )
    def test_with_status_not_flagged(self, status):
        code = _prog(
            env=["SELECT IN-FILE ASSIGN TO INDD", status],
            data=FD_DATA + ["@WORKING-STORAGE SECTION.", "@01  WS-FS PIC XX."],
            proc=["@MAIN-PARA.", "OPEN INPUT IN-FILE", "IF WS-FS NOT = '00'", "STOP RUN."],
        )
        assert _rules(code, rule="COBOL011") == []

    def test_sort_file_skipped(self):
        code = _prog(
            env=["SELECT SORT-WORK ASSIGN TO SORTWK1."],
            data=["@FILE SECTION.", "@SD  SORT-WORK.", "@01  SORT-REC PIC X(80)."],
            proc=["@MAIN-PARA.", "STOP RUN."],
        )
        assert _rules(code, rule="COBOL011") == []


def _status_prog(data_extra, proc, env_status="FILE STATUS IS WS-FS."):
    return _prog(
        env=["SELECT IN-FILE ASSIGN TO INDD", env_status],
        data=FD_DATA + ["@WORKING-STORAGE SECTION."] + data_extra,
        proc=proc,
    )


class TestCobol012FileStatusUnchecked:
    def test_status_never_referenced(self):
        code = _status_prog(
            ["@01  WS-FS PIC XX."],
            ["@MAIN-PARA.", "OPEN INPUT IN-FILE", "READ IN-FILE", "STOP RUN."],
        )
        issues = _issues(code, "COBOL012")
        assert [i.line for i in issues] == [6]
        assert issues[0].severity == AnalysisIssueSeverity.LOW

    @pytest.mark.parametrize(
        "check",
        [
            "IF WS-FS NOT = '00' DISPLAY 'ERR' END-IF",
            "IF FS-OK CONTINUE END-IF",  # 88-level
            "IF WS-FS-1 NOT = '0' DISPLAY 'ERR' END-IF",  # subordinate
        ],
    )
    def test_status_checked(self, check):
        code = _status_prog(
            ["@01  WS-FS.", "05 WS-FS-1 PIC X.", "05 WS-FS-2 PIC X.", "88 FS-OK VALUE '0'."],
            ["@MAIN-PARA.", "OPEN INPUT IN-FILE", check, "STOP RUN."],
        )
        assert _rules(code, rule="COBOL012") == []

    def test_checked_in_declaratives(self):
        code = _status_prog(
            ["@01  WS-FS PIC XX."],
            [
                "@DECLARATIVES.",
                "@IO-ERR SECTION.",
                "USE AFTER ERROR PROCEDURE ON IN-FILE.",
                "@IO-ERR-PARA.",
                "DISPLAY WS-FS.",
                "@END DECLARATIVES.",
                "@MAIN-PARA.",
                "OPEN INPUT IN-FILE",
                "STOP RUN.",
            ],
        )
        assert _rules(code, rule="COBOL012") == []

    def test_not_opened_or_copy_or_undefined(self):
        not_opened = _status_prog(["@01  WS-FS PIC XX."], ["@MAIN-PARA.", "STOP RUN."])
        with_copy = _status_prog(
            ["@01  WS-FS PIC XX."],
            ["@MAIN-PARA.", "OPEN INPUT IN-FILE", "COPY CHKFS.", "STOP RUN."],
        )
        undefined = _status_prog([], ["@MAIN-PARA.", "OPEN INPUT IN-FILE", "STOP RUN."])
        for code in (not_opened, with_copy, undefined):
            assert _rules(code, rule="COBOL012") == []


class TestCobol013DeadCode:
    @pytest.mark.parametrize("terminator", ["STOP RUN.", "GOBACK.", "EXIT PROGRAM."])
    def test_code_after_terminator(self, terminator):
        code = _prog(proc=["@MAIN-PARA.", "DISPLAY 'A'", terminator, "DISPLAY 'DEAD'."])
        issues = _issues(code, "COBOL013")
        assert [i.line for i in issues] == [8]
        assert issues[0].severity == AnalysisIssueSeverity.MEDIUM

    @pytest.mark.parametrize(
        "body",
        [
            ["IF A = B", "STOP RUN", "END-IF", "DISPLAY 'LIVE'."],
            ["IF A = B STOP RUN.", "DISPLAY 'LIVE'."],
            ["READ IN-FILE AT END GOBACK.", "DISPLAY 'LIVE'."],
            ["EVALUATE A WHEN 1 STOP RUN.", "DISPLAY 'LIVE'."],
            ["PERFORM UNTIL X > 1 STOP RUN.", "DISPLAY 'LIVE'."],
            ["EXIT PROGRAM.", "STOP RUN."],
            ["GOBACK.", "EXIT."],
            ["EXIT PROGRAM.", "ENTRY 'ALT1'.", "DISPLAY 'LIVE'."],
            ["IF A = B DISPLAY 'X' END-IF", "STOP RUN.", "@NEXT-PARA.", "DISPLAY 'Y'."],
            ["DISPLAY 'STOP RUN.'.", "DISPLAY 'LIVE'."],
        ],
    )
    def test_not_flagged(self, body):
        code = _prog(proc=["@MAIN-PARA."] + body)
        assert _rules(code, rule="COBOL013") == []

    def test_after_balanced_if(self):
        code = _prog(
            proc=["@MAIN-PARA.", "IF A = B DISPLAY 'X' END-IF", "STOP RUN.", "DISPLAY 'D'."]
        )
        assert _rules(code, rule="COBOL013") == [8]


class TestCobol013TerminatorLine:
    """B5: the message cites the line of the STOP RUN/GOBACK, not the sentence start.

    A COBOL sentence runs to the next period, so MOVE ... ACCEPT ... DISPLAY ...
    STOP RUN. is one sentence; the message used to cite where it started.
    """

    PAYROLL = (
        "      * PAYROLL: monthly payroll batch (demo program).\n"
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PAYROLL.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "           COPY EMPREC.\n"
        "       01  WS-DB-PASSWORD          PIC X(12).\n"
        "       01  WS-RUN-MONTH            PIC X(6).\n"
        "       01  WS-TOTAL                PIC S9(11)V99 COMP-3 VALUE 0.\n"
        "       01  WS-TOTAL-X REDEFINES WS-TOTAL PIC X(7).\n"
        "       01  WS-EMP-COUNT            PIC 9(4) VALUE 0.\n"
        "       01  WS-EMP-TABLE.\n"
        "           05  WS-EMP-ROW OCCURS 1 TO 500 TIMES\n"
        "                   DEPENDING ON WS-EMP-COUNT.\n"
        "               10  WS-ROW-ID       PIC 9(6).\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 'Payr0ll#2026' TO WS-DB-PASSWORD\n"
        "           ACCEPT WS-RUN-MONTH\n"
        "           DISPLAY 'RUN ' WS-RUN-MONTH\n"
        "           STOP RUN.\n"
        "           DISPLAY 'PAYROLL DONE'.\n"
    )

    def test_payroll_cites_stop_run_line(self):
        issues = _issues(self.PAYROLL, "COBOL013", name="PAYROLL.cbl")
        assert [i.line for i in issues] == [22]
        assert "(line 21)" in issues[0].message
        assert "(line 18)" not in issues[0].message

    def test_long_sentence_cites_goback_line(self):
        # 136 lines before the paragraph body: the sentence starts at 137 and
        # its GOBACK sits on line 268.
        head = ["@IDENTIFICATION DIVISION.", "@PROGRAM-ID. T.", "@DATA DIVISION."]
        head += ["@WORKING-STORAGE SECTION."]
        head += [f"@01  WS-F{i:03d} PIC X." for i in range(130)]
        head += ["@PROCEDURE DIVISION.", "@MAIN-PARA."]
        assert len(head) == 136
        body = [f"DISPLAY 'L{i:03d}'" for i in range(131)] + ["GOBACK.", "DISPLAY 'DEAD'."]
        issues = _issues(_fixed(head + body), "COBOL013")
        assert [i.line for i in issues] == [269]
        assert "(line 268)" in issues[0].message

    def test_terminator_on_the_first_line_of_the_sentence(self):
        code = _prog(proc=["@MAIN-PARA.", "STOP RUN.", "DISPLAY 'DEAD'."])
        issues = _issues(code, "COBOL013")
        assert [i.line for i in issues] == [7]
        assert "(line 6)" in issues[0].message

    def test_terminator_after_literal_with_period(self):
        code = _prog(proc=["@MAIN-PARA.", "DISPLAY 'A. B.'", "GOBACK.", "DISPLAY 'D'."])
        issues = _issues(code, "COBOL013")
        assert [i.line for i in issues] == [8]
        assert "(line 7)" in issues[0].message


class TestCobol014UnusedParagraph:
    def test_unreferenced_after_stop_run(self):
        code = _prog(
            proc=[
                "@MAIN-PARA.",
                "PERFORM USED-PARA",
                "STOP RUN.",
                "@USED-PARA.",
                "DISPLAY 'U'.",
                "@ORPHAN-PARA.",
                "DISPLAY 'O'.",
            ]
        )
        issues = _issues(code, "COBOL014")
        assert [i.line for i in issues] == [10]
        assert issues[0].severity == AnalysisIssueSeverity.LOW

    def test_bare_stop_run_sentence_ends_the_paragraph(self):
        # A sentence that is only "STOP RUN." matches at offset 0: the paragraph
        # still ends there, so the next paragraph is not reached by fall-through.
        code = _prog(
            proc=[
                "@MAIN-PARA.",
                "PERFORM USED-PARA.",
                "STOP RUN.",
                "@USED-PARA.",
                "GOBACK.",
                "@ORPHAN-PARA.",
                "DISPLAY 'O'.",
            ]
        )
        assert _rules(code, rule="COBOL014") == [10]

    def test_unused_section(self):
        code = _prog(
            proc=[
                "@MAIN SECTION.",
                "@MAIN-PARA.",
                "STOP RUN.",
                "@ORPHAN SECTION.",
                "@ORPHAN-PARA.",
                "DISPLAY 'O'.",
            ]
        )
        assert _rules(code, rule="COBOL014") == [8]

    @pytest.mark.parametrize(
        "proc",
        [
            # fall-through from the entry paragraph (no STOP RUN)
            ["@MAIN-PARA.", "DISPLAY 'A'.", "@NEXT-PARA.", "STOP RUN."],
            # GO TO target and THRU range interior
            [
                "@MAIN-PARA.",
                "PERFORM A-PARA THRU C-PARA",
                "GO TO Z-PARA.",
                "@A-PARA.",
                "DISPLAY 'A'.",
                "@B-PARA.",
                "DISPLAY 'B'.",
                "@C-PARA.",
                "DISPLAY 'C'.",
                "@Z-PARA.",
                "STOP RUN.",
            ],
            # paragraphs of a PERFORMed section
            [
                "@MAIN SECTION.",
                "@M1.",
                "PERFORM WORK-SEC",
                "STOP RUN.",
                "@WORK-SEC SECTION.",
                "@W1.",
                "DISPLAY '1'.",
                "@W2.",
                "DISPLAY '2'.",
            ],
            # empty exit paragraph
            ["@MAIN-PARA.", "STOP RUN.", "@9999-EXIT.", "EXIT."],
            # DECLARATIVES
            [
                "@DECLARATIVES.",
                "@ERR SECTION.",
                "USE AFTER ERROR PROCEDURE ON IN-FILE.",
                "@ERR-PARA.",
                "DISPLAY 'E'.",
                "@END DECLARATIVES.",
                "@MAIN-PARA.",
                "STOP RUN.",
            ],
            # a procedure copybook may perform it
            ["@MAIN-PARA.", "COPY PROCLIB.", "STOP RUN.", "@CALLED-FROM-COPY.", "DISPLAY 'C'."],
            # ALTER / SORT ... PROCEDURE references
            [
                "@MAIN-PARA.",
                "SORT SF ON ASCENDING KEY K INPUT PROCEDURE IS IN-PROC",
                "GIVING OUT-FILE",
                "STOP RUN.",
                "@IN-PROC.",
                "DISPLAY 'I'.",
            ],
        ],
    )
    def test_not_flagged(self, proc):
        code = _prog(proc=proc)
        assert _rules(code, rule="COBOL014") == []


class TestFixturesAndSafety:
    def test_copybooks_only_get_data_rules(self):
        code = _fixed(["@01  REC.", "05 F PIC X.", "@P1.", "STOP RUN.", "DISPLAY 'X'."])
        rules = {r for r, _ in _rules(code, name="X.cpy")}
        assert not rules & {"COBOL011", "COBOL012", "COBOL013", "COBOL014"}

    @pytest.mark.parametrize(
        "code",
        [
            "",
            "PROCEDURE DIVISION.",
            "       PROCEDURE DIVISION.\n       .\n",
            "       DATA DIVISION.\n       01 .\n",
            "       ENVIRONMENT DIVISION.\n           SELECT\n",
            "       PROCEDURE DIVISION.\n           EXEC SQL CONNECT\n",
        ],
    )
    def test_degenerate_input_does_not_crash(self, code):
        CobolGovernanceAnalyzer().analyze("X.cbl", code)

    def test_nested_programs_analyzed_separately(self):
        inner = _prog(proc=["@INNER-MAIN.", "GOBACK."])
        outer = _prog(proc=["@MAIN-PARA.", "STOP RUN.", "DISPLAY 'DEAD'."])
        code = outer + _fixed(["@END PROGRAM T."]) + inner
        assert [r for r, _ in _rules(code) if r >= "COBOL008"] == ["COBOL013"]


class TestRegexBacktrackingSafety:
    """Adversarial inputs for the patterns CodeQL flagged (ReDoS); each must be fast."""

    N = 20000
    LIMIT_S = 1.0

    def _timed(self, fn, *args):
        import time

        start = time.perf_counter()
        result = fn(*args)
        assert time.perf_counter() - start < self.LIMIT_S
        return result

    def test_only_terminators_repeated_exit(self):
        from hefesto.analyzers.devops import cobol_program_rules as rules

        assert not self._timed(rules.only_terminators, "exit" + " exit" * self.N + " x")
        assert self._timed(rules.only_terminators, "GOBACK EXIT PROGRAM  STOP RUN EXIT")
        assert not rules.only_terminators("")
        assert not rules.only_terminators("STOP")

    def test_open_repeated_io(self):
        from hefesto.analyzers.devops import cobol_program_rules as rules

        text = "OPEN " + "  i-o" * self.N + "!"
        ops = self._timed(rules._open_operands, text, len("OPEN"))
        assert ops == set()
        text = "OPEN " + "i-o " * self.N + "F1"
        assert self._timed(rules._open_operands, text, len("OPEN")) == {"F1"}
        assert rules._open_operands("OPEN INPUT A B OUTPUT C. OPEN X", 4) == {"A", "B", "C"}

    def test_goto_many_words_without_depending(self):
        from hefesto.analyzers.devops import cobol_program_rules as rules

        text = "GO TO P1" + " W" * self.N + "."
        assert self._timed(rules._goto_targets, text) == {"P1"}
        assert rules._goto_targets("GO TO A B C DEPENDING ON X. GO TO D.") == {"A", "B", "C", "D"}

    def test_sql_connect_many_connects_without_using(self):
        from hefesto.analyzers.devops import cobol_program_rules as rules

        sql = " CONNECT" * self.N + " TO DB"
        assert not self._timed(rules._connect_has_literal_password, sql)
        assert rules._connect_has_literal_password(" CONNECT :U IDENTIFIED BY 'x'")
        assert rules._connect_has_literal_password(" CONNECT 'scott/tiger'")
        assert not rules._connect_has_literal_password(" CONNECT :U IDENTIFIED BY :P")
