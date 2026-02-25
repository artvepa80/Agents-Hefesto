# IRIS Telemetry Aggregates Contract v1

**Status:** Stable (v1)
**Audience:** Platform teams integrating observability stacks with IRIS
**Last updated:** 2026-02-25

---

## Overview

IRIS consumes **post-deploy telemetry aggregates** to label deployment outcomes
as GREEN (healthy), YELLOW (degraded), or RED (incident). This document defines
the canonical data contract: the schema, units, and conventions that any
telemetry source must follow to feed IRIS.

**Principle:** Bring your telemetry. IRIS learns. The gate stays deterministic.

---

## Row Schema (JSONL)

Each line in the aggregates file is a self-contained JSON object:

```json
{
  "repo": "org/repo",
  "commit_sha": "abc123def456",
  "window": "1h",
  "ts": "2026-02-25T13:00:00Z",
  "restart_count": 0,
  "oom_kill_count": 0,
  "error_rate": 0.002,
  "latency_p95_delta": 12.3,
  "latency_p99_delta": 25.1,
  "memory_rss_slope": 0.4
}
```

### Identity Fields (required)

| Field | Type | Description |
|-------|------|-------------|
| `repo` | string | Repository identifier in `org/repo` format |
| `commit_sha` | string | Full or abbreviated git commit SHA of the deployment |
| `window` | string | Observation window: `"1h"` or `"24h"` |
| `ts` | string | ISO-8601 UTC timestamp when the aggregate was computed |

### Required Metrics

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `restart_count` | int | count | Container/process restarts in the window |
| `oom_kill_count` | int | count | OOM kills observed in the window |
| `error_rate` | float | ratio (0.0-1.0) | Error responses / total responses |

### Optional Metrics

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `latency_p95_delta` | float | milliseconds | p95 latency delta vs pre-deploy baseline |
| `latency_p99_delta` | float | milliseconds | p99 latency delta vs pre-deploy baseline |
| `memory_rss_slope` | float | MB/min | RSS memory growth rate (positive = leak signal) |

Missing optional metrics are treated as **no signal** (not penalized).

### Extension Fields

Additional fields MAY be included and will be **silently ignored** by the
labeler but **preserved** in stored events. This enables forward-compatible
extension without breaking existing consumers.

Example extension:
```json
{"repo": "org/repo", "commit_sha": "abc", "window": "1h", "ts": "...",
 "restart_count": 0, "oom_kill_count": 0, "error_rate": 0.001,
 "cpu_throttle_seconds": 42.5, "custom_health_score": 0.95}
```

---

## Unit Conventions

| Concept | Convention | Example |
|---------|-----------|---------|
| Ratios | 0.0 to 1.0 (NOT percentage) | `error_rate: 0.05` = 5% |
| Latency | Milliseconds (ms) | `latency_p99_delta: 150.0` |
| Memory slope | MB per minute | `memory_rss_slope: 2.5` |
| Counts | Non-negative integers | `restart_count: 3` |
| Timestamps | ISO-8601 UTC with `Z` suffix | `2026-02-25T13:00:00Z` |
| Windows | String literal | `"1h"` or `"24h"` only |

---

## Labeling Thresholds (defaults)

The labeler applies these thresholds (all configurable via `IRIS_LABEL_*` env vars):

### RED (label=2) -- any one triggers

| Condition | Default | Env var |
|-----------|---------|---------|
| `error_rate >= threshold` | 0.05 (5%) | `IRIS_LABEL_RED_ERROR_RATE` |
| `oom_kill_count > threshold` | 0 | `IRIS_LABEL_RED_OOM_KILL_COUNT` |
| `restart_count > threshold` | 3 | `IRIS_LABEL_RED_RESTART_COUNT` |

### YELLOW (label=1) -- any one triggers (if not RED)

| Condition | Default | Env var |
|-----------|---------|---------|
| `error_rate >= threshold` | 0.01 (1%) | `IRIS_LABEL_YELLOW_ERROR_RATE` |
| `latency_p99_delta > threshold` | 200.0 ms | `IRIS_LABEL_YELLOW_LATENCY_P99_DELTA` |
| `memory_rss_slope > threshold` | 10.0 MB/min | `IRIS_LABEL_YELLOW_MEMORY_RSS_SLOPE` |

### GREEN (label=0) -- default when no threshold is breached

---

## File Format

- **Encoding:** UTF-8
- **Format:** JSON Lines (one JSON object per line, newline-delimited)
- **Extension:** `.jsonl` (recommended)
- **Empty lines:** Silently skipped
- **Invalid JSON lines:** Logged as warning, skipped (no hard failure)
- **Ordering:** Most recent record wins for duplicate `(repo, commit_sha, window)` tuples

---

## Multiple Windows

IRIS evaluates deployments at two time horizons independently:

| Window | Purpose | Typical use |
|--------|---------|------------|
| `1h` | Fast feedback | Canary/rollback decisions |
| `24h` | Stability check | Soak test, memory leak detection |

A single aggregates file MAY contain rows for both windows. Each row is
independent; the labeler processes them separately.

---

## Producing Aggregates

Any script or pipeline that produces conformant JSONL can feed IRIS:

```python
import json, datetime

row = {
    "repo": "org/repo",
    "commit_sha": "abc123def456",
    "window": "1h",
    "ts": datetime.datetime.utcnow().isoformat() + "Z",
    "restart_count": 0,
    "oom_kill_count": 0,
    "error_rate": 0.002,
    "latency_p95_delta": 12.3,
    "latency_p99_delta": 25.1,
    "memory_rss_slope": 0.4,
}

with open("aggregates.jsonl", "a") as f:
    f.write(json.dumps(row) + "\n")
```

Enterprise collectors (Prometheus, Datadog, CloudWatch) and integration
runbooks are available in the PRO distribution.

---

## Consuming Aggregates (IRIS)

```bash
export IRIS_TELEMETRY_SOURCE=file
export IRIS_TELEMETRY_FILE=/path/to/aggregates.jsonl

iris label-outcomes \
  --repo org/repo \
  --commit abc123def456 \
  --env production \
  --window both \
  --json
```

---

## Validation

Use `scripts/validate_aggregates_jsonl.py` (included in this repository) to
verify your collector output before feeding it to IRIS:

```bash
python scripts/validate_aggregates_jsonl.py aggregates.jsonl
```

The validator checks required fields, type constraints, unit ranges, and
prints a concise report. Exit code 0 = valid, 1 = errors found.

---

## Schema Evolution

- **v1 (current):** 3 required + 3 optional metrics, 4 identity fields
- **Future versions** will add optional metrics only (never remove or rename)
- Unknown fields are always preserved (forward-compatible)
- Breaking changes will increment the contract version

---

## Validation Checklist

Use this to verify your collector output:

- [ ] Each line is valid JSON
- [ ] `repo` matches `org/repo` format
- [ ] `commit_sha` is a valid git SHA (7+ characters)
- [ ] `window` is exactly `"1h"` or `"24h"`
- [ ] `ts` is valid ISO-8601 with UTC timezone
- [ ] `error_rate` is a float between 0.0 and 1.0 (not a percentage)
- [ ] `restart_count` and `oom_kill_count` are non-negative integers
- [ ] Latency deltas are in milliseconds (not seconds)
- [ ] `memory_rss_slope` is in MB/min (not bytes/sec)

---

Licensed under the repository license. Copyright 2025 Narapa LLC.
