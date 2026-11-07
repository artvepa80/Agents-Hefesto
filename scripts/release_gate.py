#!/usr/bin/env python3
"""Release gate: a run with no flags must give the same JSON on base and head.

For each pinned corpus in ``scripts/release_gate_corpora.txt``, run
``hefesto analyze <corpus> --output json`` from a checkout of BASE and of
HEAD, drop the timing fields, and compare. Any difference (findings,
summary counts, exit code) fails the gate. Experimental features are off,
so new opt-in rules must not change this output.

Usage: python scripts/release_gate.py [--base origin/main] [--head HEAD] [--work DIR]
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "scripts" / "release_gate_corpora.txt"
TIMING_KEYS = frozenset({"duration_ms", "duration_seconds", "timestamp"})
CLI = "import sys; from hefesto.cli.main import cli; sys.argv[0] = 'hefesto'; sys.exit(cli())"


def read_corpora(path: Path) -> List[Tuple[str, str, str]]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name, url, sha = line.split()
            rows.append((name, url, sha))
    return rows


def normalize(value: Any) -> Any:
    """Drop timing keys and sort files by path so only real changes remain."""
    if isinstance(value, dict):
        out = {k: normalize(v) for k, v in value.items() if k not in TIMING_KEYS}
        if isinstance(out.get("files"), list):
            out["files"] = sorted(out["files"], key=lambda f: str(f.get("file", "")))
        return out
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def fetch_corpus(work: Path, name: str, url: str, sha: str) -> Path:
    dest = work / "corpora" / name
    if (dest / ".git").exists() and git("rev-parse", "HEAD", cwd=dest) == sha:
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    git("init", "-q", cwd=dest)
    git("fetch", "-q", "--depth", "1", url, sha, cwd=dest)
    git("checkout", "-q", "--detach", sha, cwd=dest)
    return dest


def checkout(work: Path, label: str, ref: str) -> Path:
    dest = work / f"ref-{label}"
    if dest.exists():
        git("worktree", "remove", "--force", str(dest))
    git("worktree", "add", "-q", "--detach", str(dest), ref)
    return dest


def run(tree: Path, corpus: Path) -> Tuple[int, Dict[str, Any]]:
    env = dict(os.environ, PYTHONPATH=str(tree))
    env.pop("HEFESTO_EXPERIMENTAL", None)
    proc = subprocess.run(
        [sys.executable, "-c", CLI, "analyze", str(corpus), "--output", "json", "--quiet"],
        cwd=tree,
        env=env,
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"unparsed_stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    return proc.returncode, normalize(data)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--work", default=str(ROOT / ".release-gate"))
    args = parser.parse_args(argv)
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    trees = {"base": checkout(work, "base", args.base), "head": checkout(work, "head", args.head)}
    failed = 0
    try:
        for name, url, sha in read_corpora(CORPORA):
            corpus = fetch_corpus(work, name, url, sha)
            results = {label: run(tree, corpus) for label, tree in trees.items()}
            (code_b, data_b), (code_h, data_h) = results["base"], results["head"]
            same = code_b == code_h and data_b == data_h
            total = data_h.get("summary", {}).get("total_issues", "?")
            print(
                f"{'same' if same else 'DIFF'} {name}@{sha[:8]} "
                f"exit={code_b}/{code_h} issues={total}"
            )
            if not same:
                failed += 1
                a = json.dumps(data_b, indent=1, sort_keys=True).splitlines()
                b = json.dumps(data_h, indent=1, sort_keys=True).splitlines()
                diff = list(difflib.unified_diff(a, b, "base", "head", lineterm="", n=2))
                print("\n".join(diff[:200]))
    finally:
        for tree in trees.values():
            git("worktree", "remove", "--force", str(tree))
    print(f"release gate: {failed} corpus(es) differ" if failed else "release gate: no difference")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
