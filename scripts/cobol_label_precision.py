#!/usr/bin/env python3
"""Precision per COBOL rule from a labelled sample of findings.

Reads a labels JSON (default: tests/fixtures/cobol/labels/phase3_labels.json),
where each label has ``rule``, ``file``, ``line``, ``verdict`` (TP/FP),
``reason`` and ``sets`` (the runs that produced the finding: ``before``,
``after`` and ``leftovers``), and prints TP / labelled findings per rule and run.

Usage:
    python scripts/cobol_label_precision.py [--labels PATH] [--json]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_LABELS = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "cobol"
    / "labels"
    / "phase3_labels.json"
)
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--json", action="store_true", help="Print the table as JSON")
    args = parser.parse_args(argv)

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
