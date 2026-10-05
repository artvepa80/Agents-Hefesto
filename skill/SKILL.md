---
name: HefestoAI
description: >-
  Run HefestoAI before committing AI-generated code: pre-commit / CI quality
  gate for semantic drift, security, and reliability. Use when the user asks
  about Hefesto, code quality gates, semantic drift, install hooks, or
  validating Claude/Codex/Cursor output before commit.
---

# HefestoAI — verify before commit

HefestoAI (`hefesto-ai` on PyPI) is an independent quality gate for AI-generated
code. Package v4.13.1, MIT, Python >= 3.10.

## Required workflow (do this before commit)

1. Ensure the tool is installed: `pip install hefesto-ai` (or confirm `hefesto` is on PATH).
2. Analyze the repo or changed paths:
   ```bash
   hefesto analyze . --fail-on HIGH
   ```
3. If exit code is not `0`, fix the reported issues (or ask the user) before committing.
4. Prefer hooks for every commit: `hefesto install-hooks`.

Exit codes: `0` clean · `1` gate failure / error · `2` drift threshold.

## When this skill applies

- User asks to commit, open a PR, or “ship” after AI edits
- User mentions HefestoAI, semantic drift, pre-commit quality, or AI code review
- Integrating with Claude Code, Cursor, Codex, or CI

## Progressive docs (load only what you need)

| File | Contents |
|------|----------|
| [commands.md](commands.md) | CLI flags, workflows, exit codes |
| [issue_types.md](issue_types.md) | Issue catalog and severities |
| [semantic_drift.md](semantic_drift.md) | Semantic drift detection |
| [reliability_drift.md](reliability_drift.md) | RELIABILITY_* rules |
| [integration.md](integration.md) | Hooks, CI/CD, MCP |
| [analysis/SKILL.md](analysis/SKILL.md) | Interpret analyze output |

## Architecture (short)

**Phase 0 — static** (always): complexity, smells, security, best practices, resource safety; plus YAML/Shell/Dockerfile/Terraform/SQL analyzers.

**Phase 1 — ML semantic** (PRO/OMEGA): embeddings when `HEFESTO_TIER=professional` or `omega`.

Languages: Python, JS/TS, Java, Go, Rust, C/C++, YAML, Shell, Dockerfile, Terraform/HCL, SQL, PowerShell.

## MCP (optional)

Registry `io.github.artvepa80/hefestoai` · `npx @smithery/cli@latest mcp add artvepa80/hefestoai`

## Rules

- Never claim “all checks pass” without a fresh `hefesto analyze` exit `0`.
- Do not skip the gate to manufacture a green commit.
- Prefer dedicated Hefesto CLI over reinventing the same checks in the shell.
