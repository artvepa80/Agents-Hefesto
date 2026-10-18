# Telemetry

Hefesto sends anonymous usage events to [PostHog Cloud](https://posthog.com) (US region, `https://us.i.posthog.com`) so we can see whether the CLI is used. It is **on by default**.

The first time a send would happen, Hefesto prints a notice on stderr and does **not** send anything in that process. Events start on a later run.

## What is sent

Five events, listed in code (`hefesto/telemetry/client.py`):

| Event | When |
|---|---|
| `first_run` | The first run after the notice, once per install id |
| `analyze` | `hefesto analyze` finished. Also sends `files`, `issues`, `duration_ms`, `exit_code`, `version`, `os`, `py`, `env` (`ci`, `docker`, `dogfood`, plus the same vendor labels as the old ping), and `src` (`pypi` or `editable`) |
| `hooks_installed` | `hefesto install-hooks` or `hefesto init` wrote at least one hook |
| `hook_blocked` | A git hook's analyze gate failed because of findings |
| `upgrade_cta_shown` | The PRO upgrade line was printed (see below) |

Each event has:

- `distinct_id`: a random UUID created on the machine (`~/.hefesto/telemetry_state.json`). It is not derived from a username, hostname, or path. Delete that file to reset it.
- `source`: `hook` (git hook), `action` (GitHub Action), `ci` (`CI=true`), or `cli` (a direct local invocation). `upgrade_cta_shown` is only sent when `source` is `hook` or `cli`, and it includes `cta` (the notice type).
- `$geoip_disable: true` on every event, and `$process_person_profile: false` so PostHog does not build a person profile.

No code, file paths, findings, repository names, or IP address is included. `issues` and `files` are counts. PostHog still sees the TCP connection; `$geoip_disable` tells it not to turn that into a location.

## Newer version

`hefesto analyze` asks PyPI (`https://pypi.org/pypi/hefesto-ai/json`) for the current release, with a 1.5s timeout. The version is cached for 24 hours in `~/.hefesto/.latest_version`. A failure is ignored. When the cached version is newer, the CLI prints `Hefesto <version> available (you have <current>). Upgrade: pip install --upgrade hefesto-ai`. This check is not a PostHog event.

The check is skipped, with no request and no cache write, when any of these holds:

- `HEFESTO_NO_UPDATE_CHECK` is `1`, `true`, `yes`, or `on`
- `HEFESTO_TELEMETRY` is `0`, `false`, `no`, or `off` (the same off values as usage events)
- `DO_NOT_TRACK` is `1`, `true`, `yes`, or `on`

Comparison ignores surrounding spaces and letter case. Usage events stay on by default. `HEFESTO_NO_UPDATE_CHECK` does not turn them off. `hefesto telemetry disable` (the `telemetry_disabled` file) turns events off and does not skip this check.

The GitHub Action exports `HEFESTO_TELEMETRY=0` unless its `telemetry` input is `1` or `true` (`scripts/action_entrypoint.sh`). With that default the check does not run on the runner. `telemetry: 1` exports `HEFESTO_TELEMETRY=1`, and the check runs.

The project key embedded in the client is a public write-only PostHog key. It is not a secret. Override it (including with an empty value, which sends nothing):

- Environment: `HEFESTO_POSTHOG_KEY`, `HEFESTO_POSTHOG_HOST` (a set-but-empty value wins).
- Config file `~/.hefesto/telemetry.json`:

```json
{"posthog_api_key": "", "posthog_host": "https://us.i.posthog.com"}
```

Environment wins over the file, and the file wins over the built-in default. The host must be an `http` or `https` origin with no user or password; anything else is treated as empty and nothing is sent.

## How to turn it off

Any one of these is enough:

```bash
hefesto telemetry disable
export HEFESTO_TELEMETRY=0
export DO_NOT_TRACK=1
```

`hefesto telemetry disable` writes `~/.hefesto/telemetry_disabled`. Delete that file to turn telemetry back on. `HEFESTO_TELEMETRY=0` also accepts `false`, `no`, and `off`. Those off values, and `DO_NOT_TRACK`, also skip the PyPI version check. The disable file does not.

Debug (prints the event on stderr, does not use the network):

```bash
export HEFESTO_TELEMETRY_DEBUG=1
```

Sending runs on a background thread with a short timeout and ignores errors. It does not change the command's exit code.

## Git hooks and the GitHub Action

Hooks installed by `hefesto install-hooks` or `hefesto init` export `HEFESTO_SOURCE=hook` before `hefesto analyze`.

The Action script is unchanged. With `telemetry: 1` or `true` it still POSTs its own `event=action` body to `https://hefestoai.narapallc.com/api/telemetry` and exports `HEFESTO_TELEMETRY=1`, which lets the CLI send the PostHog events (`source` becomes `action` because `GITHUB_ACTIONS=true`) and run the PyPI version check. The default `telemetry: 0` exports `HEFESTO_TELEMETRY=0`: the Action sends nothing, and the CLI skips the PyPI version check on the runner.

## Upgrade notices

The CLI can print one extra stderr line after the command result. Prices in that line are PRO $8/mo and OMEGA $19/mo. The link is `https://hefestoai.narapallc.com/?utm_source=hefesto-cli&utm_medium=cli&utm_campaign=growth_q4_2026&utm_content=<type>#pricing`.

| `cta` | When |
|---|---|
| `gated_serve` | `hefesto serve` without the PRO API-hardening package |
| `gated_enrich` | `hefesto analyze --enrich` without PRO enrichment |
| `gated_scope` | a scope flag (`--include-third-party`, `--include-generated`, `--include-fixtures`, `--scope-allow`, `--scope-deny`) without PRO scope gating |
| `gated_info` | `hefesto info` prints one line — PRO ($8/mo) adds the API server, enrichment, and scope gating; OMEGA ($19/mo) adds IRIS — then exits 1. The multi-line PRO message is not printed. |
| `gated_iris` | `hefesto serve` with `IRIS_BQ_PROJECT` set and the IRIS package missing (OMEGA) |
| `analyze_milestone` | 25 finished analyses, then every 100 (125, 225, ...) |
| `init` | `hefesto init`, after the hooks are installed |
| `hook_blocked` | a git hook's analyze gate failed |

`analyze_milestone` names hefesto-swarm: it is HefestoAI's security analysis pipeline, it runs on a target repo, and it can return BLOCK (`swarm/cli.py` in the PRO package).

The line is not printed when `CI=true`, when GitHub Actions, GitLab CI, Jenkins (`JENKINS_URL`), or CircleCI is detected, when stdout is not a TTY, with `--output json`, `--output sarif`, or `--quiet`, or when `HEFESTO_TELEMETRY=0`, `DO_NOT_TRACK=1`, or `HEFESTO_NO_UPSELL=1`. `HEFESTO_NO_UPSELL` also accepts `true`, `yes`, and `on`. `hefesto telemetry disable` hides the line as well, because usage events are off.

At most one notice of any type is printed every 7 days. Each type is printed at most 3 times. The counters are in `~/.hefesto/upsell.json`. If that file cannot be read or is not valid JSON, nothing is printed and the file is left as it is.

`upgrade_cta_shown` is sent only when the line is printed and telemetry can send in this process (`source` is `hook` or `cli`). The notice process prints the line and does not send the event. `cta` is the type from the table.
