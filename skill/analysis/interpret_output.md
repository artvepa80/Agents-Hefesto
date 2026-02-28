# Interpreting HefestoAI Output

## Text Output Structure

```
HEFESTO ANALYSIS PIPELINE
==================================================
Found 20 file(s)
Found 23 potential issue(s)
Duration: 0.33s

Summary:
   Files analyzed: 20
   Issues found: 23
   Critical: 0 | High: 7 | Medium: 16 | Low: 0

Issue block (one per finding):
  [file]:[line]:[column]
  |- Issue: [message]
  |- Function: [function_name]
  |- Type: [issue_type]
  |- Severity: [severity]
  +- Suggestion: [fix guidance]
```

## JSON Output Structure

Run with `--output json`. Non-JSON text goes to stderr, stdout is pure JSON.

```json
{
  "summary": {
    "files_analyzed": 20,
    "total_issues": 23,
    "critical": 0,
    "high": 7,
    "medium": 16,
    "low": 0,
    "total_loc": 2585,
    "duration_seconds": 0.38
  },
  "files": [
    {
      "file": "hefesto/core/drift_runner.py",
      "issues": [
        {
          "file": "hefesto/core/drift_runner.py",
          "line": 89,
          "column": 4,
          "type": "HIGH_COMPLEXITY",
          "severity": "MEDIUM",
          "message": "Cyclomatic complexity too high (8)",
          "function": "_load_template",
          "suggestion": "Consider simplifying the logic",
          "code_snippet": null,
          "metadata": {"complexity": 8},
          "engine": "internal"
        }
      ],
      "loc": 152,
      "duration_ms": 18.4,
      "language": "python"
    }
  ]
}
```

## Field Reference

| Field | Type | Meaning |
|-------|------|---------|
| type | string | Issue type enum (e.g. HIGH_COMPLEXITY) |
| severity | string | CRITICAL, HIGH, MEDIUM, LOW |
| message | string | Human-readable description |
| function | string/null | Function where issue was found |
| suggestion | string/null | Recommended fix |
| metadata | object | Extra data (complexity score, line counts, etc.) |
| engine | string | "internal" or "internal:resource_safety_v1" |
| rule_id | string/null | R1-R5 for reliability rules |
| confidence | float/null | 0.0-1.0 detection confidence |

## Severity to Action Mapping

| Severity | Action | Blocks commit? |
|----------|--------|---------------|
| CRITICAL | Must fix immediately | Yes (with --fail-on CRITICAL) |
| HIGH | Should fix before merge | Yes (with --fail-on HIGH) |
| MEDIUM | Fix when convenient | Only with --fail-on MEDIUM |
| LOW | Consider during refactor | No |

## Parsing Tips

- Use `--output json --quiet` for clean machine-readable output
- Filter by severity: `jq '.files[].issues[] | select(.severity=="HIGH")'`
- Count by type: `jq '[.files[].issues[].type] | group_by(.) | map({(.[0]): length}) | add'`
- Exit code 0 does NOT mean zero issues -- it means none above `--fail-on` threshold
