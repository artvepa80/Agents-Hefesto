# 2026-10-17: PyPI version-check switch (gap B1)

Handoff. No merge, no tag, no release. Runtime change (`hefesto/telemetry/client.py`): GH-8, not merged on the calendar day (America/Lima) the PR is opened.

## What was wrong

`hefesto analyze` calls `refresh_latest_version` (`hefesto/telemetry/client.py`, called from `hefesto/cli/main.py`). That function GETs `https://pypi.org/pypi/hefesto-ai/json` and writes `~/.hefesto/.latest_version`. Nothing turned the request off. `HEFESTO_TELEMETRY=0` and `DO_NOT_TRACK=1` only stop PostHog events.

## What landed

`refresh_latest_version` returns before the request and before any cache write when any of these holds:

- `HEFESTO_NO_UPDATE_CHECK` is truthy (`1`, `true`, `yes`, `on`)
- `HEFESTO_TELEMETRY` is off (`0`, `false`, `no`, `off`), the same tokens `telemetry_enabled` uses
- `DO_NOT_TRACK` is truthy (`1`, `true`, `yes`, `on`)

Surrounding spaces and letter case are ignored (`strip().lower()`), same as the other switches. Usage events stay on by default. `HEFESTO_NO_UPDATE_CHECK` does not turn them off. `hefesto telemetry disable` (the `telemetry_disabled` file) still does not skip this check.

`scripts/action_entrypoint.sh` is unchanged. It already exports `HEFESTO_TELEMETRY=0` unless the Action input `telemetry` is `1` or `true`. With that default the check does not run on the runner. `telemetry: 1` exports `HEFESTO_TELEMETRY=1`, and the check runs.

## Tests

Failing commit first (`e0b7925`), then this fix.

`pytest -q tests/telemetry/test_telemetry.py -k update_check --tb=line -p no:cacheprovider --no-cov` on that commit, before the fix:

```
15 failed, 2 passed, 24 deselected in 0.08s
```

The 15 failures are one per opt-out value. Each monkeypatches `urllib.request.Request` and `urlopen` to record the call and raise. The assertion that failed was `calls == []` (the request to `https://pypi.org/pypi/hefesto-ai/json` still happened). The 2 passes are the default (mocked fetch, cache file written) and the `telemetry_disabled` file (check still runs).

## Commands

On this tree, after the fix:

```
python scripts/guard_public_repo.py
```

```
PASSED — no paid code leaks detected.
```

```
ruff check .
```

```
All checks passed!
```

```
python -m mypy hefesto --ignore-missing-imports
```

```
Success: no issues found in 102 source files
```

```
python -m pytest -q -m "not integration and not slow"
```

Before any of this branch (main `a36d7c4`):

```
1524 passed, 11 skipped, 2 deselected, 180 warnings in 47.97s
```

After:

```
1541 passed, 11 skipped, 2 deselected, 179 warnings in 45.94s
```

Live check (no `.latest_version`; `telemetry_state.json` is the usage-event notice, which still runs):

```
STATE=$(mktemp -d)
TARGET=$(mktemp -d)
printf 'def ok():\n    return 1\n' > "$TARGET/app.py"
HEFESTO_NO_UPDATE_CHECK=1 HEFESTO_STATE_DIR="$STATE" hefesto analyze "$TARGET" --no-config
ls -la "$STATE"
```

Exit 0. `ls` showed `telemetry_state.json` and `upsell.json` only. No `.latest_version`.

A second run with the variable unset wrote `.latest_version` (`{"version": "4.20.1", ...}`), so the default check still reaches PyPI.

## Not done

- No merge. No tag. No release.
