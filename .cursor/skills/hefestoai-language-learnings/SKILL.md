---
name: hefestoai-language-learnings
description: Verified lessons from building and running HefestoAI, grouped by language and by CI area. Use when touching an analyzer in hefesto/analyzers, triaging `hefesto analyze` findings (false positives, "0 files analyzed", missing rules), or fixing a red CI job or GitHub Actions workflow in the HefestoAI repos.
---

# HefestoAI language learnings

Short, verified notes on things that went wrong (or nearly did) in HefestoAI, with the fix and an
official source. This is an engineering skill for contributors and agents. It is **not** the
customer-facing product skill in `skill/` at the repo root; leave that one alone.

## When to use

- You are changing an analyzer, a rule, file discovery or language routing.
- A `hefesto analyze` result looks wrong: a false positive, a missed rule, or "0 files analyzed".
- A CI job, workflow, release step or local pre-push check is red.

## Index

Read only the file you need.

| File | Covers |
| --- | --- |
| [references/python.md](references/python.md) | Python rules (HARDCODED_SECRET, ATTRIBUTE_NAME_MISMATCH, R3), mypy |
| [references/js-ts.md](references/js-ts.md) | JavaScript/TypeScript: EVAL_USAGE, vendored files, tree-sitter tests |
| [references/json.md](references/json.md) | JSON analyzer (J001/J002/J004/J005), "Found 0 file(s)" |
| [references/cobol.md](references/cobol.md) | COBOL rules, copybooks, precision measurement |
| [references/yaml-iac.md](references/yaml-iac.md) | YAML, Terraform and other IaC findings |
| [references/github-actions.md](references/github-actions.md) | Workflow actions, runners, release.yml |
| [references/tooling-ci.md](references/tooling-ci.md) | Local checks (ruff, mypy, guard), zero-files gate, CI behavior |

## Entry format

Every entry uses exactly these fields:

```markdown
### <short title>

- **Symptom:** what you see (message, rule id, CI status).
- **Cause:** why it happens, as established in the source.
- **Fix:** what was done or what to do.
- **Official source:** URL of the upstream documentation (or "n/a, internal behavior").
- **PR/commit:** PR number and/or commit SHA, or the CHANGELOG version.
- **Verified:** version or date it was last checked.
- **Status:** Fixed | Workaround | Open | Known limitation.
```

## Adding an entry

1. Only add something that happened in these repos and is written down: a CHANGELOG entry, a
   worklog/handoff, a PR or a commit. Do not add guesses or general advice.
2. Open the source file or commit and check the claim before writing it. Cite it in **PR/commit**.
3. Link the upstream documentation you used in **Official source**. If the behavior is our own
   code, say so.
4. Put the entry in the file for its language or area. Keep it under about 10 lines.
5. Add a line under `[Unreleased]` in `CHANGELOG.md`, run `agentskills validate` on the skill folder
   (`pip install skills-ref`), and dogfood any changed code with `HEFESTO_TELEMETRY=0 hefesto analyze`
   (Markdown is not a supported format, so the skill files themselves report 0 files).
6. Public repo: run `python scripts/guard_public_repo.py`. Internal topics (the paid package, billing,
   landing, hosted engine) never go in the public copy.

## Reviewing at each release

Part of the release checklist, before tagging:

1. For every entry with **Status: Open** or **Workaround**, check whether the release fixes it.
   If so, change the status and add the PR/commit.
2. For entries about third-party tools (actions, runners, PyPI), re-open the official source and
   check that it still says the same. Update **Verified** with the release version or date.
3. Remove entries that no longer apply, and note the removal in the CHANGELOG.
4. Keep the two copies in sync: the public repo is the source of truth; the private repo has the
   same files plus `references/pro-internal.md`.

## Sources used to seed this skill

`CHANGELOG.md`, `docs/cobol.md` and `docs/worklog/` in the public repo; `MEMORY.md`,
`CHANGELOG.md`, `docs/CI_TROUBLESHOOTING.md` and `docs/worklog/` in the private repo; PRs and
commits cited in each entry. Seeded 2026-10-16 with hefesto-ai 4.20.0.
