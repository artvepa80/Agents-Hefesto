# Hefesto - AI-Powered Code Quality Guardian

[![PyPI version](https://badge.fury.io/py/hefesto-ai.svg)](https://pypi.org/project/hefesto-ai/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Languages](https://img.shields.io/badge/languages-7-green.svg)](https://github.com/artvepa80/Agents-Hefesto)

**Multi-language AI code analysis for Python, TypeScript, JavaScript, Java, Go, Rust, and C#.**

Hefesto validates your code before production using AI-powered static analysis and ML enhancement. It caught 3 critical bugs in its own v4.0.1 release through self-validation.

---

## What is Hefesto?

Hefesto analyzes code using AI and catches issues that traditional linters miss:

| Feature | Description |
|---------|-------------|
| **7 Languages** | Python, TypeScript, JavaScript, Java, Go, Rust, C# |
| **AI Analysis** | Google Gemini for semantic code understanding |
| **Security Scanning** | SQL injection, hardcoded secrets, command injection |
| **Code Smells** | Long functions, deep nesting, high complexity |
| **Pre-Push Hooks** | Automatic validation before every commit |
| **REST API** | 8 endpoints for CI/CD integration |

---

## Quick Start

```bash
# Install
pip install hefesto-ai

# Analyze code
hefesto analyze .

# Filter by severity
hefesto analyze . --severity HIGH

# Check license status
hefesto status
```

### Example Output

```
HEFESTO CODE ANALYSIS
========================

Summary:
   Files analyzed: 8
   Issues found: 51
   Critical: 0
   High: 32
   Medium: 19

HIGH Issues (32):

  server/routes/api.ts:235:60
  - Issue: Cyclomatic complexity too high (13, threshold=10)
  - Function: handleRequest
  - Type: HIGH_COMPLEXITY
  - Suggestion: Refactor to reduce complexity. Consider:
    - Extracting nested conditions
    - Using early returns
    - Breaking into smaller functions

  server/routes/api.ts:121
  - Issue: Potential SQL injection via string concatenation
  - Type: SQL_INJECTION_RISK
  - Suggestion: Use parameterized queries with placeholders
```

---

## Language Support

| Language | Parser | Status |
|----------|--------|--------|
| Python | Native AST | Full support |
| TypeScript | TreeSitter | Full support |
| JavaScript | TreeSitter | Full support |
| Java | TreeSitter | Full support |
| Go | TreeSitter | Full support |
| Rust | TreeSitter | Full support |
| C# | TreeSitter | Full support |

### TypeScript/JavaScript Analysis (v4.3.3)

- **Arrow function naming**: Infers names from `const foo = () => {}`
- **Accurate parameter counting**: Uses AST formal_parameters, not comma counting
- **Method detection**: Handles Express routes, callbacks, class methods
- **Threshold visibility**: Shows `(13 lines, threshold=10)` in all messages

---

## Features by Tier

| Feature | FREE | PRO ($8/mo) | OMEGA ($19/mo) |
|---------|------|-------------|----------------|
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

### Get PRO or OMEGA

- **PRO**: [Start Free Trial](https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b) - $8/month
- **OMEGA**: [Start Free Trial](https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c) - $19/month

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
hefesto analyze . --format json

# Check status
hefesto status

# Install git hook
hefesto install-hook

# Start API server (PRO)
hefesto serve --port 8000
```

---

## Pre-Push Hook

Automatic validation before every git push:

```bash
# Install hook
hefesto install-hook

# Now every push validates automatically
git push

# Output:
# HEFESTO Pre-Push Validation
# ================================
# 1. Running linters...
#    - Black formatting... OK
#    - Import sorting... OK
#    - Flake8 linting... OK
# 2. Running unit tests...
#    - Unit tests... OK
# 3. Hefesto code analysis...
#    - Analyzing changed files...
# ================================
# All validations passed!
# Pushing to remote...
```

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
# Start server
hefesto serve --port 8000

# Analyze code
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "def test(): pass", "severity": "MEDIUM"}'
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Analyze code |
| `/health` | GET | Health check |
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
export HEFESTO_LICENSE_KEY="your-key"
export HEFESTO_SEVERITY="MEDIUM"
export HEFESTO_OUTPUT="json"
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

## License

MIT License for core functionality. PRO and OMEGA features are licensed separately.

---

**Hefesto: AI-powered code quality that caught 3 critical bugs in its own release.**

© 2025 Narapa LLC, Miami, Florida
