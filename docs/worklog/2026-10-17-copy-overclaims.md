# 2026-10-17: public copy overclaims (handoff)

Docs only, plus one comment in `scripts/action_entrypoint.sh` and the README telemetry assertion in `tests/test_readme_telemetry_claim.py`. No analyzer, CLI, or Action behaviour change. No tag, no release, no merge.

GH-8: this PR touches `scripts/action_entrypoint.sh` (comment only). That path is runtime. Do not merge it on the calendar day (America/Lima) it was opened.

## What changed

Copy now matches hefesto-ai 4.20.1.

- `PICKLE_USAGE` is the `import pickle` / `import cPickle` / `from pickle import …` line. `pickle.loads()` and `pickle.load()` are not a separate finding, and `yaml.load` is not detected (`hefesto/analyzers/security.py`). Updated: `README.md`, `README.zh-CN.md`, `README.ja.md`, `skill/issue_types.md`, `SECURITY.md`, `docs/ANALYSIS_RULES.md` (heading, rule id `PICKLE_USAGE`, the summary table row that used to say `SECURITY_004` / "Unsafe Pickle"), `llms.txt` already named the import, and `.well-known/agent-card.json` example, which must read exactly: "Analyze this Python file for hardcoded secrets and pickle imports."
- Telemetry: the CLI sends anonymous PostHog usage events by default (`hefesto telemetry disable`, `HEFESTO_TELEMETRY=0`, `DO_NOT_TRACK=1`). The GitHub Action sends no usage events unless `telemetry: 1`. Separately, `hefesto analyze` asks pypi.org for the latest version (1.5 s timeout, cached 24 hours). That check runs with telemetry off. Version 4.20.1 has no setting to turn it off. Updated: `README.md` (Telemetry section and the Action `telemetry` input row), new sections in `README.zh-CN.md` and `README.ja.md`, and a Telemetry section in `llms.txt`.
- `scripts/action_entrypoint.sh` comment: with the default `telemetry: 0`, no telemetry leaves the runner (the CLI's pypi.org version check still runs). The `if` that sends the Action ping is unchanged.
- Hosted MCP lines in `README.md`, `README.zh-CN.md`, and `README.ja.md` no longer say hefesto-ai 4.19.0. This repo does not state a verified current pin for the hosted engine, so the lines say the hosted MCP runs a recent hefesto-ai release.
- `docs/INTEGRATION.md` offline design notes now say static analysis needs no internet, and the embedding model needs no API calls, and that the CLI still sends opt-out telemetry and a pypi.org version check.

`tests/test_readme_telemetry_claim.py` pins the README telemetry sentence. The expected string was updated to the new sentence. The assertions on `telemetry_enabled()` and the Action default `0` are unchanged.

## Left for later

- A later change adds a switch for the pypi.org version check. This copy describes 4.20.1, which has no switch. Update the "no setting" / "no switch" sentences when that change is released.
- `action.yml` and `skill/integration.md` still say the default telemetry value sends nothing. That is true of the Action ping and the CLI usage events. They do not mention the pypi.org check. Not edited here.
- `docs/telemetry.md` already says the version check runs when usage events are off. It does not say 4.20.1 has no switch. Not edited here.
- Historical CHANGELOG sections and older worklogs that name hefesto-ai 4.19.0 as the hosted engine were left as written.
