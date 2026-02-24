# MEMORY - HefestoAI Project Status

> Last updated: 2026-02-24

---

## Current Version: 4.9.3

| Location | Version | Branch | HEAD |
|----------|---------|--------|------|
| Mac | 4.9.3 | main | `24d66b4` |
| GitHub main | 4.9.3 | main | `24d66b4` |
| PyPI | 4.9.3 | — | BLOCKED (email verification pending) |

---

## Session 2026-02-24 (Monday)

### AI Discovery Pack Sprint
- **Phase 1 — Copy corrections**: Removed "zero false positives", absolute comparatives, unverifiable claims from `agent.json`, `mcp.js`, `mcp-protocol.js`, `ask.js`, `llms.txt`
- **Phase 2 — llms.txt restructure**: AI Discovery Pack format with Primary Intent, Verifiable Facts, 30 intent queries (EN+ES), CTA, endpoints. Kept all multilingual sections.
- **Phase 3 — docs/ai-discovery.md**: New high semantic density page for crawlers/agents (workflows, semantic drift definition, integrations)
- **Phase 4 — README.md**: Added MCP/guardrails block with Smithery install command and endpoint table
- **Phase 5 — /api/ask.js enhanced**: 10 knowledge topics (was 7), added governance, mcp_integration, diff_analysis. Expanded keywords across all entries.
- **Plan docs created**: `DISCOVERABILITY_PLAN.md` (execution plan), `PROMPT_DISCOVERABILITY.md` (reusable Socratic prompt)
- **Security**: Added `.mcpregistry_*` to `.gitignore` (credential tokens from MCP Registry login)
- **Commit**: `7562512`, pushed to main
- **Bugfix**: Removed overly broad "how to" keyword from install entry in ask.js (was stealing MCP queries). Commit `abd6976`.
- **Vercel deploy**: Deployed to correct project (`vercel`, not `hefesto-landing`). All endpoints verified live.
- **Social media copy**: Corrected posts ready (X hacker, X founder, LinkedIn enterprise). No fragile claims.
- **STATUS: COMPLETE** — all 7 phases done, endpoints live, CI green.

### @artvepa Cron Pipeline + Engagement Monitor — VERIFIED & CLOSED
Dry-run confirmed all components operational on VM:
- **post_x.py**: `--account artvepa` reads `X_ARTVEPA_*` env vars (7 credentials confirmed)
- **cron_publisher.py**: `x_artvepa` platform routes to `post_x.py --account artvepa`
- **content_generator.py**: `--platform-filter artvepa` generates only artvepa posts. Rate limit 8/day.
- **trend_feeds.json**: 3 artvepa feeds (`artvepa_buildinpublic`, `artvepa_geopolitics`, `artvepa_bridge`)
- **cron_artvepa.sh**: Full pipeline (trend scan → content gen → WhatsApp notification). Cron: `0 15 * * 1,3,4,6,0`
- **x_engagement_monitor_artvepa.py**: Search + voice card + staging + WhatsApp approval. Cron: `0 */2 * * *` + reply check `*/30 * * * *`
- **voice_artvepa.md**: Voice card loaded by engagement monitor
- **Dry-run results**: Engagement search found candidates, WhatsApp notification sent (message ID confirmed), content generator hit daily rate limit (8/8 = pipeline already active today)
- **BLOCKER**: Anthropic API credits depleted — engagement replies fail to generate. User will recharge.
- **STATUS: COMPLETE** — pipeline operational, pending only Anthropic credits recharge.

### Key corrections applied (from ChatGPT advisory review)
1. "Zero false positives" → "Designed for low false positives" (all files)
2. "The only pre-commit tool" → "Pre-commit guardian built for AI coding era"
3. "100% local analysis" → "local-first workflow" (since remote endpoints exist)
4. Pricing in llms.txt → link to website (not hardcoded prices)
5. Removed "Codex" from primary compatible_with lists
6. Company info → minimal "Narapa LLC (website)" instead of biography

---

## Session 2026-02-23 (Monday) — continued

### HefestoAI Discoverability Sprint
- **llms.txt**: Multilingual product description (10 languages), competitor differentiation, agent swarm section
- **robots.txt**: Explicitly allows all AI crawlers (GPTBot, ClaudeBot, PerplexityBot, etc.)
- **.well-known/agent.json**: A2A/MCP agent metadata with endpoints, pricing, capabilities
- **middleware.js**: Bot detection for 17 User-Agents (NOTE: inactive with @vercel/static — TD-001)
- **sitemap.xml**: 3 URLs (landing, llms.txt, agent.json)
- **vercel.json**: Content-Type headers for all discoverability files, X-Robots-Tag: all
- **README.md**: Added LLM keywords block after badges

### Vercel Fix: All static files were serving index.html
- **Root cause**: `builds: [{ src: "index.html", use: "@vercel/static" }]` only deployed index.html
- **Fix**: Removed `builds` and `routes` sections — Vercel auto-serves all static files
- **Also fixed**: Vercel project Root Directory was `landing-page` (stale), corrected to `landing`
- All discoverability files now serving with correct Content-Type

### Analytics & SEO
- **Vercel Web Analytics**: Added `/_vercel/insights/script.js` to index.html
- **Vercel Speed Insights**: Added `/_vercel/speed-insights/script.js` to index.html
- **Microsoft Clarity**: Added tracking script (project `vm5io2kbxz`), confirmed receiving data
- **Bing Webmaster Tools**: Verified via meta tag `msvalidate.01`
- **Google Search Console**: Verified, sitemap indexed, serving correct XML
- **Brave Search**: URL submitted, crawling organically via robots.txt

### MCP & AI Agent Endpoints (live)
- **`/api/mcp`**: REST discoverability endpoint (GET capabilities, POST queries)
- **`/api/ask`**: Natural language Q&A endpoint (7 knowledge base topics, multilingual keywords)
- **`/api/openapi.json`**: OpenAPI 3.0 spec for LangChain/AutoGPT discovery
- **`/api/mcp-protocol`**: Real JSON-RPC 2.0 MCP handler (initialize, tools/list, tools/call with 4 tools: pricing, install, compare, analyze)

### MCP Registry Registrations
- **Official MCP Registry** (registry.modelcontextprotocol.io): `io.github.artvepa80/hefestoai` — status: active, published 2026-02-24T02:32:06Z
- **Smithery** (smithery.ai/servers/artvepa80/hefestoai): Published, MCP URL: `https://hefestoai--artvepa80.run.tools`

### Documentation
- **TECHNICAL_DEBT.md**: Created with 6 entries (TD-001 to TD-006), dependency graph, priority order

### Earlier in session
- **OSS api_hardening wiring**: `hefesto/server.py` (NEW FastAPI app), `pro_optional.py` (HAS_API_HARDENING + apply_hardening fallback), `cli/main.py` (serve command functional), `tests/test_pro_wiring.py` (+7 tests)
- **server.py delegates to CLI helpers**: `_setup_analyzer_engine` / `_run_analysis_loop` — no duplication
- **Version bump**: 4.9.2 → 4.9.3, CHANGELOG + README + pyproject.toml updated
- **Tag v4.9.3**: pushed, Release (PyPI) workflow green, CI green (3.10, 3.11, 3.12)
- **Fix flaky test**: `test_server_module_creates_app` failed in CI because `fastapi` not in base deps. Fixed with `pytest.mark.skipif`
- **PRO repo**: PR #33 merged, tag v3.9.0 pushed (Phase 2b: HERMES + @artvepa + landing page)
- **HERMES @artvepa pipeline**: fully operational on VM (content pipeline + engagement monitor + WhatsApp approval)
- **VM synced**: rebased to match origin/main at `a0bd79c`
- **Issue #14 opened**: flaky `TestSimulatedProScopeGating` test isolation (bug, low priority)

### PRO repo session
- CHANGELOG.md merge conflict resolved
- PR #33 merged (feat/phase2b-supply-chain-agents)
- Tag v3.9.0 created and pushed

---

## Completed STOPs (2026-02-19 session)

| STOP | Description | PR | Commit |
|------|-------------|-----|--------|
| Track A | CI Hardening | — | done |
| Track B | Marketplace Split | — | done |
| Patch C (C0-C2) | — | PR #14 (PRO) | merged |
| EPIC 1 | Scope Gating (PRO) | PR #15 (PRO) | merged |
| EPIC 2 | Multi-Language Discovery (PRO) | PR #16 (PRO) | merged |
| EPIC 3 | Safe Enrichment (PRO) | PR #17 (PRO) | merged |
| **STOP 7** | **OSS wiring for PRO EPICs** | **PR #13 (OSS)** | `25816c8` |
| Pinning | black==26.1.0, isort==6.1.0 | direct to main | `e926fd9` |

### STOP 7 deliverables (OSS repo)
- `hefesto/pro_optional.py` (NEW) — optional import bridge with ModuleNotFoundError fallbacks
- `hefesto/cli/main.py` (MOD) — 10 Click flags (scope + enrichment), config builders
- `hefesto/core/analyzer_engine.py` (MOD) — scope gating, multilang, enrichment, `_build_meta()`
- `hefesto/core/analysis_models.py` (MOD) — `meta` on Report, `metadata` on FileResult
- `tests/test_pro_wiring.py` (NEW) — 14 tests (fallbacks, CLI flags, monkeypatched PRO, accumulation)

---

## Next STOPs (pending, choose one)

1. **STOP 8 — Fix 7 pre-existing test failures**
   - Files: `test_patch_d_gate_and_eval.py` (4 fails), `test_patch_e_exclude_types.py` (3 fails)
   - Goal: CI green total (0 failures)

2. **STOP 8b — Tooling guardrails**
   - `make lint` / `make fmt` / `make test` or scripts
   - Optional pre-push hook

3. **STOP 9 — Patch C (API hardening)**
   - CORS/docs/auth/rate-limit/path sandbox/cache caps

---

## PRO Repo Status

- Repo: `artvepa80/Agents-Hefesto-Pro-Private`
- All 19 tasks finalized (C0.1-C0.2, C1.1-C1.4, C2.1-C2.4, E1.1-E1.3, E2.1-E2.2, E3.1-E3.3, I0.1)
- PRs #14-#17 all merged
- PR #33 merged (Phase 2b: HERMES + @artvepa + landing page)
- Tag v3.9.0 pushed (2026-02-23)

---

## EPIC Status (OSS + PRO combined)

| EPIC | OSS Wiring | PRO Implementation | Validation |
|------|-----------|-------------------|------------|
| EPIC 1 — Scope Gating | Done (STOP 7) | Done (PR #15) | Needs golden tests on real repos |
| EPIC 2 — Multi-Language | Done (STOP 7) | Done (PR #16) | Needs IRIS/AEGIS schema confirm |
| EPIC 3 — Enrichment | Done (STOP 7) | Done (PR #17) | Needs deterministic enforcement |

---

## GCP VM State

- Instance: `hefestoai` in `us-central1-a`, project `bustling-wharf-478016-p9`
- Swarm project stashed: `git stash list` shows `stash@{0}: vm-swarm-wip-2026-02-19`
- Local excludes in `.git/info/exclude` for swarm artifacts
- To restore Swarm: `git stash branch feat/swarm-wip`
- Recommended: use `git worktree` for future separation

---

## Tooling Pins (2026-02-19)

| Tool | Version | Config |
|------|---------|--------|
| black | ==26.1.0 | `required-version = "26.1.0"` in `[tool.black]` |
| isort | ==6.1.0 | `profile = "black"` in `[tool.isort]` |
| Python | >=3.10 | `requires-python = ">=3.10"` in `[project]` |

**Note:** Mac has Python 3.9.6 (out of contract). Use VM venv for formatting, or install Python 3.11+ locally.

---

## PyPI Release Status

**STATUS: BLOCKED — Needs user action**

- PyPI latest: v4.5.5 (versions 4.6.x–4.9.x never published)
- Release workflow runs but `twine upload` fails silently (`continue-on-error` masks it as green)
- PyPI account `OmegaAI` needs email verification
- Token valid in GitHub Secrets (`PYPI_API_TOKEN`) and GCP Secret Manager
- Steps to unblock: verify email at https://pypi.org/manage/account/, then re-push tag

---

## Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| **GCP VM** | Active | `hefestoai`, `us-central1-a`, project `bustling-wharf-478016-p9` |
| **GitHub OSS** | Active | `artvepa80/Agents-Hefesto` |
| **GitHub PRO** | Active | `artvepa80/Agents-Hefesto-Pro-Private` |
| **PyPI** | BLOCKED | v4.5.5 — email verification pending for OmegaAI account |
| **ClawHub Skill** | Published | `@artvepa80/hefestoai-auditor@1.2.0` (not a GitHub repo) |
| **Landing Page** | Live | `hefestoai.narapallc.com` via Vercel, DNS Squarespace |
| **HERMES @artvepa** | Live | VM cron: content pipeline + engagement monitor + WhatsApp approval |
| **MCP Registry** | Active | `io.github.artvepa80/hefestoai` on registry.modelcontextprotocol.io |
| **Smithery** | Active | `artvepa80/hefestoai` on smithery.ai |
| **Bing Webmaster** | Verified | `hefestoai.narapallc.com` |
| **Google Search Console** | Verified | Sitemap indexed |
| **Microsoft Clarity** | Active | Project `vm5io2kbxz` |
| **Vercel Analytics** | Active | Web Analytics + Speed Insights |

---

## Credentials Reference

- **GitHub PAT:** stored in `~/.claude.json` (artvepa80)
- **Stripe API:** stored in `~/.claude.json`
- **PyPI Token:** GitHub Secrets (`PYPI_API_TOKEN`) + GCP Secret Manager
- **PyPI Account:** `OmegaAI` (needs email verification)
- **VM SSH:** `gcloud compute ssh hefestoai --zone=us-central1-a`
