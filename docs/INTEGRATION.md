# Integration Guide

How to run HefestoAI from your own tooling: the CLI, its JSON output, and the
Python `AnalyzerEngine` that the CLI is built on.

> This page used to describe a "Phase 0 validation layer" (`hefesto.llm.validators`,
> `get_validator`, `enable_validation`) and a BigQuery-backed ML pipeline. None of
> that exists in the package. Everything below is the API that ships today.

## Table of Contents

- [CLI](#cli)
- [JSON output](#json-output)
- [Python API: AnalyzerEngine](#python-api-analyzerengine)
- [PRO features](#pro-features)
- [Related Documentation](#related-documentation)

---

## CLI

The simplest integration is the command line. Every analyzer is deterministic
and runs locally; no API key or AI provider is needed.

```bash
hefesto analyze . --severity MEDIUM          # human-readable report
hefesto analyze . --output json              # machine-readable report on stdout
hefesto analyze . --fail-on HIGH             # exit code 2 if any HIGH or CRITICAL finding
hefesto analyze . --exclude "build/,dist/"   # skip paths
hefesto install-hooks                        # pre-commit hook
```

Use `--fail-on` to turn the analysis into a CI gate. Without it, `hefesto analyze`
exits 0 even when it reports findings.

## JSON output

`hefesto analyze <path> --output json` prints a single JSON document on stdout
(progress messages go to stderr):

```json
{
  "summary": {
    "files_analyzed": 1,
    "total_issues": 1,
    "critical": 0,
    "high": 0,
    "medium": 1,
    "low": 0,
    "total_loc": 5,
    "duration_seconds": 0.004,
    "suppressed": 0
  },
  "files": [
    {
      "file": "app.py",
      "issues": [
        {
          "file": "app.py",
          "line": 4,
          "column": 0,
          "type": "BARE_EXCEPT",
          "severity": "MEDIUM",
          "message": "Bare except clause catches all exceptions",
          "function": null,
          "suggestion": "Catch specific exceptions: ...",
          "code_snippet": null,
          "metadata": {"type": "bare_except"},
          "engine": "internal"
        }
      ],
      "loc": 5,
      "duration_ms": 4.2,
      "language": "python"
    }
  ],
  "timestamp": "2026-10-29T17:31:26.423624"
}
```

`summary.suppressed` is always present: it is the number of findings
suppressed with `# hefesto: ignore[TYPE] reason` comments (an integer, `0` when
none). Do not confuse it with the per-finding `"suppressed": true` (a boolean)
on the entries listed under each file's `suppressed_issues`. See
[ANALYSIS_RULES.md](ANALYSIS_RULES.md) for the suppression syntax.

Example: count CRITICAL findings with `jq`:

```bash
hefesto analyze . --output json | jq '[.files[].issues[] | select(.severity == "CRITICAL")] | length'
```

For code-scanning dashboards, use `--output sarif` instead.

## Python API: AnalyzerEngine

`hefesto.core.analyzer_engine.AnalyzerEngine` runs the same pipeline as the CLI.
Create an engine, register analyzers from `hefesto.analyzers`, then analyze a
path:

```python
from hefesto.analyzers import (
    BestPracticesAnalyzer,
    CodeSmellAnalyzer,
    ComplexityAnalyzer,
    SecurityAnalyzer,
)
from hefesto.core.analyzer_engine import AnalyzerEngine

engine = AnalyzerEngine(severity_threshold="MEDIUM", quiet=True)
engine.register_analyzer(ComplexityAnalyzer())
engine.register_analyzer(CodeSmellAnalyzer())
engine.register_analyzer(SecurityAnalyzer())
engine.register_analyzer(BestPracticesAnalyzer())

report = engine.analyze_path("src/", exclude_patterns=["build/"])

print(report.summary.total_issues, report.summary.critical_issues)
for file_result in report.file_results:
    for issue in file_result.issues:
        print(file_result.file_path, issue.line, issue.severity.value,
              issue.issue_type.value, issue.message)
```

- `analyze_path(path, exclude_patterns=None)` analyzes a file or a directory.
- `analyze_files(paths, project_root=None)` analyzes an explicit list of files
  without directory discovery.
- `register_project_analyzer(analyzer)` adds a project-level analyzer that runs
  once per `analyze_path` call (the CLI registers the Operational Truth analyzers
  from `hefesto.analyzers.operational_truth` this way).

A runnable version is in [`examples/basic_usage.py`](../examples/basic_usage.py).

## PRO features

PRO and OMEGA are a separate package (`hefesto-ai[pro]`) plus a license key in
the `HEFESTO_LICENSE_KEY` environment variable, format
`HFST-XXXX-XXXX-XXXX-XXXX-XXXX`. Check both with:

```bash
hefesto status
```

- **Duplicate-function detection (`DUPLICATE_CODE`)** uses local
  `sentence-transformers` embeddings; no code is sent to any AI service. It runs
  inside `hefesto analyze` only with PRO installed and `HEFESTO_TIER=professional`
  or `omega`. See [`examples/pro_semantic_analysis.py`](../examples/pro_semantic_analysis.py).
- **Enrichment** (`hefesto analyze --enrich local|remote`) is off by default. No AI
  provider is bundled; you bring your own through the PRO enrichment provider
  contract.

## Related Documentation

- [Getting Started](GETTING_STARTED.md)
- [Analysis Rules](ANALYSIS_RULES.md)
- [Installation](INSTALLATION.md)
- [Quick Start](QUICK_START.md)
