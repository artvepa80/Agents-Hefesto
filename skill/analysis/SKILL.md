# Auto-Analysis Skill — Interpret HefestoAI Output

This skill activates after any `hefesto analyze` run.
It interprets results, suggests fixes, and generates
commit quality summaries for HERMES content.

## When to Trigger

- After `hefesto analyze .` completes (any exit code)
- After a pre-commit hook runs HefestoAI
- After CI reports HefestoAI gate results
- When a user asks "what did HefestoAI find?"

## Document Index

| File | Purpose |
|------|---------|
| [interpret_output.md](interpret_output.md) | Parse text and JSON output, field meanings |
| [fix_suggestions.md](fix_suggestions.md) | Fix guidance per issue category |
| [report_template.md](report_template.md) | Standard commit quality report format |
| [hermes_integration.md](hermes_integration.md) | Feed results to HERMES content pipeline |

## Quick Reference

Exit codes: 0 = clean, 1 = gate failure or error, 2 = drift threshold.
Output formats: `--output text` (default), `--output json`, `--output html`.
Gate: `--fail-on HIGH` exits 1 if any HIGH+ issues found.

## Workflow

```
hefesto analyze . --output json --fail-on HIGH
       |
       v
  Parse JSON output (interpret_output.md)
       |
       v
  Generate fix suggestions (fix_suggestions.md)
       |
       v
  Build commit quality report (report_template.md)
       |
       v
  Stage HERMES content if applicable (hermes_integration.md)
```
