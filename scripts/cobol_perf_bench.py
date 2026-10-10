#!/usr/bin/env python3
"""Performance benchmark for the COBOL analyzer on synthetic inputs.

Generates a deterministic synthetic COBOL project (programs, nested copybooks,
``COPY ... REPLACING``, big single files) and measures wall time and peak
memory of the analysis, each scenario in a fresh subprocess.

Usage:
    python scripts/cobol_perf_bench.py                 # default scenarios
    python scripts/cobol_perf_bench.py --json          # machine-readable
    python scripts/cobol_perf_bench.py --scenario big-500k --keep /tmp/perf
    python scripts/cobol_perf_bench.py generate --programs 50 --out /tmp/p

Scenarios (lines are physical source lines):
    project-1m   1,000 programs of ~1,000 lines + 60 copybooks (~1M lines)
    big-100k     one 100,000-line program
    big-500k     one 500,000-line program
    cli-1m       project-1m through ``hefesto analyze --output json``

Target (Phase 4 of the COBOL plan): under 10 s per 1M lines.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
TARGET_SECONDS_PER_MLOC = 10.0

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "project-1m": {"programs": 1000, "paragraphs": 60, "big": []},
    "big-100k": {"programs": 0, "paragraphs": 0, "big": [100_000]},
    "big-500k": {"programs": 0, "paragraphs": 0, "big": [500_000]},
    "cli-1m": {"programs": 1000, "paragraphs": 60, "big": [], "cli": True},
}
DEFAULT_SCENARIOS = ["project-1m", "big-100k", "big-500k", "cli-1m"]


# ---------------------------------------------------------------- generation


def _a(text: str) -> str:
    return " " * 7 + text


def _b(text: str) -> str:
    return " " * 11 + text


def _copybooks(out: Path) -> Dict[str, List[str]]:
    """60 copybooks: 20 leaf records, 20 that COPY a leaf (nested, one with
    REPLACING), 20 that COPY a level-2 one (depth 3)."""
    books: Dict[str, List[str]] = {}
    for i in range(20):
        books[f"LEAF{i:03d}"] = [
            _b(f"05  :TAG:-ID-{i:03d}       PIC 9(9) COMP."),
            _b(f"05  :TAG:-NAME-{i:03d}     PIC X(30)."),
            _b(f"05  :TAG:-AMT-{i:03d}      PIC S9(7)V99 COMP-3."),
            _b(f"05  :TAG:-FLAG-{i:03d}     PIC X."),
            _b(f"    88  :TAG:-ON-{i:03d}   VALUE 'Y'."),
        ]
    for i in range(20):
        books[f"MID{i:03d}"] = [
            _a(f"01  MID-REC-{i:03d}."),
            _b(f"COPY LEAF{i:03d} REPLACING ==:TAG:== BY ==MID{i:03d}==."),
            _b(f"05  MID-FILLER-{i:03d}   PIC X(10)."),
        ]
    for i in range(20):
        books[f"TOP{i:03d}"] = [
            _b(f"COPY MID{i:03d}."),
            _a(f"01  TOP-COUNT-{i:03d}      PIC 9(4) COMP."),
        ]
    cpy = out / "copybooks"
    cpy.mkdir(parents=True, exist_ok=True)
    for name, lines in books.items():
        (cpy / f"{name}.cpy").write_text("\n".join(lines) + "\n")
    return books


def _program(name: str, paragraphs: int, seed: int) -> List[str]:
    lines = [
        _a("IDENTIFICATION DIVISION."),
        _a(f"PROGRAM-ID. {name}."),
        _a("ENVIRONMENT DIVISION."),
        _a("INPUT-OUTPUT SECTION."),
        _a("FILE-CONTROL."),
        _b("SELECT IN-FILE ASSIGN TO INFILE"),
        _b("    FILE STATUS IS WS-IN-STATUS."),
        _b("SELECT OUT-FILE ASSIGN TO OUTFILE."),
        _a("DATA DIVISION."),
        _a("FILE SECTION."),
        _a("FD  IN-FILE."),
        _a("01  IN-REC                  PIC X(80)."),
        _a("FD  OUT-FILE."),
        _a("01  OUT-REC                 PIC X(80)."),
        _a("WORKING-STORAGE SECTION."),
        _a("01  WS-IN-STATUS            PIC XX."),
        _a("01  WS-COUNT                PIC 9(4) COMP VALUE 0."),
        _a("01  WS-AMOUNT               PIC S9(9)V99 COMP-3."),
        _a("01  WS-AMOUNT-X REDEFINES WS-AMOUNT PIC X(6)."),
        _a("01  WS-TABLE."),
        _b("05  WS-ENTRY OCCURS 1 TO 100 TIMES DEPENDING ON WS-COUNT."),
        _b("    10  WS-KEY          PIC X(10)."),
        _b(f"COPY TOP{seed % 20:03d}."),
        _b(f"COPY LEAF{(seed + 7) % 20:03d} REPLACING ==:TAG:== BY ==WS{seed % 97:02d}==."),
        _a("PROCEDURE DIVISION."),
        _a("MAIN-PARA."),
        _b("OPEN INPUT IN-FILE OUTPUT OUT-FILE"),
        _b("IF WS-IN-STATUS NOT = '00'"),
        _b("    DISPLAY 'OPEN ERROR ' WS-IN-STATUS"),
        _b("END-IF"),
        _b("PERFORM PARA-0001 THRU PARA-0002"),
    ]
    lines += [_b(f"PERFORM PARA-{p:04d}") for p in range(3, paragraphs + 1)]
    lines += [_b("CLOSE IN-FILE OUT-FILE"), _b("GOBACK.")]
    for p in range(1, paragraphs + 1):
        lines += [
            _a(f"PARA-{p:04d}."),
            _b("READ IN-FILE"),
            _b("    AT END MOVE 'Y' TO WS-IN-STATUS"),
            _b("END-READ"),
            _b(f"MOVE IN-REC(1:10) TO WS-KEY({(p % 100) + 1})"),
            _b("ADD 1 TO WS-COUNT"),
            _b(f"COMPUTE WS-AMOUNT = WS-AMOUNT + {p} * 1.05"),
            _b("IF WS-COUNT > 50"),
            _b(f"    GO TO PARA-{p:04d}-EXIT"),
            _b("END-IF"),
            _b("EXEC SQL"),
            _b("    SELECT NAME INTO :WS-KEY FROM CUST WHERE ID = :WS-COUNT"),
            _b("END-EXEC"),
            _b("WRITE OUT-REC FROM IN-REC."),
            _a(f"PARA-{p:04d}-EXIT."),
            _b("EXIT."),
        ]
    lines += [_a("UNUSED-PARA."), _b("DISPLAY 'NEVER CALLED'.")]
    return lines


def generate(
    out: Path, programs: int, paragraphs: int, big: Optional[List[int]] = None
) -> Dict[str, int]:
    """Write the synthetic project; return {"files": n, "lines": n}."""
    out.mkdir(parents=True, exist_ok=True)
    files, total = 0, 0
    if programs:
        books = _copybooks(out)
        files += len(books)
        total += sum(len(b) for b in books.values())
        src = out / "src"
        src.mkdir(exist_ok=True)
        for n in range(programs):
            lines = _program(f"PRG{n:05d}", paragraphs, n)
            (src / f"PRG{n:05d}.cbl").write_text("\n".join(lines) + "\n")
            files += 1
            total += len(lines)
    for size in big or []:
        paragraphs_needed = size // 17 + 1
        lines = _program(f"BIG{size}", paragraphs_needed, 1)[:size]
        (out / f"BIG{size}.cbl").write_text("\n".join(lines) + "\n")
        files += 1
        total += len(lines)
    return {"files": files, "lines": total}


# ---------------------------------------------------------------- measurement


def _measure_engine(path: Path) -> Dict[str, Any]:
    """Run in the child process: analyze ``path`` and report time/memory."""
    sys.path.insert(0, str(ROOT))
    from hefesto.core.analyzer_engine import AnalyzerEngine

    engine = AnalyzerEngine(severity_threshold="LOW")
    start = time.perf_counter()
    report = engine.analyze_path(str(path))
    seconds = time.perf_counter() - start
    issues = [i for r in report.file_results for i in r.issues]
    by_rule: Dict[str, int] = {}
    for issue in issues:
        by_rule[issue.rule_id or "?"] = by_rule.get(issue.rule_id or "?", 0) + 1
    return {
        "seconds": round(seconds, 3),
        "peak_rss_mb": round(_peak_rss_mb(), 1),
        "files_analyzed": report.summary.files_analyzed,
        "findings": len(issues),
        "by_rule": dict(sorted(by_rule.items())),
    }


def _peak_rss_mb(children: bool = False) -> float:
    who = resource.RUSAGE_CHILDREN if children else resource.RUSAGE_SELF
    kb = resource.getrusage(who).ru_maxrss
    # Linux reports KiB, macOS bytes
    return kb / 1024 / 1024 if sys.platform == "darwin" else kb / 1024


def _child_env() -> Dict[str, str]:
    env = dict(os.environ)
    env.setdefault("HEFESTO_TELEMETRY_ENV", "benchmark")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH", "")]))
    return env


def _run_engine_child(path: Path) -> Dict[str, Any]:
    """Fresh interpreter per scenario: peak RSS is not polluted by earlier runs."""
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "_child", str(path)],
        capture_output=True,
        text=True,
        check=True,
        env=_child_env(),
    )
    return dict(json.loads(proc.stdout.strip().splitlines()[-1]))


def _run_cli(path: Path) -> Dict[str, Any]:
    """Through a fresh wrapper process: RUSAGE_CHILDREN then covers only the CLI."""
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "_cli", str(path)],
        capture_output=True,
        text=True,
        check=True,
        env=_child_env(),
    )
    return dict(json.loads(proc.stdout.strip().splitlines()[-1]))


def _measure_cli(path: Path) -> Dict[str, Any]:
    """``hefesto analyze --output json`` end to end (startup, report, JSON)."""
    cmd = [
        sys.executable,
        "-m",
        "hefesto.cli.main",
        "analyze",
        str(path),
        "--severity",
        "low",
        "--output",
        "json",
    ]
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, env=_child_env(), cwd=str(ROOT))
    seconds = time.perf_counter() - start
    return {
        "seconds": round(seconds, 3),
        "rc": proc.returncode,
        "peak_rss_mb": round(_peak_rss_mb(children=True), 1),
        "json_mb": round(len(proc.stdout) / 1e6, 1),
    }


def run_scenario(name: str, workdir: Path) -> Dict[str, Any]:
    spec = SCENARIOS[name]
    target = workdir / name
    size = generate(target, spec["programs"], spec["paragraphs"], spec["big"])
    result = _run_cli(target) if spec.get("cli") else _run_engine_child(target)
    result.update(size)
    result["scenario"] = name
    result["seconds_per_mloc"] = round(result["seconds"] / (size["lines"] / 1e6), 2)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["_child"]:
        print(json.dumps(_measure_engine(Path(argv[1]))))
        return 0
    if argv[:1] == ["_cli"]:
        print(json.dumps(_measure_cli(Path(argv[1]))))
        return 0
    if argv[:1] == ["generate"]:
        gen = argparse.ArgumentParser(description="Write a synthetic COBOL project")
        gen.add_argument("--out", type=Path, required=True)
        gen.add_argument("--programs", type=int, default=1000)
        gen.add_argument("--paragraphs", type=int, default=60)
        gen.add_argument("--big", type=int, action="append", default=[])
        a = gen.parse_args(argv[1:])
        print(json.dumps(generate(a.out, a.programs, a.paragraphs, a.big)))
        return 0

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", action="append", choices=sorted(SCENARIOS))
    parser.add_argument("--keep", type=Path, help="Generate into this directory and keep it")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--max-seconds-per-mloc",
        type=float,
        default=None,
        help=f"Exit 1 if any scenario is slower (target: {TARGET_SECONDS_PER_MLOC})",
    )
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="cobol-perf-") as tmp:
        workdir = args.keep or Path(tmp)
        results = [run_scenario(n, workdir) for n in (args.scenario or DEFAULT_SCENARIOS)]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"{'scenario':<12} {'lines':>9} {'files':>6} {'s':>7} {'s/Mloc':>7} {'MB':>7}")
        for r in results:
            print(
                f"{r['scenario']:<12} {r['lines']:>9} {r['files']:>6} {r['seconds']:>7.2f} "
                f"{r['seconds_per_mloc']:>7.2f} {r['peak_rss_mb']:>7.1f}"
                + (f"  findings={r['findings']}" if "findings" in r else f"  json={r['json_mb']}MB")
            )
    limit = args.max_seconds_per_mloc
    return 1 if limit and any(r["seconds_per_mloc"] > limit for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
