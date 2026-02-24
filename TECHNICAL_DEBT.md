# Technical Debt Registry

> Last updated: 2026-02-23

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

## TD-002: License validator is format-only

- **Impact:** High
- **Effort:** Medium
- **Added:** 2026-02-23
- **Status:** Open
- **Blocked by:** TD-003

`hefesto_pro/licensing/license_validator.py` validates the `HFST-XXXX-XXXX-XXXX-XXXX-XXXX` format but performs NO database lookup. Any string matching the format is treated as a valid PRO license. Two hardcoded OMEGA keys exist in a set for internal use.

Line 64-66 of `license_validator.py`:
```python
# TODO: Validate with backend API when available
# For now, if format is valid, assume professional
return "professional"
```

**Why it exists:** Built before any backend infrastructure was ready. Designed to be replaced by DB-backed validation once GCP billing is active.

**Fix:** Add Datastore lookup in `get_tier_for_key()` — query license collection by key hash, check expiry and tier. Requires TD-003 resolved first.

---

## TD-003: GCP billing suspended

- **Impact:** High
- **Effort:** Low (~1 hour)
- **Added:** 2026-02-23
- **Status:** Open — requires manual action
- **Blocks:** TD-002, TD-005, TD-006

Billing account `NarapaLLC` (01D045-1C8487-713A3A) has `"open": false`. All paid GCP APIs return `BILLING_DISABLED`: Secret Manager, Datastore, Cloud Run, Cloud Functions.

Project `bustling-wharf-478016-p9` shows `billingEnabled: true` but the underlying billing account is closed/suspended.

**Why it exists:** Likely expired payment method or unpaid balance.

**Fix:** Go to https://console.cloud.google.com/billing/01D045-1C8487-713A3A — update payment method or pay outstanding balance.

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

## TD-005: Licensing fulfillment is 100% manual

- **Impact:** High
- **Effort:** Medium
- **Added:** 2026-02-23
- **Status:** Open
- **Blocked by:** TD-003

`scripts/fulfill_order.py` is a CLI script that generates a license key, creates an S3 presigned URL, and outputs an email template. There is no Stripe webhook handler — no automated flow from payment to key delivery.

Current flow: Stripe payment → Arturo manually runs `fulfill_order.py` → manually sends email.

**Why it exists:** Built as MVP before any customers existed. Webhook automation was deferred.

**Fix:** Create Stripe webhook endpoint (Vercel Serverless Function or Cloud Run), listen for `checkout.session.completed`, auto-generate key, store in Datastore, send email via Gmail API. Requires TD-003 and TD-006 resolved first.

---

## TD-006: Gmail API not configured

- **Impact:** Medium
- **Effort:** Low (~30 min)
- **Added:** 2026-02-23
- **Status:** Open
- **Blocked by:** TD-003

No Gmail API credentials exist. API is not enabled in GCP. No code exists for sending license delivery emails programmatically.

**Why it exists:** Email is sent manually today. Gmail API setup was deferred until the full licensing automation pipeline was needed.

**Fix:** Enable Gmail API in GCP console, create OAuth credentials for `sales@narapallc.com`, store refresh token in Secret Manager. Requires GCP billing (TD-003) to be active first.

---

## Dependency Graph

```
TD-003 (GCP billing)
  ├── TD-002 (license DB lookup)
  ├── TD-005 (automated fulfillment)
  │     └── TD-006 (Gmail API)
  └── TD-006 (Gmail API)

TD-004 (test isolation) — independent
TD-001 (bot middleware) — independent
```

## Priority Order

1. **TD-003** — unblocks everything, ~1 hour manual action
2. **TD-002** — security gap, revenue risk
3. **TD-005** — blocks scale
4. **TD-006** — needed by TD-005
5. **TD-004** — low priority, workaround exists
6. **TD-001** — cosmetic, no revenue impact
