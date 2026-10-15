# Telemetry

Hefesto sends anonymous usage events to [PostHog Cloud](https://posthog.com) (US region, `https://us.i.posthog.com`) so we can see whether the CLI is used. It is **on by default**.

The first time a send would happen, Hefesto prints a notice on stderr and does **not** send anything in that process. Events start on a later run.

## What is sent

Five events, listed in code (`hefesto/telemetry/client.py`):

| Event | When |
|---|---|
| `first_run` | The first run after the notice, once per install id |
| `analyze` | `hefesto analyze` finished. Also sends `files`, `issues`, `duration_ms`, `exit_code`, `version`, `os`, `py`, `env` (`ci`, `docker`, `dogfood`, plus the same vendor labels as the old ping), and `src` (`pypi` or `editable`) |
| `hooks_installed` | `hefesto install-hooks` wrote at least one hook |
| `hook_blocked` | A git hook's analyze gate failed because of findings |
| `upgrade_cta_shown` | The PRO upgrade line was printed (see below) |

Each event has:

- `distinct_id`: a random UUID created on the machine (`~/.hefesto/telemetry_state.json`). It is not derived from a username, hostname, or path. Delete that file to reset it.
- `source`: `hook` (git hook), `action` (GitHub Action), `ci` (`CI=true`), or `cli` (a direct local invocation). `upgrade_cta_shown` is only sent when `source` is `hook`, `ci`, or `action`.
- `$geoip_disable: true` on every event, and `$process_person_profile: false` so PostHog does not build a person profile.

No code, file paths, findings, repository names, or IP address is included. `issues` and `files` are counts. PostHog still sees the TCP connection; `$geoip_disable` tells it not to turn that into a location.

## Newer version

`hefesto analyze` asks PyPI (`https://pypi.org/pypi/hefesto-ai/json`) for the current release, with a 1.5s timeout. The version is cached for 24 hours in `~/.hefesto/.latest_version`. A failure is ignored. When the cached version is newer, the CLI prints `Hefesto <version> available (you have <current>). Upgrade: pip install --upgrade hefesto-ai`. This check is not a PostHog event and it still runs when usage events are turned off.

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

`hefesto telemetry disable` writes `~/.hefesto/telemetry_disabled`. Delete that file to turn telemetry back on. `HEFESTO_TELEMETRY=0` also accepts `false`, `no`, and `off`.

Debug (prints the event on stderr, does not use the network):

```bash
export HEFESTO_TELEMETRY_DEBUG=1
```

Sending runs on a background thread with a short timeout and ignores errors. It does not change the command's exit code.

## Git hooks and the GitHub Action

Hooks installed by `hefesto install-hooks` export `HEFESTO_SOURCE=hook` before `hefesto analyze`.

The GitHub Action is unchanged. With `telemetry: 1` or `true` it still POSTs its own `event=action` body to `https://hefestoai.narapallc.com/api/telemetry` and exports `HEFESTO_TELEMETRY=1`, which lets the CLI send the PostHog events (`source` becomes `action` because `GITHUB_ACTIONS=true`). The default `telemetry: 0` exports `HEFESTO_TELEMETRY=0` and the Action sends nothing.

`upgrade_cta_shown` is reserved for the one-time PRO line printed after a hook blocks a commit. It is not printed when `CI=true` or when `GITHUB_ACTIONS` is set.
