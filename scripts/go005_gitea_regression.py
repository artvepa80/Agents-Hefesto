#!/usr/bin/env python3
"""Check GO005 against the retired GO002 sites on a gitea checkout.

The 57 file:line pairs live in
``tests/fixtures/go005/gitea_retired_go002_sites.txt``, pinned to gitea
``5c723ee0fd8954e11ebef8b2868745ee1e98e7f7`` (2026-11-03). GO005 must report
none of those lines. ``modelmigration/base/db.go:348`` is not in the list and
must stay reported. The script reads ``git rev-parse HEAD`` in the checkout
and exits with an error when that commit is different.

CI does not fetch gitea. ``tests/fixtures/go005/gitea_retired_go002_result.txt``
is the recorded result of this script. Refresh it with a local checkout:

    python scripts/go005_gitea_regression.py /path/to/gitea --write-result
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "tests" / "fixtures" / "go005" / "gitea_retired_go002_sites.txt"
RESULT = ROOT / "tests" / "fixtures" / "go005" / "gitea_retired_go002_result.txt"
SHA = "5c723ee0fd8954e11ebef8b2868745ee1e98e7f7"
KEPT = "modelmigration/base/db.go:348"


class CheckoutPinError(RuntimeError):
    """The checkout HEAD is not the pinned gitea commit."""


def read_head(root: Path) -> str:
    """Return ``git rev-parse HEAD`` for ``root``."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or "git rev-parse HEAD failed"
        raise CheckoutPinError(f"{root}: {detail}")
    return proc.stdout.strip()


def require_pin(root: Path) -> str:
    """Exit path for a checkout that is not ``SHA``. Returns the HEAD when it matches."""
    head = read_head(root)
    if head != SHA:
        raise CheckoutPinError(f"checkout HEAD {head} is not the pinned commit {SHA}")
    return head


def load_sites(path: Path = SITES) -> list[tuple[str, int]]:
    """Return ``(relative path, line)`` pairs. Comments and blank lines are skipped."""
    rows: list[tuple[str, int]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rel, _, number = line.rpartition(":")
        rows.append((rel, int(number)))
    return rows


def _go005_lines(root: Path, rel: str) -> set[int]:
    from hefesto.analyzers.security import SecurityAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    text = (root / rel).read_text(encoding="utf-8")
    tree = TreeSitterParser("go").parse(text, rel)
    analyzer = SecurityAnalyzer()
    analyzer.lang_rules = True
    return {issue.line for issue in analyzer.analyze(tree, rel, text) if issue.rule_id == "GO005"}


def check(root: Path, sites: list[tuple[str, int]] | None = None) -> dict[str, object]:
    """Report GO005 lines that land on retired sites, and whether the kept hit remains."""
    require_pin(root)
    chosen = load_sites() if sites is None else sites
    by_file: dict[str, set[int]] = defaultdict(set)
    for rel, line in chosen:
        by_file[rel].add(line)
    kept_file, _, kept_line_text = KEPT.rpartition(":")
    by_file[kept_file].add(int(kept_line_text))
    found: dict[str, set[int]] = {}
    missing: list[str] = []
    for rel in sorted(by_file):
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        found[rel] = _go005_lines(root, rel)
    hits = [
        f"{rel}:{line}"
        for rel, lines in sorted(by_file.items())
        if rel != kept_file
        for line in sorted(lines & found.get(rel, set()))
    ]
    kept_present = int(kept_line_text) in found.get(kept_file, set())
    return {
        "sha": SHA,
        "retired_sites": len(chosen),
        "go005_on_retired_sites": hits,
        "kept_hit": KEPT,
        "kept_hit_reported": kept_present,
        "missing_files": missing,
    }


def format_result(report: dict[str, object]) -> str:
    hits = report["go005_on_retired_sites"]
    missing = report["missing_files"]
    if not isinstance(hits, list) or not isinstance(missing, list):
        raise TypeError("regression report lists are the wrong type")
    lines = [
        f"sha: {report['sha']}",
        f"retired_sites: {report['retired_sites']}",
        f"go005_on_retired_sites: {len(hits)}",
        f"kept_hit: {report['kept_hit']}",
        f"kept_hit_reported: {str(report['kept_hit_reported']).lower()}",
        "ci: CI does not fetch gitea. This file is the recorded result of",
        "scripts/go005_gitea_regression.py on a local checkout of the sha above.",
    ]
    if hits:
        lines.append("hits:")
        lines.extend(f"  {hit}" for hit in hits)
    if missing:
        lines.append("missing:")
        lines.extend(f"  {rel}" for rel in missing)
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("checkout", type=Path, help="gitea checkout of the pinned sha")
    parser.add_argument(
        "--write-result",
        action="store_true",
        help="write tests/fixtures/go005/gitea_retired_go002_result.txt",
    )
    args = parser.parse_args(argv)
    try:
        report = check(args.checkout)
    except CheckoutPinError as exc:
        print(f"go005 gitea regression: {exc}", file=sys.stderr)
        return 1
    text = format_result(report)
    if args.write_result:
        RESULT.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    ok = (
        report["retired_sites"] == 57
        and report["go005_on_retired_sites"] == []
        and report["kept_hit_reported"] is True
        and report["missing_files"] == []
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
