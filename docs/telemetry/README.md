# IRIS Telemetry Integration

IRIS (Intelligent Risk & Incident Scoring) consumes post-deploy telemetry to
label deployment outcomes as GREEN, YELLOW, or RED. The labeling is fully
deterministic — same inputs always produce the same label.

## Public Interface

- **[AGGREGATES_CONTRACT.md](AGGREGATES_CONTRACT.md)** — The canonical v1 schema
  for telemetry input. Any observability stack (Prometheus, Datadog, CloudWatch,
  New Relic, Splunk, or custom) can produce this format.

- **[validate_aggregates_jsonl.py](../../scripts/validate_aggregates_jsonl.py)** —
  Stdlib-only validator to check your JSONL before feeding it to IRIS.

- **[examples/aggregates.sample.jsonl](examples/aggregates.sample.jsonl)** —
  Sample file with 4 rows covering GREEN, YELLOW, and RED scenarios.

## Quick Validation

```bash
# Validate your file before feeding it to IRIS
python scripts/validate_aggregates_jsonl.py your_aggregates.jsonl

# Try with the included sample
python scripts/validate_aggregates_jsonl.py docs/telemetry/examples/aggregates.sample.jsonl
```

## Architecture

```
[Your Observability Stack]
        |
        v
  aggregates.jsonl        <-- contract defined here
        |
        v
  [IRIS Labeler]          <-- deterministic GREEN/YELLOW/RED
        |
        v
  DeployOutcomeEvent      <-- stored for learning risk model
```

**Telemetry is pluggable. GCP is one adapter.** The core IRIS labeler uses
stdlib only — no cloud lock-in.

## Enterprise Features (PRO)

Enterprise collectors (Prometheus, Datadog, CloudWatch) and integration
runbooks are available in the PRO distribution (`hefesto-pro` package).
See [PyPI](https://pypi.org/project/hefesto-pro/) for details.
