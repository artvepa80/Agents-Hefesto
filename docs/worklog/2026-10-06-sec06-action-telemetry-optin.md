# 2026-10-06: SEC-06, Action telemetry opt-in, truthful `telemetry status` (+ BUG-13)

- **Items:** SEC-06 (High, public-repo part) and BUG-13 (Medium) from the fix
  plan `plan-arreglos-hefesto` (2026-10-02). SEC-06 was PARTIAL in the
  2026-10-06 status audit (docs only); BUG-13 was OPEN.
- **Branch:** `fix/sec06-action-telemetry-optin`, cut from `main` @ `21cee2b` (v4.14.0).
- **Scope:** public repo only. The private receiver (`landing-page/api/telemetry.js`:
  no auth or rate limit, `Number(exit_code) ?? null`, table missing from
  `schema.sql`) is not touched.

## Context

- `scripts/action_entrypoint.sh` ended every run with an unconditional
  `curl` POST to `https://hefestoai.narapallc.com/api/telemetry` (comment:
  "always-on for CI"), although `action.yml` documented `telemetry` as
  "Opt-in … (1=enable, 0=disable)" with default `0`. The README (#51/#59)
  already admitted this.
- The entrypoint exported the raw input as `HEFESTO_TELEMETRY`. The CLI's
  remote ping is opt-out (only `0/false/no/off` disable it), so values such
  as `yes` or `enabled` turned the CLI ping on.
- `hefesto telemetry status` printed only the local JSONL log's state, which
  is opt-in (`Enabled: False` by default), while `_ping_remote` (opt-out) was
  sending pings. The status was misleading.
- BUG-13: `action.yml` offered `INFO` for `min_severity`, but the CLI's
  `--severity` is a click `Choice` of LOW/MEDIUM/HIGH/CRITICAL, so the Action
  exited 2.

## What changed

- `scripts/action_entrypoint.sh`
  - The `telemetry` input is normalized (whitespace removed, lower-cased).
    Only `1` or `true` sets `TELEMETRY_ENABLED=1`. Everything else, including
    the default `0`, an empty value, `yes` or `2`, means disabled.
  - `HEFESTO_TELEMETRY` is exported as exactly `1` or `0`, so the CLI ping
    follows the same decision.
  - The version/count extraction and the `curl` ping are wrapped in
    `if [ "$TELEMETRY_ENABLED" = "1" ]`. The temp file is removed either way.
  - `min_severity: INFO` is mapped to `LOW` with a `::warning::` (BUG-13).
- `action.yml`: the `telemetry` description says exactly what is sent and
  when. The `min_severity` description drops INFO (it is still accepted and
  treated as LOW).
- `hefesto/telemetry/client.py`: new `remote_ping_enabled()` (opt-out,
  used by `_ping_remote`) and `local_log_enabled()` (opt-in, used by
  `TelemetryClient`). `get_status()` adds `remote_ping_enabled` and
  `remote_endpoint`. **CLI defaults are unchanged.** The only behavior
  difference is that surrounding whitespace in `HEFESTO_TELEMETRY` is now
  ignored for the ping (`" 0 "` disables it).
- `hefesto/cli/main.py`: `hefesto telemetry status` prints `Usage ping:
  enabled|disabled` with the endpoint and how to disable it, plus `Local log:
  enabled|disabled`, path and sizes. The group's help no longer says
  "local-only".
- Docs: README (Action inputs table, Telemetry section, the note about
  `telemetry status`), `skill/integration.md`, `skill/commands.md`.
- `CHANGELOG.md`: `[Unreleased]` → `### Security` (SEC-06) and `### Fixed` (BUG-13).

## How it was tested

- New `tests/scripts/test_action_entrypoint.py` (18 cases). Runs the real
  entrypoint under bash with fake `hefesto` and `curl` on `PATH` (no network):
  - telemetry unset, `""`, `0`, `false`, `no`, `off`, `yes`, `2`,
    `enabled`: no `curl` call, and the CLI sees `HEFESTO_TELEMETRY=0`;
  - `1`, `true`, `TRUE`, `True`, `" 1 "`: exactly the expected JSON is
    POSTed to the endpoint, and the CLI sees `HEFESTO_TELEMETRY=1`;
  - the exit code and `GITHUB_OUTPUT` still propagate;
  - `INFO`/`info` → `--severity LOW` with a warning, and `high` → `HIGH`.
  - 15 of the 18 cases fail against the old entrypoint.
- New `tests/telemetry/test_telemetry_optin.py` (14 cases): helper truth
  table, `_ping_remote` makes no request when disabled and one by default
  (with `urlopen` mocked), `telemetry status` output for the default and
  disabled cases, and `get_status()` keys.
- `tests/telemetry/test_telemetry.py::test_telemetry_status_command` updated
  to the new status lines.
- Full unit suite (`-m "not integration and not slow"`) green except
  `tests/test_version.py::test_version_drift`, which fails only in the local
  venv because of a stale editable install (4.13.1 metadata).
- `bash -n` on the entrypoint. `black --check`, `isort`, `flake8` and `mypy`
  clean. `HEFESTO_TELEMETRY_ENV=dogfood hefesto analyze` on the changed
  files shows no new findings.
- The `Action Smoke Test` workflow exercises the Docker action end to end
  with the default `telemetry: 0`.

## What remains

- **Decision for the owner (not done):** the plan proposes one opt-in
  `telemetry_enabled()` for both the CLI ping and the local log. Today the
  CLI ping is opt-out and the local log is opt-in. Making the CLI ping opt-in
  would sharply reduce the analytics that #56 just started tagging, so this PR
  only makes the status truthful and keeps the CLI defaults. If the owner
  wants opt-in everywhere, change `remote_ping_enabled()` to use
  `_env_truthy` and update the README Telemetry section and the first-run
  notice.
- The README says the CLI collects anonymous usage data by default; that is
  still accurate.
- Private repo: the `/api/telemetry` receiver hardening (SEC-06 [pro]).
- Releases: users pinned to `@v4.14.0` or older still get the
  unconditional ping until they upgrade to a release that contains this fix.
- `CHANGELOG.md`: the SEC-03 and SEC-05 PRs also add entries under
  `[Unreleased]` → `### Security`. Whichever merges second hits a trivial
  conflict; keep both entries.
