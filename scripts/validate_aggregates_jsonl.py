#!/usr/bin/env python3
"""
IRIS Telemetry Aggregates Validator (stdlib-only)

Validates a JSONL file against the IRIS Aggregates Contract v1.
See: docs/telemetry/AGGREGATES_CONTRACT.md

Usage:
  python scripts/validate_aggregates_jsonl.py aggregates.jsonl
  python scripts/validate_aggregates_jsonl.py --strict aggregates.jsonl

Exit codes:
  0 = valid (all rows pass)
  1 = errors found
  2 = file not found / usage error

Copyright 2025 Narapa LLC. Licensed under the repository license.
"""

import json
import re
import sys

# ---------------------------------------------------------------------------
# Contract v1 definitions
# ---------------------------------------------------------------------------

VALID_WINDOWS = {"1h", "24h"}

REQUIRED_IDENTITY = {"repo", "commit_sha", "window", "ts"}

REQUIRED_METRICS = {"restart_count", "oom_kill_count", "error_rate"}

OPTIONAL_METRICS = {"latency_p95_delta", "latency_p99_delta", "memory_rss_slope"}

# ISO-8601 UTC pattern (accepts Z or +00:00 suffix)
ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

# repo format: org/repo (at least one slash)
REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")

# commit SHA: 7+ hex characters
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,}$")


def validate_row(row, lineno, strict=False):
    """Validate a single JSONL row. Returns list of error strings."""
    errors = []

    # --- Identity fields ---
    for field in REQUIRED_IDENTITY:
        if field not in row:
            errors.append(f"line {lineno}: missing required field '{field}'")

    repo = row.get("repo", "")
    if repo and not REPO_RE.match(repo):
        errors.append(f"line {lineno}: 'repo' should be 'org/repo' format, got '{repo}'")

    sha = row.get("commit_sha", "")
    if sha and not SHA_RE.match(sha):
        errors.append(f"line {lineno}: 'commit_sha' should be 7+ hex chars, got '{sha}'")

    window = row.get("window", "")
    if window and window not in VALID_WINDOWS:
        errors.append(f"line {lineno}: 'window' must be '1h' or '24h', got '{window}'")

    ts = row.get("ts", "")
    if ts and not ISO8601_RE.match(ts):
        errors.append(f"line {lineno}: 'ts' must be ISO-8601 UTC, got '{ts}'")

    # --- Required metrics ---
    for field in REQUIRED_METRICS:
        if field not in row:
            errors.append(f"line {lineno}: missing required metric '{field}'")

    # restart_count: non-negative int
    rc = row.get("restart_count")
    if rc is not None:
        if not isinstance(rc, int) or rc < 0:
            errors.append(f"line {lineno}: 'restart_count' must be non-negative int, got {rc}")

    # oom_kill_count: non-negative int
    oom = row.get("oom_kill_count")
    if oom is not None:
        if not isinstance(oom, int) or oom < 0:
            errors.append(f"line {lineno}: 'oom_kill_count' must be non-negative int, got {oom}")

    # error_rate: float 0.0-1.0
    er = row.get("error_rate")
    if er is not None:
        if not isinstance(er, (int, float)):
            errors.append(f"line {lineno}: 'error_rate' must be float, got {type(er).__name__}")
        elif er < 0.0 or er > 1.0:
            errors.append(
                f"line {lineno}: 'error_rate' must be 0.0-1.0 (ratio, not percentage), got {er}"
            )

    # --- Optional metrics ---
    for field in ("latency_p95_delta", "latency_p99_delta"):
        val = row.get(field)
        if val is not None and not isinstance(val, (int, float)):
            errors.append(
                f"line {lineno}: '{field}' must be numeric (ms), got {type(val).__name__}"
            )

    slope = row.get("memory_rss_slope")
    if slope is not None and not isinstance(slope, (int, float)):
        errors.append(
            f"line {lineno}: 'memory_rss_slope' must be numeric (MB/min), "
            f"got {type(slope).__name__}"
        )

    # --- Strict mode: warn on missing optional metrics ---
    if strict:
        for field in OPTIONAL_METRICS:
            if field not in row:
                errors.append(f"line {lineno}: (strict) missing optional metric '{field}'")

    return errors


def validate_file(path, strict=False):
    """Validate a JSONL file. Returns (total_rows, errors_list)."""
    errors = []
    total = 0

    try:
        with open(path, "r") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"line {lineno}: invalid JSON: {e}")
                    continue
                if not isinstance(row, dict):
                    errors.append(f"line {lineno}: expected JSON object, got {type(row).__name__}")
                    continue
                errors.extend(validate_row(row, lineno, strict=strict))
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 0, [f"file not found: {path}"]
    except OSError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 0, [str(e)]

    return total, errors


def main():
    strict = False
    args = sys.argv[1:]

    if "--strict" in args:
        strict = True
        args.remove("--strict")

    if not args or args[0] in ("-h", "--help"):
        print("Usage: python validate_aggregates_jsonl.py [--strict] <file.jsonl>")
        print()
        print("Validates JSONL against IRIS Aggregates Contract v1.")
        print("See: docs/telemetry/AGGREGATES_CONTRACT.md")
        print()
        print("Options:")
        print("  --strict  Also warn on missing optional metrics")
        print()
        print("Exit codes: 0 = valid, 1 = errors, 2 = usage error")
        sys.exit(2)

    path = args[0]
    total, errors = validate_file(path, strict=strict)

    if not errors:
        print(f"OK: {total} rows validated against Aggregates Contract v1")
        sys.exit(0)
    else:
        print(f"ERRORS: {len(errors)} issues in {total} rows\n")
        for err in errors:
            print(f"  {err}")
        print("\nSee: docs/telemetry/AGGREGATES_CONTRACT.md")
        sys.exit(1)


if __name__ == "__main__":
    main()
