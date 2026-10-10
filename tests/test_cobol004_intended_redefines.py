"""COBOL004: REDEFINES idioms that never reinterpret a value are not reported.

COBOL004 flags a REDEFINES whose two views lay out packed, binary, pointer or
signed data differently, because reading one view through the other can
corrupt values or abend (S0C7). Four common idioms keep the bytes and their
meaning identical and were reported anyway:

1. a signed zoned number split into digit groups whose last group carries the
   sign (``S9(10)`` as ``9(9)`` + ``S9``): same bytes, sign in the same byte;
2. a pointer viewed as an address-sized number or byte string
   (``USAGE POINTER`` as ``PIC X(8)`` / ``PIC 9(9) COMP``);
3. a table of constants (FILLERs with VALUE) redefined as an ``OCCURS`` table
   with the same layout per entry;
4. the bytes of a *signed* binary field viewed as ``PIC X`` (only the unsigned
   form was exempt before).
"""

import pytest

from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer

HEADER = [
    "       IDENTIFICATION DIVISION.",
    "       PROGRAM-ID. RDF.",
    "       DATA DIVISION.",
    "       WORKING-STORAGE SECTION.",
]
FOOTER = ["       PROCEDURE DIVISION.", "           GOBACK."]


def _flagged(*data_lines):
    """True if COBOL004 fires on a program with these WORKING-STORAGE lines.

    Lines are written from column 8; a leading ``|`` marks Area B (column 12).
    """
    body = []
    for line in data_lines:
        body.append(("           " + line[1:]) if line.startswith("|") else "       " + line)
    src = "\n".join(HEADER + body + FOOTER) + "\n"
    issues = CobolGovernanceAnalyzer().analyze("RDF.cbl", src)
    return any(i.rule_id == "COBOL004" for i in issues)


# ------------------------------------------------------------ 1. zoned split


class TestZonedSignedSplit:
    def test_split_with_sign_in_last_group(self):
        assert not _flagged(
            "01  REC.",
            "|05  BBCOM       PIC S9(10).",
            "|05  REDCOM REDEFINES BBCOM.",
            "|    10  COMDIZ  PIC 9(9).",
            "|    10  COMFRS  PIC S9.",
        )

    def test_split_with_decimal_point(self):
        assert not _flagged(
            "01  RATE        PIC S9(4)V9(6).",
            "01  RATE-PARTS REDEFINES RATE.",
            "|05  R-INT    PIC 9(4).",
            "|05  R-DEC    PIC 9(5).",
            "|05  R-LAST   PIC S9.",
        )

    def test_reverse_direction(self):
        assert not _flagged(
            "01  PARTS.",
            "|05  P-HIGH   PIC 9(9).",
            "|05  P-LOW    PIC S9.",
            "01  WHOLE REDEFINES PARTS PIC S9(10).",
        )

    @pytest.mark.parametrize(
        "parts",
        [
            ("PIC S9.", "PIC 9(9)."),  # sign moved to the first group
            ("PIC 9(8).", "PIC S9."),  # 9 digits over 10
            ("PIC 9(9).", "PIC 9."),  # sign dropped
            ("PIC 9(9).", "PIC X."),  # sign byte read as text
            ("PIC 9(9) COMP-3.", "PIC S9."),  # packed part
        ],
    )
    def test_other_splits_still_flagged(self, parts):
        assert _flagged(
            "01  WHOLE       PIC S9(10).",
            "01  PARTS REDEFINES WHOLE.",
            f"|05  P-A   {parts[0]}",
            f"|05  P-B   {parts[1]}",
        )

    def test_sign_clause_still_flagged(self):
        assert _flagged(
            "01  WHOLE       PIC S9(10) SIGN LEADING SEPARATE.",
            "01  PARTS REDEFINES WHOLE.",
            "|05  P-A   PIC 9(9).",
            "|05  P-B   PIC S9.",
        )

    def test_packed_whole_still_flagged(self):
        assert _flagged(
            "01  WHOLE       PIC S9(9) COMP-3.",
            "01  PARTS REDEFINES WHOLE.",
            "|05  P-A   PIC 9(8).",
            "|05  P-B   PIC S9.",
        )


# ------------------------------------------------------------ 2. pointer views


class TestPointerViews:
    @pytest.mark.parametrize(
        "view",
        ["PIC X(8).", "PIC X(4).", "PIC 9(8) BINARY.", "PIC 9(9) COMP.", "PIC 9(18) COMP-5."],
    )
    def test_pointer_as_address_sized_view(self, view):
        assert not _flagged("01  WS-PTR  USAGE POINTER.", f"01  WS-VIEW REDEFINES WS-PTR {view}")

    def test_byte_string_redefined_as_pointer(self):
        assert not _flagged(
            "01  FCD.",
            "|05  FCD-PTR-FILLER1   PIC X(8) COMP-X.",
            "|05  FCD-HANDLE        REDEFINES FCD-PTR-FILLER1",
            "|                      USAGE POINTER.",
        )

    def test_procedure_pointer(self):
        assert not _flagged("01  P  PROCEDURE-POINTER.", "01  PV REDEFINES P PIC X(8).")

    @pytest.mark.parametrize(
        "view",
        [
            "PIC X(6).",  # not an address size
            "PIC S9(9) COMP.",  # signed number
            "PIC 9(8).",  # display digits
            "PIC 9(4) COMP.",  # 2 bytes
        ],
    )
    def test_other_views_still_flagged(self, view):
        assert _flagged("01  WS-PTR  USAGE POINTER.", f"01  WS-VIEW REDEFINES WS-PTR {view}")

    def test_group_view_still_flagged(self):
        assert _flagged(
            "01  WS-PTR  USAGE POINTER.",
            "01  WS-VIEW REDEFINES WS-PTR.",
            "|05  V1  PIC X(4).",
            "|05  V2  PIC X(4).",
        )

    def test_index_is_not_a_pointer(self):
        assert _flagged("01  IDX  USAGE INDEX.", "01  IV REDEFINES IDX PIC X(4).")


# ------------------------------------------------------------ 3. constant tables


class TestConstantTables:
    def test_values_redefined_as_occurs_table(self):
        assert not _flagged(
            "01  FILLER.",
            "|05  KW-VALUES.",
            "|    10  FILLER PIC X(80) VALUE ' TESTSUITE '.",
            "|    10  FILLER PIC S9(02) VALUE 11.",
            "|    10  FILLER PIC X(80) VALUE ' TESTCASE '.",
            "|    10  FILLER PIC S9(02) VALUE 10.",
            "|05  KW-TABLE REDEFINES KW-VALUES.",
            "|    10  FILLER OCCURS 2 INDEXED BY KW-IX.",
            "|        15  KW-TEXT    PIC X(80).",
            "|        15  KW-LENGTH  PIC S99.",
        )

    def test_nested_occurs(self):
        rows = []
        for n in range(2):
            rows += [f"|05  ROW-{n}.", "|    10  PIC S9(4) COMP VALUE 81."]
            rows += ["|    10  PIC S9(4) COMP VALUE -1."] * 2
        assert not _flagged(
            "01  RULES.",
            *rows,
            "01  RULE-TABLE REDEFINES RULES.",
            "|05  OCCURS 2 TIMES.",
            "|    10  RULE-ENTRY PIC S9(4) COMP OCCURS 3 TIMES.",
        )

    def test_adjacent_text_fields_are_one_byte_string(self):
        assert not _flagged(
            "01  ENTRIES.",
            "|05  E1.",
            "|    10  PIC X(34) VALUE 'DFHCOMMAREA/epspcom_principle_data'.",
            "|    10  PIC X(6) VALUE SPACES.",
            "|    10  PIC 9(4) USAGE COMP-5 VALUE 2.",
            "|05  E2.",
            "|    10  PIC X(40) VALUE SPACES.",
            "|    10  PIC 9(4) USAGE COMP-5.",
            "01  ENTRY-TABLE REDEFINES ENTRIES.",
            "|05  EHT OCCURS 2 TIMES.",
            "|    10  ELEMENT-NAME  PIC X(40).",
            "|    10  ROUTING-CODE  PIC 9(4) USAGE COMP-5.",
        )

    @pytest.mark.parametrize(
        "entry",
        [
            ("10  FILLER OCCURS 3 TIMES.", "PIC S99."),  # 3 entries over 2
            ("10  FILLER OCCURS 2 TIMES.", "PIC 99."),  # unsigned over signed
            ("10  FILLER OCCURS 1 TO 2 DEPENDING ON N.", "PIC S99."),  # variable
        ],
    )
    def test_different_tables_still_flagged(self, entry):
        assert _flagged(
            "01  N  PIC 9.",
            "01  FILLER.",
            "|05  KW-VALUES.",
            "|    10  FILLER PIC X(8) VALUE 'SUITE'.",
            "|    10  FILLER PIC S9(02) VALUE 11.",
            "|    10  FILLER PIC X(8) VALUE 'CASE'.",
            "|    10  FILLER PIC S9(02) VALUE 10.",
            "|05  KW-TABLE REDEFINES KW-VALUES.",
            f"|    {entry[0]}",
            "|        15  KW-TEXT    PIC X(8).",
            f"|        15  KW-LENGTH  {entry[1]}",
        )


# ------------------------------------------------------------ 4. signed byte view


class TestSignedByteView:
    def test_bytes_of_signed_binary(self):
        assert not _flagged(
            "01  DEC      PIC S9(4) COMP.",
            "01  FILLER   REDEFINES DEC.",
            "|02  FILLER  PIC X.",
            "|02  DECBYTE PIC X.",
        )

    def test_size_mismatch_still_flagged(self):
        assert _flagged("01  DEC  PIC S9(4) COMP.", "01  DX REDEFINES DEC PIC X(3).")


# ------------------------------------------------------------ real findings stay


@pytest.mark.parametrize(
    "lines",
    [
        # packed number read as display digits (S0C7 risk)
        ("01  JUNK-FIELD  PIC X(5).", "01  NUM-BAD REDEFINES JUNK-FIELD PIC S9(9) COMP-3."),
        # display value reinterpreted as binary
        ("01  DISP-VALUE  PIC 9(4).", "01  COMP-VALUE REDEFINES DISP-VALUE PIC 9(4) COMP."),
        # packed key over a text key
        ("01  KEY-PACK  PIC S9(7) COMP-3.", "01  KEY-X REDEFINES KEY-PACK PIC X(4)."),
    ],
)
def test_reinterpreting_redefines_still_flagged(lines):
    assert _flagged(*lines)
