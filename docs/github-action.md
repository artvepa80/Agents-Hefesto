# HefestoAI GitHub Action

`uses: artvepa80/Agents-Hefesto@<ref>` runs `hefesto analyze` on the checked-out
repository, fails the job when findings reach `fail_on`, and can upload the
findings to GitHub code scanning as SARIF 2.1.0.

## How it runs

The Action is a composite action with three steps:

1. **Install HefestoAI**: `python3 -m venv $RUNNER_TEMP/hefesto-venv`, then
   `pip install` of the Action's own checkout (the package is not pulled from
   PyPI; its dependencies are). The virtualenv is only on `PATH` inside the
   Action, so later steps of the job keep their own `python`. Needs `python3`
   >= 3.10 on the runner; `ubuntu-latest` has it, otherwise add
   `actions/setup-python` before the Action.
2. **Run HefestoAI**: `scripts/action_entrypoint.sh` builds
   `hefesto analyze <target> --severity <min_severity> --fail-on <fail_on>
   --output <format>` (plus `--sarif-file <sarif_file>` with `sarif: true`)
   from the `INPUT_*` variables and writes the outputs.
3. **Upload SARIF** (only with `sarif: true`, `upload_sarif: true` and a
   written file): `github/codeql-action/upload-sarif@v4` with
   `sarif_file` and `category: <sarif_category>`. It runs even when the gate
   failed (`if: always()`), so the alerts that failed the build are visible.

Up to v4.14.1 the Action was a Docker action built from `Dockerfile.action`.
That image is still in the repository for running the same entrypoint with
`docker run` elsewhere; `action.yml` no longer uses it.

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `target` | `.` | File or directory to analyze |
| `fail_on` | `CRITICAL` | Fail when a finding is at or above this severity |
| `min_severity` | `LOW` | Lowest severity reported (`INFO` is read as `LOW`) |
| `format` | `text` | Report printed to the log: `text`, `json`, `html` or `sarif` |
| `sarif` | `false` | `true`/`1`/`yes`: also write a SARIF file and upload it |
| `sarif_file` | `hefesto.sarif` | Where the SARIF file is written (relative to the workspace) |
| `upload_sarif` | `true` | With `sarif: true`, `false` writes the file without uploading it |
| `sarif_category` | `hefesto` | Code scanning category (use one per Hefesto job in the same repository) |
| `telemetry` | `0` | Opt-in anonymous telemetry, see the README |

## Outputs

| Output | Description |
|--------|-------------|
| `exit_code` | `hefesto analyze` exit code (0 pass, 1 gate failed or error, 2 usage error) |
| `sarif_file` | Path of the SARIF file, set only when it was written |

## Code scanning workflow

```yaml
name: HefestoAI
on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  hefesto:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write   # required by upload-sarif
      actions: read            # private repositories only
    steps:
      - uses: actions/checkout@v4
      - uses: artvepa80/Agents-Hefesto@v4.15.0   # SARIF needs v4.15.0 or later
        with:
          target: '.'
          fail_on: 'CRITICAL'
          sarif: 'true'
          sarif_category: 'hefesto'
```

Requirements and limits on the GitHub side:

- **Permissions**: the job needs `security-events: write`; private repositories
  also need `actions: read` and GitHub Advanced Security / Code Security.
  Without them the upload step fails (the analysis step result is unchanged).
- **Forks**: pull requests from forks get a read-only token, so GitHub rejects
  their upload. Use `upload_sarif: 'false'` on fork PRs (or skip them) if that
  failure is noise.
- **Size**: GitHub accepts up to 25,000 results per run and 10 MB of gzipped
  SARIF. Hefesto keeps the highest-severity results under both limits and says
  in the SARIF tool notifications how many it dropped.
- **Several runs**: give each job its own `sarif_category`, otherwise a later
  upload replaces the earlier one's alerts.

## Verifying it on GitHub

1. Run the workflow (push, pull request, or **Run workflow** with
   `workflow_dispatch`). The job log shows `SARIF file: hefesto.sarif (upload:
   yes, category: ...)` and then the **Upload SARIF to GitHub code scanning**
   step with the upload ID.
2. **Security > Code scanning** lists one alert per finding; filter with
   `tool:HefestoAI`. Each alert shows the rule help, the severity (security
   rules also get a security severity) and, for COBOL findings from a copybook,
   the copybook line as a related location.
3. On a pull request, the **Code scanning results / HefestoAI** check and the
   annotations in **Files changed** show alerts introduced by the PR.
4. Moving code without changing it does not reopen alerts: the fingerprints
   use the text of the flagged line, not its number.
5. To inspect the file itself, set `upload_sarif: 'false'` and upload
   `${{ steps.<id>.outputs.sarif_file }}` with `actions/upload-artifact`, or run
   `hefesto analyze . --format sarif` locally.

## Example repository

A complete example (a small COBOL payroll batch with six planted issues, a
copybook included with `COPY ... REPLACING`, `.hefesto.yaml`, and a workflow
that uploads SARIF) is prepared as a standalone repository,
`hefesto-cobol-ci-example`. Its expected alerts:

| Rule | Severity | What |
|------|----------|------|
| COBOL008 | CRITICAL | Password in a `VALUE` clause |
| COBOL004 | HIGH | Packed field overlaid via `REDEFINES` in the copybook (related location: the copybook line) |
| COBOL003 | MEDIUM | Unvalidated `ACCEPT` |
| COBOL011 | LOW | `SELECT` without `FILE STATUS` |
| COBOL012 | LOW | `FILE STATUS` never checked |
| COBOL014 | LOW | Paragraph never performed |
