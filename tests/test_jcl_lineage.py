"""JCL lineage (``--lineage``): jobs, steps, datasets, programs and ASSIGN DD names."""

import json
from pathlib import Path
from typing import Dict, List

from click.testing import CliRunner

from hefesto.cli.main import cli


def fixed(*lines: str) -> str:
    return "\n".join(f"000100 {line}" for line in lines) + "\n"


def prog(name: str, *body: str, files: str = "") -> str:
    env = []
    if files:
        env = [
            "ENVIRONMENT DIVISION.",
            "INPUT-OUTPUT SECTION.",
            "FILE-CONTROL.",
            *files.splitlines(),
        ]
    return fixed(
        "IDENTIFICATION DIVISION.",
        f"PROGRAM-ID. {name}.",
        *env,
        "DATA DIVISION.",
        "WORKING-STORAGE SECTION.",
        "01 WS-DD PIC X(8).",
        "PROCEDURE DIVISION.",
        *body,
        "    GOBACK.",
    )


def jcl(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def write(root: Path, files: Dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def run(root: Path, *extra: str) -> dict:
    result = CliRunner().invoke(cli, ["analyze", str(root), "--output", "json", "--quiet", *extra])
    assert result.exit_code in (0, 1), result.output
    return json.loads(result.output[result.output.index("{") :])


def lineage(tmp_path: Path, files: Dict[str, str]) -> dict:
    return run(write(tmp_path, files), "--lineage")["lineage"]


def edges(lin: dict, kind: str) -> List[tuple]:
    return sorted(
        (e["from"], e["to"], e.get("dd", ""), e.get("via", ""))
        for e in lin["edges"]
        if e["kind"] == kind
    )


def refs(lin: dict, kind: str) -> List[tuple]:
    return sorted(
        (r["from"], r["class"], r["target"], r.get("via", ""))
        for r in lin["references"]
        if r["kind"] == kind
    )


def unresolved(lin: dict) -> List[tuple]:
    return sorted((u["kind"], u["from"], u["expression"], u["reason"]) for u in lin["unresolved"])


def node_ids(lin: dict, kind: str) -> List[str]:
    return sorted(n["id"] for n in lin["nodes"] if n["kind"] == kind)


JOB = "//PAYJOB   JOB (ACCT),'PAY',CLASS=A"


# ------------------------------------------------------------ JCL without COBOL


def test_jcl_without_cobol_has_jobs_steps_and_datasets(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "jcl/pay.jcl": jcl(
                JOB,
                "//* a comment line",
                "//STEP1    EXEC PGM=IEFBR14",
                "//OUT      DD DSN=PAY.MASTER.FILE,DISP=SHR",
                "//STEP2    EXEC PGM=PAYCALC",
            )
        },
    )
    path = str(tmp_path / "jcl/pay.jcl")
    assert node_ids(lin, "jcl_job") == [f"jcl_job:PAYJOB@{path}"]
    assert node_ids(lin, "jcl_step") == [
        f"jcl_step:PAYJOB.STEP1@{path}",
        f"jcl_step:PAYJOB.STEP2@{path}",
    ]
    assert node_ids(lin, "dataset") == ["dataset:PAY.MASTER.FILE"]
    assert edges(lin, "DD_DATASET") == [
        (f"jcl_step:PAYJOB.STEP1@{path}", "dataset:PAY.MASTER.FILE", "OUT", "")
    ]
    # No COBOL in the tree: utilities are system, the rest external, never an edge.
    assert edges(lin, "EXEC_PGM") == []
    assert refs(lin, "EXEC_PGM") == [
        (f"jcl_step:PAYJOB.STEP1@{path}", "system", "IEFBR14", ""),
        (f"jcl_step:PAYJOB.STEP2@{path}", "external", "PAYCALC", ""),
    ]
    step = [e for e in lin["edges"] if e["kind"] == "DD_DATASET"][0]
    assert (step["source_file"], step["line"]) == (path, 4)


def test_without_the_flag_jcl_changes_nothing(tmp_path):
    root = write(tmp_path, {"pay.jcl": jcl(JOB, "//S1 EXEC PGM=IEFBR14"), "m.py": "x = 1\n"})
    plain = run(root)
    assert "lineage" not in plain
    assert [f["file"] for f in plain["files"]] == [str(root / "m.py")]
    flagged = run(root, "--lineage")
    flagged.pop("lineage")
    for data in (plain, flagged):
        data.pop("timestamp", None)
        data.get("summary", {}).pop("duration_seconds", None)
        data.get("meta", {}).pop("duration_seconds", None)
    strip = [{k: v for k, v in f.items() if k != "duration_ms"} for f in plain["files"]]
    assert [{k: v for k, v in f.items() if k != "duration_ms"} for f in flagged["files"]] == strip
    assert flagged["summary"]["total_issues"] == plain["summary"]["total_issues"]


def test_no_jcl_and_no_cobol_still_has_no_lineage(tmp_path):
    assert "lineage" not in run(write(tmp_path, {"m.py": "x = 1\n"}), "--lineage")


def test_only_jcl_extensions_are_read(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "a.jcl": jcl(JOB, "//S1 EXEC PGM=IEFBR14"),
            "b.template": jcl("//OTHER JOB", "//S1 EXEC PGM=IEFBR14"),
            "node_modules/c.jcl": jcl("//VENDOR JOB", "//S1 EXEC PGM=IEFBR14"),
        },
    )
    assert [n["name"] for n in lin["nodes"] if n["kind"] == "jcl_job"] == ["PAYJOB"]


# ------------------------------------------------------------ statements


def test_continuation_column_72_and_inline_comments(tmp_path):
    long = "//IN       DD DSN=PAY.INPUT.DATA,          A COMMENT AFTER THE OPERANDS"
    lin = lineage(
        tmp_path,
        {
            "a.jcl": jcl(
                JOB,
                "//S1       EXEC PGM=SORT,",
                "//            PARM='X'",
                long,
                "//            DISP=SHR" + " " * 51 + "SEQ00001",
            )
        },
    )
    assert node_ids(lin, "dataset") == ["dataset:PAY.INPUT.DATA"]
    assert [r["target"] for r in lin["references"]] == ["SORT"]


def test_in_stream_data_is_not_read_as_statements(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "a.jcl": jcl(
                JOB,
                "//S1       EXEC PGM=IEBGENER",
                "//SYSUT1   DD DATA,DLM=$$",
                "//S9       EXEC PGM=NOTREAL",
                "//X        DD DSN=NOT.A.DATASET",
                "$$",
                "//SYSIN    DD *",
                "  GENERATE MAXFLDS=1",
                "/*",
                "//SYSUT2   DD DSN=PAY.COPY,DISP=SHR",
            )
        },
    )
    assert [r["target"] for r in lin["references"]] == ["IEBGENER"]
    assert node_ids(lin, "dataset") == ["dataset:PAY.COPY"]


def test_symbols_temporary_and_referback_are_never_edges(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "B.cbl": prog("B"),
            "a.jcl": jcl(
                JOB,
                "//S1       EXEC PGM=&PGMNAME",
                "//IN       DD DSN=&HLQ..PAY.DATA,DISP=SHR",
                "//TMP      DD DSN=&&WORK,DISP=(NEW,PASS)",
                "//S2       EXEC PGM=*.S1.SYSLMOD",
                "//NUL      DD DUMMY",
                "//OUT      DD SYSOUT=*",
            ),
        },
    )
    s1 = f"jcl_step:PAYJOB.S1@{tmp_path / 'a.jcl'}"
    s2 = f"jcl_step:PAYJOB.S2@{tmp_path / 'a.jcl'}"
    assert lin["edges"] == []
    assert node_ids(lin, "dataset") == []
    assert unresolved(lin) == [
        ("DD_DATASET", s1, "&&WORK", "temporary"),
        ("DD_DATASET", s1, "&HLQ..PAY.DATA", "symbol"),
        ("EXEC_PGM", s1, "&PGMNAME", "symbol"),
        ("EXEC_PGM", s2, "*.S1.SYSLMOD", "referback"),
    ]


def test_in_repo_program_is_an_edge_and_wins_over_the_utility_table(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "cbl/PAYCALC.cbl": prog("PAYCALC"),
            "cbl/SORT.cbl": prog("SORT"),
            "a.jcl": jcl(JOB, "//S1 EXEC PGM=PAYCALC", "//S2 EXEC PGM=SORT"),
        },
    )
    path = tmp_path / "a.jcl"
    assert edges(lin, "EXEC_PGM") == [
        (f"jcl_step:PAYJOB.S1@{path}", "program:PAYCALC", "", ""),
        (f"jcl_step:PAYJOB.S2@{path}", "program:SORT", "", ""),
    ]
    assert lin["references"] == []


# ------------------------------------------------------------ indirect programs


def test_ikjeft01_run_program_in_stream(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "B.cbl": prog("B"),
            "a.jcl": jcl(
                JOB,
                "//S1       EXEC PGM=IKJEFT01",
                "//SYSTSIN  DD *",
                "  DSN SYSTEM(DB2P)",
                "  RUN PROGRAM(B) PLAN(BPLAN)",
                "  RUN PROGRAM(DSNTIAD) PLAN(X)",
                "  END",
                "/*",
                "//S2       EXEC PGM=IKJEFT1B",
                "//SYSTSIN  DD DSN=PAY.CNTL(RUNB),DISP=SHR",
            ),
        },
    )
    path = tmp_path / "a.jcl"
    s1, s2 = (f"jcl_step:PAYJOB.{s}@{path}" for s in ("S1", "S2"))
    assert edges(lin, "EXEC_PGM") == [(s1, "program:B", "", "IKJEFT01")]
    assert refs(lin, "EXEC_PGM") == [
        (s1, "system", "DSNTIAD", "IKJEFT01"),
        (s1, "system", "IKJEFT01", ""),
        (s2, "system", "IKJEFT1B", ""),
    ]
    assert unresolved(lin) == [("EXEC_PGM", s2, "PAY.CNTL(RUNB)", "systsin_not_inline")]
    run_edge = [e for e in lin["edges"] if e["kind"] == "EXEC_PGM"][0]
    assert run_edge["line"] == 5


def test_dfsrrc00_second_parm_operand(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "B.cbl": prog("B"),
            "a.jcl": jcl(
                JOB,
                "//S1 EXEC PGM=DFSRRC00,PARM='DLI,B,BPSB'",
                "//S2 EXEC PGM=DFSRRC00,PARM=(BMP,&MBR,PSB)",
                "//S3 EXEC PGM=DFSRRC00,PARM='ULU,DFSURGU0,DBD'",
            ),
        },
    )
    path = tmp_path / "a.jcl"
    s1, s2, s3 = (f"jcl_step:PAYJOB.{s}@{path}" for s in ("S1", "S2", "S3"))
    assert edges(lin, "EXEC_PGM") == [(s1, "program:B", "", "DFSRRC00")]
    assert (s3, "system", "DFSURGU0", "DFSRRC00") in refs(lin, "EXEC_PGM")
    assert unresolved(lin) == [("EXEC_PGM", s2, "&MBR", "symbol")]


# ------------------------------------------------------------ PROCs and INCLUDE


def test_cataloged_proc_is_expanded_and_override_replaces_its_dd(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "B.cbl": prog("B"),
            "proc/PAYPROC.prc": jcl(
                "//PAYPROC  PROC",
                "//RUN      EXEC PGM=B",
                "//IN       DD DSN=PAY.DEFAULT.IN,DISP=SHR",
                "//LOG      DD DSN=PAY.LOG,DISP=SHR",
                "//         PEND",
            ),
            "a.jcl": jcl(
                JOB,
                "//CALL1    EXEC PAYPROC",
                "//RUN.IN   DD DSN=PAY.OVERRIDE.IN,DISP=SHR",
                "//CALL2    EXEC PROC=MISSING",
            ),
        },
    )
    path = tmp_path / "a.jcl"
    step = f"jcl_step:PAYJOB.CALL1.RUN@{path}"
    assert edges(lin, "EXEC_PGM") == [(step, "program:B", "", "")]
    assert edges(lin, "DD_DATASET") == [
        (step, "dataset:PAY.LOG", "LOG", ""),
        (step, "dataset:PAY.OVERRIDE.IN", "IN", ""),
    ]
    assert unresolved(lin) == [
        ("EXEC_PROC", f"jcl_step:PAYJOB.CALL2@{path}", "MISSING", "proc_not_found")
    ]
    exec_edge = [e for e in lin["edges"] if e["kind"] == "EXEC_PGM"][0]
    assert exec_edge["source_file"] == str(tmp_path / "proc/PAYPROC.prc")


def test_in_stream_proc_and_include(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "inc/DDLIB.jcl": jcl("//EXTRA    DD DSN=PAY.EXTRA,DISP=SHR"),
            "a.jcl": jcl(
                JOB,
                "//LIB      JCLLIB ORDER=(PAY.PROCLIB)",
                "//LOCAL    PROC",
                "//P1       EXEC PGM=IEFBR14",
                "//         PEND",
                "//S1       EXEC LOCAL",
                "//S2       EXEC PGM=IEBGENER",
                "//         INCLUDE MEMBER=DDLIB",
                "//         INCLUDE MEMBER=NOPE",
            ),
        },
    )
    path = tmp_path / "a.jcl"
    assert node_ids(lin, "jcl_step") == [
        f"jcl_step:PAYJOB.S1.P1@{path}",
        f"jcl_step:PAYJOB.S2@{path}",
    ]
    assert edges(lin, "DD_DATASET") == [
        (f"jcl_step:PAYJOB.S2@{path}", "dataset:PAY.EXTRA", "EXTRA", "")
    ]
    assert unresolved(lin) == [("INCLUDE", f"jcl_job:PAYJOB@{path}", "NOPE", "include_not_found")]


def test_recursive_proc_stops(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "LOOP.prc": jcl("//LOOP PROC", "//X EXEC LOOP"),
            "a.jcl": jcl(JOB, "//S1 EXEC LOOP"),
        },
    )
    assert [u["reason"] for u in lin["unresolved"]] == ["proc_recursion"]


# ------------------------------------------------------------ ASSIGN TO


def test_assign_dd_one_edge_set_per_step(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "B.cbl": prog(
                "B",
                "    EXEC CICS ASSIGN USERID(WS-DD) END-EXEC.",
                files=(
                    "    SELECT IN-FILE ASSIGN TO UT-S-INFILE.\n"
                    "    SELECT OUT-FILE\n"
                    "        ASSIGN TO OUTFILE\n"
                    "        ORGANIZATION IS SEQUENTIAL.\n"
                    "    SELECT VAR-FILE ASSIGN TO WS-DD."
                ),
            ),
            "a.jcl": jcl(
                JOB,
                "//S1       EXEC PGM=B",
                "//INFILE   DD DSN=PAY.IN,DISP=SHR",
                "//OUTFILE  DD DSN=PAY.OUT,DISP=SHR",
                "//S2       EXEC PGM=B",
                "//INFILE   DD DSN=PAY.IN2,DISP=SHR",
            ),
        },
    )
    path = tmp_path / "a.jcl"
    s1, s2 = (f"jcl_step:PAYJOB.{s}@{path}" for s in ("S1", "S2"))
    assert edges(lin, "ASSIGN_DD") == [
        ("program:B", s1, "INFILE", ""),
        ("program:B", s1, "OUTFILE", ""),
        ("program:B", s2, "INFILE", ""),
    ]
    assert unresolved(lin) == [
        ("ASSIGN_DD", "program:B", "OUTFILE", "dd_not_found"),
        ("ASSIGN_DD", "program:B", "WS-DD", "variable_target"),
    ]
    by_dd = {(e["to"], e["dd"]): e for e in lin["edges"] if e["kind"] == "ASSIGN_DD"}
    assert by_dd[(s1, "INFILE")]["source_file"] == str(tmp_path / "B.cbl")
    assert by_dd[(s1, "INFILE")]["line"] == 6


def test_assign_without_jcl_adds_nothing(tmp_path):
    lin = lineage(tmp_path, {"B.cbl": prog("B", files="    SELECT F ASSIGN TO INFILE.")})
    assert [e for e in lin["edges"] if e["kind"] == "ASSIGN_DD"] == []
    assert lin["unresolved"] == []


# ------------------------------------------------------------ invariants


def test_every_exec_pgm_is_classified_once(tmp_path):
    lin = lineage(
        tmp_path,
        {
            "B.cbl": prog("B"),
            "a.jcl": jcl(
                JOB,
                "//S1 EXEC PGM=B",
                "//S2 EXEC PGM=IDCAMS",
                "//S3 EXEC PGM=EXTPGM",
                "//S4 EXEC PGM=&X",
            ),
        },
    )
    seen = [e["from"] for e in lin["edges"] if e["kind"] == "EXEC_PGM"]
    seen += [r["from"] for r in lin["references"] if r["kind"] == "EXEC_PGM"]
    seen += [u["from"] for u in lin["unresolved"] if u["kind"] == "EXEC_PGM"]
    assert sorted(seen) == sorted(node_ids(lin, "jcl_step"))
    assert not any("&" in e["to"] for e in lin["edges"])


def test_output_is_deterministic(tmp_path):
    files = {
        "B.cbl": prog("B", files="    SELECT F ASSIGN TO INFILE."),
        "z.jcl": jcl("//ZJOB JOB", "//S1 EXEC PGM=B", "//INFILE DD DSN=Z.IN"),
        "a.jcl": jcl(JOB, "//S1 EXEC PGM=B", "//INFILE DD DSN=A.IN"),
    }
    first = lineage(tmp_path / "one", files)
    second = lineage(tmp_path / "two", dict(reversed(list(files.items()))))
    text = json.dumps(first).replace(str(tmp_path / "one"), "R")
    assert text == json.dumps(second).replace(str(tmp_path / "two"), "R")


def test_cataloged_proc_is_found_by_member_name_not_by_its_label(tmp_path):
    # A cataloged PROC is a library member: EXEC calls the member (file) name.
    lin = lineage(
        tmp_path,
        {
            "proc/BUILDONL.prc": jcl("//BLDONL   PROC", "//COB      EXEC PGM=IGYCRCTL"),
            "a.jcl": jcl(JOB, "//S1 EXEC BUILDONL", "//S2 EXEC BLDONL"),
        },
    )
    path = tmp_path / "a.jcl"
    assert node_ids(lin, "jcl_step") == [
        f"jcl_step:PAYJOB.S1.COB@{path}",
        f"jcl_step:PAYJOB.S2@{path}",
    ]
    assert unresolved(lin) == [
        ("EXEC_PROC", f"jcl_step:PAYJOB.S2@{path}", "BLDONL", "proc_not_found")
    ]


# ------------------------------------------------------- ids relative to the root


def _jcl_checkout(base: Path) -> Path:
    """A git checkout with a job whose step runs a COBOL program and has an unresolved DSN."""
    repo = base / "repo"
    (repo / ".git").mkdir(parents=True)
    write(
        repo,
        {
            "src/PAYROLL.cbl": prog("PAYROLL"),
            "jcl/NIGHTLY.jcl": jcl(
                "//NIGHTLY JOB (ACCT),'X'",
                "//STEP1   EXEC PGM=PAYROLL",
                "//IN      DD DSN=&HLQ..IN,DISP=SHR",
            ),
        },
    )
    return repo


def _jcl_lineage(repo: Path, monkeypatch) -> dict:
    monkeypatch.chdir(repo)
    return run(repo, "--lineage")["lineage"]


def test_jcl_ids_are_relative_to_the_root(tmp_path, monkeypatch):
    section = _jcl_lineage(_jcl_checkout(tmp_path), monkeypatch)
    ids = {n["id"] for n in section["nodes"] if n["kind"].startswith("jcl_")}
    assert ids == {"jcl_job:NIGHTLY@jcl/NIGHTLY.jcl", "jcl_step:NIGHTLY.STEP1@jcl/NIGHTLY.jcl"}
    froms = {u["from"] for u in section["unresolved"]}
    assert froms == {"jcl_step:NIGHTLY.STEP1@jcl/NIGHTLY.jcl"}


def test_jcl_ids_are_the_same_in_two_checkouts(tmp_path, monkeypatch):
    first = _jcl_lineage(_jcl_checkout(tmp_path / "one"), monkeypatch)
    second = _jcl_lineage(_jcl_checkout(tmp_path / "two"), monkeypatch)
    for key in ("nodes", "edges", "unresolved"):
        a = [{k: v for k, v in e.items() if k not in ("file", "source_file")} for e in first[key]]
        b = [{k: v for k, v in e.items() if k not in ("file", "source_file")} for e in second[key]]
        assert a == b, key


def test_jcl_node_file_keeps_the_report_path(tmp_path, monkeypatch):
    repo = _jcl_checkout(tmp_path)
    section = _jcl_lineage(repo, monkeypatch)
    job = next(n for n in section["nodes"] if n["kind"] == "jcl_job")
    assert Path(job["file"]).resolve() == (repo / "jcl/NIGHTLY.jcl").resolve()


def test_jcl_outside_the_root_keeps_an_absolute_id(tmp_path, monkeypatch):
    repo = _jcl_checkout(tmp_path)
    outside = write(tmp_path / "elsewhere", {"J2.jcl": jcl("//J2 JOB (A)", "//S EXEC PGM=IEFBR14")})
    monkeypatch.chdir(repo)
    section = run(repo, str(outside), "--lineage")["lineage"]
    absolute = (outside / "J2.jcl").resolve().as_posix()
    assert f"jcl_job:J2@{absolute}" in {n["id"] for n in section["nodes"]}


def _old_id_path(path: str, root) -> str:
    """The pathlib form the cached id path must match exactly."""
    resolved = Path(path).resolve()
    if root is not None:
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            pass
    return resolved.as_posix()


def test_id_path_matches_the_pathlib_form(tmp_path, monkeypatch):
    from hefesto.analyzers.devops import cobol_lineage

    root = tmp_path / "repo"
    (root / "jcl").mkdir(parents=True)
    (root / "jcl" / "A.jcl").write_text("//A JOB\n")
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / "B.jcl").write_text("//B JOB\n")
    (root / "link.jcl").symlink_to(outside / "B.jcl")
    (root / "inlink").symlink_to(root / "jcl")
    (tmp_path / "repo2").mkdir()
    monkeypatch.chdir(root)
    cases = [
        str(root / "jcl" / "A.jcl"),
        "jcl/A.jcl",
        "./jcl//A.jcl",
        "jcl/../jcl/A.jcl",
        "jcl/A.jcl/",
        "link.jcl",
        "inlink/A.jcl",
        str(outside / "B.jcl"),
        "../out/B.jcl",
        "../repo2/x.jcl",
        "missing/Z.jcl",
        str(root),
        ".",
        "",
    ]
    resolved_root = root.resolve()
    for root_arg in (resolved_root, None, Path("/")):
        graph = cobol_lineage._Graph(root_arg)
        for case in cases:
            assert graph.id_path(case) == _old_id_path(case, root_arg), (case, root_arg)


def test_id_path_is_computed_once_per_distinct_file(tmp_path, monkeypatch):
    from hefesto.analyzers.devops import cobol_lineage

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    files = {"src/PAYROLL.cbl": prog("PAYROLL"), "src/OTHER.cbl": prog("OTHER")}
    for j in range(3):
        files[f"jcl/J{j}.jcl"] = jcl(
            f"//J{j} JOB (ACCT),'X'",
            "//S1 EXEC PGM=PAYROLL",
            "//IN DD DSN=A.B,DISP=SHR",
            "//S2 EXEC PGM=OTHER",
            "//S3 EXEC PGM=IEFBR14",
        )
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    calls: List[str] = []
    real = cobol_lineage._compute_id_path

    def counting(path, root):
        calls.append(path)
        return real(path, root)

    monkeypatch.setattr(cobol_lineage, "_compute_id_path", counting)
    section = _jcl_lineage(repo, monkeypatch)
    assert any(n["kind"] == "jcl_step" for n in section["nodes"])
    assert len(calls) == len(set(calls))
    assert len(set(calls)) <= 3


def test_lineage_leaves_the_collector_as_it_found_it(tmp_path, monkeypatch):
    import gc

    repo = _jcl_checkout(tmp_path)
    assert gc.isenabled()
    _jcl_lineage(repo, monkeypatch)
    assert gc.isenabled()
    gc.disable()
    try:
        _jcl_lineage(repo, monkeypatch)
        assert not gc.isenabled()
    finally:
        gc.enable()
