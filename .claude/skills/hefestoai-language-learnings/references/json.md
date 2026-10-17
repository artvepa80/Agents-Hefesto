# JSON learnings

### `config.json` with secrets reported "Found 0 file(s)"

- **Symptom:** up to 4.19.0, `hefesto analyze config.json` analyzed 0 files, even with secrets inside.
- **Cause:** `JsonAnalyzer` shipped as a module, but no `LanguageSpec` routed `*.json` to it.
- **Fix:** 4.20.0 dispatches JSON (and eight more formats). After the release, `config.json` with fake secrets gives "Found 1 file(s)" and 2 CRITICAL `HARDCODED_SECRET` with rule id J001.
- **Official source:** n/a, internal behavior
- **PR/commit:** #124 (`4bb568f`), released in 4.20.0 (`ea260bc`); `docs/worklog/2026-10-16-release-4.20.0.md`
- **Verified:** 4.20.0 from PyPI in a fresh venv (2026-10-16)
- **Status:** Fixed

### JSON rule ids are J001, J002, J004, J005 (no J003)

- **Symptom:** docs or tests that expect J003.
- **Cause:** J003 does not exist.
- **Fix:** list J001, J002, J004 and J005. JSON secret keys match whole tokens, so `author` and dependency names are not secrets.
- **Official source:** n/a, internal behavior
- **PR/commit:** CHANGELOG 4.20.0 (Documentation, Upgrading)
- **Verified:** 4.20.0
- **Status:** Fixed

### A `.json` file can be routed to another analyzer

- **Symptom:** a JSON file gets CloudFormation/ARM findings instead of J00x.
- **Cause:** shared suffixes are classified by content: `*.tf.json` stays Terraform; `$schema` with `deploymentTemplate.json` is ARM; `AWSTemplateFormatVersion` or `Resources` with `AWS::` types is CloudFormation. Generated lockfiles (`package-lock.json`, ...) are skipped in directory walks.
- **Fix:** expected. Name a lockfile on the command line to analyze it.
- **Official source:** n/a, internal behavior; precedence in `docs/design/devops-analyzers-wiring.md`
- **PR/commit:** #124, CHANGELOG 4.20.0
- **Verified:** 4.20.0
- **Status:** Known limitation (by design)

