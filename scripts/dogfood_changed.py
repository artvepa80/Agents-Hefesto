#!/usr/bin/env python3
"""Changed-file ruff and Hefesto gate.

``.github/workflows/dogfood.yml`` runs this on pull requests (diff against the
base commit) and on pushes to ``main``. Each command is printed before it runs
so the job log is the evidence.

``hefesto analyze`` requires at least one PATH. An empty diff does not invoke
it and exits 0. A diff whose files are all unsupported still invokes it, with
``--allow-no-files``, which keeps that empty run at exit 0. Without the flag
the same run exits 1.

Python files support ``# hefesto: ignore[TYPE] reason`` (up to HIGH, never
CRITICAL). Every such comment the diff adds is listed with its reason, and
``--fail-on-new-suppressions`` turns any new one into exit 1. ``--exclude-types``
drops a whole issue type, which would silence every ``HARDCODED_SECRET``, so it
is not used.

Paths that are not gated come from the repository's ``.hefesto.yaml``
``exclude`` list, read with the package's own ``load_config``, and are matched
with the engine's ``path_is_excluded``: the same component matcher a full
``hefesto analyze .`` uses. The script filters the changed paths itself,
because ``hefesto analyze`` does not apply ``exclude`` to paths named on the
command line. Patterns are whole path components (``tests/fixtures/``), not
globs: ``tests/fixtures/**`` matches nothing. Without a config file the script
falls back to ``FALLBACK_EXCLUDES`` and says so in the log.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import NamedTuple, Optional

from hefesto.config.project_config import ConfigError, find_config, load_config
from hefesto.core.analyzer_engine import path_is_excluded

REPO_ROOT = Path(__file__).resolve().parent.parent

# Fake AKIA key committed for the Action smoke fixture. Not under tests/.
PLANTED_CRITICAL = ".github/action-smoke/critical_secret.py"
PACKAGE = "hefesto"

# Used only when the repository has no .hefesto.yaml/.hefesto.yml. Test
# fixtures and the Action smoke fixture contain planted findings on purpose;
# the self-check still analyzes PLANTED_CRITICAL by name.
FALLBACK_EXCLUDES = ("tests/fixtures/", ".github/action-smoke/")
_GLOB_CHARS = frozenset("*?[")

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


class GateExcludes(NamedTuple):
    """Exclude patterns for the changed-file gate and the file they came from."""

    patterns: tuple[str, ...]
    source: Optional[Path]  # None: no config file, FALLBACK_EXCLUDES apply


def gate_excludes(repo: Path) -> GateExcludes:
    """``exclude`` from the repo's ``.hefesto.yaml``, or the fallback list.

    Uses the same discovery and validation as ``hefesto analyze``. A config
    without ``exclude`` gates every changed file. An invalid config is an
    error (exit 2), not a silent fallback.
    """
    try:
        path = find_config(repo)
        if path is None:
            return GateExcludes(FALLBACK_EXCLUDES, None)
        values = load_config(path).values
    except ConfigError as exc:
        raise DogfoodError(f"cannot read project config: {exc}") from exc
    raw = values.get("exclude", "")
    patterns = tuple(part.strip() for part in str(raw).split(",") if part.strip())
    return GateExcludes(patterns, path)


def warn_glob_patterns(patterns: tuple[str, ...]) -> None:
    """Warn about patterns written as globs; the matcher compares whole names."""
    for pattern in patterns:
        if _GLOB_CHARS & set(pattern):
            print(
                f"warning: exclude pattern {pattern!r} contains glob characters; "
                "patterns are whole path components (write 'tests/fixtures/'), "
                "so this one matches nothing",
                file=sys.stderr,
                flush=True,
            )


def split_gate_files(files: list[str], patterns: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Split repo-relative changed files into (gated, excluded).

    ``path_is_excluded`` is the engine's matcher, so a changed path is skipped
    exactly when a directory walk from the repository root would skip it.
    """
    kept: list[str] = []
    skipped: list[str] = []
    for name in files:
        if path_is_excluded(PurePosixPath(name).parts, patterns):
            skipped.append(name)
        else:
            kept.append(name)
    return kept, skipped


def _print_excludes(repo: Path, excludes: GateExcludes) -> None:
    listed = ", ".join(excludes.patterns) or "(none)"
    if excludes.source is None:
        print(
            "Gate excludes: no .hefesto.yaml/.hefesto.yml in the repository; "
            f"using the built-in fallback: {listed}",
            flush=True,
        )
        return
    try:
        shown = excludes.source.resolve().relative_to(repo)
    except ValueError:
        shown = excludes.source
    print(f"Gate excludes from {shown}: {listed}", flush=True)


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
    try:
        issues = critical_issues(repo, [PACKAGE])
    except (DogfoodError, KeyError, TypeError) as exc:
        print(f"SELF-CHECK FAILED: {exc}", file=sys.stderr)
        return False
    if issues:
        print("SELF-CHECK FAILED: CRITICAL findings under hefesto/", file=sys.stderr)
        _print_issues(issues)
        return False
    print("current tree has no CRITICAL findings under hefesto/", flush=True)
    return True


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
    parser.add_argument(
        "--fail-on-new-suppressions",
        action="store_true",
        help="Exit 1 when the diff adds a `# hefesto: ignore[TYPE] reason` comment",
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
        excludes = gate_excludes(repo)
    except DogfoodError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Changed files ({len(files)}):", flush=True)
    for name in files:
        print(f"  {name}", flush=True)
    if not files:
        print("  (none)", flush=True)
    _print_excludes(repo, excludes)
    warn_glob_patterns(excludes.patterns)
    files, skipped = split_gate_files(files, excludes.patterns)
    if skipped:
        print(f"Files excluded from the gate ({len(skipped)}):", flush=True)
        for name in skipped:
            print(f"  {name}", flush=True)
    exit_code = run_changed_gate(repo, files)
    try:
        new_count = report_new_suppressions(repo, args.base, args.head)
    except DogfoodError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if new_count and args.fail_on_new_suppressions:
        print("Gate failure: new line suppressions (--fail-on-new-suppressions)", flush=True)
        exit_code = exit_code or 1
    return exit_code


def report_new_suppressions(repo: Path, base: str, head: str) -> int:
    """Print each ``# hefesto: ignore`` comment the diff adds. Returns the count."""
    from hefesto.core.suppressions import format_new_suppressions, new_suppressions_in_diff

    base_rev = empty_tree(repo) if is_zero_rev(base) else base
    proc = _git(repo, ["diff", "--no-color", "--unified=0", base_rev, head, "--", "*.py"])
    if proc.returncode != 0:
        raise DogfoodError(proc.stderr.strip() or f"git diff exited {proc.returncode}")
    found = new_suppressions_in_diff(proc.stdout, repo)
    print(f"New line suppressions ({len(found)}):", flush=True)
    for line in format_new_suppressions(found):
        print(f"  {line}", flush=True)
    if not found:
        print("  (none)", flush=True)
    return len(found)


if __name__ == "__main__":
    sys.exit(main())
