"""Phase 3 leftovers: EXEC SQL INCLUDE / extension-less copybooks, copybook_paths,
CardDemo binary byte-view idiom (COBOL004), literal continuation and the
inferred free-format notice."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hefesto.analyzers.devops.cobol_governance_analyzer import (
    CobolGovernanceAnalyzer,
    _join_continuation,
)
from hefesto.analyzers.devops.cobol_project_index import (
    CobolProjectIndex,
    copy_names,
    library_copybook_names,
    looks_like_copybook,
)
from hefesto.config.project_config import ConfigError, load_config
from hefesto.core.analyzer_engine import COBOL_INFERRED_FREE_NOTICE, AnalyzerEngine


def _fixed(*lines):
    """Fixed-format source: ('A'|'B'|'*'|'-', text) -> columns 1-72."""
    out = []
    for area, text in lines:
        if area == "A":
            out.append(" " * 7 + text)
        elif area == "B":
            out.append(" " * 11 + text)
        elif area == "*":
            out.append(" " * 6 + "*" + text)
        else:
            out.append(" " * 6 + "-" + text)
    return "\n".join(out) + "\n"


def _program(name, data=(), proc=(("B", "GOBACK."),)):
    return _fixed(
        ("A", "IDENTIFICATION DIVISION."),
        ("A", f"PROGRAM-ID. {name}."),
        ("A", "DATA DIVISION."),
        ("A", "WORKING-STORAGE SECTION."),
        *data,
        ("A", "PROCEDURE DIVISION."),
        *proc,
    )


def _rules(report, name=None):
    out = []
    for result in report.file_results:
        if name and Path(result.file_path).name != name:
            continue
        out.extend(i.rule_id for i in result.issues if (i.rule_id or "").startswith("COBOL"))
    return out


def _analyze(path, copybook_paths=None):
    engine = AnalyzerEngine(severity_threshold="LOW")
    if copybook_paths:
        engine.set_copybook_paths([str(p) for p in copybook_paths])
    return engine, engine.analyze_path(str(path))


# ---------------------------------------------------------------- copy_names


class TestCopyNames:
    def test_exec_sql_include_single_and_multi_line(self):
        src = _fixed(
            ("B", "EXEC SQL INCLUDE SQLCA END-EXEC."),
            ("B", "EXEC SQL"),
            ("B", "   INCLUDE DCLACCT"),
            ("B", "END-EXEC."),
            ("B", "COPY CUSTREC."),
        )
        assert [n for _, n in copy_names(src)] == ["SQLCA", "DCLACCT", "CUSTREC"]

    def test_include_in_comment_or_literal_ignored(self):
        src = _fixed(
            ("*", "    EXEC SQL INCLUDE OLDBOOK END-EXEC."),
            ("B", "DISPLAY 'EXEC SQL INCLUDE FAKE END-EXEC'."),
            ("B", "MOVE 'INCLUDE X' TO WS-A."),
        )
        assert copy_names(src) == []

    def test_include_outside_exec_sql_ignored(self):
        assert copy_names(_fixed(("B", "INCLUDE NOTSQL."))) == []

    def test_looks_like_copybook(self):
        assert looks_like_copybook(_fixed(("A", "01  CUST-REC."), ("B", "05 X PIC X.")))
        assert looks_like_copybook(_fixed(("B", "EXEC SQL DECLARE T TABLE (A INT) END-EXEC.")))
        assert not looks_like_copybook("#!/bin/sh\necho 01 hello\n")


# ---------------------------------------------------------------- index


class TestIndexExtraCopybooks:
    def test_extensionless_kept_only_if_referenced_and_cobol(self):
        prog = _program("P1", data=(("B", "COPY CUSTLAY."),))
        index = CobolProjectIndex.from_sources(
            [("p1.cbl", prog)],
            extra_copybooks=[
                ("lib/CUSTLAY", _fixed(("A", "01  CUST."), ("B", "05 A PIC X."))),
                ("lib/NOTREF", _fixed(("A", "01  N."))),
                ("lib/CUSTLAY2", "plain text"),
            ],
        )
        assert "CUSTLAY" in index.available
        assert "NOTREF" not in index.available
        assert index.is_copybook_file("lib/CUSTLAY")
        assert not index.is_copybook_file("lib/NOTREF")
        assert index.is_copybook_file("x/ANY.cpy")

    def test_referenced_but_not_cobol_content_is_not_a_copybook(self):
        prog = _program("P1", data=(("B", "COPY MARKER."),))
        index = CobolProjectIndex.from_sources(
            [("p1.cbl", prog)], extra_copybooks=[("scripts/MARKER", "echo done\n")]
        )
        assert "MARKER" not in index.available

    def test_library_names(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "A.cpy").write_text("       01  A.\n")
        (tmp_path / "sub" / "DCLB.dcl").write_text("       01  B.\n")
        (tmp_path / "sub" / "MEMBERC").write_text("       01  C.\n")
        (tmp_path / "README").write_text("not a copybook\n")
        assert library_copybook_names([tmp_path]) == {"A", "DCLB", "MEMBERC"}


def _include_project(root: Path):
    (root / "dcl").mkdir()
    (root / "dcl" / "DCLACCT.dcl").write_text(
        _fixed(
            ("B", "EXEC SQL DECLARE ACCT TABLE (ID INTEGER) END-EXEC."),
            ("A", "01  DCLACCT."),
            ("B", "05 ACCT-ID PIC S9(9) COMP."),
        )
    )
    (root / "copy").mkdir()
    (root / "copy" / "HDR.cpy").write_text(_fixed(("A", "01  HDR-REC."), ("B", "05 H PIC X.")))
    (root / "P1.cbl").write_text(
        _program(
            "P1",
            data=(
                ("B", "COPY HDR."),
                ("B", "EXEC SQL INCLUDE DCLACCT END-EXEC."),
                ("B", "EXEC SQL INCLUDE DCLGONE END-EXEC."),
                ("B", "EXEC SQL INCLUDE SQLCA END-EXEC."),
            ),
        )
    )


class TestEngineIncludes:
    def test_include_resolved_and_missing(self, tmp_path):
        _include_project(tmp_path)
        _, report = _analyze(tmp_path)
        p1 = [i for r in report.file_results for i in r.issues if i.rule_id == "COBOL015"]
        assert len(p1) == 1
        text = p1[0].message + json.dumps(p1[0].metadata or {})
        assert "DCLGONE" in text and "DCLACCT" not in text and "SQLCA" not in text

    def test_extensionless_copybook_is_analyzed(self, tmp_path):
        (tmp_path / "copylib").mkdir()
        (tmp_path / "copylib" / "CONNLAY").write_text(
            _fixed(
                ("A", "01  CONN-LAYOUT."),
                ("B", "05 CONN-URL PIC X(60) VALUE"),
                ("B", "   'jdbc:db2://h:50000/D;user=a;password=Rt7kQ2x9;'."),
            )
        )
        (tmp_path / "P1.cbl").write_text(_program("P1", data=(("B", "COPY CONNLAY."),)))
        _, report = _analyze(tmp_path)
        assert "COBOL009" in _rules(report, "CONNLAY")
        assert "COBOL015" not in _rules(report)

    def test_unreferenced_extensionless_file_not_analyzed(self, tmp_path):
        (tmp_path / "NOTES").write_text("01 this is prose, password=hunter2\n")
        (tmp_path / "P1.cbl").write_text(_program("P1"))
        _, report = _analyze(tmp_path)
        assert all(Path(r.file_path).name != "NOTES" for r in report.file_results)


# ---------------------------------------------------------------- copybook_paths


class TestCopybookPaths:
    def _project(self, tmp_path):
        src = tmp_path / "src"
        lib = tmp_path / "lib"
        (src / "copy").mkdir(parents=True)
        lib.mkdir()
        (src / "copy" / "LOCAL.cpy").write_text(_fixed(("A", "01  L."), ("B", "05 A PIC X.")))
        (lib / "SHARED.cpy").write_text(_fixed(("A", "01  S."), ("B", "05 A PIC X.")))
        (src / "P1.cbl").write_text(
            _program("P1", data=(("B", "COPY LOCAL."), ("B", "COPY SHARED.")))
        )
        return src, lib

    def test_engine_resolves_library_copybooks(self, tmp_path):
        src, lib = self._project(tmp_path)
        _, without = _analyze(src)
        assert "COBOL015" in _rules(without)
        _, with_lib = _analyze(src, [lib])
        assert "COBOL015" not in _rules(with_lib)
        # library files are not analyzed
        assert all("lib" not in Path(r.file_path).parts for r in with_lib.file_results)

    def test_config_relative_to_config_file(self, tmp_path):
        src, lib = self._project(tmp_path)
        cfg = src / ".hefesto.yaml"
        cfg.write_text("copybook_paths:\n  - ../lib\n")
        loaded = load_config(cfg)
        assert loaded.values["copybook_paths"] == (str(lib.resolve()),)

    def test_config_missing_dir_is_error(self, tmp_path):
        cfg = tmp_path / ".hefesto.yaml"
        cfg.write_text("copybook_paths: [nope]\n")
        with pytest.raises(ConfigError, match="copybook_paths"):
            load_config(cfg)

    @pytest.mark.parametrize("via", ["flag", "config"])
    def test_cli(self, tmp_path, via):
        from hefesto.cli.main import cli

        src, lib = self._project(tmp_path)
        args = ["analyze", str(src), "--severity", "LOW", "--output", "json", "--quiet"]
        if via == "flag":
            args += ["--copybook-path", str(lib), "--no-config"]
        else:
            (src / ".hefesto.yaml").write_text("copybook_paths: [../lib]\n")
        result = CliRunner().invoke(cli, args)
        assert result.exception is None or isinstance(result.exception, SystemExit), result.output
        assert "COBOL015" not in result.output

        baseline = CliRunner().invoke(
            cli, ["analyze", str(src), "--severity", "LOW", "--output", "json", "--no-config"]
        )
        assert "COBOL015" in baseline.output


# ---------------------------------------------------------------- COBOL004 byte view


def _redefines(binary_pic, *byte_pics):
    data = [("A", f"01  TWO-BYTES-BINARY        PIC {binary_pic} BINARY.")]
    data.append(("A", "01  TWO-BYTES-ALPHA         REDEFINES TWO-BYTES-BINARY."))
    data += [("B", f"05  BYTE-{i}   PIC {pic}.") for i, pic in enumerate(byte_pics)]
    return _program("RDF", data=tuple(data))


@pytest.mark.parametrize(
    "binary_pic, bytes_, flagged",
    [
        ("9(4)", ("X", "X"), False),  # CardDemo file-status idiom
        ("9(4)", ("X(2)",), False),
        ("9(9)", ("X(2)", "XX"), False),
        ("9(18)", ("X(8)",), False),
        ("S9(4)", ("X", "X"), True),  # signed: sign handling, still flagged
        ("9(4)", ("X", "X", "X"), True),  # size mismatch
        ("9(4)", ("X", "9"), True),  # a digit view, not bytes
        ("9(5)", ("X", "X"), True),  # 9(5) BINARY is 4 bytes
    ],
)
def test_byte_view_idiom(binary_pic, bytes_, flagged):
    issues = CobolGovernanceAnalyzer().analyze("RDF.cbl", _redefines(binary_pic, *bytes_))
    assert any(i.rule_id == "COBOL004" for i in issues) is flagged


def test_byte_view_reverse_direction():
    src = _program(
        "RDF",
        data=(
            ("A", "01  BYTES-VIEW."),
            ("B", "05  B1   PIC X."),
            ("B", "05  B2   PIC X."),
            ("A", "01  BIN-VIEW REDEFINES BYTES-VIEW PIC 9(4) COMP."),
        ),
    )
    issues = CobolGovernanceAnalyzer().analyze("RDF.cbl", src)
    assert not [i for i in issues if i.rule_id == "COBOL004"]


# ---------------------------------------------------------------- continuation


class TestContinuation:
    def test_literal_continuation_joins_without_quote(self):
        assert _join_continuation("VALUE 'ABC;PW", "'D=x;'.") == "VALUE 'ABC;PWD=x;'."

    def test_non_literal_continuation_joins_with_space(self):
        assert _join_continuation("MOVE A", "TO B.") == "MOVE A TO B."

    def test_closed_literal_then_new_literal(self):
        assert _join_continuation("DISPLAY 'A'", "'B'.") == "DISPLAY 'A' 'B'."

    def test_connection_string_split_over_continuation(self):
        head = "01  WS-CONN PIC X(80) VALUE 'SERVER=DBPROD01;DB=CARDS;UID=APPS;PW"
        assert len(" " * 7 + head) == 72
        src = _program("CONT", data=(("A", head), ("-", "    'D=Kq7#mZ2;'.")))
        issues = CobolGovernanceAnalyzer().analyze("CONT.cbl", src)
        assert any(i.rule_id == "COBOL009" for i in issues)


# ---------------------------------------------------------------- free-format notice


class TestFormatNotice:
    def _project(self, tmp_path):
        (tmp_path / "FREE.cbl").write_text(
            "IDENTIFICATION DIVISION.\nPROGRAM-ID. FREE.\nPROCEDURE DIVISION.\n    GOBACK.\n"
        )
        (tmp_path / "FIXED.cbl").write_text(_program("FIXED"))

    def test_meta_and_file_metadata(self, tmp_path):
        self._project(tmp_path)
        engine, report = _analyze(tmp_path)
        meta = engine._build_meta()
        notices = meta["cobol_format_notices"]
        assert [Path(p).name for p in notices["inferred_free"]] == ["FREE.cbl"]
        assert notices["message"] == COBOL_INFERRED_FREE_NOTICE
        formats = {
            Path(r.file_path).name: (r.metadata or {}).get("cobol_source_format")
            for r in report.file_results
        }
        assert formats["FREE.cbl"] == "inferred-free"
        assert formats["FIXED.cbl"] is None

    def test_no_notice_for_fixed_only(self, tmp_path):
        (tmp_path / "FIXED.cbl").write_text(_program("FIXED"))
        engine, _ = _analyze(tmp_path)
        assert "cobol_format_notices" not in engine._build_meta()

    def test_text_report_shows_notes(self, tmp_path):
        from hefesto.cli.main import cli

        self._project(tmp_path)
        result = CliRunner().invoke(cli, ["analyze", str(tmp_path), "--no-config"])
        assert "Notes:" in result.output
        assert "FREE.cbl" in result.output
        assert "free format" in result.output

    def test_text_report_caps_list(self):
        from hefesto.core.analysis_models import AnalysisReport, AnalysisSummary
        from hefesto.reports.text_reporter import TextReporter

        files = [f"/x/F{i}.cbl" for i in range(13)]
        summary = AnalysisSummary(
            files_analyzed=0,
            total_issues=0,
            critical_issues=0,
            high_issues=0,
            medium_issues=0,
            low_issues=0,
            total_loc=0,
            duration_seconds=0.0,
        )
        report = AnalysisReport(summary=summary, file_results=[])
        report.meta = {"cobol_format_notices": {"inferred_free": files, "message": "m"}}
        notes = TextReporter()._format_notes(report)
        assert "13 COBOL file(s)" in notes and "F9.cbl" in notes
        assert "F10.cbl" not in notes and "3 more" in notes
