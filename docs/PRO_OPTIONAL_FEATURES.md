# PRO Optional Features (Hefesto PRO Add-On)

Hefesto OSS runs **fully without** Hefesto PRO installed. When PRO is present, OSS can
optionally activate additional capabilities via a guarded import bridge (`hefesto/pro_optional.py`).
If PRO is not installed, all PRO hooks degrade to **no-op** behavior (no crashes).

This document describes:
- Patch C: API Hardening for `hefesto serve`
- EPIC 1: Scope Gating (first-party vs third-party/generated/fixtures)
- EPIC 2: Multi-Language Discovery (TS/JS symbol extraction + skip reporting)
- EPIC 3: Safe Deterministic Enrichment (schema-first, bounded, timeout + cache)

---

## How OSS connects to PRO

OSS uses a single bridge module:

- `hefesto/pro_optional.py`

This module attempts guarded imports (PRO installed) and exposes feature booleans:
- `HAS_API_HARDENING`
- `HAS_SCOPE_GATING`
- `HAS_MULTILANG`
- `HAS_ENRICHMENT`

When PRO is missing, the bridge returns safe fallbacks (no middleware, no filtering, no enrichment).

---

## Patch C — API Hardening (FastAPI server)

Patch C applies to the OSS **server** path (`hefesto serve`), not the static analysis core.
OSS creates a vanilla FastAPI app and then (optionally) applies hardening:

```python
app = create_app()
apply_hardening(app, settings=HardeningSettings(...))  # only when PRO is available
```

### What Patch C enforces (when enabled via env/config)
- **CORS** allowlist from env (no wildcard with credentials)
- **Docs/OpenAPI toggle** off by default unless explicitly enabled
- **Optional API key auth** (`X-API-Key`) when configured
- **Rate limiting** (token bucket, in-memory)
- **Workspace sandbox** path enforcement (analysis inputs must stay under a workspace root)
- **Bounded cache** (TTL + size cap)

### Patch C environment variables

All Patch C env vars are prefixed with `HEFESTO_`.

| Variable | Default | Description |
|----------|---------|-------------|
| `HEFESTO_EXPOSE_DOCS` | `0` (disabled) | Set `1` to enable docs + OpenAPI |
| `HEFESTO_CORS_ORIGINS` | localhost only | Comma-separated allowed origins |
| `HEFESTO_API_KEY` | unset (no auth) | If set, non-health endpoints require `X-API-Key` header |
| `HEFESTO_RATE_LIMIT_PER_MINUTE` | `60` | Set `0` to disable |
| `HEFESTO_WORKSPACE_ROOT` | autodetect | Root directory for file path arguments |
| `HEFESTO_CACHE_TTL_SECONDS` | `300` | Cache entry time-to-live |
| `HEFESTO_CACHE_MAX_SIZE` | `1000` | Maximum cache entries |
| `HEFESTO_BIND_HOST` | `127.0.0.1` | Default bind address (loopback) |

### Example: local hardened server

```bash
export HEFESTO_EXPOSE_DOCS=0
export HEFESTO_API_KEY="replace-with-strong-key"
export HEFESTO_RATE_LIMIT_PER_MINUTE=60
export HEFESTO_CORS_ORIGINS="https://app.example.com"
export HEFESTO_WORKSPACE_ROOT="/workspace"

hefesto serve --port 8000
```

---

## EPIC 1 — Scope Gating (analysis input filtering)

Scope gating prevents analysis from spending time on:
- vendored deps (`node_modules/`, `vendor/`, `site-packages/`, etc.)
- build output (`dist/`, `build/`, `coverage/`, etc.)
- fixtures/test data (snapshots, testdata)

### Defaults (when PRO is installed)
- FIRST_PARTY only is included by default.
- THIRD_PARTY / GENERATED / FIXTURE are skipped unless explicitly enabled.

### CLI flags (analyze)
- `--include-third-party`
- `--include-generated`
- `--include-fixtures`
- `--scope-allow <pattern>` (repeatable)
- `--scope-deny <pattern>` (repeatable)

### Output
When scope gating skips files, OSS reports a deterministic summary in `report.meta.scope`
(only present when non-empty).

---

## EPIC 2 — Multi-Language Discovery (TS/JS metadata)

When enabled via PRO, OSS can attach lightweight TS/JS symbol metadata to file results
(without changing core parsing):
- Imports, functions, classes, exports (bounded, deterministic)
- Skip reason reporting (e.g. `binary`, `too_large`, `decode_error`, `unsupported_language`)

### Runtime requirement

TS/JS parsing requires a pre-built grammar pack. Install with the `multilang` extra:

```bash
pip install "hefesto-ai[multilang]"
```

This pulls in `tree-sitter-language-pack` (165+ languages, pre-built wheels).
Without it, JS/TS files are found by `_find_files` but silently skipped at parse time.

### Output
- Per file: `file_result.file_meta.symbols = { imports, functions, classes, exports }`
- Report meta: `report.meta.multilang.skipped = { ... }` (only when non-empty)

---

## EPIC 3 — Safe Deterministic Enrichment (schema-first)

Enrichment is metadata-only and must never affect gating decisions or determinism.

### Guarantees
- Always returns a valid schema (`status=ok|skipped|error`)
- Bounded structured output (depth/keys/string limits)
- Central masking via MaskRegistry on input + output
- Timeouts enforced per provider
- Cache (TTL + size cap)
- If PRO missing or providers filtered out: `status="skipped"`

### CLI flags (analyze)
- `--enrich off|local|remote` (default: `off`)
- `--enrich-provider <name>` (repeatable allowlist)
- `--enrich-timeout <seconds>` (default: `30`)
- `--enrich-cache-ttl <seconds>` (default: `300`)
- `--enrich-cache-max <entries>` (default: `500`)

### Output
Enrichment attaches to each finding:
- `issue.metadata["enrichment"] = { ...schema dict... }`

---

## Security note

- OSS should never import PRO modules directly outside the guarded bridge.
- PRO features must remain optional: no breaking changes when PRO is absent.
- LLM enrichment is never used for gating decisions.

---

## Evidence Appendix (file:line pointers)

| Component | File | Line(s) | What |
|-----------|------|---------|------|
| **serve command** | `hefesto/cli/main.py` | 100 | `def serve(host, port, reload)` — CLI entry point |
| **PRO gate check** | `hefesto/cli/main.py` | 109-116 | `HAS_API_HARDENING` check, exit(1) if missing |
| **create_app()** | `hefesto/server.py` | 44 | Vanilla FastAPI factory (no middleware) |
| **apply_hardening call** | `hefesto/cli/main.py` | 131-132 | `app = create_app(); apply_hardening(app, settings=settings)` |
| **HardeningSettings import** | `hefesto/cli/main.py` | 125 | `from hefesto.pro_optional import HardeningSettings, apply_hardening` |
| **Hardening bridge** | `hefesto/pro_optional.py` | 81-94 | Guarded import of `hefesto_pro.api_hardening` with no-op fallback |
| **Scope gating bridge** | `hefesto/pro_optional.py` | 15-40 | EPIC 1: `filter_paths`, `ScopeGatingConfig` with no-op fallback |
| **Multi-lang bridge** | `hefesto/pro_optional.py` | 47-55 | EPIC 2: `TsJsParser`, `SkipReport` with `None` fallback |
| **Enrichment bridge** | `hefesto/pro_optional.py` | 62-74 | EPIC 3: `EnrichmentOrchestrator`, `EnrichmentConfig` with `None` fallback |
| **Server docstring** | `hefesto/server.py` | 8-9 | "Hardening is applied externally by `hefesto_pro.api_hardening.apply_hardening`" |
| **Wiring tests** | `tests/test_pro_wiring.py` | all | 21 tests, 100% coverage on `pro_optional.py` |
