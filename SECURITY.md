# Security Policy

## Reporting Security Issues

If you discover a security vulnerability in Hefesto, please report it responsibly:

**Email:** security@narapallc.com

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

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

- **Security issues:** security@narapallc.com
- **General support:** support@narapallc.com
- **Sales & licensing:** sales@narapallc.com

---

**Copyright © 2025 Narapa LLC, Miami, Florida**
