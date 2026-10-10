# 2026-10-06: SEC-03, scan secrets by path segment, not substring

- **Item:** SEC-03 (High) from the fix plan `plan-arreglos-hefesto` (2026-10-02),
  public-repo part. Still open in the 2026-10-06 status audit.
- **Branch:** `fix/sec03-secret-path-segments`, cut from `main` @ `21cee2b` (v4.14.0).
- **Scope:** `hefesto/analyzers/security.py` only (public repo). The private
  repo's `swarm/agents/static_sec.py` has the same bug and is not touched here.

## Context

`SecurityAnalyzer._check_hardcoded_secrets` skipped a finding whenever the
lower-cased file path contained the substring `test` or `example`. Because the
engine passes resolved absolute paths, this silently disabled secret detection
for:

- production code such as `src/contest/config.py`, `latest_settings.py`,
  `latest_app/`, `app/attestation.py`, `src/counterexample.py`;
- every file analyzed from a checkout whose absolute path contains `test`
  (for example pytest's `/tmp/pytest-of-<user>/…`).

A hardcoded exception re-enabled scanning for `tests/fixtures/action/` so the
GitHub Action smoke test could still find its fixture secret.
`_check_assert_usage` had the same `"test" in file_path.lower()` check.

## What changed

- `hefesto/analyzers/security.py`
  - New module-level helpers: `is_test_path()`, `is_example_path()` and
    `is_test_or_example_path()`, with `_path_segments()` underneath.
    - Test code: a directory segment exactly `test`, `tests` or `__tests__`,
      or a file named `test_*`, `*_test.<ext>`, `*.test.<ext>`,
      `*.spec.<ext>`, `conftest.py`, `test.py` or `tests.py`.
    - Example code: a directory segment exactly `example` or `examples`, or a
      `*.example` file (e.g. `.env.example`).
    - Matching is case-insensitive and handles `\` separators.
    - An absolute path inside the current working directory is made relative
      to it first, so parent directories outside the project (e.g.
      `/home/me/tests/myrepo/`) do not count. The CLI and the Action run from
      the project root, so this is effectively "relative to the repo root".
  - `_check_hardcoded_secrets` returns early for test/example code (same
    intent as before) and no longer has the `tests/fixtures/action/` exception.
  - `_check_assert_usage` skips test code only, using `is_test_path()`
    (example code is still checked, as before).
- Action smoke fixtures moved `tests/fixtures/action/` → `.github/action-smoke/`
  (`clean.py`, `critical_secret.py`, plus a README explaining why). Updated
  `.github/workflows/action-smoke.yml`, the path in a comment in
  `scripts/action_entrypoint.sh`, and `tests/test_secret_detection.py`.
  Under the new rule a fixture under `tests/` is test code, so it would be
  skipped and the "critical" smoke step would stop failing as it should.
- Docs: `docs/ANALYSIS_RULES.md` §2.1 (Hardcoded Secrets) and §2.5 (Assert in
  Production) now say exactly which paths are skipped.
- `CHANGELOG.md`: entry under `[Unreleased]` → `### Security`.

## How it was tested

- New `tests/test_sec03_path_segments.py` (41 test cases):
  - secrets are found in `contest/config.py`, `latest_settings.py`,
    `latest_app/…`, `fixtures/…`, a Windows-style path, and under pytest's
    `tmp_path`;
  - a repo under `…/tests/myrepo/` with cwd at the repo root is scanned;
  - secrets in `tests/test_x.py`, `tests/fixtures/action/…`, `__tests__/`,
    `*_test.go`, `*.spec.js`, `conftest.py`, `examples/`, `.env.example` are
    still skipped;
  - asserts are flagged in `contest/app.py` and skipped in `tests/test_app.py`;
  - end to end: `AnalyzerEngine.analyze_path` on a temp project reports the
    secret in `src/contest/config.py` and not the one in `tests/test_x.py`.
  - The file name avoids `secret`, because `.gitignore` ignores `*secret*`.
- `tests/test_secret_detection.py` passes against the moved fixtures.
- Full unit suite: `pytest -m "not integration and not slow"`, all green
  except `tests/test_version.py::test_version_drift`, which fails only in the
  local venv (its editable install points at another checkout with 4.13.1
  metadata). Not related to this change, and CI installs fresh.
- `black --check`, `isort --check-only`, `flake8` on the changed Python files
  and `mypy` on `security.py`: clean.
- `HEFESTO_TELEMETRY_ENV=dogfood hefesto analyze` on the changed files: the
  same 15 pre-existing complexity/length findings in `security.py` as on
  `main`, none new.
- Manual: from the repo root, `hefesto analyze .github/action-smoke/critical_secret.py
  --fail-on CRITICAL` exits 1 and `clean.py` exits 0. The same critical file
  copied under `tests/fixtures/` exits 0 (skipped, as intended).

## What remains

- Plan suggestions not done here, because they change product behavior and
  need a decision: report test-path secrets at a lower severity instead of
  skipping them, and add an `--include-tests` flag.
- Files analyzed from outside the working directory are still judged on their
  full absolute path (a parent directory literally named `tests` would make
  them test code). Passing the project root from the engine to the analyzers
  would fix that, but it changes the analyzer interface.
- Private repo: `swarm/agents/static_sec.py:83-89` has the same substring bug
  (SEC-03 [pro]). The private CI consumes `hefesto-ai` from PyPI, so it picks
  this fix up only after a public release.
- `CHANGELOG.md`: the SEC-05 and SEC-06 PRs also add entries under
  `[Unreleased]` → `### Security`. Whichever merges second hits a trivial
  conflict; keep both entries.
- This handoff is named `…-sec03-path-segments.md` (not `…-secret-…`) for the
  same `.gitignore` `*secret*` reason as the test file.
