# Action smoke-test fixtures

Inputs for `.github/workflows/action-smoke.yml`, which runs the Hefesto GitHub
Action (`uses: ./`) against:

- `clean.py`: no findings, so the Action must exit 0.
- `critical_secret.py`: a fake AWS access key ID, so the Action must exit 1
  (`fail_on: CRITICAL`).
- `clean.ts`: no findings. Job `smoke-multilang` runs it with `multilang`
  off (the file is skipped, no file is analyzed, exit 1) and with
  `multilang: 'true'` (1 file analyzed, exit 0).
- `c-cpp/unsafe.c`: a `gets()` call (CC001, HIGH). `c-cpp/.hefesto.yaml`
  turns on `experimental: [c-cpp, lang-security]`. Job `smoke-c-cpp` runs the
  directory with `multilang: 'true'` and `fail_on: HIGH` (exit 1, CC001 in the
  SARIF), then the same file copied outside that config (not found, exit 0
  with `allow_no_files`).

These files are deliberately **not** under `tests/`. Secret detection skips
test code, which it recognizes by path segment (`tests/`, `test/`,
`__tests__/`) and test file-name conventions (SEC-03). There is no hardcoded
exception for fixture directories, so a fixture under `tests/` would be skipped
and the critical smoke test would fail.

The key in `critical_secret.py` is a non-functional placeholder that matches
the `AKIA[0-9A-Z]{16}` pattern.
