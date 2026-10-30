"""COBOL program lineage (JSON ``lineage`` section): rules and invariants."""

import json
import re
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.analyzers.devops.cobol_lineage import build_lineage, extract, is_system_service
from hefesto.analyzers.devops.cobol_project_index import CobolProjectIndex
from hefesto.cli.main import cli


def fixed(*lines: str) -> str:
    """Fixed-format source: sequence area, indicator, then code from column 8."""
    return "\n".join(f"000100 {line}" for line in lines) + "\n"


def prog(name: str, *body: str) -> str:
    return fixed(
        "IDENTIFICATION DIVISION.",
        f"PROGRAM-ID. {name}.",
        "PROCEDURE DIVISION.",
        *body,
        "    GOBACK.",
    )


def lineage(files):
    return build_lineage(CobolProjectIndex.from_sources(sorted(files.items()), lineage=True))


def kinds(section, kind):
    return [
        (e["from"], e.get("to", e.get("target", e.get("expression"))), e["line"])
        for section_entry in [section]
        for e in section_entry
        if e["kind"] == kind
    ]


# --------------------------------------------------------------- 3.1 classes


def test_call_literal_to_repo_program_is_an_edge():
    g = lineage({"a/A.cbl": prog("A", "    CALL 'B' USING X."), "a/B.cbl": prog("B")})
    assert kinds(g["edges"], "CALL") == [("program:A", "program:B", 4)]
    assert g["references"] == [] and g["unresolved"] == []


@pytest.mark.parametrize("name", ["MQOPEN", "CEEDAYS", "CBLTDLI", "AIBTDLI", "DSNTIAC"])
def test_system_services_are_references_not_nodes(name):
    g = lineage({"A.cbl": prog("A", f"    CALL '{name}' USING X.")})
    assert g["edges"] == []
    assert [(r["class"], r["target"]) for r in g["references"]] == [("system_service", name)]
    assert all(n["kind"] != "program" or n["name"] != name for n in g["nodes"])
    assert is_system_service(name.lower())


def test_non_cobol_module_of_the_repo_is_external():
    g = lineage({"cbl/A.cbl": prog("A", "    CALL 'MVSWAIT' USING X.")})
    assert [(r["class"], r["target"]) for r in g["references"]] == [("external", "MVSWAIT")]


def test_repo_program_wins_over_service_prefix():
    g = lineage({"A.cbl": prog("A", "    CALL 'MQUTIL'."), "MQUTIL.cbl": prog("MQUTIL")})
    assert kinds(g["edges"], "CALL") == [("program:A", "program:MQUTIL", 4)]


# ------------------------------------------------------------ 3.2 names


def test_program_id_on_the_next_line_resolves():
    src = fixed("IDENTIFICATION DIVISION.", "PROGRAM-ID.", "    TGT.", "PROCEDURE DIVISION.")
    assert extract(src).program_id == "TGT"
    g = lineage({"x/other.cbl": src, "A.cbl": prog("A", "    CALL 'TGT'.")})
    assert kinds(g["edges"], "CALL") == [("program:A", "program:TGT", 4)]


def test_program_resolves_by_file_name_too():
    g = lineage({"B.cbl": prog("BPGM"), "A.cbl": prog("A", "    CALL 'B'.")})
    assert kinds(g["edges"], "CALL") == [("program:A", "program:BPGM", 4)]


def test_name_of_two_files_is_ambiguous_never_picked():
    g = lineage({"x/B.cbl": prog("B"), "y/B.cbl": prog("B"), "A.cbl": prog("A", "    CALL 'B'.")})
    assert g["edges"] == [] or all(e["kind"] != "CALL" for e in g["edges"])
    assert [(u["reason"], u["expression"]) for u in g["unresolved"]] == [("ambiguous", "B")]


# ------------------------------------------------------- 3.3 literal/variable


def test_variable_targets_are_unresolved_with_expression():
    g = lineage(
        {
            "A.cbl": prog(
                "A",
                "    CALL WS-PGM USING X.",
                "    EXEC CICS XCTL PROGRAM(WS-NEXT) END-EXEC.",
            ),
            "WS-PGM.cbl": prog("WS-PGM"),
        }
    )
    assert all(e["kind"] == "COPY" for e in g["edges"])
    assert sorted((u["kind"], u["expression"], u["reason"]) for u in g["unresolved"]) == [
        ("CALL", "WS-PGM", "variable_target"),
        ("XCTL", "PROGRAM(WS-NEXT)", "variable_target"),
    ]


def test_cics_block_over_several_lines():
    g = lineage(
        {
            "A.cbl": prog(
                "A",
                "    EXEC CICS",
                "         LINK",
                "         PROGRAM ('B')",
                "         COMMAREA(X)",
                "    END-EXEC.",
            ),
            "B.cbl": prog("B"),
        }
    )
    assert kinds(g["edges"], "LINK") == [("program:A", "program:B", 5)]


def test_call_inside_literal_or_comment_is_ignored():
    src = (
        prog(
            "A",
            "    DISPLAY 'PLEASE CALL SUPPORT'.",
            "    MOVE \"CALL 'B'\" TO X.",
            "    CONTINUE. *> CALL 'B'",
        )
        + "000200*    CALL 'B'.\n"
    )
    assert extract(src).refs == []


def test_end_call_and_sql_call_are_not_calls():
    src = prog("A", "    CALL 'B'", "    END-CALL", "    EXEC SQL CALL PROC1 END-EXEC.")
    assert [(r.kind, r.target) for r in extract(src).refs] == [("CALL", "B")]


# ------------------------------------------------------- 3.4 copybooks


def test_call_in_copybook_counts_for_every_copier():
    files = {
        "cpy/UTIL.cpy": fixed("    CALL 'T' USING X."),
        "cpy/MID.cpy": fixed("    COPY UTIL."),
        "A.cbl": prog("A", "    COPY UTIL."),
        "B.cbl": prog("B", "    COPY MID."),
        "T.cbl": prog("T"),
    }
    g = lineage(files)
    calls = [e for e in g["edges"] if e["kind"] == "CALL"]
    assert [(e["from"], e["to"], e["source_file"], e["line"]) for e in calls] == [
        ("program:A", "program:T", "cpy/UTIL.cpy", 1),
        ("program:B", "program:T", "cpy/UTIL.cpy", 1),
    ]


def test_copy_edges_are_direct_only():
    files = {
        "LEAF.cpy": fixed("01 X PIC X."),
        "MID.cpy": fixed("    COPY LEAF."),
        "A.cbl": prog("A", "    COPY MID."),
    }
    g = lineage(files)
    copies = sorted((e["from"], e["to"]) for e in g["edges"] if e["kind"] == "COPY")
    assert copies == [("copybook:MID", "copybook:LEAF"), ("program:A", "copybook:MID")]


# ------------------------------------------------------------ 3.5 SQL


def sql(*lines):
    src = prog("A", "    EXEC SQL", *[f"      {line}" for line in lines], "    END-EXEC.")
    return sorted((r.target, r.op) for r in extract(src).refs if r.kind == "SQL")


def test_select_into_names_host_variables_not_tables():
    assert sql("SELECT A, B INTO :WS-A, :WS-B", "FROM SCH.T1 WHERE A = :K") == [
        ("SCH.T1", "SELECT")
    ]


def test_insert_update_delete_and_join():
    assert sql("INSERT INTO T1 (A) VALUES (:X)") == [("T1", "INSERT")]
    assert sql("UPDATE T2 SET A = 1 WHERE CURRENT OF C1") == [("T2", "UPDATE")]
    assert sql("DELETE FROM T3 WHERE A = 1") == [("T3", "DELETE")]
    assert sql("SELECT 1 FROM T4 X JOIN T5 AS Y ON X.A = Y.A") == [
        ("T4", "SELECT"),
        ("T5", "SELECT"),
    ]
    assert sql("SELECT 1 FROM T6, T7 Z WHERE 1 = 1") == [("T6", "SELECT"), ("T7", "SELECT")]


def test_cursor_subquery_and_functions():
    assert sql(
        "DECLARE C1 CURSOR WITH HOLD FOR SELECT A, EXTRACT(YEAR FROM B)",
        "FROM (SELECT A FROM INNERT) AS Q FOR UPDATE OF A",
    ) == [("INNERT", "SELECT")]


def test_no_table_statements():
    assert sql("FETCH C1 INTO :A, :B") == []
    assert sql("INCLUDE SQLCA") == []
    assert sql("DECLARE T1 TABLE (A CHAR(1))") == []
    assert sql("OPEN C1") == []


def test_dynamic_sql_is_unresolved():
    g = lineage({"A.cbl": prog("A", "    EXEC SQL PREPARE S1 FROM :STMT END-EXEC.")})
    assert [(u["kind"], u["reason"]) for u in g["unresolved"]] == [("SQL", "dynamic_sql")]
    assert all(e["kind"] != "SQL" for e in g["edges"])


# ----------------------------------------------------------- edge cases


def test_empty_file_and_unterminated_exec():
    assert extract("").refs == []
    src = prog("A", "    EXEC CICS LINK PROGRAM('B')")  # no END-EXEC
    assert [(r.kind, r.target) for r in extract(src).refs] == [("LINK", "B")]


def test_free_format_and_non_ascii_literal():
    src = (
        "IDENTIFICATION DIVISION.\nPROGRAM-ID. A.\nPROCEDURE DIVISION.\n"
        "    DISPLAY 'Año CALL ñ'.\n    CALL 'B'.\n    GOBACK.\n"
    )
    assert [(r.kind, r.target, r.line) for r in extract(src, fixed=False).refs] == [
        ("CALL", "B", 5)
    ]


def test_big_file_is_linear():
    body = ["    CALL 'B'."] * 20_000
    refs = extract(prog("A", *body)).refs
    assert len(refs) == 20_000


# ------------------------------------------------------------ invariants


CORPUS = {
    "cbl/A.cbl": prog(
        "A",
        "    CALL 'B'.",
        "    CALL WS-X.",
        "    CALL 'MQPUT'.",
        "    CALL 'ZZZ'.",
        "    EXEC CICS XCTL PROGRAM('B') END-EXEC.",
        "    COPY UTIL.",
    ),
    "cbl/B.cbl": prog("B", "    EXEC CICS LINK PROGRAM(WS-P) END-EXEC."),
    "cpy/UTIL.cpy": fixed("    CALL 'B'."),
}


def test_invariant_no_dynamic_target_is_an_edge_and_no_service_is_a_node():
    g = lineage(CORPUS)
    program_names = {n["name"] for n in g["nodes"] if n["kind"] == "program"}
    assert program_names == {"A", "B"}
    targets = {e["to"] for e in g["edges"] if e["kind"] != "COPY"}
    assert targets <= {n["id"] for n in g["nodes"] if n["kind"] == "program"}


def test_invariant_conservation_each_literal_once():
    g = lineage(CORPUS)
    literal_refs = sum(
        1
        for path, text in CORPUS.items()
        for r in extract(text).refs
        if r.kind != "SQL" and not r.reason
    )
    classified = (
        sum(len(e["lines"]) for e in g["edges"] if e["kind"] in ("CALL", "LINK", "XCTL"))
        + len(g["references"])
        + sum(1 for u in g["unresolved"] if u["reason"] == "ambiguous")
    )
    assert literal_refs == classified == 5  # 4 in A (CALL B, MQPUT, ZZZ, XCTL B) + 1 in UTIL


def test_invariant_deterministic_in_any_input_order():
    one = build_lineage(CobolProjectIndex.from_sources(list(CORPUS.items()), lineage=True))
    two = build_lineage(
        CobolProjectIndex.from_sources(list(reversed(list(CORPUS.items()))), lineage=True)
    )
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)


# ----------------------------------------------------------------- CLI


def _analyze_json(path: Path, *extra: str) -> dict:
    args = ["analyze", str(path), "--output", "json", "--quiet", "--lineage", *extra]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code in (0, 1), result.output
    return json.loads(result.output[result.output.index("{") :])


def test_cli_json_has_lineage_for_cobol(tmp_path):
    (tmp_path / "A.cbl").write_text(prog("A", "    CALL 'B'."))
    (tmp_path / "B.cbl").write_text(prog("B"))
    data = _analyze_json(tmp_path)
    assert data["lineage"]["schema_version"] == 1
    edge = [e for e in data["lineage"]["edges"] if e["kind"] == "CALL"][0]
    assert edge["source_file"] in {f["file"] for f in data["files"]}


def test_cli_json_without_cobol_has_no_lineage(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    data = _analyze_json(tmp_path)
    assert "lineage" not in data
    assert set(data) <= {"summary", "files", "timestamp", "meta"}


def test_lineage_adds_no_findings(tmp_path):
    (tmp_path / "A.cbl").write_text(prog("A", "    CALL 'B'.", "    CALL WS-X."))
    data = _analyze_json(tmp_path)
    rules = {i.get("rule_id") or i.get("type") for f in data["files"] for i in f.get("issues", [])}
    assert not any("LINEAGE" in str(r).upper() for r in rules)


# ------------------------------------------------- opt-in (--lineage) contract

LINEAGE_PROJECT = Path(__file__).parent / "fixtures" / "cobol" / "lineage_project"
# JSON of `hefesto analyze <project> --output json` on main a089df3 (before lineage),
# with run-dependent values (timestamp, durations) zeroed and files sorted by path.
MAIN_GOLDEN = LINEAGE_PROJECT.with_name("lineage_project.main.json")


def _normalized(text: str, root: Path) -> str:
    data = json.loads(text[text.index("{") :].replace(str(root), "<ROOT>"))
    data["files"] = sorted(data["files"], key=lambda f: f["file"])
    out = json.dumps(data, indent=2)
    out = re.sub(r'"(duration_seconds|duration_ms)": [0-9.e-]+', '"\\1": 0', out)
    return re.sub(r'"timestamp": "[^"]*"', '"timestamp": "T"', out) + "\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    shutil.copytree(LINEAGE_PROJECT, root)
    return root


def test_default_json_is_byte_identical_to_main_for_cobol(tmp_path):
    root = _project(tmp_path)
    result = CliRunner().invoke(cli, ["analyze", str(root), "--output", "json", "--quiet"])
    assert result.exit_code in (0, 1), result.output
    assert "lineage" not in json.loads(result.output[result.output.index("{") :])
    assert _normalized(result.output, root) == MAIN_GOLDEN.read_text(encoding="utf-8")


def test_lineage_flag_only_adds_the_lineage_key(tmp_path):
    root = _project(tmp_path)
    data = _analyze_json(root)
    lin = data.pop("lineage")
    assert _normalized(json.dumps(data), root) == MAIN_GOLDEN.read_text(encoding="utf-8")
    assert lin["schema_version"] == 1


def test_default_run_does_not_extract_lineage():
    from hefesto.core.analyzer_engine import AnalyzerEngine

    engine = AnalyzerEngine(quiet=True)
    assert engine.collect_lineage is False
    assert engine.cobol_lineage() is None
    index = CobolProjectIndex.from_sources([("A.cbl", prog("A", "    CALL 'B'."))])
    assert index.lineage_by_file == {}


@pytest.mark.parametrize("fmt", ["text", "sarif"])
def test_lineage_with_non_json_output_warns_and_is_ignored(tmp_path, fmt):
    root = _project(tmp_path)
    plain = CliRunner().invoke(cli, ["analyze", str(root), "--output", fmt, "--quiet"])
    flagged = CliRunner().invoke(
        cli, ["analyze", str(root), "--output", fmt, "--quiet", "--lineage"]
    )
    assert flagged.exit_code == plain.exit_code
    assert f"--lineage is JSON-only; ignored with --output {fmt}" in flagged.stderr
    assert "lineage" not in flagged.stdout.lower()


def test_duplicate_edges_are_merged_with_their_lines(tmp_path):
    data = _analyze_json(_project(tmp_path))
    calls = [
        e
        for e in data["lineage"]["edges"]
        if e["kind"] == "CALL" and e["source_file"].endswith("MAINPGM.cbl")
    ]
    assert len(calls) == 1
    assert calls[0]["lines"] == [8, 9] and calls[0]["line"] == 8


def test_sql_include_copybook_refs_belong_to_the_including_program(tmp_path):
    data = _analyze_json(_project(tmp_path))
    lin = data["lineage"]
    variable = [u for u in lin["unresolved"] if u["file"].endswith("SQLCPY.cpy")]
    assert [(u["from"], u["kind"], u["reason"], u["expression"]) for u in variable] == [
        ("program:MAINPGM", "CALL", "variable_target", "LIT-DSNTIAC")
    ]
    util = [e for e in lin["edges"] if e["source_file"].endswith("UTILCPY.cpy")]
    assert [(e["from"], e["to"]) for e in util] == [("program:MAINPGM", "program:SUBPGM")]
