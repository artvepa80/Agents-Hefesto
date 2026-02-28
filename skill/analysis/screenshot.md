# Screenshot Automation

Captures terminal output after every `hefesto analyze` run as evidence
for HERMES build-in-public content.

## When to Capture

- After every `hefesto analyze` run (manual or pre-commit hook)
- After CI runs HefestoAI gate
- Before and after fixing issues (to show the diff)

## What Gets Captured

Each run produces 3 files in `~/hefesto_tools/hermes/evidence/`:

| File | Format | Contents |
|------|--------|----------|
| `YYYYMMDD_HHMMSS_analysis.json` | JSON | Full structured output |
| `YYYYMMDD_HHMMSS_analysis.txt` | Text | Human-readable terminal output |
| `YYYYMMDD_HHMMSS_metadata.json` | JSON | Summary metadata (below) |

## Metadata Schema

```json
{
  "timestamp": "2026-02-28T20:00:00Z",
  "files_analyzed": 20,
  "total_issues": 23,
  "critical": 0,
  "high": 7,
  "medium": 16,
  "low": 0,
  "exit_code": 0,
  "duration_seconds": 0.33,
  "status": "clean|issues|blocked",
  "text_file": "/path/to/text",
  "json_file": "/path/to/json"
}
```

## Usage

```bash
# Instead of: hefesto analyze hefesto/core/
# Run:
./scripts/capture_analysis.sh hefesto/core/

# With gate:
./scripts/capture_analysis.sh . --fail-on HIGH

# Output: 1-line summary
# [hefesto] 20 files, 23 issues (0C/7H/16M/0L) -- issues [0.33s]
```

## HERMES Integration

Evidence files are referenced by HERMES when generating posts:
- Clean run evidence -> "clean commit" build-in-public post
- Issues-found evidence -> "caught before production" post
- Before/after pair -> "this is what pre-commit caught" post

See [hermes_integration.md](hermes_integration.md) for content templates.

## Storage

- Location: `~/hefesto_tools/hermes/evidence/`
- Retention: manual cleanup (not auto-rotated)
- Private: never commit evidence files to git
