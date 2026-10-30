#!/usr/bin/env python3
"""Precision per COBOL rule from a labelled sample of findings.

Reads a labels JSON (default: tests/fixtures/cobol/labels/phase3_labels.json),
where each label has ``rule``, ``file``, ``line``, ``verdict`` (TP/FP),
``reason`` and ``sets`` (the runs that produced the finding: ``before``,
``after`` and ``leftovers``), and prints TP / labelled findings per rule and run.

With ``--lineage REPORT`` (repeatable, ``corpus=path/to/analyze.json``) it
instead checks the ``lineage`` section of ``hefesto analyze --output json``
reports against tests/fixtures/cobol/labels/lineage_labels.json: precision per
corpus and edge kind (every produced program/table edge must be labelled) and
conservation (every literal CALL/LINK/XCTL target classified exactly once,
against the expected counts in the labels file).

Usage:
    python scripts/cobol_label_precision.py [--labels PATH] [--json]
    python scripts/cobol_label_precision.py --lineage carddemo=cd.json --lineage genapp=ga.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_LABELS = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "cobol"
    / "labels"
    / "phase3_labels.json"
)
LINEAGE_LABELS = DEFAULT_LABELS.with_name("lineage_labels.json")
PROGRAM_KINDS = ("CALL", "LINK", "XCTL")
VERDICTS = ("TP", "FP")
REQUIRED = ("corpus", "rule", "file", "line", "verdict", "reason", "sets")
# Runs in order: main before Phase 3, the Phase 3 branch, the Phase 3 leftovers branch.
RUNS = ("before", "after", "leftovers")
LATEST_RUN = RUNS[-1]


def validate(doc: dict) -> List[str]:
    """Return a list of problems with the labels document (empty = valid)."""
    problems = []
    labels = doc.get("labels")
    if not isinstance(labels, list):
        return ["'labels' must be a list"]
    seen = set()
    for i, label in enumerate(labels):
        missing = [k for k in REQUIRED if k not in label]
        if missing:
            problems.append(f"label {i}: missing {missing}")
            continue
        if label["verdict"] not in VERDICTS:
            problems.append(f"label {i}: verdict must be TP or FP")
        if not str(label["reason"]).strip():
            problems.append(f"label {i}: empty reason")
        if not isinstance(label["line"], int) or label["line"] < 1:
            problems.append(f"label {i}: line must be a positive integer")
        if not label["sets"] or not set(label["sets"]) <= set(RUNS):
            problems.append(f"label {i}: sets must be a non-empty subset of {'/'.join(RUNS)}")
        key = (
            label["corpus"],
            label["rule"],
            label["file"],
            label["line"],
            label.get("duplicate", 0),
        )
        if key in seen:
            problems.append(f"label {i}: duplicate key {key}")
        seen.add(key)
    return problems


def precision(doc: dict) -> Dict[str, Dict[str, Tuple[int, int]]]:
    """Return {rule: {set: (true positives, labelled)}}."""
    stats: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for label in doc["labels"]:
        for run in label["sets"]:
            cell = stats[label["rule"]][run]
            cell[0] += label["verdict"] == "TP"
            cell[1] += 1
    return {
        rule: {run: (runs[run][0], runs[run][1]) for run in RUNS if run in runs}
        for rule, runs in sorted(stats.items())
    }


def _fmt(cell) -> str:
    if not cell:
        return "-"
    tp, total = cell
    return f"{tp}/{total} ({100 * tp / total:.0f}%)"


def _occurrences(edges: List[dict]) -> List[dict]:
    """One entry per source line of each (merged) edge."""
    return [dict(edge, line=line) for edge in edges for line in edge.get("lines", [edge["line"]])]


def _find_label(labels: Dict[tuple, List[dict]], corpus: str, edge: dict) -> Optional[dict]:
    """Label of ``edge``: same corpus/kind/from/to/line, labelled file a suffix of its path."""
    key = (corpus, edge["kind"], edge["from"], edge["to"], edge["line"])
    path = edge["source_file"].replace("\\", "/")
    for label in labels.get(key, []):
        if path == label["file"] or path.endswith("/" + label["file"]):
            return label
    return None


def lineage_precision(doc: dict, reports: Dict[str, dict]) -> Dict[str, Dict[str, list]]:
    """{corpus: {kind: [labelled, TP, FP, unlabelled]}} for program and table edges."""
    labels: Dict[tuple, List[dict]] = defaultdict(list)
    for lb in doc["labels"]:
        labels[(lb["corpus"], lb["kind"], lb["from"], lb["to"], lb["line"])].append(lb)
    table: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    for corpus, report in sorted(reports.items()):
        for edge in _occurrences(report["lineage"]["edges"]):
            if edge["kind"] == "COPY":
                continue
            label = _find_label(labels, corpus, edge)
            cell = table[corpus][edge["kind"]]
            if label is None:
                cell[3] += 1
                continue
            cell[0] += 1
            cell[1 if label["verdict"] == "TP" else 2] += 1
    return {c: dict(k) for c, k in table.items()}


def lineage_conservation(report: dict) -> Dict[str, Dict[str, int]]:
    """Literal and variable CALL / LINK+XCTL targets by class, from one report."""
    lin = report["lineage"]
    out: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for edge in _occurrences(lin["edges"]):
        if edge["kind"] in PROGRAM_KINDS:
            out[_group(edge["kind"])]["program"] += 1
    for ref in lin["references"]:
        out[_group(ref["kind"])][ref["class"]] += 1
    for item in lin["unresolved"]:
        if item["kind"] in PROGRAM_KINDS:
            out[_group(item["kind"])][item["reason"]] += 1
    return {g: dict(c) for g, c in out.items()}


def _group(kind: str) -> str:
    return "CALL" if kind == "CALL" else "LINK/XCTL"


def _lineage_main(args) -> int:
    doc = json.loads(args.labels.read_text(encoding="utf-8"))
    reports = {}
    for spec in args.lineage:
        corpus, _, path = spec.partition("=")
        reports[corpus] = json.loads(Path(path).read_text(encoding="utf-8"))
    result = {
        "precision": lineage_precision(doc, reports),
        "conservation": {
            c: {"expected": doc["expected"].get(c, {}), "got": lineage_conservation(r)}
            for c, r in sorted(reports.items())
        },
    }
    ok = all(v["expected"] == v["got"] for v in result["conservation"].values())
    ok = ok and all(
        cell[2] == 0 and cell[3] == 0 for k in result["precision"].values() for cell in k.values()
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_lineage(result)
    return 0 if ok else 1


def _print_lineage(result: dict) -> None:
    head = ("corpus", "kind", "labelled", "TP", "FP", "unlab.", "precision")
    print("{:<12} {:<6} {:>8} {:>4} {:>4} {:>6} {:>9}".format(*head))
    for corpus, kinds in sorted(result["precision"].items()):
        for kind, (lab, tp, fp, unl) in sorted(kinds.items()):
            prec = f"{100 * tp / lab:.1f}%" if lab else "-"
            print(f"{corpus:<12} {kind:<6} {lab:>8} {tp:>4} {fp:>4} {unl:>6} {prec:>9}")
    for corpus, cons in result["conservation"].items():
        status = "OK" if cons["expected"] == cons["got"] else "MISMATCH"
        print(f"conservation {corpus}: {status} expected={cons['expected']} got={cons['got']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print the table as JSON")
    parser.add_argument("--lineage", action="append", default=[], metavar="CORPUS=REPORT")
    args = parser.parse_args(argv)
    if args.lineage:
        args.labels = args.labels or LINEAGE_LABELS
        return _lineage_main(args)
    args.labels = args.labels or DEFAULT_LABELS

    doc = json.loads(args.labels.read_text(encoding="utf-8"))
    problems = validate(doc)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    table = precision(doc)
    if args.json:
        print(json.dumps(table, indent=2))
        return 0
    print(f"{len(doc['labels'])} labels from {args.labels}")
    print(f"{'rule':<10}" + "".join(f" {run:>16}" for run in RUNS))
    for rule, runs in table.items():
        print(f"{rule:<10}" + "".join(f" {_fmt(runs.get(run)):>16}" for run in RUNS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
