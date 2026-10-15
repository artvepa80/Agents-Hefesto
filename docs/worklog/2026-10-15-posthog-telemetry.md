# 2026-10-15: PostHog telemetry (handoff)

Public repo only. No tag, no release, no merge (Arturo merges, and not the same day).

## What landed

- The Narapa usage ping (`hefestoai.narapallc.com/api/telemetry`) and the local JSONL log (`HEFESTO_TELEMETRY=1`, `~/.hefesto/telemetry.jsonl`, `hefesto telemetry status` / `clear`) are gone.
- Events go to PostHog Cloud US (`https://us.i.posthog.com`) with the public write-only project key as the default. Override with `HEFESTO_POSTHOG_KEY` / `HEFESTO_POSTHOG_HOST` or `~/.hefesto/telemetry.json`. An empty key or host sends nothing.
- On by default. Notice on stderr before the first send; that process does not send. Off with `hefesto telemetry disable`, `HEFESTO_TELEMETRY=0`, or `DO_NOT_TRACK=1`. `HEFESTO_TELEMETRY_DEBUG=1` prints the event and does not open a socket.
- Five events: `first_run`, `analyze`, `hooks_installed`, `hook_blocked`, `upgrade_cta_shown`. Body: random UUID, `source`, `$geoip_disable: true`, `$process_person_profile: false`. No paths, code, findings, repository names, or IP. `analyze` also sends `files`, `issues`, `duration_ms`, `exit_code`, `version`, `os`, `py`, `env` (`ci` / `docker` / `dogfood`, plus the old vendor labels), and `src` (`pypi` or `editable`). Arturo confirmed this on 2026-10-15.
- The `Hefesto X available` line now comes from a PyPI query (`hefesto-ai` JSON, 1.5s timeout, 24h cache in `~/.hefesto/.latest_version`). Failure is ignored. It still runs when usage events are off.
- The GitHub Action script is not part of this change. It still POSTs `event=action` to `/api/telemetry` when `telemetry` is 1.
- The console script and `python -m hefesto` call `cli()`, so telemetry starts in the Click callback. `main()` (used by `python -m hefesto.cli.main`) still exits 2 on a Click usage error.
- The Action script is untouched. Default `telemetry: 0` still exports `HEFESTO_TELEMETRY=0`. `telemetry: 1` still curls the old endpoint and turns the CLI events on.

## Design choices

- Direct local invocation uses `source=cli`. `hook`, `ci`, and `action` stay accurate. `upgrade_cta_shown` is dropped unless `source` is `hook`, `ci`, or `action` (Growth). The CTA itself is the follow-up command, not this change.
- `$geoip_disable` is a property on every event. PostHog can still see the TCP address; the property asks it not to store a location. The payload has no IP field.
- The first process only prints the notice (Homebrew-style). `first_run` is the first event, on a later process.
- Sends are a daemon thread with a 1.5s timeout. A process that exits immediately can drop the event. Failures are ignored.
- Unit tests do not emit unless `HEFESTO_TELEMETRY_UNDER_TEST=1`, so the rest of the suite cannot phone home.

## Not done

- No merge. No tag. No release.
- `hefesto init` and the one-time PRO line are a separate branch stacked on this one.
