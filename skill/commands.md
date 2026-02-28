# HefestoAI CLI Reference

Entry point: `hefesto` (installed via `pip install hefesto-ai`)

## analyze

Run static analysis on files or directories.

```bash
hefesto analyze <paths...> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--severity` | MEDIUM | Minimum severity to report: LOW, MEDIUM, HIGH, CRITICAL |
| `--output` | text | Output format: text, json, html |
| `--fail-on` | (none) | Exit 1 if issues at this severity or above found |
| `--exclude` | (none) | Comma-separated patterns: tests/,docs/ |
| `--exclude-types` | (none) | Comma-separated issue types to skip in gate |
| `--quiet` | false | Summary only, no pipeline details |
| `--max-issues` | all | Cap displayed issues |
| `--save-html` | (none) | Save HTML report to file path |
| `--enable-memory-budget-gate` | false | Enable memory budget gate (EPIC 4) |

**Scope gating (PRO):**
`--include-third-party`, `--include-generated`, `--include-fixtures`,
`--scope-allow <pattern>`, `--scope-deny <pattern>`

**Enrichment (PRO):**
`--enrich off|local|remote`, `--enrich-provider <name>`,
`--enrich-timeout <sec>`, `--enrich-cache-ttl <sec>`, `--enrich-cache-max <n>`

### Examples

```bash
# Analyze current directory
hefesto analyze .

# CI gate — fail on HIGH or CRITICAL
hefesto analyze . --fail-on HIGH --exclude tests/,docs/

# JSON output for piping
hefesto analyze src/ --output json --quiet

# HTML report
hefesto analyze . --output html --save-html report.html

# Skip specific issue types in gate
hefesto analyze . --fail-on HIGH --exclude-types VERY_HIGH_COMPLEXITY,LONG_FUNCTION

# Analyze multiple paths
hefesto analyze src/ lib/ types/
```

## install-hooks

Install pre-commit and pre-push git hooks.

```bash
hefesto install-hooks [--force]
```

Copies hooks from `scripts/git-hooks/` to `.git/hooks/`.
The pre-commit hook runs `hefesto analyze . --severity HIGH` and blocks
on CRITICAL/HIGH issues. Bypass with `SKIP_HEFESTO_HOOKS=1 git commit`.

## drift

Detect configuration drift in Infrastructure-as-Code.

```bash
hefesto drift <template_file> --region <aws-region> [options]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--region` | yes | AWS region |
| `--stack-name` | no | CloudFormation stack name |
| `--tags` | no | Tags: key=value,key2=value2 |
| `--fail-on` | no | Exit 2 if severity >= level (default: HIGH) |

## check

Verify HefestoAI installation and dependencies.

```bash
hefesto check
```

Checks: Python version (3.10+), click, pydantic, radon, bandit, vulture,
pylint, jinja2.

## check-ci-parity

Compare local and CI environments for discrepancies.

```bash
hefesto check-ci-parity [--project-root <path>]
```

Compares tool versions (flake8, black, isort, pytest), flake8 config, and
Python version. Exits 1 if HIGH priority parity issues found.

## check-test-contradictions

Find contradictory assertions in test suite.

```bash
hefesto check-test-contradictions [<test_directory>]
```

Default directory: `tests/`. Detects same function called with same inputs
but different expected outputs. Exits 1 if contradictions found.

## telemetry

Local-only, privacy-first telemetry management.

```bash
hefesto telemetry status     # Show telemetry config and file info
hefesto telemetry clear      # Delete local telemetry data
hefesto telemetry clear --yes  # Skip confirmation
```

## License Management (PRO)

```bash
hefesto activate HFST-XXXX-XXXX-XXXX-XXXX-XXXX
hefesto deactivate
hefesto status
hefesto info
```

These commands require the PRO/OMEGA private distribution.

## serve (PRO)

Start the HefestoAI API server.

```bash
hefesto serve [--host <addr>] [--port <port>] [--reload]
```

Requires PRO. Starts a uvicorn server with MCP, REST, and OpenAPI endpoints.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Analysis passed (or no `--fail-on` set) |
| 1 | Gate failure: issues at or above `--fail-on` severity found |
| 1 | Installation/runtime error |
| 2 | Drift detection: findings at or above threshold (`drift` command) |
