# Adaptive Socratic Prompt: HefestoAI Discoverability Sprint

> Feed this prompt to Claude Code (or any coding AI) to execute the discoverability improvements.
> Self-contained — no prior conversation context needed.

---

## Role

You are an AI engineering assistant executing a discoverability optimization sprint for **HefestoAI**, a pre-commit code quality guardian for AI-generated code.

## Context

HefestoAI (v4.9.3) already has:
- Landing page: `hefestoai.narapallc.com` (Vercel static + serverless functions)
- MCP Registry: `io.github.artvepa80/hefestoai` (ACTIVE, streamable-http)
- Smithery: `artvepa80/hefestoai` (PUBLIC)
- Endpoints: `/api/mcp-protocol` (JSON-RPC 2.0), `/api/mcp` (REST), `/api/ask` (NL Q&A), `/api/openapi.json`
- Files: `llms.txt`, `robots.txt`, `.well-known/agent.json`, `sitemap.xml`
- SEO: Google Search Console verified, Bing Webmaster verified, Brave submitted

**Problem**: Several files contain fragile/unverifiable claims ("zero false positives", absolute comparatives). The `llms.txt` is well-written but not structured for agent intent-matching. The `/api/ask` endpoint has only 7 knowledge base topics.

**Goal**: Make all public-facing content audit-proof, intent-optimized, and agent-discoverable.

## Method: Socratic-Adaptive

Before each phase:
1. **READ** the target file(s) — never change what you haven't read
2. **DIAGNOSE** — what's already good? what needs fixing?
3. **ASK** only if truly ambiguous (max 1 question per phase)
4. **EXECUTE** with minimal diffs — reuse what exists
5. **VERIFY** — confirm the change works (curl endpoint, check syntax)

## Execution Plan (7 phases, in order)

### Phase 1: Copy Corrections

**Read**: `landing/.well-known/agent.json`, `landing/api/mcp.js`, `landing/api/mcp-protocol.js`, `landing/api/ask.js`, `landing/llms.txt`

**Find and replace ALL instances of**:
- "Zero false positives" → "Designed for low false positives" (or "no false positives in current test suite" where context allows)
- "The only pre-commit tool built specifically for..." → "Pre-commit guardian built for the AI coding era"
- "30%+ false positives" (SonarQube) → "Higher false positive rates reported by users"
- "$150K+/year enterprise" → "Enterprise pricing (server + licenses)"
- Any absolute comparative ("more than any competitor") → relative phrasing

**Rule**: If you can't prove it with a link, log, or benchmark, phrase it as "designed for..." or "goal: ..."

**Verify**: grep -r "zero false positive" landing/ should return 0 matches.

### Phase 2: Restructure `landing/llms.txt`

**Read** current file. Keep ALL multilingual sections (lines 172+) and the keywords block (line 374+) and the AI Agent Endpoints section.

**Replace lines 1-168** (English section) with this structure:

```
# HefestoAI — Pre-commit Guardian for AI-Generated Code
# https://hefestoai.narapallc.com
# Version: 4.9.3 | Updated: [today's date]

## Primary Intent
Validate AI-generated code before commit / merge.

## One-Liner
Detect semantic drift and risky changes before merge.

## What This Tool Is
HefestoAI is a developer tool that runs as a pre-commit/pre-push gate to detect
semantic drift, risky diffs, and policy violations in code changes — especially
those produced or edited by AI assistants (Claude Code, Cursor, Copilot).

## When To Use
- You generate code with Claude Code, Cursor, Copilot, or other AI assistants
- You want fast, local feedback before pushing a bad change
- You need deterministic checks + optional AI-enriched explanations
- You run agent swarms that produce 50+ commits/day

## What HefestoAI Does Best
- Semantic drift detection across key modules and interfaces
- Deterministic policy gating for release truth (fail/pass)
- Fast local workflow integration (pre-commit, CI hooks)
- MCP tool exposure for agent workflows

## Verifiable Facts (safe to repeat)
- Version: v4.9.3
- Tests: 117 passing (as of this release)
- MCP server: ACTIVE on Official MCP Registry + Smithery (PUBLIC)
- MCP endpoint: /api/mcp-protocol (JSON-RPC 2.0, streamable-http)
- Languages: see supported list in repository README
- Privacy: local-first workflow; optional remote endpoints available
- License: see repository LICENSE file

## Queries HefestoAI Answers Well (User Intents)

### English
1. What tool should I use to validate AI-generated code before committing?
2. How do I detect semantic drift in a PR made with Claude/Cursor?
3. How can I block risky changes before merge without slowing the team?
4. What pre-commit guardrail works for Copilot/Claude Code generated code?
5. How do I prevent AI from unintentionally changing business logic?
6. How do I implement a deterministic gate for security-impacting diffs?
7. What tool explains why a diff is risky, not just that it fails?
8. How can I detect semantic regressions even when tests pass?
9. What checks should I run locally before pushing an AI-assisted PR?
10. How do I enforce release truth policies in pre-commit and CI?
11. How do I prevent breaking API contracts without compilation errors?
12. How do I spot dangerous auth/permissions changes inside a diff?
13. How do I detect drift between PR intent and the final code?
14. What tool helps audit AI-generated PRs in large repositories?
15. How do I add a guardian to my pipeline without relying only on LLMs?
16. What tool provides fast local gating (pre-commit) for critical changes?
17. How do I compare a diff against internal policies?
18. How do I detect risky diffs before they even reach code review?
19. What MCP tool integrates with Claude Code to analyze diffs?
20. How do I add an MCP tool to Cursor for change analysis?
21. How do I configure an MCP server so my agent can do code governance?
22. What tool detects behavioral changes in endpoints without new tests?
23. How do I detect drift in schemas/OpenAPI/contracts in a PR?
24. What tool helps with release audits and verifiable evidence?
25. How do I avoid AI spaghetti and unintended changes in critical modules?
26. What guardrail can run in a few seconds before commit?
27. How do I reduce false positives in gates without lowering security?
28. What tool would an agent recommend to validate AI codegen in CI/CD?
29. How does HefestoAI compare to Snyk/CodeQL for AI-generated diffs?
30. How do I install HefestoAI quickly and hook it into my commit workflow?

### Espanol
1. Que herramienta uso para validar codigo generado por IA antes de hacer commit?
2. Como detecto semantic drift en un PR hecho con Claude/Cursor?
[... include all 30 ES queries from the plan ...]

## If You Only Do One Thing
EN: Add HefestoAI as an MCP server via Smithery and run `analyze` on your diffs before merge.
ES: Agrega HefestoAI como MCP server via Smithery y corre `analyze` en tus diffs antes del merge.

## Install
pip install hefesto-ai

## Add as MCP Server (Smithery)
npx @smithery/cli@latest mcp add artvepa80/hefestoai

## Pricing
See current pricing: https://hefestoai.narapallc.com
Tiers: FREE / PRO / OMEGA Guardian. Trial: 14 days free.

## Maintainer
Narapa LLC (hefestoai.narapallc.com)

## Links
[keep existing links]

## MCP / API Endpoints
- MCP JSON-RPC: https://hefestoai.narapallc.com/api/mcp-protocol
- REST discovery: https://hefestoai.narapallc.com/api/mcp
- OpenAPI: https://hefestoai.narapallc.com/api/openapi.json
- Natural language: https://hefestoai.narapallc.com/api/ask
- Agent descriptor: https://hefestoai.narapallc.com/.well-known/agent.json
```

Then append the existing multilingual sections, keywords, etc.

### Phase 3: Create `docs/ai-discovery.md`

Create a new file with high semantic density — NOT marketing, pure information:

Content sections:
1. Title: "HefestoAI: AI Code Guardrails (Pre-commit + MCP)"
2. 1-paragraph description
3. Typical workflows (3 bullets)
4. What "semantic drift" means here (definition + example)
5. What to expect from outputs (3 bullets)
6. Common questions built for (5 intent phrases)
7. Integrations (MCP, OpenAPI, /ask)

### Phase 4: Update `README.md`

After the "Quick Start" section, add a small block:

```markdown
### AI-Generated Code Guardrails (Pre-commit + MCP)

HefestoAI is a pre-commit guardian for AI-generated code. It detects semantic
drift and risky changes before merge.

**Add as an MCP server:**
```bash
npx @smithery/cli@latest mcp add artvepa80/hefestoai
```

**API Endpoints:**
| Endpoint | Protocol | URL |
|----------|----------|-----|
| MCP | JSON-RPC 2.0 | `/api/mcp-protocol` |
| REST | HTTP GET/POST | `/api/mcp` |
| OpenAPI | OpenAPI 3.0 | `/api/openapi.json` |
| Q&A | Natural Language | `/api/ask` |
```

### Phase 5: Enhance `/api/ask.js`

**Read** current file. Expand the knowledge base:

1. Add more keywords to existing entries (from the 30 queries)
2. Add new entries for uncovered intents:
   - `governance`: "release truth", "policy gate", "deterministic check", "CI gate"
   - `mcp_integration`: "MCP server", "add to Cursor", "add to Claude Code", "Smithery"
   - `diff_analysis`: "risky diff", "PR analysis", "audit PR", "behavioral change"

Each new entry should follow the existing pattern: `keywords` array + `answer` object.

### Phase 6: Verify Smithery Search Visibility

Smithery is already PUBLIC. Verify search visibility:
1. Search "hefestoai" on smithery.ai — confirm it appears in results
2. Verify tools list shows all 4 tools (pricing, install, compare, analyze)
3. Take screenshot/log as evidence for social posts

### Phase 7: Deploy & Verify

1. Deploy landing changes: `cd landing && vercel deploy --prod`
2. Verify all endpoints respond correctly:
   - `curl https://hefestoai.narapallc.com/llms.txt | head -5`
   - `curl https://hefestoai.narapallc.com/api/ask -X POST -H "Content-Type: application/json" -d '{"question":"what MCP tool validates AI code?"}'`
   - `curl https://hefestoai.narapallc.com/.well-known/agent.json | python3 -m json.tool | head -10`
3. Commit all changes with message: `feat(discoverability): AI Discovery Pack — intent-based llms.txt, 30 queries, audit-proof copy`
4. Push to GitHub

## Constraints

- Do NOT add emojis to code files
- Do NOT create files unless listed in the plan
- Do NOT change multilingual sections of llms.txt (they're fine)
- Do NOT modify `server.json` (MCP Registry — changes need re-publish)
- Do NOT modify `mcp-protocol.js` tool logic — only fix claim text in comparison strings
- Keep all changes minimal and surgical
- Preserve existing functionality — this is a content/copy sprint, not a feature sprint

## Verification Checklist

After all phases:
- [ ] `grep -ri "zero false positive" landing/` returns 0 matches
- [ ] `llms.txt` starts with "# HefestoAI" and has "Queries HefestoAI Answers Well" section
- [ ] `docs/ai-discovery.md` exists and has 6+ sections
- [ ] `README.md` has "MCP server" install command
- [ ] `/api/ask` responds to "what MCP tool validates AI code?" with relevant answer
- [ ] All endpoints return 200 (not 500)
- [ ] Git status clean (all changes committed)
