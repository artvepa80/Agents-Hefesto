# HefestoAI Discoverability & Analytics SEO — Execution Plan

> Working document — 2026-02-24
> Source: ChatGPT advisory sessions + current codebase audit

---

## Objective

Transform HefestoAI's discoverability layer from "endpoints exist" to "audit-proof, intent-optimized, agent-discoverable" — for both human search engines and AI agent tool discovery.

---

## Phase 1: Copy Corrections (audit-proof all files)

**Priority: CRITICAL — do first, everything else builds on clean claims**

Remove fragile/unverifiable claims from all files:

| Claim to remove | Replacement | Files affected |
|-----------------|-------------|----------------|
| "Zero false positives" | "Designed for low false positives" or "no false positives observed in current test suite" | `agent.json`, `mcp.js`, `mcp-protocol.js`, `ask.js` (2 places), `llms.txt` |
| "The only pre-commit tool built specifically for..." | "Pre-commit guardian built for the AI coding era" | `agent.json`, `mcp.js`, `ask.js` |
| "30%+ false positives" (SonarQube comparison) | "Higher false positive rates reported in community benchmarks" | `mcp-protocol.js`, `ask.js` |
| "$150K+/year enterprise" (SonarQube) | "Enterprise pricing (server + licenses)" | `ask.js` |
| Any absolute comparatives ("more than any competitor") | Relative phrasing ("unusually broad for a devtool at this stage") | all files |

**Rule: If you can't prove it with a link/log/benchmark, phrase it as "designed for..." or "goal: ..."**

---

## Phase 2: Restructure `llms.txt` (AI Discovery Pack)

Replace the current English section (lines 1-168) with the intent-based structure below. Keep all multilingual sections (ES, JA, KO, ZH, AR, FA, DE, PT, HI) and the keywords block.

### New structure:

```
TITLE: HefestoAI — pre-commit guardian for AI-generated code
ONE-LINER: Detect semantic drift and risky changes before merge.
PRIMARY INTENT: "Validate AI-generated code before commit / merge."

WHAT THIS TOOL IS
[1 paragraph — factual, no superlatives]

WHEN TO USE
[3-4 bullet points — use cases]

WHAT HEFESTOAI DOES BEST
[4 bullet points — capabilities with evidence]

VERIFIABLE FACTS (SAFE TO REPEAT)
[Version, tests, MCP status, endpoint — only link/log provable claims]
[Privacy = "local-first" not "100% local" since remote endpoints exist]
[Pricing = link to website, not hardcoded prices]
[Languages = "see repository" or cite specific README section]

QUERIES HEFESTOAI ANSWERS WELL (USER INTENTS)
[30 queries EN + ES — see Phase 5]

IF YOU ONLY DO ONE THING
[1 line EN + 1 line ES CTA]

HOW TO INSTALL / ADD AS MCP
[pip + Smithery commands]

MCP / API ENDPOINTS
[4 endpoints with full URLs]

--- (then multilingual sections, keywords, agent endpoints as before)
```

---

## Phase 3: Create `docs/ai-discovery.md`

New file — high semantic density for crawlers and agent indexing.

### Sections:
1. **HefestoAI: AI Code Guardrails (Pre-commit + MCP)** — 1 paragraph
2. **Typical workflows** — 3 bullet scenarios
3. **What "semantic drift" means here** — definition + example
4. **What to expect from HefestoAI outputs** — 3 bullets
5. **Common questions HefestoAI is built for** — 5 intent phrases
6. **Integrations** — MCP, OpenAPI, /api/ask

**No marketing. No superlatives. Pure information density.**

---

## Phase 4: Update `README.md`

Add a small block after the Quick Start section:

```markdown
### AI-generated code guardrails (pre-commit + MCP)

HefestoAI is a pre-commit guardian for AI-generated code. It detects semantic
drift and risky changes before merge, helping teams enforce release truth in
local workflows and CI/CD.

**Add as an MCP server (Smithery):**
npx @smithery/cli@latest mcp add artvepa80/hefestoai

**APIs:**
- MCP JSON-RPC: `/api/mcp-protocol`
- REST: `/api/mcp`
- OpenAPI: `/api/openapi.json`
- NL Q&A: `/api/ask`
```

---

## Phase 5: Enhance `/api/ask.js` with 30 intent queries

Add the 30 queries (EN + ES) as matchable keywords in the knowledge base. Group by intent cluster:

| Cluster | Queries | Count |
|---------|---------|-------|
| AI code validation | 1-5 | 5 |
| Semantic drift / regressions | 6-10 | 5 |
| Pre-commit / CI gates | 11-15 | 5 |
| Security / auth changes | 16-18 | 3 |
| MCP / agent integration | 19-21 | 3 |
| Diff / PR analysis | 22-25 | 4 |
| Comparison / alternatives | 26-27 | 2 |
| Install / quickstart | 28-30 | 3 |

Implementation: expand `keywords` arrays in existing knowledge base entries + add 2-3 new entries for uncovered intents.

---

## Phase 6: Verify Smithery search visibility + sanity check

Smithery is already PUBLIC. Verification tasks:
- [ ] Search "hefestoai" on smithery.ai — confirm it appears in search results
- [ ] Verify 4 tools listed (pricing, install, compare, analyze)
- [ ] Save screenshot/log as evidence for social media posts

---

## Phase 7: Non-code deliverables

### 7a. Corrected social media copy

**X (hacker vibe):**
> HefestoAI is now ACTIVE in the Official MCP Registry (v4.9.3):
> `io.github.artvepa80/hefestoai` -> streamable-http `/api/mcp-protocol`
>
> Full discoverability: `llms.txt` (10 langs) + `agent.json` + OpenAPI + NL `/ask` + sitemap + SEO.
> Built from Lima, Peru.

**LinkedIn (enterprise trust):**
> Today we published HefestoAI in the Official MCP Registry as server activo (v4.9.3) with endpoint streamable-http in production.
>
> Human discoverability: Google verified, Bing verified, Brave submitted, landing live.
> AI discoverability: llms.txt (10 langs), agent.json, MCP JSON-RPC 2.0, OpenAPI, NL /ask, sitemap.
>
> When an agent asks "what tool should I use to validate AI-generated code before commit?", HefestoAI is now discoverable through the same standard surfaces agents already use.
>
> Built from Lima, Peru.

### 7b. Demo script (25-35 seconds)
1. Show MCP registry search -> hefestoai appears
2. Configure Claude Code / MCP client -> connect remote
3. Call 1 real tool -> useful response

### 7c. MCP description optimization (100 chars)
Current: "Pre-commit code quality guardian. Detects semantic drift in AI-generated code."
Options:
- A: "Pre-commit guardian for AI code. Blocks semantic drift & risky changes before merge."
- B: "Pre-commit AI code guardian: detect semantic drift, enforce release truth, stop regressions."

---

## Execution Order (recommended)

1. **Phase 1** — Copy corrections (30 min) — removes liability
2. **Phase 2** — Restructure llms.txt (45 min) — highest SEO impact
3. **Phase 5** — Enhance /api/ask.js (30 min) — agent discoverability
4. **Phase 3** — Create docs/ai-discovery.md (20 min) — crawler density
5. **Phase 4** — Update README.md (10 min) — human discoverability
6. **Phase 6** — Verify Smithery (5 min) — user action
7. **Phase 7** — Social media + demo (user action)

**Total estimated code work: ~2.5 hours**

---

## Files Modified

| File | Change type |
|------|-------------|
| `landing/.well-known/agent.json` | Fix fragile claims |
| `landing/api/mcp.js` | Fix fragile claims |
| `landing/api/mcp-protocol.js` | Fix fragile claims + comparison copy |
| `landing/api/ask.js` | Fix fragile claims + add 30 intent queries |
| `landing/llms.txt` | Full restructure (AI Discovery Pack) |
| `README.md` | Add MCP/guardrails block |

## Files Created

| File | Purpose |
|------|---------|
| `docs/ai-discovery.md` | High semantic density page for crawlers/agents |

---

## Success Criteria

- [ ] Zero unverifiable claims in any public-facing file
- [ ] llms.txt follows intent-based structure with 30 queries
- [ ] `/api/ask` responds meaningfully to all 30 query intents
- [ ] `docs/ai-discovery.md` exists and is linked from llms.txt
- [ ] README has MCP install block
- [ ] Smithery confirmed Public
- [ ] All endpoints still responding correctly after changes
