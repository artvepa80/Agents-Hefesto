# 2026-10-15: hosted engine docs (handoff)

Public repo only. Docs catch-up after the hosted engine moved to hefesto-ai 4.19.0. No tag, no release, no merge (Arturo merges).

## What landed

- README: the MCP `analyze` / `POST /api/analyze` line now says hefesto-ai 4.19.0. The engine at https://hefestoai.narapallc.com runs that release (private repo PR #148, merged and in production on 2026-10-15). PyPI `hefesto-ai` 4.19.0 is the current package release, and `v4` points at that commit.
- README env-var comment: `HEFESTO_TELEMETRY=0` disables anonymous usage events. The CLI usage ping was removed in 4.18.0. The Telemetry section already said "usage events".
- `action.yml` `telemetry` description: with `1` or `true`, one anonymous Action ping per run and the CLI usage events. It no longer says "CLI usage ping".
- `llms.txt` and `.well-known/agent-card.json` security skill: dropped `PATH_TRAVERSAL` and `UNSAFE_DESERIALIZATION` (no analyzer emits them; the README table was corrected in 4.17.0). They name `PICKLE_USAGE`. The card uses `SQL_INJECTION_RISK`.
- `skill/integration.md` and `skill/commands.md`: `install-hooks` in a user's project writes the package templates (staged files, `--fail-on HIGH`; the repository, `--fail-on CRITICAL`). `scripts/git-hooks/` is only for a clone of this repository. The Action `format` row includes `sarif`.
- `.github/copilot-instructions.md`: dropped the retired "in 0.01s" claim. The architecture sketch points at files that exist in this tree. `omega/` and `licensing/` are not here (the public-repo guard forbids those directories).
- `docs/CLAUDE_HEFESTO.md`: `hefesto analyze .`. There is no `--project` flag on `analyze`.

## Left unchanged

Historical CHANGELOG sections and worklogs were not rewritten.

Ambiguous, so not edited:

- Exact-pin examples still say `@v4.15.1` in `docs/github-action.md` ("exact stability"), `skill/integration.md`, `llms.txt`, and `.github/copilot-instructions.md`. The 4.16.0 worklog says those examples stay on `@v4.15.1` on purpose (the release before the zero-files exit-code change). The README's parallel sentence now uses `@v4.19.0`.
- `docs/github-action.md` still says `@v4.15.0` keeps the exclusion bug fixed in 4.15.1. That is still true.
- `[4.18.0]` and `[4.19.0]` in CHANGELOG still say the tag, the GitHub Release, and the PyPI publish stay for Arturo. Those steps have since happened for 4.19.0. The released sections were left as written.
- `skill/SKILL.md` still says `install-hooks` exists from 4.17.1. That is still true. The 4.19.0 release worklog left it on purpose.
- `skill/integration.md` still says the Action telemetry input "sends the per-run ping". The Action still POSTs its own `event=action` ping. `tests/test_skill_integration_docs.py` locks that sentence. The Action inputs table still omits `allow_no_files` and the SARIF upload inputs.
- Test counts: `CLAUDE.md` says 507 tests; Copilot instructions say 531 across 38 test files. Not recollected.
- `docs/CLAUDE_HEFESTO.md` mission still says "AI-powered analysis", and it still tells contributors to run `omega-guardian run`. That command is not in this repo.
- `CONTRIBUTING.md` still says coverage is currently 96%. Not measured here.
- Tests that use `"4.17.1"` as a sample newer-version string, and the 4.17.0 false-positive note in `tests/validators/test_test_contradictions_env.py`, are not docs.

## Not done

- No merge. No tag. No release. PR #111 was not touched.
- The private landing serves the same agent card (`landing-page/api/agent-card.js`). `tests/test_positioning_cards.py` says that copy is deep-compared with this file, so the security-skill description changed here needs the same edit there or that parity test fails. This PR does not touch the private repo.
