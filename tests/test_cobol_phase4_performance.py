"""Phase 4 (performance): scaling, bounded copybook search, nested COPY.

The timing checks compare the analyzer against itself (a 4x bigger input must
not take ~16x longer, which is what an O(n^2) path does) with a wide margin,
so they do not depend on how fast the CI machine is.
"""

import importlib.util
import sys
import time
from pathlib import Path

import pytest

from hefesto.analyzers.devops import cobol_project_index as cpi
from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer
from hefesto.analyzers.devops.cobol_project_index import (
    CobolProjectIndex,
    library_copybook_names,
)
from hefesto.core.analyzer_engine import AnalyzerEngine

ROOT = Path(__file__).parents[1]


def _load_bench():
    spec = importlib.util.spec_from_file_location(
        "cobol_perf_bench_script", ROOT / "scripts" / "cobol_perf_bench.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["cobol_perf_bench_script"] = module
    spec.loader.exec_module(module)
    return module


bench = _load_bench()


def _a(text):
    return " " * 7 + text


def _b(text):
    return " " * 11 + text


def _sectioned_program(paragraphs):
    """A PERFORMed SECTION whose many paragraphs only run inside it: each one
    used to rescan the section from its start (O(n^2) in COBOL014)."""
    lines = [
        _a("IDENTIFICATION DIVISION."),
        _a("PROGRAM-ID. SECTS."),
        _a("DATA DIVISION."),
        _a("WORKING-STORAGE SECTION."),
        _a("01  WS-N PIC 9(4)."),
        _a("PROCEDURE DIVISION."),
        _a("MAIN-SECTION SECTION."),
        _a("MAIN-PARA."),
        _b("PERFORM WORK-SECTION"),
        _b("GOBACK."),
        _a("WORK-SECTION SECTION."),
        _b("MOVE 0 TO WS-N."),  # the section has its own sentence first
    ]
    for p in range(paragraphs):
        lines += [_a(f"P-{p:05d}."), _b("ADD 1 TO WS-N"), _b("DISPLAY WS-N.")]
    return "\n".join(lines) + "\n"


def _best_time(source, repeat=3):
    analyzer = CobolGovernanceAnalyzer()
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        analyzer.analyze("BIG.cbl", source)
        best = min(best, time.perf_counter() - start)
    return best


def _generated_program(lines):
    return "\n".join(bench._program("BIG", lines // 17 + 1, 1)[:lines]) + "\n"


@pytest.mark.parametrize("make", [_generated_program, lambda n: _sectioned_program(n // 3)])
def test_analysis_time_grows_linearly(make):
    small = _best_time(make(5_000))
    large = _best_time(make(20_000))
    # linear: ~4x; quadratic: ~16x. 10x leaves room for noisy CI runners.
    assert large < max(small, 0.01) * 10, (small, large)


def test_big_file_absolute_bound():
    # ~20k lines in well under a second locally; 10 s is a loose ceiling
    # (500 s per 1M lines) that only a pathological regression can hit.
    assert _best_time(_generated_program(20_000), repeat=1) < 10


def test_big_file_output_stays_grouped():
    issues = CobolGovernanceAnalyzer().analyze("BIG.cbl", _generated_program(20_000))
    # thousands of GO TO / paragraphs, but one grouped finding per rule
    by_rule = {}
    for issue in issues:
        by_rule[issue.rule_id] = by_rule.get(issue.rule_id, 0) + 1
    assert len(issues) <= 10, by_rule
    assert all(count == 1 for count in by_rule.values()), by_rule


def test_generator_writes_nested_copy_project(tmp_path):
    size = bench.generate(tmp_path, programs=5, paragraphs=3, big=[200])
    assert size["files"] == 60 + 5 + 1
    assert size["lines"] == sum(
        len(p.read_text().splitlines()) for p in tmp_path.rglob("*") if p.is_file()
    )
    mid = (tmp_path / "copybooks" / "MID000.cpy").read_text()
    assert "COPY LEAF000 REPLACING ==:TAG:== BY ==MID000==." in mid
    report = AnalyzerEngine(severity_threshold="LOW").analyze_path(str(tmp_path))
    rules = {i.rule_id for r in report.file_results for i in r.issues}
    assert "COBOL015" not in rules  # nested and REPLACING copybooks all resolve


def test_nested_copy_dependents_are_transitive_and_cycle_safe():
    index = CobolProjectIndex.from_sources(
        [
            ("src/P1.cbl", _b("COPY TOP.") + "\n"),
            ("src/P2.cbl", _b("COPY MID REPLACING ==:X:== BY ==Y==.") + "\n"),
            ("cpy/TOP.cpy", _b("COPY MID.") + "\n"),
            ("cpy/MID.cpy", _b("COPY LEAF.") + "\n" + _b("COPY TOP.") + "\n"),  # cycle
            ("cpy/LEAF.cpy", _b("05 X PIC X.") + "\n"),
        ]
    )
    assert index.dependent_programs("LEAF") == ["src/P1.cbl", "src/P2.cbl"]
    assert index.dependent_programs("TOP") == ["src/P1.cbl", "src/P2.cbl"]
    assert index.copy_names_for("src/P2.cbl") == [(1, "MID")]


def test_missing_nested_copybook_reported_in_the_copybook(tmp_path):
    (tmp_path / "P1.cbl").write_text(
        "\n".join(
            [
                _a("IDENTIFICATION DIVISION."),
                _a("PROGRAM-ID. P1."),
                _a("DATA DIVISION."),
                _a("WORKING-STORAGE SECTION."),
                _b("COPY OUTER."),
                _a("PROCEDURE DIVISION."),
                _b("GOBACK."),
            ]
        )
        + "\n"
    )
    (tmp_path / "OUTER.cpy").write_text(_a("01 REC.") + "\n" + _b("COPY GONE.") + "\n")
    report = AnalyzerEngine(severity_threshold="LOW").analyze_path(str(tmp_path))
    found = [
        (Path(r.file_path).name, i.rule_id)
        for r in report.file_results
        for i in r.issues
        if i.rule_id == "COBOL015"
    ]
    assert found == [("OUTER.cpy", "COBOL015")]


def test_library_search_is_bounded_and_skips_hidden_dirs(tmp_path, caplog):
    deep = tmp_path
    for level in range(5):
        deep = deep / f"d{level}"
        deep.mkdir()
        (deep / f"LVL{level}.cpy").write_text(_b("05 X PIC X.") + "\n")
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "HIDDEN.cpy").write_text(_b("05 X PIC X.") + "\n")

    assert library_copybook_names([tmp_path]) == {f"LVL{n}" for n in range(5)}
    # d0 is depth 0 below the root: max_depth=2 walks d0 and d1 only
    assert library_copybook_names([tmp_path], max_depth=2) == {"LVL0", "LVL1"}
    with caplog.at_level("WARNING"):
        assert len(library_copybook_names([tmp_path], max_files=2)) == 2
    assert "stopped after 2 files" in caplog.text


def test_engine_walks_copybook_paths_once(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "EXT.cpy").write_text(_b("05 X PIC X.") + "\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "P1.cbl").write_text(_a("IDENTIFICATION DIVISION.") + "\n" + _b("COPY EXT.") + "\n")
    calls = []
    real = cpi.library_copybook_files

    def counting(dirs, *args, **kwargs):
        calls.append(list(dirs))
        return real(dirs, *args, **kwargs)

    monkeypatch.setattr(cpi, "library_copybook_files", counting)
    engine = AnalyzerEngine(severity_threshold="LOW")
    engine.set_copybook_paths([str(lib)])
    engine.analyze_path(str(src))
    engine.analyze_path(str(src))
    assert len(calls) == 1
    assert "EXT" in engine._cobol_index.available
    engine.set_copybook_paths([str(lib)])
    engine.analyze_path(str(src))
    assert len(calls) == 2
