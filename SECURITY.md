# Security Policy

## Supported Versions
| Version | Supported          |
|---------|--------------------|
| 4.x.x   | ✅ Full support    |
| <4.0    | ❌ Not supported   |

## Reporting a Vulnerability
If you discover a vulnerability or security issue, please contact us at:
- **support@narapallc.com**
- **contact@narapallc.com**

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to acknowledge reports within **48 hours** and ship a fix within **5 business days** whenever feasible.

## Scope
Hefesto focuses on scanning source code for semantic and logical inconsistencies. Please avoid reporting issues out of scope (e.g., unrelated third-party dependencies or infrastructure not maintained by this project).

## Sensitive Information

This repository is **open source**. Sensitive information (credentials, internal documentation, proprietary scripts, business data) is kept in a **private repository**.

## What's Public vs Private

### ✅ Public (this repository)
- Hefesto open-source code (MIT License)
- Public documentation
- Example configurations
- Test suite

### 🔒 Private (submodule)
- License key generation logic
- Order fulfillment automation
- AWS/GCP credentials and configs
- Internal business documentation
- Production deployment scripts

## Never Commit

The following should **NEVER** be committed to this repository:

- ❌ API keys or tokens (Stripe, AWS, GCP, etc.)
- ❌ `.env` files with real values
- ❌ Customer data or PII
- ❌ Internal business metrics
- ❌ Service account JSON files
- ❌ Private keys (`.pem`, `.key`)

## .gitignore Protection

Our `.gitignore` includes patterns to prevent accidental commits:

```gitignore
.env
*secret*
*credentials*
*api_key*
*.pem
*.key
*service-account*.json
gcp-*.json
```

## Access Control

### Public Repository
- Open to all
- MIT License
- Community contributions welcome

### Private Repository
- Restricted to Narapa LLC team members
- Requires GitHub authentication
- Contains proprietary code

## Security Features in Hefesto

Hefesto helps you avoid security issues in your code:

- **Hardcoded Secret Detection** - Finds API keys, passwords, tokens in code
- **SQL Injection Detection** - Identifies unsafe query construction
- **eval() Usage Warnings** - Flags dangerous dynamic code execution
- **Pickle Warnings** - Alerts on unsafe deserialization

Run Hefesto on your code:
```bash
hefesto analyze --min-severity CRITICAL
```

## API Hardening (v4.7.0)

The `hefesto serve` API server is **secure by default** with layered protections:

### Authentication
- **API Key** via `X-API-Key` header (set `HEFESTO_API_KEY` to enable)
- Health and ping endpoints are always accessible without auth

### Network Security
- **Host binding** defaults to `127.0.0.1` (loopback only, not `0.0.0.0`)
- **CORS** restricted to `localhost` origins by default
- Blocks dangerous `*` + `allow_credentials=True` CORS configuration

### Rate Limiting
- Sliding-window rate limiter per client (API key or IP)
- Set `HEFESTO_API_RATE_LIMIT_PER_MINUTE` to enable

### Path Sandbox
- All file paths resolved and validated against `HEFESTO_WORKSPACE_ROOT`
- Prevents directory traversal attacks via `resolve_under_root()`

### Cache Guardrails
- Bounded in-memory cache with TTL and LRU eviction
- Prevents DoS via unbounded memory growth

### API Documentation
- `/docs`, `/redoc`, `/openapi.json` disabled by default
- Set `HEFESTO_EXPOSE_DOCS=true` to enable in development

## Security Updates

We release security patches as soon as possible after discovering vulnerabilities.

**Stay updated:**
```bash
pip install --upgrade hefesto-ai
```

## Responsible Disclosure

We follow responsible disclosure practices:

1. Report received → Acknowledged within 48h
2. Issue validated → Fix developed
3. Patch released → Security advisory published
4. Credit given to reporter (unless anonymous requested)

## Contact

- **Security & Support:** support@narapallc.com
- **General inquiries:** contact@narapallc.com

---

**Copyright © 2025 Narapa LLC, Miami, Florida**
