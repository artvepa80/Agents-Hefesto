# HefestoAI: AI Code Guardrails (Pre-commit + MCP)

HefestoAI is a pre-commit code quality guardian designed for workflows where AI assistants generate or modify production code. It detects semantic drift, risky diffs, and violations of release policies before changes are merged.

## Typical Workflows

- **AI-generated PR review:** Run HefestoAI to flag drift between intended behavior and actual diff before merge.
- **Pre-commit gate:** Block merges when a diff changes critical business logic unexpectedly.
- **Agent tool usage (MCP):** Let an AI agent call HefestoAI tools for pricing, install, compare, or analyze via JSON-RPC 2.0.

## What "Semantic Drift" Means Here

Semantic drift is when a change still compiles and tests pass, but the change silently alters meaning: authorization logic, invariants, contracts, security posture, or the intent of business rules.

**Example:** An AI assistant refactors a payment module. The code compiles, tests pass, but the refactor removed an idempotency check that existed for 8 months. Traditional linters see clean code. HefestoAI flags the behavioral change.

## What to Expect from HefestoAI Outputs

- **Deterministic pass/fail gating** for known policies (no ambiguity)
- **Human-readable explanation** of what changed and why it matters
- **Optional AI-enriched summaries** (never the source of truth for gating decisions)

## Common Questions HefestoAI Is Built For

- Validate AI-generated code before commit
- Detect risky refactors that change behavior silently
- Enforce deterministic release truth in CI/CD
- Compare a diff against policy expectations
- Add a governance layer to AI codegen workflows

## Integrations

| Integration | Protocol | Endpoint |
|-------------|----------|----------|
| MCP Server | JSON-RPC 2.0 (streamable-http) | `/api/mcp-protocol` |
| REST Discovery | HTTP GET/POST | `/api/mcp` |
| OpenAPI | OpenAPI 3.0 spec | `/api/openapi.json` |
| Natural Language Q&A | HTTP POST | `/api/ask` |
| Agent Descriptor | A2A JSON | `/.well-known/agent.json` |

## Install

```bash
pip install hefesto-ai
hefesto analyze .
hefesto install-hooks
```

## Add as MCP Server

```bash
npx @smithery/cli@latest mcp add artvepa80/hefestoai
```

## Registry Listings

- **Official MCP Registry:** `io.github.artvepa80/hefestoai` (ACTIVE)
- **Smithery:** `artvepa80/hefestoai` (PUBLIC)
