# Technical Debt Registry

> Last updated: 2026-03-10

---

## TD-001: Bot Analytics Middleware inactive

- **Impact:** Low
- **Effort:** Medium
- **Added:** 2026-02-23
- **Status:** Open

`landing/middleware.js` exists with bot detection logic (GPTBot, ClaudeBot, PerplexityBot, etc.) but `@vercel/static` builds do not support Vercel Edge Middleware. The file is served as a static asset, not executed.

**Why it exists:** Landing page was built as plain HTML/CSS/JS, not a framework project. Middleware requires Next.js or another Vercel-supported framework.

**Fix:** Convert landing page to a Next.js project or use Vercel Serverless Functions as an alternative for bot logging.

---

## TD-004: Flaky test isolation (TestSimulatedProScopeGating)

- **Impact:** Low
- **Effort:** Low
- **Added:** 2026-02-23
- **Status:** Open — tracked in GitHub issue #14
- **Workaround:** `setup_method` reload in `TestApiHardeningWiring`

`TestSimulatedProScopeGating` injects fake `hefesto_pro` modules via `monkeypatch.setitem(sys.modules, ...)` and reloads `pro_optional`. The `_cleanup_pro_optional` fixture reloads `pro_optional` while monkeypatch fakes are still active, leaving `HAS_API_HARDENING = True` after teardown.

**Why it exists:** monkeypatch cleanup ordering — `pro_optional` reload happens before monkeypatch restores `sys.modules`.

**Fix:** Add proper teardown to `TestSimulatedProScopeGating` that reloads `pro_optional` AFTER monkeypatch restores `sys.modules`. Current workaround: each test in `TestApiHardeningWiring` reloads `pro_optional` in `setup_method`.

---

## TD-007: Content generator semantic dedup gap

- **Impact:** Low
- **Effort:** Medium
- **Added:** 2026-03-10
- **Status:** Open

SequenceMatcher catches text-similar duplicates but not same-topic-different-words posts (e.g., 3 posts about mutable default arguments). Need topic-level dedup, not just text similarity.

**Why it exists:** Initial dedup was built for exact/near-exact match detection. Semantic similarity requires embeddings or topic extraction, which was deferred.

**Fix:** Add topic-level dedup using either keyword extraction (TF-IDF) or lightweight embeddings to detect when recent posts cover the same concept despite different wording.

---

## Priority Order

1. **TD-004** — test reliability, workaround exists
2. **TD-007** — content quality, prevents topic repetition
3. **TD-001** — cosmetic, no revenue impact
