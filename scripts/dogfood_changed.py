#!/usr/bin/env python3
"""Changed-file ruff and Hefesto gate.

``.github/workflows/dogfood.yml`` runs this on pull requests (diff against the
base commit) and on pushes to ``main``. Each command is printed before it runs
so the job log is the evidence.

``hefesto analyze`` requires at least one PATH. An empty diff does not invoke
it and exits 0. A diff whose files are all unsupported still invokes it, with
``--allow-no-files``, which keeps that empty run at exit 0. Without the flag
the same run exits 1.

No line-level suppression exists. ``# hefesto: ignore`` is an example in
``docs/ANALYSIS_RULES.md`` (specific-rule suppression is marked as a future
feature) and no detector reads it. ``--exclude-types`` drops a whole issue
type, which would silence every ``HARDCODED_SECRET``. The self-check therefore
expects the one documented public key under ``hefesto/`` and does not hide it
from the changed-file gate.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Fake AKIA key committed for the Action smoke fixture. Not under tests/.
PLANTED_CRITICAL = ".github/action-smoke/critical_secret.py"
PACKAGE = "hefesto"
# Public write-only PostHog project key. See docs/telemetry.md.
DOCUMENTED_KEY_PATH = "hefesto/telemetry/client.py"
DOCUMENTED_KEY_LINE = 28
DOCUMENTED_KEY_TYPE = "HARDCODED_SECRET"
# Components relative to the analyzed directory ``hefesto/``.
DOCUMENTED_KEY_EXCLUDE = "telemetry/client.py"

# Test fixtures and the Action smoke fixture contain planted findings on
# purpose. They are not gated; the self-check still analyzes PLANTED_CRITICAL.
GATE_EXCLUDED_PREFIXES = ("tests/fixtures/", ".github/action-smoke/")

GATE_OPTIONS = [
    "--severity",
    "medium",
    "--fail-on",
    "critical",
    "--allow-no-files",
]


class DogfoodError(RuntimeError):
    """The gate could not be run (bad revision, or the analyzer did not start)."""


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def is_zero_rev(rev: str) -> bool:
    """True for GitHub's all-zero ``before`` SHA on a newly created branch."""
    compact = rev.strip().lower()
    return bool(compact) and set(compact) == {"0"}


def empty_tree(repo: Path) -> str:
    """Object id of an empty tree in ``repo`` (used when ``before`` is all zeros)."""
    proc = _git(repo, ["hash-object", "-t", "tree", "/dev/null"])
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = proc.stderr.strip() or "git hash-object failed"
        raise DogfoodError(detail)
    return proc.stdout.strip()


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    """Existing files added, copied, modified, renamed or type-changed.

    Deleted paths are omitted: they are not on disk to analyze.
    """
    resolved_base = empty_tree(repo) if is_zero_rev(base) else base
    proc = _git(
        repo,
        ["diff", "--name-only", "--diff-filter=ACMRT", "-z", resolved_base, head],
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"git diff exited {proc.returncode}"
        raise DogfoodError(detail)
    names = [name for name in proc.stdout.split("\0") if name]
    return [name for name in names if (repo / name).is_file()]


def split_gate_files(files: list[str]) -> tuple[list[str], list[str]]:
    """Split changed files into (gated, excluded fixture paths)."""
    kept: list[str] = []
    skipped: list[str] = []
    for name in files:
        if name.startswith(GATE_EXCLUDED_PREFIXES):
            skipped.append(name)
        else:
            kept.append(name)
    return kept, skipped


def _telemetry_env() -> dict[str, str]:
    env = os.environ.copy()
    env["HEFESTO_TELEMETRY"] = "0"
    return env


def print_command(argv: list[str], *, telemetry: bool = False) -> None:
    rendered = shlex.join(argv)
    if telemetry:
        rendered = "HEFESTO_TELEMETRY=0 " + rendered
    print("+ " + rendered, flush=True)


def _run(argv: list[str], repo: Path, *, capture: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=repo,
        env=_telemetry_env(),
        check=False,
        capture_output=capture,
        text=True,
    )


def ruff_argv(py_files: list[str]) -> list[str]:
    # --force-exclude: files passed explicitly still honour [tool.ruff]
    # extend-exclude (scripts/, examples/), as they do on a tree walk.
    return [sys.executable, "-m", "ruff", "check", "--force-exclude", *py_files]


def hefesto_argv(paths: list[str], extra: list[str] | None = None) -> list[str]:
    return [sys.executable, "-m", "hefesto", "analyze", *paths, *GATE_OPTIONS, *(extra or [])]


def run_changed_gate(repo: Path, files: list[str]) -> int:
    """Ruff on changed Python files, then Hefesto on every existing changed file."""
    exit_code = 0
    py_files = [name for name in files if name.endswith(".py")]
    if py_files:
        argv = ruff_argv(py_files)
        print_command(argv)
        result = _run(argv, repo, capture=False)
        exit_code = result.returncode or exit_code
    else:
        print("ruff check: no changed .py files; not run", flush=True)

    if files:
        argv = hefesto_argv(files)
        print_command(argv, telemetry=True)
        result = _run(argv, repo, capture=False)
        if result.returncode != 0:
            exit_code = result.returncode
    else:
        print(
            "hefesto analyze: no changed files. PATHS is required, so analyze was not run. "
            "An empty analyzable set is "
            + shlex.join(hefesto_argv(["<files>"]))
            + " (--allow-no-files exits 0).",
            flush=True,
        )
    return exit_code


def critical_issues(repo: Path, paths: list[str]) -> list[dict[str, object]]:
    """CRITICAL findings for ``paths``. Exit 2 from the CLI is an error."""
    argv = [
        sys.executable,
        "-m",
        "hefesto",
        "analyze",
        *paths,
        "--output",
        "json",
        "--severity",
        "critical",
        "--allow-no-files",
    ]
    print_command(argv, telemetry=True)
    proc = _run(argv, repo, capture=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DogfoodError(detail or f"hefesto analyze exited {proc.returncode}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise DogfoodError(f"hefesto JSON was not parseable: {exc}") from exc
    found: list[dict[str, object]] = []
    for file_result in payload["files"]:
        for issue in file_result["issues"]:
            if issue.get("severity") == "CRITICAL":
                found.append(issue)
    return found


def _is_documented_key(repo: Path, issue: dict[str, object]) -> bool:
    raw = issue.get("file")
    if not isinstance(raw, str):
        return False
    try:
        same_file = Path(raw).resolve() == (repo / DOCUMENTED_KEY_PATH).resolve()
    except OSError:
        return False
    return (
        same_file
        and issue.get("line") == DOCUMENTED_KEY_LINE
        and issue.get("type") == DOCUMENTED_KEY_TYPE
    )


def _documented_key_line(repo: Path) -> bool:
    path = repo / DOCUMENTED_KEY_PATH
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    if len(lines) < DOCUMENTED_KEY_LINE:
        return False
    line = lines[DOCUMENTED_KEY_LINE - 1]
    return "POSTHOG_API_KEY" in line and "phc_" in line


def _print_issues(issues: list[dict[str, object]]) -> None:
    for issue in issues:
        print(
            f"  {issue.get('file')}:{issue.get('line')} {issue.get('type')}",
            file=sys.stderr,
        )


def _planted_must_fail(repo: Path) -> bool:
    print("Self-check 1: planted CRITICAL must fail the gate", flush=True)
    planted = repo / PLANTED_CRITICAL
    if not planted.is_file():
        print(f"SELF-CHECK FAILED: missing {PLANTED_CRITICAL}", file=sys.stderr)
        return False
    argv = hefesto_argv([PLANTED_CRITICAL])
    print_command(argv, telemetry=True)
    result = _run(argv, repo, capture=False)
    if result.returncode == 0:
        print(
            "SELF-CHECK FAILED: planted AKIA key did not fail --fail-on critical",
            file=sys.stderr,
        )
        return False
    print(f"planted CRITICAL failed the gate (exit {result.returncode})", flush=True)
    return True


def _current_tree_must_pass(repo: Path) -> bool:
    print("Self-check 2: current hefesto/ tree", flush=True)
    if not _documented_key_line(repo):
        print(
            "SELF-CHECK FAILED: "
            f"{DOCUMENTED_KEY_PATH}:{DOCUMENTED_KEY_LINE} is not the PostHog public key",
            file=sys.stderr,
        )
        return False
    try:
        issues = critical_issues(repo, [PACKAGE])
    except (DogfoodError, KeyError, TypeError) as exc:
        print(f"SELF-CHECK FAILED: {exc}", file=sys.stderr)
        return False
    known = [issue for issue in issues if _is_documented_key(repo, issue)]
    if len(issues) != 1 or len(known) != 1:
        print("SELF-CHECK FAILED: unexpected CRITICAL findings under hefesto/", file=sys.stderr)
        _print_issues(issues)
        return False
    print(
        "sole CRITICAL under hefesto/ is "
        f"{DOCUMENTED_KEY_TYPE} at {DOCUMENTED_KEY_PATH}:{DOCUMENTED_KEY_LINE} "
        "(PostHog public write-only project key, docs/telemetry.md). "
        "The pass check below excludes that file only. The changed-file gate does not.",
        flush=True,
    )
    argv = hefesto_argv([PACKAGE], ["--exclude", DOCUMENTED_KEY_EXCLUDE, "--output", "json"])
    print_command(argv, telemetry=True)
    proc = _run(argv, repo, capture=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:])
        sys.stderr.write(proc.stderr[-4000:])
        print(f"SELF-CHECK FAILED: current tree exit {proc.returncode}", file=sys.stderr)
        return False
    try:
        summary = json.loads(proc.stdout)["summary"]
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"SELF-CHECK FAILED: {exc}", file=sys.stderr)
        return False
    critical = summary.get("critical")
    files = summary.get("files_analyzed")
    print(
        "current tree passed --fail-on critical "
        f"(files {files}, critical {critical}; "
        f"{DOCUMENTED_KEY_EXCLUDE} excluded from this pass check only)",
        flush=True,
    )
    return bool(critical == 0)


def self_check(repo: Path) -> int:
    """Exit 0 when a planted CRITICAL fails and the current package otherwise passes."""
    if not _planted_must_fail(repo):
        return 1
    if not _current_tree_must_pass(repo):
        return 1
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--base", help="Base revision (pull_request base SHA, or push before)")
    parser.add_argument("--head", default="HEAD", help="Head revision (default: HEAD)")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Prove a planted CRITICAL fails and the current hefesto/ tree passes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.self_check:
            return self_check(repo)
        if not args.base:
            print("error: --base is required unless --self-check", file=sys.stderr)
            return 2
        files = changed_files(repo, args.base, args.head)
    except DogfoodError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Changed files ({len(files)}):", flush=True)
    for name in files:
        print(f"  {name}", flush=True)
    if not files:
        print("  (none)", flush=True)
    files, skipped = split_gate_files(files)
    if skipped:
        print(
            f"Fixture files excluded from the gate ({len(skipped)}; "
            + ", ".join(GATE_EXCLUDED_PREFIXES)
            + "):",
            flush=True,
        )
        for name in skipped:
            print(f"  {name}", flush=True)
    return run_changed_gate(repo, files)


if __name__ == "__main__":
    sys.exit(main())
