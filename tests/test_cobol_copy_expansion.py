"""COPY ... REPLACING expansion (cobol_copy_expansion) and its use by the analyzer."""

from pathlib import Path

from hefesto.analyzers.devops.cobol_copy_expansion import (
    CopyExpander,
    Origin,
    _tokenize,
    apply_replacing,
    find_statement,
    parse_replacing,
    significant,
)
from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer
from hefesto.analyzers.devops.cobol_project_index import CobolProjectIndex
from hefesto.core.analyzer_engine import AnalyzerEngine


def _a(text):
    return " " * 7 + text


def _b(text):
    return " " * 11 + text


def _reps(clause):
    return parse_replacing(significant(_tokenize(clause, 0)))


def _apply(clause, *texts):
    lines = [(Origin("c.cpy", n), t, False) for n, t in enumerate(texts, start=1)]
    return [text for _, text, _ in apply_replacing(lines, _reps(clause))]


# ---------------------------------------------------------------- REPLACING


def test_parse_operands():
    reps = _reps(
        "==:TAG:== BY ==CUST== 'OLD' BY 'NEW' A OF B BY C T(1) BY T(2) "
        "LEADING ==TPL-== BY ==WS-== TRAILING ==-IN== BY ==-OUT== ==X Y== BY ===="
    )
    assert [(r.pattern, r.by, r.mode) for r in reps] == [
        ((":", "TAG", ":"), "CUST", "text"),
        (("'OLD'",), "'NEW'", "text"),
        (("A", "OF", "B"), "C", "text"),
        (("T", "(", "1", ")"), "T(2)", "text"),
        (("TPL-",), "WS-", "leading"),
        (("-IN",), "-OUT", "trailing"),
        (("X", "Y"), "", "text"),
    ]


def test_tag_idiom_replaces_inside_words():
    assert _apply("==:TAG:== BY ==CUST==", "05 :TAG:-ID PIC X. 05 :tag:-NAME PIC X.") == [
        "05 CUST-ID PIC X. 05 CUST-NAME PIC X."
    ]


def test_parenthesized_tag_idiom():  # CardDemo CSSETATY
    assert _apply("==(TESTVAR1)== BY ==ACCT-STATUS==", "IF (TESTVAR1) = SPACES") == [
        "IF ACCT-STATUS = SPACES"
    ]


def test_whole_words_only_and_case_insensitive():
    out = _apply("==WS-A== BY ==WS-Z==", "MOVE ws-a TO WS-AB WS-A-1 X-WS-A, WS-A.")
    assert out == ["MOVE WS-Z TO WS-AB WS-A-1 X-WS-A, WS-Z."]


def test_literals_match_exactly():
    assert _apply("'abc' BY 'xyz'", "VALUE 'abc'. VALUE 'ABC'.") == ["VALUE 'xyz'. VALUE 'ABC'."]


def test_pseudo_text_spans_lines_and_keeps_line_count():
    out = _apply("==PIC X(10)== BY ==PIC X(20)==", "05 A PIC", "X(10).")
    assert out == ["05 A PIC X(20)", "."]


def test_first_match_wins_and_no_rescan():
    assert _apply("==A== BY ==B== ==B== BY ==C==", "MOVE A TO B") == ["MOVE B TO C"]


def test_leading_and_trailing_partial_words():
    out = _apply(
        "LEADING ==TPL-== BY ==WS-== TRAILING ==-IN== BY ==-OUT==",
        "05 TPL-KEY. 05 KEY-IN. 05 TPL-IN. 05 XTPL-KEY.",
    )
    assert out == ["05 WS-KEY. 05 KEY-OUT. 05 WS-IN. 05 XTPL-KEY."]


def test_empty_replacement_removes_text():
    assert _apply("==SYNC== BY ====", "05 A PIC S9(4) COMP SYNC.") == ["05 A PIC S9(4) COMP ."]


def test_replaced_lines_are_marked():
    lines = [(Origin("c", 1), "05 :T:-A PIC X.", False), (Origin("c", 2), "05 B PIC X.", False)]
    out = apply_replacing(lines, _reps("==:T:== BY ==WS=="))
    assert [o.replaced for o, _, _ in out] == [True, False]


# ---------------------------------------------------------------- statements


def _lines(*texts):
    return [(n, t, False) for n, t in enumerate(texts, start=1)]


def test_find_copy_statement_spanning_lines():
    stmt = find_statement(
        _lines("01 X. COPY BOOK", "REPLACING ==A== BY ==B==", "==C.== BY ==D==. 01 Y."), 0
    )
    assert (stmt.name, stmt.first, stmt.start, stmt.last) == ("BOOK", 0, 6, 2)
    assert [r.pattern for r in stmt.replacing] == [("A",), ("C", ".")]


def test_copy_in_a_literal_is_not_a_statement():
    assert find_statement(_lines("DISPLAY 'COPY X.'"), 0) is None


def test_exec_sql_include_is_a_statement():
    stmt = find_statement(_lines("EXEC SQL", "INCLUDE DCLACCT", "END-EXEC."), 0)
    assert (stmt.name, stmt.last) == ("DCLACCT", 2)
    assert find_statement(_lines("EXEC SQL SELECT A INTO :B FROM T END-EXEC"), 0) is None


# ---------------------------------------------------------------- expander


def _expander(books, **kwargs):
    def load(path):
        text = books.get(path)
        if text is None:
            return None
        return [(n, t, False) for n, t in enumerate(text.split("\n"), start=1) if t]

    return CopyExpander(lambda name, _: name if name in books else None, load, **kwargs)


def _texts(expanded):
    return [text for _, text, _ in expanded]


def test_expand_with_text_around_the_statement_and_origins():
    exp = _expander({"BOOK": "05 B1 PIC X.\n05 B2 PIC X."})
    out = exp.expand("p.cbl", [(1, "01 R. COPY BOOK. 01 S PIC X.", True), (2, "01 T.", True)])
    assert _texts(out) == ["01 R.", "05 B1 PIC X.", "05 B2 PIC X.", "01 S PIC X.", "01 T."]
    assert out[1][0] == Origin("BOOK", 1, (("p.cbl", 1),), False, "BOOK")
    assert out[0][0] == out[3][0] == 1 and out[4][0] == 2  # program lines keep their number


def test_nested_copy_gets_the_outer_replacing():
    # IBM example: REPLACING on the outer COPY applies to nested library text
    exp = _expander(
        {
            "PAYLIB": "01 PAYROLL.\n02 :TAG:-GROSS-PAY PIC S9(5)V99.\nCOPY PAYLIB2.",
            "PAYLIB2": "01 PAYROLL2.\n02 :TAG:2-GROSS-PAY PIC S9(5)V99.",
        }
    )
    out = exp.expand(
        "p.cbl",
        [
            (
                1,
                "COPY PAYLIB REPLACING ==:TAG:== BY ==PAYROLL== "
                "TRAILING ==GROSS-PAY== BY ==NET-PAY==.",
                False,
            )
        ],
    )
    assert _texts(out) == [
        "01 PAYROLL.",
        "02 PAYROLL-NET-PAY PIC S9(5)V99.",
        "01 PAYROLL2.",
        "02 PAYROLL2-NET-PAY PIC S9(5)V99.",
    ]
    assert out[3][0].via == (("p.cbl", 1), ("PAYLIB", 3))


def test_guards_recursion_depth_size_and_missing():
    exp = _expander({"A": "COPY B.", "B": "05 X PIC X.\nCOPY A."})
    out = exp.expand("p.cbl", [(1, "COPY A.", False)])
    assert _texts(out) == ["05 X PIC X.", "COPY A."]  # recursion left as written
    assert exp.not_expanded == {"A": "recursive"}

    deep = _expander({"A": "COPY B.", "B": "05 X PIC X."}, max_depth=1)
    assert _texts(deep.expand("p.cbl", [(1, "COPY A.", False)])) == ["COPY B."]
    assert deep.not_expanded == {"B": "too deep"}

    small = _expander({"A": "05 X PIC X.\n05 Y PIC X.", "B": "05 Z PIC X."}, max_lines=2)
    out = small.expand("p.cbl", [(1, "COPY A.", False), (2, "COPY B.", False)])
    assert _texts(out) == ["05 X PIC X.", "05 Y PIC X.", "COPY B."]
    assert small.not_expanded == {"B": "size limit"}

    none = _expander({})
    assert none.expand("p.cbl", [(1, "COPY GONE.", False)]) is None
    assert none.not_expanded == {"GONE": "not found"}


# ---------------------------------------------------------------- analyzer


def _program(*body):
    return "\n".join([_a("IDENTIFICATION DIVISION."), _a("PROGRAM-ID. P1."), *body]) + "\n"


def _scan(tmp_path, files, library=None):
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    engine = AnalyzerEngine(severity_threshold="LOW")
    if library:
        engine.set_copybook_paths([str(tmp_path / library)])
    report = engine.analyze_path(str(tmp_path / "src"))
    return [
        (Path(r.file_path).name, i.line, i.rule_id, i)
        for r in report.file_results
        for i in r.issues
        if i.rule_id not in ("COBOL007", "COBOL015")
    ]


REDEF = "\n".join(
    [_a("01  AMT          PIC S9(7)V99 COMP-3."), _a("01  AMT-X REDEFINES AMT PIC X(6).")]
)


def test_copybook_data_finding_is_not_repeated_in_programs(tmp_path):
    found = _scan(
        tmp_path,
        {
            "src/P1.cbl": _program(
                _a("DATA DIVISION."), _a("WORKING-STORAGE SECTION."), _b("COPY AMTS.")
            ),
            "src/AMTS.cpy": REDEF + "\n",
        },
    )
    assert [(f, line, rule) for f, line, rule, _ in found] == [("AMTS.cpy", 2, "COBOL004")]


def test_copybook_outside_the_scan_is_reported_in_the_program(tmp_path):
    found = _scan(
        tmp_path,
        {
            "src/P1.cbl": _program(
                _a("DATA DIVISION."), _a("WORKING-STORAGE SECTION."), _b("COPY AMTS.")
            ),
            "lib/AMTS.cpy": REDEF + "\n",
        },
        library="lib",
    )
    assert [(f, line, rule) for f, line, rule, _ in found] == [("P1.cbl", 5, "COBOL004")]
    meta = found[0][3].metadata["expanded_from"]
    assert meta["copybook"] == "AMTS" and meta["line"] == 2 and meta["copy_lines"] == [5]
    assert meta["file"].endswith("lib/AMTS.cpy")


def test_program_lines_after_an_expansion_keep_their_numbers(tmp_path):
    found = _scan(
        tmp_path,
        {
            "src/P1.cbl": _program(
                _a("DATA DIVISION."),
                _a("WORKING-STORAGE SECTION."),
                _b("COPY BIG."),
                _a("01  WS-T."),
                _b("05 WS-E OCCURS 1 TO 9 TIMES DEPENDING ON WS-N PIC X."),
            ),
            "src/BIG.cpy": "\n".join(_a(f"01  B{n} PIC X.") for n in range(40)) + "\n",
        },
    )
    assert [(f, line, rule) for f, line, rule, _ in found] == [("P1.cbl", 7, "COBOL005")]
    assert "expanded_from" not in (found[0][3].metadata or {})


def test_without_an_index_nothing_is_expanded():
    analyzer = CobolGovernanceAnalyzer()
    issues = analyzer.analyze("P1.cbl", _program(_a("DATA DIVISION."), _b("COPY AMTS.")))
    assert issues == []


def test_index_resolves_closest_copybook():
    index = CobolProjectIndex.from_sources(
        [
            ("a/P1.cbl", ""),
            ("a/cpy/REC.cpy", ""),
            ("b/cpy/REC.cpy", ""),
            ("REC.cbl", ""),
        ]
    )
    assert index.resolve("REC", "a/P1.cbl") == "a/cpy/REC.cpy"
    assert index.resolve("rec", "b/x/P2.cbl") == "b/cpy/REC.cpy"
    assert index.resolve("NONE", "a/P1.cbl") is None


def test_expansion_time_grows_linearly_with_copy_count():
    import time

    def run(copies):
        exp = _expander({"BOOK": "05 :T:-A PIC X.\n05 :T:-B PIC X."})
        lines = [(n, f"COPY BOOK REPLACING ==:T:== BY ==W{n}==.", False) for n in range(copies)]
        best = None
        for _ in range(3):
            start = time.perf_counter()
            exp.expand("p.cbl", lines)
            took = time.perf_counter() - start
            best = took if best is None else min(best, took)
        return best

    small, large = run(1_000), run(4_000)
    # linear: ~4x; quadratic: ~16x. 10x leaves room for noisy CI runners.
    assert large < max(small, 0.005) * 10, (small, large)
