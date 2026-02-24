# MEMORY - HefestoAI Project Status

> Last updated: 2026-02-24

---

## Current Version: 4.9.3

| Location | Version | Branch | HEAD |
|----------|---------|--------|------|
| Mac | 4.9.3 | main | `a8343f8` |
| GitHub main | 4.9.3 | main | `a8343f8` |
| VM | 4.9.3 | main | `a8343f8` |
| PyPI | 4.9.3 | — | BLOCKED (email verification pending) |

---

## Session 2026-02-24 (Monday) — late night

### AI Discoverability Stack → Pro-Private (IP Protection)

**CRITICAL: All AI discoverability infrastructure is proprietary IP. Work ONLY in Pro-Private.**

Migrated full landing page + AI crawlers/bots/agents stack from `Agents-Hefesto/landing/` (public OSS) to `Agents-Hefesto-Pro-Private/landing-page/` (private).

| File | Purpose |
|------|---------|
| `index.html` | Dark/orange landing (v4.9.3, Stripe Buy Buttons, i18n EN/ES/JA/KO) |
| `api/ask.js` | Natural language Q&A (11 topics) |
| `api/mcp.js` | MCP capability discovery |
| `api/mcp-protocol.js` | JSON-RPC 2.0 MCP server (4 tools) |
| `api/openapi.json.js` | OpenAPI 3.0 spec |
| `api/changelog.json.js` | Product changelog |
| `api/faq.json.js` | 13 FAQ entries |
| `.well-known/agent.json` | A2A agent descriptor |
| `llms.txt` | 10 languages, 30 intent queries |
| `robots.txt` | AI crawler allow rules |
| `sitemap.xml` | 3 URLs |
| `middleware.js` | Bot detection (17 patterns) |
| `vercel.json` | Headers, CORS, redirects, security |

**Vercel**: Reconnected to `Agents-Hefesto-Pro-Private`, Root Directory = `landing-page`. All 11 endpoints verified 200 at `hefestoai.narapallc.com`.

**Public repo cleanup**: Deleted `landing/` directory from `Agents-Hefesto` (OSS). No AI discoverability files in public repo.

**Commits (Pro-Private):**
| Commit | What |
|--------|------|
| `e01360e` | feat: add full AI discoverability stack (12 files) |
| `ec98b54` | feat: update index.html to v4.9.3 |
| `541c628` | fix: trigger redeploy with correct root directory |

---

## Session 2026-02-24 (Monday) — continued (evening)

### Patch C + EPICs 1-3 Golden Validation & EPIC 2 Runtime Fix

**Golden validation on VM** (with PRO installed, Python 3.11.2):

| Feature | Result | Evidence |
|---------|--------|----------|
| **Patch C** (serve hardening) | 6/6 PASS | `/analyze` returns JSON, CORS/auth/rate-limit active |
| **EPIC 1** (scope gating) | 4/4 PASS | `--scope-deny third_party_lib` → `files_analyzed: 1`, `meta.scope` in JSON |
| **EPIC 3** (enrichment) | 2/2 PASS | `--enrich local` → `metadata.enrichment.status="skipped"`, `error.code="local_only"` |
| **EPIC 2** (JS/TS parsing) | PASS after fix | `files_analyzed: 2`, `file_meta.symbols` with imports/functions/classes |

**Bugs found & fixed during golden validation:**
- **PR #16**: `server.py:94` used `i.title` but `AnalysisIssue` has `i.message` → fixed, merged
- **PR #17**: `cli/main.py:890` passed `extra_allow`/`extra_deny` but PRO expects `allow_patterns`/`deny_patterns` → fixed, merged

**STOP 8 — EPIC 2 runtime backend (PR #18, merged):**
- **Root cause**: `tree-sitter-languages 1.10.2` incompatible with modern `tree-sitter` API. `TreeSitterParser.__init__()` crashed with `TypeError`, silently swallowed by broad `except Exception: return None` in `analyzer_engine.py:304`.
- **Fix**: Cascading import in `treesitter_parser.py`: `tree-sitter-language-pack` → `tree-sitter-languages` → manual build
- Added `[multilang]` optional dependency in `pyproject.toml`
- Added `logger.debug()` to parse failures (was completely silent)
- Updated `requirements.txt` to replace pinned broken deps
- Documented `[multilang]` extra in README + `docs/PRO_OPTIONAL_FEATURES.md`
- **Evidence**: `EPIC2_SYMBOLS_OK` — JS file in JSON with `file_meta.symbols` (imports, functions, classes)

**Issue #14 — test isolation leak (root-cause fix, commit `37a18ea`):**
- **Root cause**: `_cleanup_pro_optional()` reloaded `hefesto.pro_optional` while `monkeypatch` still had fake PRO modules in `sys.modules`. Reload picked up fakes → `HAS_*=True` leaked into `test_enrichment_off_by_default` → CLI produced empty output → `JSONDecodeError`.
- **Fix**: Use `monkeypatch.delitem(sys.modules, key)` to remove `hefesto_pro.*` entries before reloading.
- `a8343f8`: Black formatting applied → CI green on all 3 Python versions (3.10, 3.11, 3.12).
- 21/21 tests pass in full suite (no more skip workaround).

**CI note**: Click 8.3.1 (resolved in CI) removed `mix_stderr` parameter from `CliRunner` (removed in Click 8.2.0). Use `result.output` (already stdout-only in Click 8.2+).

**Commits on main (this session):**

| Commit | PR | What |
|--------|-----|------|
| `c852617` | #15 | docs: PRO_OPTIONAL_FEATURES.md + README snippet |
| `d1aff84` | #16 | fix: server.py `i.title` → `i.message` |
| `c1f1b07` | #17 | fix: scope gating kwargs `allow_patterns`/`deny_patterns` |
| `0824e59` | #18 | fix: tree-sitter-language-pack migration |
| `8b81a8d` | — | docs: `[multilang]` extra in README + PRO docs |
| `3330e0f` | — | fix: logger after imports (E402) |
| `37a18ea` | — | fix: root-cause test isolation leak (#14) |
| `a8343f8` | — | style: Black formatting |

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
- **Issue #14 opened**: flaky test isolation (bug, low priority) — **FIXED** in evening session (`37a18ea`)

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
| Golden Validation | Patch C + EPIC 1-3 evidence on VM | PRs #15-#17 (OSS) | `c852617`..`c1f1b07` |
| **STOP 8** | **EPIC 2 runtime (tree-sitter-language-pack)** | **PR #18 (OSS)** | `0824e59` |
| Issue #14 fix | Test isolation leak root-cause | direct to main | `37a18ea` |

### STOP 7 deliverables (OSS repo)
- `hefesto/pro_optional.py` (NEW) — optional import bridge with ModuleNotFoundError fallbacks
- `hefesto/cli/main.py` (MOD) — 10 Click flags (scope + enrichment), config builders
- `hefesto/core/analyzer_engine.py` (MOD) — scope gating, multilang, enrichment, `_build_meta()`
- `hefesto/core/analysis_models.py` (MOD) — `meta` on Report, `metadata` on FileResult
- `tests/test_pro_wiring.py` (NEW) — 21 tests (fallbacks, CLI flags, monkeypatched PRO, accumulation, enrichment, hardening)

---

## Next STOPs (pending, choose one)

1. **STOP 9 — Tooling guardrails**
   - `make lint` / `make fmt` / `make test` or scripts
   - Optional pre-push hook

2. **STOP 10 — Enrichment with real provider**
   - Golden test with a configured enrichment provider (not just `status="skipped"`)

3. **STOP 11 — PyPI publish**
   - BLOCKED on email verification for OmegaAI account
   - Once unblocked: re-push tag v4.9.3 or bump to v4.9.4

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
| EPIC 1 — Scope Gating | Done (STOP 7) | Done (PR #15 PRO) | **CLOSED** — golden evidence on VM |
| EPIC 2 — Multi-Language | Done (STOP 7 + PR #18) | Done (PR #16 PRO) | **CLOSED** — `EPIC2_SYMBOLS_OK` on VM |
| EPIC 3 — Enrichment | Done (STOP 7) | Done (PR #17 PRO) | **CLOSED** — golden evidence on VM |
| Patch C — API Hardening | Done (STOP 7) | Done (PR #14 PRO) | **CLOSED** — 6/6 golden on VM |

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
| **Landing Page** | Live | `hefestoai.narapallc.com` via Vercel → **Pro-Private** repo (`landing-page/`). IP protected. |
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
