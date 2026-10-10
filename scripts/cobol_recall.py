#!/usr/bin/env python3
"""Recall per COBOL rule on the seeded-issue fixture.

Scans ``tests/fixtures/cobol/recall/`` (one ``analyze_path`` call, so the COPY
index sees every program and copybook) and checks every seed listed in
``seeds.json``: a seed is found when a finding of the same rule is reported
in the same file within ``tolerance`` lines of the seeded line. Seeds marked
``known_limit`` document cases the regex analyzer is known to miss; they are
counted in the totals so recall is not overstated.

Usage:
    python scripts/cobol_recall.py [--fixture DIR] [--json] [--min-recall 0.9]

Exit code 1 if overall recall is below ``--min-recall`` (default 0, report only).
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "cobol" / "recall"


def load_seeds(fixture: Path) -> dict:
    return json.loads((fixture / "seeds.json").read_text(encoding="utf-8"))


def scan(fixture: Path) -> List[Tuple[str, str, int]]:
    """(rule, path relative to the fixture, line) for every COBOL finding."""
    sys.path.insert(0, str(ROOT))
    from hefesto.core.analyzer_engine import AnalyzerEngine

    engine = AnalyzerEngine(severity_threshold="LOW")
    report = engine.analyze_path(str(fixture))
    root = fixture.resolve()
    found = []
    for result in report.file_results:
        rel = Path(result.file_path).resolve().relative_to(root).as_posix()
        for issue in result.issues:
            if (issue.rule_id or "").startswith("COBOL"):
                found.append((issue.rule_id, rel, issue.line))
    return found


def match(seeds: dict, findings: List[Tuple[str, str, int]]) -> List[dict]:
    """Each seed with ``found`` set (and the matching line, if any)."""
    tolerance = int(seeds.get("tolerance", 0))
    out = []
    for seed in seeds["seeds"]:
        lines = [
            line
            for rule, rel, line in findings
            if rule == seed["rule"]
            and rel == seed["file"]
            and abs(line - seed["line"]) <= tolerance
        ]
        out.append({**seed, "found": bool(lines), "reported_line": min(lines) if lines else None})
    return out


def recall(results: List[dict]) -> Dict[str, Tuple[int, int]]:
    """{rule: (found, seeded)} plus an ``ALL`` row."""
    table: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for item in results:
        for key in (item["rule"], "ALL"):
            table[key][0] += item["found"]
            table[key][1] += 1
    return {rule: (cell[0], cell[1]) for rule, cell in sorted(table.items())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true", help="Print seeds and recall as JSON")
    parser.add_argument("--min-recall", type=float, default=0.0)
    args = parser.parse_args(argv)

    results = match(load_seeds(args.fixture), scan(args.fixture))
    table = recall(results)
    if args.json:
        print(json.dumps({"recall": table, "seeds": results}, indent=2))
    else:
        print(f"{'rule':<10} {'found':>9}")
        for rule, (hit, total) in table.items():
            print(f"{rule:<10} {hit:>3}/{total:<3} ({100 * hit / total:.0f}%)")
        missed = [r for r in results if not r["found"]]
        for item in missed:
            tag = "MISSED (known limit)" if item.get("known_limit") else "MISSED"
            print(f"{tag} {item['rule']} {item['file']}:{item['line']} ({item['seed']})")
    hit, total = table["ALL"]
    return 0 if total and hit / total >= args.min_recall else 1


if __name__ == "__main__":
    sys.exit(main())
