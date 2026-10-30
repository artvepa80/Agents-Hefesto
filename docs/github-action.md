# HefestoAI GitHub Action

`uses: artvepa80/Agents-Hefesto@<ref>` runs `hefesto analyze` on the checked-out
repository, fails the job when findings reach `fail_on`, and can upload the
findings to GitHub code scanning as SARIF 2.1.0.

## Versions

- `@v4` is a floating tag that follows the whole 4.x line, minor releases
  included. Each v4.x.y release moves it to that release's commit
  (`release.yml` does it after publishing), so `@v4` always runs the latest
  4.x release. It is the only tag that ever moves.
- Because it follows minors, `@v4` also receives behaviour changes, such as
  the 4.16.0 change that makes a run with no analyzed files fail the gate
  instead of passing (see "Runs that analyze no files" below).
- If you need exact stability, pin an exact release tag such as `@v4.20.4`
  (exact tags never move) or a commit SHA, and bump it yourself.
- The Action installs HefestoAI from its own checkout, not from PyPI, so a fix
  reaches a workflow only through a ref that contains it: `@v4.15.0` keeps the
  exclusion bug fixed in 4.15.1, `@v4` gets the fix.

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
   --output <format>` (plus `--sarif-file <sarif_file>` with `sarif: true`
   and `--allow-no-files` with `allow_no_files: true`; the log shows
   `Allow no files: yes (--allow-no-files)`)
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
| `allow_no_files` | `false` | `true`/`1`/`yes`: pass `--allow-no-files`, so a run that analyzes no files keeps exit 0 (see below) |
| `allow_not_analyzed` | `false` | `true`/`1`/`yes`: pass `--allow-not-analyzed`, so a found file that could not be analyzed does not fail the step (see below) |
| `min_severity` | `LOW` | Lowest severity reported (`INFO` is read as `LOW`) |
| `format` | `text` | Report printed to the log: `text`, `json`, `html` or `sarif` |
| `sarif` | `false` | `true`/`1`/`yes`: also write a SARIF file and upload it |
| `sarif_file` | `hefesto.sarif` | Where the SARIF file is written (relative to the workspace) |
| `upload_sarif` | `true` | With `sarif: true`, `false` writes the file without uploading it |
| `sarif_category` | `hefesto` | Code scanning category (use one per Hefesto job in the same repository) |
| `telemetry` | `0` | Opt-in anonymous telemetry, see the README |

### Runs that analyze no files

If `target` contains no supported source files, or every file is excluded,
the step fails: `fail_on` always has a value (default `CRITICAL`), and a gate
that checked nothing does not pass. The log says "No files were analyzed" and
names the path; when files were left out as vendored JavaScript it also says
how many and suggests `--include-vendored`. For runs that are empty on
purpose, such as a changed-files-only job on a PR that touches only Markdown,
set `allow_no_files: 'true'`: the Action passes `--allow-no-files`, and only the
exit code changes (0 instead of 1); "Files analyzed: 0" and the warning are
still printed.

### Files that could not be analyzed

Since 4.20.1, a file the step found but could not analyze (it could not be
read, or its analyzer raised an error) fails the step: the log lists it under "Not
analyzed" with the reason and prints "Gate failure: N file(s) could not be
analyzed (exit 1)". In 4.20.0 such a file was dropped without a warning. Set
`allow_not_analyzed: 'true'` to keep the old exit code; the file is still
listed and warned about.

A Java, Go, Rust, C#, JavaScript or TypeScript file whose tree-sitter grammar
could not be loaded is in the same group. The Action image does not ship the
grammars yet, so each run downloads them; if that download fails (an outage, a
rate limit, a self-hosted runner without internet access), the file is listed
as "tree-sitter grammar '<name>' could not be loaded" and fails the step
instead of being skipped.

A file that is not valid UTF-8 is not in this group: it is read with the
`latin-1` fallback, analyzed, and listed as "decoded with fallback" (a
`warning` notification in SARIF). Only its findings can fail the step.

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
      - uses: artvepa80/Agents-Hefesto@v4   # SARIF needs v4.15.0 or later
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
   the copybook line as a related location. Python security rules that have a
   CWE also carry the tag `external/cwe/cwe-N` (no zero-padding), which code
   scanning can filter on. The mapping is in
   [docs/ANALYSIS_RULES.md](ANALYSIS_RULES.md#27-cwe-in-sarif).
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
