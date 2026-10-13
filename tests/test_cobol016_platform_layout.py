"""COBOL016: REDEFINES whose bytes depend on the platform (MEDIUM).

Three patterns, each with its own message and suggestion:

* native byte view: PIC X bytes over COMP-5 or BINARY-SHORT/LONG/LONG-LONG/
  DOUBLE (native byte order: big-endian on z/OS, little-endian on x86);
* BINARY over POINTER: a POINTER is stored in native byte order, BINARY/COMP
  is big-endian everywhere, so on x86 the number is the address byte-swapped
  (here COMP-5 is the portable view, BINARY the dangerous one);
* 4-byte POINTER view: a POINTER is 4 bytes on z/OS (31-bit) and 8 bytes on
  64-bit platforms.

These moved out of COBOL004 (HIGH, "can corrupt values"), which still reports
real reinterpretations.
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


def _issues(*data_lines):
    body = []
    for line in data_lines:
        body.append(("           " + line[1:]) if line.startswith("|") else "       " + line)
    src = "\n".join(HEADER + body + FOOTER) + "\n"
    found = CobolGovernanceAnalyzer().analyze("RDF.cbl", src)
    return [i for i in found if i.rule_id in ("COBOL004", "COBOL016")]


def _one_cobol016(*lines):
    issues = _issues(*lines)
    assert [i.rule_id for i in issues] == ["COBOL016"], [(i.rule_id, i.message) for i in issues]
    issue = issues[0]
    assert issue.severity.value == "MEDIUM"
    return issue


# ------------------------------------------------------------ native byte views


@pytest.mark.parametrize("pic, bytes_", [("9(4)", "X(2)"), ("S9(4)", "X(2)"), ("9(9)", "X(4)")])
def test_comp5_byte_view_is_cobol016(pic, bytes_):
    issue = _one_cobol016(
        f"01  WS-NUM PIC {pic} COMP-5.", f"01  WS-X REDEFINES WS-NUM PIC {bytes_}."
    )
    assert "native byte order" in issue.message and "z/OS" in issue.message
    assert "TRUNC(BIN)" in issue.suggestion and "-fnotrunc" in issue.suggestion


@pytest.mark.parametrize(
    "usage, size",
    [("BINARY-SHORT", 2), ("BINARY-LONG", 4), ("BINARY-LONG-LONG", 8), ("BINARY-DOUBLE", 8)],
)
@pytest.mark.parametrize("sign", ["", " SIGNED", " UNSIGNED"])
def test_binary_type_byte_view_is_cobol016(usage, size, sign):
    issue = _one_cobol016(f"01  WS-NUM {usage}{sign}.", f"01  WS-X REDEFINES WS-NUM PIC X({size}).")
    assert "native byte order (platform-dependent)" in issue.message
    assert usage in issue.message
    assert "z/OS" not in issue.message  # not an IBM Enterprise COBOL type
    assert "C, SQL or OS calls" in issue.suggestion


def test_binary_char_byte_view_is_clean():
    # one byte has no byte order
    assert not _issues("01  WS-NUM BINARY-CHAR.", "01  WS-X REDEFINES WS-NUM PIC X.")


@pytest.mark.parametrize("usage", ["BINARY", "COMP", "COMP-4"])
def test_portable_binary_byte_view_is_clean(usage):
    assert not _issues(
        f"01  WS-NUM PIC S9(4) {usage}.",
        "01  WS-X REDEFINES WS-NUM.",
        "|05  WS-HI PIC X.",
        "|05  WS-LO PIC X.",
    )


def test_native_size_mismatch_stays_cobol004():
    issues = _issues("01  WS-NUM PIC 9(4) COMP-5.", "01  WS-X REDEFINES WS-NUM PIC X(3).")
    assert [i.rule_id for i in issues] == ["COBOL004"]
    assert "can corrupt" in issues[0].message


# --------------------------------------------------------- BINARY over POINTER


@pytest.mark.parametrize("view", ["PIC 9(18) BINARY", "PIC 9(18) COMP", "PIC 9(18) COMP-4"])
def test_big_endian_binary_over_pointer_is_cobol016(view):
    issue = _one_cobol016("01  WS-PTR USAGE POINTER.", f"01  WS-NUM REDEFINES WS-PTR {view}.")
    assert "big-endian" in issue.message and "byte" in issue.message
    assert "COMP-5" in issue.suggestion


def test_inqacc_fixture():
    """Bank-of-Z src/base/cics/cobol/INQACC.cbl:164-166."""
    issues = _issues(
        "01 WS-POINTER USAGE POINTER.",
        "01 WS-POINTER-BYTES  REDEFINES WS-POINTER  PIC X(8).",
        "01 WS-POINTER-NUMBER  REDEFINES WS-POINTER PIC 9(8) BINARY.",
    )
    assert [(i.rule_id, i.line) for i in issues] == [("COBOL016", 7)]
    message = issues[0].message
    assert "WS-POINTER-NUMBER" in message and "big-endian" in message
    assert "4 bytes" in message and "8 bytes" in message


# ------------------------------------------------------- 4-byte POINTER views


@pytest.mark.parametrize("view", ["PIC X(4)", "PIC 9(9) COMP-5", "BINARY-LONG UNSIGNED"])
def test_four_byte_pointer_view_is_cobol016(view):
    issue = _one_cobol016("01  WS-PTR USAGE POINTER.", f"01  WS-V REDEFINES WS-PTR {view}.")
    assert "4 bytes" in issue.message and "8 bytes" in issue.message
    assert "big-endian" not in issue.message
    assert "X(8)" in issue.suggestion


@pytest.mark.parametrize("view", ["PIC X(8)", "PIC 9(18) COMP-5", "BINARY-LONG-LONG UNSIGNED"])
def test_eight_byte_native_pointer_view_is_clean(view):
    assert not _issues("01  WS-PTR USAGE POINTER.", f"01  WS-V REDEFINES WS-PTR {view}.")


def test_signed_pointer_view_stays_cobol004():
    issues = _issues("01  WS-PTR USAGE POINTER.", "01  WS-V REDEFINES WS-PTR PIC S9(9) COMP.")
    assert [i.rule_id for i in issues] == ["COBOL004"]


# ------------------------------------------- suggestion for BINARY over POINTER


def test_binary_over_pointer_suggestion_is_portable_and_clean():
    import re

    issue = _one_cobol016("01  WS-PTR USAGE POINTER.", "01  WS-NUM REDEFINES WS-PTR PIC 9(9) COMP.")
    text = issue.suggestion
    assert "SET ptr UP BY/DOWN BY n" in text and "SET ptr TO ADDRESS OF" in text
    assert "IF ptr =" in text and "portable" in text
    assert "platform-dependent" in text
    assert "pointer's size" not in text  # a 4-byte COMP-5 view is itself COBOL016
    assert "big-endian by default on every compiler" in issue.message
    assert "big-endian everywhere" not in issue.message
    # the numeric view the suggestion names does not trigger COBOL016
    view = re.search(r"PIC 9\(18\) COMP-5", text).group(0)
    assert not _issues("01  WS-PTR USAGE POINTER.", f"01  WS-ADDR REDEFINES WS-PTR {view}.")


def test_comp5_of_four_bytes_over_pointer_is_a_four_byte_view():
    issue = _one_cobol016("01  WS-PTR USAGE POINTER.", "01  WS-A REDEFINES WS-PTR PIC 9(9) COMP-5.")
    assert "4-byte view" in issue.message
