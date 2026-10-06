# Action smoke-test fixtures

Inputs for `.github/workflows/action-smoke.yml`, which runs the Hefesto GitHub
Action (`uses: ./`) against:

- `clean.py`: no findings, so the Action must exit 0.
- `critical_secret.py`: a fake AWS access key ID, so the Action must exit 1
  (`fail_on: CRITICAL`).

These files are deliberately **not** under `tests/`. Secret detection skips
test code, which it recognizes by path segment (`tests/`, `test/`,
`__tests__/`) and test file-name conventions (SEC-03). There is no hardcoded
exception for fixture directories, so a fixture under `tests/` would be skipped
and the critical smoke test would fail.

The key in `critical_secret.py` is a non-functional placeholder that matches
the `AKIA[0-9A-Z]{16}` pattern.
