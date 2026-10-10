#!/usr/bin/env python3
"""Generate the seeded-issue recall fixture (fixed-format COBOL + one free-format file).

Usage (regenerates tests/fixtures/cobol/recall/ from scratch):
    rm -rf tests/fixtures/cobol/recall
    python scripts/cobol_recall_fixture.py tests/fixtures/cobol/recall

Every seeded line is recorded in seeds.json with its rule; scripts/cobol_recall.py
measures recall per rule against it.
"""

import json
import sys
from collections import Counter
from pathlib import Path

OUT = Path(sys.argv[1])
seeds = []


def fixed(spec):
    lines = []
    for item in spec:
        area, text = item[0], item[1]
        if area == "A":
            line = " " * 7 + text
        elif area == "B":
            line = " " * 11 + text
        elif area == "*":
            line = " " * 6 + "*" + text
        elif area == "-":
            line = " " * 6 + "-" + text
        elif area == "":
            line = ""
        else:
            line = area + text  # raw
        assert len(line) <= 72, line
        lines.append(line)
    return lines


def write(rel, spec, raw=False):
    lines = spec if raw else fixed(spec)
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    items = spec if not raw else []
    for num, item in enumerate(items, start=1):
        if len(item) > 2:
            rule, why = item[2], item[3]
            seed = {"rule": rule, "file": rel, "line": num, "seed": why}
            if why.startswith("known limit"):
                seed["known_limit"] = True
            if why.startswith("after expansion"):
                seed["after_expansion"] = True
            seeds.append(seed)


def header(pid):
    return [
        ("A", "IDENTIFICATION DIVISION."),
        ("A", f"PROGRAM-ID. {pid}."),
    ]


# ---------------------------------------------------------------- RCL01
spec = header("RCL01") + [
    ("A", "ENVIRONMENT DIVISION."),
    ("A", "INPUT-OUTPUT SECTION."),
    ("A", "FILE-CONTROL."),
    ("B", "SELECT CUST-FILE ASSIGN TO CUSTIN", "COBOL011", "SELECT without FILE STATUS"),
    ("B", "    ORGANIZATION IS SEQUENTIAL."),
    ("A", "DATA DIVISION."),
    ("A", "FILE SECTION."),
    ("A", "FD  CUST-FILE."),
    ("A", "01  CUST-REC                PIC X(80)."),
    ("A", "WORKING-STORAGE SECTION."),
    ("B", "COPY RECSHARE."),
    ("B", "COPY CUSTLAYOUT."),
    ("A", "01  WS-DB-PASSWORD          PIC X(16)."),
    ("A", "01  WS-CUST-ID              PIC X(10)."),
    ("A", "01  WS-I                    PIC 9(4) VALUE 0."),
    ("A", "PROCEDURE DIVISION."),
    ("A", "MAIN-PARA."),
    ("B", "OPEN INPUT CUST-FILE"),
    ("B", "MOVE 'Pr0d#Secret9' TO WS-DB-PASSWORD", "COBOL002", "MOVE literal to password"),
    ("B", "ACCEPT WS-CUST-ID", "COBOL003", "ACCEPT from SYSIN, unvalidated"),
    ("B", "GO TO STEP-01.", "COBOL001", "first of 11 GO TO"),
]
for n in range(1, 11):
    nxt = f"STEP-{n + 1:02d}" if n < 10 else "DONE-PARA"
    spec += [("A", f"STEP-{n:02d}."), ("B", "ADD 1 TO WS-I"), ("B", f"GO TO {nxt}.")]
spec += [("A", "DONE-PARA."), ("B", "CLOSE CUST-FILE"), ("B", "STOP RUN.")]
write("RCL01.cbl", spec)

# ---------------------------------------------------------------- RCL02
spec = header("RCL02") + [
    ("A", "ENVIRONMENT DIVISION."),
    ("A", "INPUT-OUTPUT SECTION."),
    ("A", "FILE-CONTROL."),
    ("B", "SELECT ACCT-FILE ASSIGN TO ACCTIN", "COBOL012", "status field never checked"),
    ("B", "    FILE STATUS IS WS-ACCT-STATUS."),
    ("A", "DATA DIVISION."),
    ("A", "FILE SECTION."),
    ("A", "FD  ACCT-FILE."),
    ("A", "01  ACCT-REC                PIC X(100)."),
    ("A", "WORKING-STORAGE SECTION."),
    ("B", "COPY RECSHARE."),
    ("B", "COPY CUSTLAYOUT."),
    ("A", "01  WS-ACCT-STATUS          PIC XX."),
    ("A", "01  WS-BALANCE              PIC S9(7)V99 COMP-3."),
    (
        "A",
        "01  WS-BALANCE-X            REDEFINES WS-BALANCE",
        "COBOL004",
        "COMP-3 overlaid by PIC X",
    ),
    ("B", "                            PIC X(5)."),
    ("A", "01  WS-RET-CODE             PIC S9(4) COMP."),
    (
        "A",
        "01  WS-RET-BYTES            REDEFINES WS-RET-CODE.",
        "COBOL004",
        "signed binary split into bytes (not the unsigned idiom)",
    ),
    ("B", "05  WS-RET-HI               PIC X."),
    ("B", "05  WS-RET-LO               PIC X."),
    ("A", "01  WS-COUNT                PIC 9(3) VALUE 0."),
    ("A", "01  WS-TABLE."),
    ("B", "05  WS-ENTRY OCCURS 1 TO 50 TIMES DEPENDING ON WS-COUNT", "COBOL005", "single-line ODO"),
    ("B", "                            PIC X(20)."),
    ("A", "01  WS-TABLE-2."),
    ("B", "05  WS-ITEM", "COBOL005", "ODO split over three lines"),
    ("B", "        OCCURS 1 TO 99 TIMES"),
    ("B", "        DEPENDING ON WS-COUNT    PIC X(8)."),
    ("A", "PROCEDURE DIVISION."),
    ("A", "MAIN-PARA."),
    ("B", "OPEN INPUT ACCT-FILE"),
    ("B", "READ ACCT-FILE"),
    ("B", "CLOSE ACCT-FILE"),
    ("B", "STOP RUN."),
]
write("RCL02.cbl", spec)

# ---------------------------------------------------------------- RCL03
spec = header("RCL03") + [
    ("A", "DATA DIVISION."),
    ("A", "WORKING-STORAGE SECTION."),
    ("B", "COPY RECSHARE."),
    ("B", "COPY CUSTLAYOUT."),
    (
        "A",
        "01  WS-SMTP-PASSWORD        PIC X(12) VALUE 'Mailer2024!'.",
        "COBOL008",
        "VALUE secret on password field",
    ),
    ("A", "01  WS-CONN-STR             PIC X(60) VALUE", "COBOL009", "connection string with PWD="),
    ("B", "'DSN=PRODDB;UID=BATCH;PWD=Xy7#kq;'."),
    ("A", "01  WS-N                    PIC 9 VALUE 0."),
    ("A", "PROCEDURE DIVISION."),
    ("A", "MAIN-PARA."),
    ("B", "PERFORM P1 THRU P6", "COBOL006", "PERFORM THRU over 6 paragraphs"),
    ("B", "STOP RUN."),
    ("B", "DISPLAY 'NEVER RUNS'.", "COBOL013", "statement after STOP RUN"),
    ("A", "P1."),
    ("B", "ADD 1 TO WS-N."),
    ("A", "P2."),
    ("B", "ADD 1 TO WS-N."),
    ("A", "P3."),
    ("B", "ADD 1 TO WS-N."),
    ("A", "P4."),
    ("B", "ADD 1 TO WS-N."),
    ("A", "P5."),
    ("B", "ADD 1 TO WS-N."),
    ("A", "P6."),
    ("B", "ADD 1 TO WS-N."),
    ("B", "GOBACK."),
    ("A", "OLD-REPORT.", "COBOL014", "paragraph never performed or reached"),
    ("B", "DISPLAY 'OLD'."),
]
write("RCL03.cbl", spec)

# ---------------------------------------------------------------- RCL04
spec = header("RCL04") + [
    ("A", "ENVIRONMENT DIVISION."),
    ("A", "INPUT-OUTPUT SECTION."),
    ("A", "FILE-CONTROL."),
    ("B", "SELECT RPT-FILE ASSIGN TO RPTOUT.", "COBOL011", "SELECT without FILE STATUS"),
    ("A", "DATA DIVISION."),
    ("A", "FILE SECTION."),
    ("A", "FD  RPT-FILE."),
    ("A", "01  RPT-REC                 PIC X(132)."),
    ("A", "WORKING-STORAGE SECTION."),
    ("B", "COPY RECSHARE."),
    ("B", "COPY CUSTLAYOUT."),
    ("B", "COPY NOSUCHBK.", "COBOL015", "COPY of a copybook not in the tree"),
    ("B", "EXEC SQL INCLUDE SQLCA END-EXEC."),
    ("B", "EXEC SQL INCLUDE DCLACCT END-EXEC."),
    (
        "B",
        "EXEC SQL INCLUDE DCLGONE END-EXEC.",
        "COBOL015",
        "EXEC SQL INCLUDE of a member not in the tree",
    ),
    ("A", "01  WS-USER                 PIC X(8) VALUE 'BATCH'."),
    ("A", "PROCEDURE DIVISION."),
    ("A", "MAIN-PARA."),
    (
        "B",
        "EXEC SQL CONNECT :WS-USER IDENTIFIED BY 'Db2Pass!'",
        "COBOL010",
        "CONNECT ... IDENTIFIED BY literal",
    ),
    ("B", "END-EXEC"),
    ("B", "EXEC SQL", "COBOL010", "CONNECT TO ... USER ... USING literal, multi-line"),
    ("B", "    CONNECT TO PRODDB USER :WS-USER USING 'S3cond!'"),
    ("B", "END-EXEC"),
    ("B", "OPEN OUTPUT RPT-FILE"),
    ("B", "CLOSE RPT-FILE"),
    ("B", "GOBACK."),
    ("B", "MOVE 0 TO RETURN-CODE.", "COBOL013", "statement after GOBACK"),
    ("A", "UNUSED-CLEANUP.", "COBOL014", "paragraph never referenced"),
    ("B", "DISPLAY 'CLEANUP'."),
]
write("RCL04.cbl", spec)

# ---------------------------------------------------------------- RCL05 (lowercase style)
spec = [
    ("A", "identification division."),
    ("A", "program-id. rcl05."),
    ("A", "environment division."),
    ("A", "input-output section."),
    ("A", "file-control."),
    ("B", "select log-file assign to logout", "COBOL012", "lowercase, status never checked"),
    ("B", "    file status is ws-log-fs."),
    ("A", "data division."),
    ("A", "file section."),
    ("A", "fd  log-file."),
    ("A", "01  log-rec                 pic x(80)."),
    ("A", "working-storage section."),
    ("B", "copy recshare."),
    ("B", "copy custlayout."),
    ("A", "01  ws-log-fs               pic xx."),
    ("A", "01  ws-api-token            pic x(32)."),
    ("A", "01  ws-amount               pic 9(7)."),
    ("A", "01  ws-k                    pic 9 value 0."),
    ("A", "procedure division."),
    ("A", "main-para."),
    ("B", "open output log-file"),
    ("B", 'move "tok_9f8e7d6c5b" to ws-api-token', "COBOL002", "lowercase MOVE to token"),
    ("B", "accept ws-amount from console", "COBOL003", "ACCEPT FROM CONSOLE"),
    ("B", "perform q1 thru q6", "COBOL006", "lowercase PERFORM THRU, 6 paragraphs"),
    ("B", "close log-file"),
    ("B", "stop run."),
    ("A", "q1."),
    ("B", "add 1 to ws-k."),
    ("A", "q2."),
    ("B", "add 1 to ws-k."),
    ("A", "q3."),
    ("B", "add 1 to ws-k."),
    ("A", "q4."),
    ("B", "add 1 to ws-k."),
    ("A", "q5."),
    ("B", "add 1 to ws-k."),
    ("A", "q6."),
    ("B", "add 1 to ws-k."),
]
write("RCL05.cbl", spec)

# ---------------------------------------------------------------- RCL06 free format, no directive
free = [
    "IDENTIFICATION DIVISION.",
    "PROGRAM-ID. RCL06.",
    "DATA DIVISION.",
    "WORKING-STORAGE SECTION.",
    "COPY RECSHARE.",
    "01 WS-FTP-PASSWORD PIC X(10) VALUE 'ftp-Pa55!'.",
    "01 WS-X PIC 9(4) VALUE 0.",
    "PROCEDURE DIVISION.",
    "MAIN-PARA.",
    "    GO TO F01.",
]
free_seeds = [
    (6, "COBOL008", "free format (no directive), VALUE secret"),
    (10, "COBOL001", "free format (no directive), 11 GO TO"),
]
for n in range(1, 11):
    nxt = f"F{n + 1:02d}" if n < 10 else "FEND"
    free += [f"F{n:02d}.", "    ADD 1 TO WS-X", f"    GO TO {nxt}."]
free += ["FEND.", "    STOP RUN."]
(OUT / "RCL06.cbl").write_text("\n".join(free) + "\n")
for line, rule, why in free_seeds:
    seeds.append({"rule": rule, "file": "RCL06.cbl", "line": line, "seed": why})

# ---------------------------------------------------------------- RCL07 harder cases
spec = header("RCL07") + [
    ("A", "DATA DIVISION."),
    ("A", "WORKING-STORAGE SECTION."),
    (
        "A",
        "01  WS-ADMIN-PASSWORD       PIC X(16) VALUE 'secretAdmin2024'.",
        "COBOL008",
        "known limit: credential word inside the value (skipped to avoid placeholder FPs)",
    ),
    ("A", "01  WS-K1                   PIC X(8)  VALUE 'Zx81!qTe'."),
    ("A", "01  WS-DB-PASSWORD          PIC X(8)."),
    (
        "A",
        "01  WS-CONN PIC X(80) VALUE 'SERVER=DBPROD01;DB=CARDS;UID=APPS;PW",
        "COBOL009",
        "connection string split by a continuation line",
    ),
    ("-", "    'D=Kq7#mZ2;'."),
    ("A", "PROCEDURE DIVISION."),
    ("A", "MAIN-PARA."),
    (
        "B",
        "MOVE WS-K1 TO WS-DB-PASSWORD",
        "COBOL002",
        "known limit: literal reaches the password through another field (no data flow)",
    ),
    ("B", "GOBACK."),
]
write("RCL07.cbl", spec)

# ---------------------------------------------------------------- RCL08
# Every seed here only fires once COPY ... REPLACING is expanded: the issue is
# in copybook text (or created by REPLACING) and is reported at the COPY line.
spec = header("RCL08") + [
    ("A", "ENVIRONMENT DIVISION."),
    ("A", "INPUT-OUTPUT SECTION."),
    ("A", "FILE-CONTROL."),
    ("B", "COPY XSELECT.", "COBOL011", "after expansion: SELECT without FILE STATUS in a copybook"),
    ("B", "COPY XSELST.", "COBOL012", "after expansion: status field from another copybook unused"),
    ("A", "DATA DIVISION."),
    ("A", "FILE SECTION."),
    ("A", "FD  X-IN."),
    ("A", "01  X-IN-REC                PIC X(80)."),
    ("A", "FD  X-OUT."),
    ("A", "01  X-OUT-REC               PIC X(80)."),
    ("A", "WORKING-STORAGE SECTION."),
    ("B", "COPY XSTATUS."),
    (
        "B",
        "COPY XSECRET REPLACING ==:PFX:== BY ==WS==",
        "COBOL008",
        "after expansion: REPLACING puts a secret literal in a VALUE",
    ),
    ("B", "                       ==:PWD:== BY =='Tr0ub4dor&3'==."),
    (
        "B",
        "COPY XTABLE REPLACING LEADING ==TPL-== BY ==WS-==.",
        "COBOL005",
        "after expansion: OCCURS DEPENDING ON in a nested copybook",
    ),
    (
        "B",
        "COPY XAMOUNT REPLACING ==:T:== BY ==WS-TOT==.",
        "COBOL004",
        "after expansion: REDEFINES over COMP-3 named by REPLACING",
    ),
    ("A", "01  WS-DB-PASSWORD          PIC X(12)."),
    ("A", "PROCEDURE DIVISION."),
    ("A", "MAIN-PARA."),
    ("B", "OPEN INPUT X-IN OUTPUT X-OUT"),
    ("B", "PERFORM WORK-PARA"),
    (
        "B",
        "COPY XFINISH.",
        "COBOL013",
        "after expansion: statements after STOP RUN in a procedure copybook",
    ),
    ("A", "WORK-PARA."),
    ("B", "DISPLAY 'WORK'."),
    (
        "A",
        "ORPHAN-PARA.",
        "COBOL014",
        "after expansion: unused paragraph (a PROCEDURE COPY used to skip the rule)",
    ),
    ("B", "DISPLAY 'NEVER'."),
]
write("RCL08.cbl", spec)
write("copy/XSELECT.cpy", [("B", "SELECT X-IN ASSIGN TO XIN.")])
write(
    "copy/XSELST.cpy",
    [("B", "SELECT X-OUT ASSIGN TO XOUT"), ("B", "    FILE STATUS IS XS-STATUS.")],
)
write("copy/XSTATUS.cpy", [("A", "01  XS-STATUS               PIC XX.")])
write("copy/XSECRET.cpy", [("A", "01  :PFX:-DB-PASSWORD       PIC X(12) VALUE :PWD:.")])
write(
    "copy/XTABLE.cpy",
    [
        ("A", "01  TPL-TABLE."),
        ("B", "05  TPL-COUNT             PIC 9(4) COMP."),
        ("B", "05  TPL-ENTRY OCCURS 1 TO 50 TIMES DEPENDING ON TPL-COUNT."),
        ("B", "    COPY XTKEY."),
    ],
)
write("copy/XTKEY.cpy", [("B", "    10  TPL-KEY           PIC X(8).")])
write(
    "copy/XAMOUNT.cpy",
    [
        ("A", "01  :T:-AMT                 PIC S9(7)V99 COMP-3."),
        ("A", "01  :T:-AMT-X REDEFINES :T:-AMT PIC X(6)."),
    ],
)
write(
    "copy/XFINISH.cpy",
    [
        ("B", "CLOSE X-IN X-OUT"),
        ("B", "STOP RUN."),
        ("B", "DISPLAY 'AFTER STOP'."),
    ],
)

# ---------------------------------------------------------------- copybooks
write(
    "copy/RECSHARE.cpy",
    [
        ("*", " SHARED RECORD, COPYED BY 6 PROGRAMS", "COBOL007", "copybook used by 6 programs"),
        ("A", "01  SHARED-REC."),
        ("B", "05  SH-ID                   PIC X(10)."),
        (
            "B",
            "05  SH-API-SECRET           PIC X(24) VALUE",
            "COBOL008",
            "VALUE secret inside a copybook",
        ),
        ("B", "    'q8ZtV2mPx7Lw4RbN'."),
        ("B", "05  SH-AMOUNT               PIC S9(5)V99 COMP-3."),
    ],
)
write(
    "copylib/CUSTLAYOUT",
    [
        (
            "*",
            " CUSTOMER LAYOUT, NO FILE EXTENSION (COPYLIB MEMBER)",
            "COBOL007",
            "extension-less copybook used by 5 programs",
        ),
        ("A", "01  CUST-LAYOUT."),
        ("B", "05  CL-NAME                 PIC X(30)."),
        (
            "B",
            "05  CL-JDBC                 PIC X(60) VALUE",
            "COBOL009",
            "PASSWORD= inside a literal in a copybook",
        ),
        ("B", "    'jdbc:db2://h:50000/DB;user=a;password=Zq9!x;'."),
    ],
)
write(
    "dcl/DCLACCT.dcl",
    [
        ("B", "EXEC SQL DECLARE ACCT TABLE"),
        ("B", "( ACCT_ID   CHAR(11) NOT NULL ) END-EXEC."),
        ("A", "01  DCLACCT."),
        ("B", "10 ACCT-ID                  PIC X(11)."),
    ],
)

# RECSHARE line-1 is the comment line; COBOL007 reports line 1 of the copybook.
seeds.sort(key=lambda s: (s["file"], s["line"]))
doc = {
    "schema_version": 1,
    "description": (
        "Seeded COBOL issues for measuring recall. Each seed is one issue planted on "
        "purpose at file:line in tests/fixtures/cobol/recall/; a seed counts as found "
        "when the analyzer reports the same rule in the same file within "
        "'tolerance' lines of it. Scan the whole directory so the COPY index "
        "(COBOL007/COBOL015) sees every program and copybook."
    ),
    "tolerance": 2,
    "seeds": seeds,
}
(OUT / "seeds.json").write_text(json.dumps(doc, indent=1) + "\n")
print(len(seeds), sorted(Counter(s["rule"] for s in seeds).items()))
