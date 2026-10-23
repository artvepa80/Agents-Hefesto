---
name: HefestoAI Output Analysis
description: >-
  Interpret HefestoAI analyze / pre-commit / CI output, suggest fixes, and
  draft a commit-quality summary. Use after `hefesto analyze`, after a Hefesto
  hook or CI gate, or when the user asks what Hefesto found.
---

# Interpret HefestoAI output

Activate after any `hefesto analyze` run (any exit code), after the pre-commit
hook, after CI gate results, or when the user asks what Hefesto found.

## Quick reference

- Exit codes: `0` clean · `1` gate failure / error · `2` drift threshold
- Formats: `--output text` (default), `--output json`, `--output html`
- Gate: `--fail-on HIGH` exits `1` if any HIGH+ issues

## Workflow

```
hefesto analyze . --output json --fail-on HIGH
  → parse JSON (interpret_output.md)
  → fix suggestions (fix_suggestions.md)
  → commit quality report (report_template.md)
  → optional HERMES staging (hermes_integration.md)
```

## Progressive docs

| File | Purpose |
|------|---------|
| [interpret_output.md](interpret_output.md) | Parse text/JSON fields |
| [fix_suggestions.md](fix_suggestions.md) | Fixes by category |
| [report_template.md](report_template.md) | Commit quality report |
| [hermes_integration.md](hermes_integration.md) | HERMES content pipeline |

## Rules

- Quote severities and issue codes from the actual output; do not invent findings.
- If exit code is non-zero, do not recommend committing until fixed or the user overrides.
