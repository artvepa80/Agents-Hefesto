"""BINARY-CHAR/SHORT/LONG/LONG-LONG/DOUBLE are binary usages.

These ISO 2002 / GnuCOBOL usages carry no PIC. The usage classifier did not
recognise them (the ``(?![\\w-])`` lookahead of ``_USAGE_BINARY`` fails on the
hyphen), so they were classed as alphanumeric and COBOL004 never saw a
reinterpreting REDEFINES over them. Their sizes are fixed (1, 2, 4, 8, 8
bytes), not derived from PIC digits.
"""

import pytest

from hefesto.analyzers.devops import cobol_program_rules as rules
from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer

HEADER = [
    "       IDENTIFICATION DIVISION.",
    "       PROGRAM-ID. RDF.",
    "       DATA DIVISION.",
    "       WORKING-STORAGE SECTION.",
]
FOOTER = ["       PROCEDURE DIVISION.", "           GOBACK."]


def _flagged(*data_lines):
    """True if COBOL004 fires; a leading ``|`` puts the line in Area B."""
    body = []
    for line in data_lines:
        body.append(("           " + line[1:]) if line.startswith("|") else "       " + line)
    src = "\n".join(HEADER + body + FOOTER) + "\n"
    issues = CobolGovernanceAnalyzer().analyze("RDF.cbl", src)
    return any(i.rule_id == "COBOL004" for i in issues)


TYPES = {
    "BINARY-CHAR": 1,
    "BINARY-SHORT": 2,
    "BINARY-LONG": 4,
    "BINARY-LONG-LONG": 8,
    "BINARY-DOUBLE": 8,
}


@pytest.mark.parametrize("usage", list(TYPES))
@pytest.mark.parametrize("sign", ["", " SIGNED", " UNSIGNED"])
@pytest.mark.parametrize("prefix", ["", "USAGE ", "USAGE IS "])
def test_classified_as_binary(usage, sign, prefix):
    assert rules._usage_class(f"{prefix}{usage}{sign}.") == "binary"


@pytest.mark.parametrize("usage, size", list(TYPES.items()))
def test_fixed_size_table(usage, size):
    assert rules._fixed_binary_bytes(usage) == size


# ------------------------------------------------ reinterpretation is reported


@pytest.mark.parametrize(
    "lines",
    [
        ("01  WS-LONG  BINARY-LONG.", "01  WS-NUM REDEFINES WS-LONG PIC 9(4)."),
        ("01  WS-DISP  PIC 9(4).", "01  WS-SHORT REDEFINES WS-DISP BINARY-SHORT."),
        ("01  WS-PACK  PIC S9(7) COMP-3.", "01  WS-LONG REDEFINES WS-PACK BINARY-LONG."),
        # size mismatch of a byte view
        ("01  WS-SHORT BINARY-SHORT.", "01  WS-X REDEFINES WS-SHORT PIC X(3)."),
        ("01  WS-DBL   BINARY-DOUBLE.", "01  WS-X REDEFINES WS-DBL PIC X(4)."),
    ],
)
def test_reinterpreting_redefines_is_flagged(lines):
    assert _flagged(*lines)


# -------------------------------------------- same-size byte views stay exempt


@pytest.mark.parametrize("usage, size", list(TYPES.items()))
def test_same_size_byte_view_is_not_flagged_by_cobol004(usage, size):
    assert not _flagged(f"01  WS-BIN {usage}.", f"01  WS-X REDEFINES WS-BIN PIC X({size}).")


def test_byte_by_byte_view_is_not_flagged_by_cobol004():
    assert not _flagged(
        "01  WS-SHORT BINARY-SHORT UNSIGNED.",
        "01  WS-BYTES REDEFINES WS-SHORT.",
        "|05  WS-HI PIC X.",
        "|05  WS-LO PIC X.",
    )


def test_pointer_viewed_as_eight_byte_binary_is_not_flagged():
    assert not _flagged(
        "01  WS-PTR USAGE POINTER.", "01  WS-ADDR REDEFINES WS-PTR BINARY-LONG-LONG UNSIGNED."
    )


# ------------------------------------------------- CobolCraft controls (clean)
# Signed/unsigned views of the same binary type are the same bytes and value
# range of one integer; CobolCraft uses them to decode Minecraft wire formats.


@pytest.mark.parametrize(
    "lines",
    [
        # src/world/chunk-io.cob:35, :764, :925
        (
            "01 LONG-ARRAY-ENTRY         BINARY-LONG-LONG UNSIGNED.",
            "01 LONG-ARRAY-ENTRY-SIGNED  REDEFINES LONG-ARRAY-ENTRY BINARY-LONG-LONG.",
        ),
        # src/encoding/encode.cob:139 and src/encoding/decode.cob:141
        (
            "01 SIGNED-VALUE         BINARY-LONG.",
            "01 CURRENT-VALUE        REDEFINES SIGNED-VALUE BINARY-LONG UNSIGNED.",
        ),
    ],
)
def test_cobolcraft_signed_unsigned_views_stay_clean(lines):
    assert not _flagged(*lines)
