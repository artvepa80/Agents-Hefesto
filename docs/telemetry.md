# Telemetry

Moved from the README.


HefestoAI collects anonymous usage data by default to help improve the tool.

**What's sent (CLI):** event type, version, OS, Python version, file count, duration, issue count, exit code, a random anonymous ID stored in `~/.hefesto/.session_id` (delete the file to reset it), environment flags such as `ci`, `github_actions`, `docker` or `dogfood`, and the install source (`pypi` or `editable`).
**What's sent (GitHub Action):** nothing by default. The Action's telemetry is opt-in: only with the `telemetry` input set to `1` or `true` does it send version, file count, issue count and exit code once per run, and it turns on the CLI ping described above. With `telemetry: 0` (the default) or any other value, the Action sends no ping and runs the CLI with `HEFESTO_TELEMETRY=0`. (Up to v4.14.0 the Action sent its ping even with `telemetry: 0`.)
**What's NOT sent:** code, file paths, file contents, project names, or any PII.

The CLI prints a one-time notice to stderr the first time it sends a ping, and it uses the server's reply to tell you when a newer version is on PyPI. Disable the CLI ping with:
```bash
export HEFESTO_TELEMETRY=0
```

Tag owner/dogfood runs so they do not mix with end-user analytics (`env` includes `dogfood`; also auto-tagged for editable installs):
```bash
export HEFESTO_TELEMETRY_ENV=dogfood
# or: export HEFESTO_DOGFOOD=1
```
Filter in Neon: `WHERE NOT ('dogfood' = ANY(env))`.

`hefesto telemetry status` shows whether the CLI ping is enabled and where it goes, plus the state of a separate local telemetry log (opt-in with `HEFESTO_TELEMETRY=1`, never uploaded). `hefesto telemetry clear` deletes that local log; it does not affect the remote ping.
