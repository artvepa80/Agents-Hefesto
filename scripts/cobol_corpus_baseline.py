#!/usr/bin/env python3
"""Baseline of HefestoAI findings on public COBOL corpora at pinned commits.

Clones AWS CardDemo, IBM CICS GenApp and IBM zopeneditor-sample at fixed
commits (the corpus code is never committed here), runs ``hefesto analyze``
on each one and records counts per rule, per severity and per file, plus
the individual findings and timing.

Usage:
    # (Re)generate the committed baseline
    python scripts/cobol_corpus_baseline.py run --output benchmark/cobol/baseline.json

    # Compare a fresh run against it (exit 1 if findings changed)
    python scripts/cobol_corpus_baseline.py compare --baseline benchmark/cobol/baseline.json

    # Reuse existing clones or an already saved run
    ... --workdir ~/.cache/hefesto-cobol-corpus
    ... compare --current /tmp/new.json

Needs git and network for the first clone. Not run in CI by default.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = REPO_ROOT / "benchmark" / "cobol" / "baseline.json"

CORPORA: List[Dict[str, str]] = [
    {
        "name": "carddemo",
        "url": "https://github.com/aws-samples/aws-mainframe-modernization-carddemo.git",
        "commit": "59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e",
        "license": "Apache-2.0",
    },
    {
        "name": "genapp",
        "url": "https://github.com/cicsdev/cics-genapp.git",
        "commit": "f6f3f4b2580d31b7d8dcc31ce3e3676f4cceaaaa",
        "license": "EPL-2.0",
    },
    {
        "name": "zopeneditor-sample",
        "url": "https://github.com/IBM/zopeneditor-sample.git",
        "commit": "8f9835308de6159eb54f226041d5f81a780cb8eb",
        "license": "Apache-2.0",
    },
]

Finding = Tuple[str, str, int]  # (rule, relative file, line)


def _git(args: List[str], cwd: Optional[Path] = None) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return out.stdout.strip()


def checkout(corpus: Dict[str, str], workdir: Path) -> Path:
    """Shallow-fetch the pinned commit into ``workdir/<name>`` (reused if present)."""
    target = workdir / corpus["name"]
    if (target / ".git").is_dir():
        try:
            if _git(["rev-parse", "HEAD"], target) == corpus["commit"]:
                return target
        except subprocess.CalledProcessError:
            pass
    else:
        target.mkdir(parents=True, exist_ok=True)
        _git(["init", "-q"], target)
        _git(["remote", "add", "origin", corpus["url"]], target)
    _git(["fetch", "-q", "--depth", "1", "origin", corpus["commit"]], target)
    _git(["checkout", "-q", "--force", "FETCH_HEAD"], target)
    head = _git(["rev-parse", "HEAD"], target)
    if head != corpus["commit"]:
        raise RuntimeError(f"{corpus['name']}: expected {corpus['commit']}, got {head}")
    return target


def analyze(path: Path) -> Tuple[Dict[str, Any], float]:
    """Run ``hefesto analyze`` (JSON, all severities); return report and wall time."""
    env = dict(os.environ)
    env.setdefault("HEFESTO_TELEMETRY_ENV", "dogfood")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO_ROOT), env.get("PYTHONPATH")]))
    cmd = [sys.executable, "-m", "hefesto", "analyze", str(path)]
    cmd += ["--severity", "low", "--output", "json"]
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    wall = time.perf_counter() - start
    stdout = proc.stdout
    if "{" not in stdout:
        raise RuntimeError(
            f"hefesto analyze produced no JSON (exit {proc.returncode}):\n{proc.stderr}"
        )
    return json.loads(stdout[stdout.index("{") :]), wall


def _rel(file_path: str, root: Path) -> str:
    try:
        return Path(file_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(file_path).as_posix()


def summarize(report: Dict[str, Any], root: Path) -> Dict[str, Any]:
    """Reduce a ``hefesto analyze`` JSON report to stable counts and findings."""
    by_rule: collections.Counter = collections.Counter()
    by_severity: collections.Counter = collections.Counter()
    per_file: Dict[str, Dict[str, int]] = {}
    findings: List[Finding] = []
    for entry in report.get("files", []):
        rel = _rel(entry.get("file", ""), root)
        counts: collections.Counter = collections.Counter()
        for issue in entry.get("issues", []):
            rule = issue.get("rule_id") or issue.get("type") or "UNKNOWN"
            by_rule[rule] += 1
            by_severity[issue.get("severity", "UNKNOWN")] += 1
            counts[rule] += 1
            findings.append((rule, rel, int(issue.get("line") or 0)))
        if counts:
            per_file[rel] = dict(sorted(counts.items()))
    summary = report.get("summary", {})
    cobol = {k: v for k, v in by_rule.items() if k.startswith("COBOL")}
    return {
        "files_analyzed": summary.get("files_analyzed"),
        "total_loc": summary.get("total_loc"),
        "total_findings": sum(by_rule.values()),
        "cobol_findings": sum(cobol.values()),
        "by_rule": dict(sorted(by_rule.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "per_file": dict(sorted(per_file.items())),
        "findings": [list(f) for f in sorted(findings)],
    }


# Paths whose uncommitted changes would make the findings differ from ``commit``.
ANALYZER_PATHS = ["hefesto", "pyproject.toml"]


def _hefesto_ref() -> Dict[str, Any]:
    """Version from pyproject.toml (installed metadata can be stale) and git commit.

    ``commit`` is the HEAD the findings were produced from. ``dirty`` is True
    when the analyzer code had uncommitted changes, i.e. the findings do not
    correspond to ``commit``. Commit the code first, then regenerate the
    baseline, so the committed file says ``dirty: false``. ``analyzer_tree``
    is the git tree hash of ``hefesto/`` at ``commit``: unlike the commit SHA
    it survives a squash merge, so ``git rev-parse <commit>:hefesto`` on main
    tells whether a later commit still has the same analyzer code.
    """
    version: Optional[str] = None
    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.is_file():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.startswith("version"):
                version = line.split("=", 1)[1].strip().strip('"')
                break
    commit: Optional[str]
    tree: Optional[str]
    dirty: Optional[bool]
    try:
        commit = _git(["rev-parse", "HEAD"], REPO_ROOT)
        tree = _git(["rev-parse", "HEAD:hefesto"], REPO_ROOT)
        dirty = bool(_git(["status", "--porcelain", "--", *ANALYZER_PATHS], REPO_ROOT))
    except (subprocess.CalledProcessError, OSError):
        commit, tree, dirty = None, None, None
    if dirty:
        print(
            f"warning: uncommitted analyzer changes; findings do not match {commit}",
            file=sys.stderr,
        )
    return {"version": version, "commit": commit, "analyzer_tree": tree, "dirty": dirty}


def run_all(workdir: Path, only: Optional[List[str]] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hefesto": _hefesto_ref(),
        "corpora": {},
    }
    for corpus in CORPORA:
        if only and corpus["name"] not in only:
            continue
        path = checkout(corpus, workdir)
        report, wall = analyze(path)
        data = summarize(report, path)
        data["timing"] = {
            "analyze_seconds": round(
                float(report.get("summary", {}).get("duration_seconds") or 0), 3
            ),
            "wall_seconds": round(wall, 3),
        }
        result["corpora"][corpus["name"]] = {
            "url": corpus["url"],
            "commit": corpus["commit"],
            "license": corpus["license"],
            **data,
        }
        print(
            f"{corpus['name']:20} files={data['files_analyzed']} findings={data['total_findings']}"
            f" cobol={data['cobol_findings']} wall={wall:.1f}s",
            file=sys.stderr,
        )
    return result


def diff(baseline: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    """Per corpus and rule: findings new in ``current`` and removed since ``baseline``."""
    out: Dict[str, Any] = {}
    names = sorted(set(baseline.get("corpora", {})) | set(current.get("corpora", {})))
    for name in names:
        old_c = baseline.get("corpora", {}).get(name)
        new_c = current.get("corpora", {}).get(name)
        if old_c is None or new_c is None:
            out[name] = {"status": "missing in baseline" if old_c is None else "missing in current"}
            continue
        old = collections.Counter(tuple(f) for f in old_c.get("findings", []))
        new = collections.Counter(tuple(f) for f in new_c.get("findings", []))
        added, removed = new - old, old - new
        rules: Dict[str, Dict[str, List[List[Any]]]] = {}
        for label, bag in (("new", added), ("removed", removed)):
            for finding in sorted(bag.elements()):
                rules.setdefault(finding[0], {"new": [], "removed": []})[label].append(
                    [finding[1], finding[2]]
                )
        entry: Dict[str, Any] = {"rules": dict(sorted(rules.items()))}
        if old_c.get("commit") != new_c.get("commit"):
            entry["commit_changed"] = [old_c.get("commit"), new_c.get("commit")]
        old_t = (old_c.get("timing") or {}).get("analyze_seconds")
        new_t = (new_c.get("timing") or {}).get("analyze_seconds")
        entry["timing"] = {"baseline": old_t, "current": new_t}
        out[name] = entry
    return out


def has_changes(result: Dict[str, Any]) -> bool:
    return any("status" in c or c.get("rules") or c.get("commit_changed") for c in result.values())


def format_diff(result: Dict[str, Any], limit: int = 20) -> str:
    lines: List[str] = []
    for name, entry in result.items():
        if "status" in entry:
            lines.append(f"{name}: {entry['status']}")
            continue
        timing = entry["timing"]
        lines.append(f"{name}: analyze {timing['baseline']}s -> {timing['current']}s")
        if entry.get("commit_changed"):
            lines.append(
                f"  commit changed: {entry['commit_changed'][0]} -> {entry['commit_changed'][1]}"
            )
        if not entry["rules"]:
            lines.append("  no finding changes")
        for rule, change in entry["rules"].items():
            lines.append(f"  {rule}: +{len(change['new'])} -{len(change['removed'])}")
            for label, sign in (("new", "+"), ("removed", "-")):
                for path, line in change[label][:limit]:
                    lines.append(f"    {sign} {path}:{line}")
                if len(change[label]) > limit:
                    lines.append(f"    {sign} ... {len(change[label]) - limit} more")
    return "\n".join(lines)


def _workdir(arg: Optional[Path]) -> Path:
    if arg:
        arg.mkdir(parents=True, exist_ok=True)
        return arg
    return Path(tempfile.mkdtemp(prefix="hefesto-cobol-corpus-"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="Clone pinned corpora, analyze, write a baseline JSON")
    run_p.add_argument("--output", type=Path, default=DEFAULT_BASELINE)
    cmp_p = sub.add_parser("compare", help="Diff a fresh (or saved) run against a baseline")
    cmp_p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    cmp_p.add_argument("--current", type=Path, help="Saved run JSON instead of a fresh run")
    cmp_p.add_argument("--save", type=Path, help="Also write the fresh run here")
    cmp_p.add_argument("--json", action="store_true", help="Print the diff as JSON")
    for p in (run_p, cmp_p):
        p.add_argument("--workdir", type=Path, help="Where clones live (reused if pinned)")
        p.add_argument("--corpus", action="append", help="Limit to this corpus (repeatable)")
    args = parser.parse_args(argv)

    if args.command == "run":
        result = run_all(_workdir(args.workdir), args.corpus)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(f"baseline written to {args.output}", file=sys.stderr)
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if args.current:
        current = json.loads(args.current.read_text(encoding="utf-8"))
    else:
        current = run_all(_workdir(args.workdir), args.corpus)
        if args.save:
            args.save.write_text(json.dumps(current, indent=1) + "\n", encoding="utf-8")
    if args.corpus:
        baseline = {
            **baseline,
            "corpora": {k: v for k, v in baseline["corpora"].items() if k in args.corpus},
        }
    result = diff(baseline, current)
    print(json.dumps(result, indent=1) if args.json else format_diff(result))
    return 1 if has_changes(result) else 0


if __name__ == "__main__":
    sys.exit(main())
