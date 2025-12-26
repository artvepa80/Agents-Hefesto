# 🔥 Hefesto - AI-Powered Code Quality Guardian

[![PyPI version](https://badge.fury.io/py/hefesto-ai.svg)](https://badge.fury.io/py/hefesto-ai)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Multi-language AI code quality validation powered by Gemini that works seamlessly with AI coding assistants.**

Hefesto is the AI-powered code quality guardian that validates your Python, TypeScript, JavaScript, Java, Go, Rust, and C# code before it hits production. It caught 3 critical bugs in its own v4.0.1 release through self-validation (dogfooding). Now it's protecting codebases worldwide.

---

## 🎯 What is Hefesto?

Hefesto analyzes your code using AI and catches issues that traditional linters miss:

- **Multi-Language Support:** Python, TypeScript, JavaScript, Java, Go, Rust, C# (7 languages!)
- **AI-Powered Analysis:** Uses Google Gemini for semantic code understanding
- **ML Enhancement:** Detects code smells, duplications, and anti-patterns
- **Security Scanning:** Finds hardcoded secrets, SQL injections, command injections
- **Pre-Push Hooks:** Validates code automatically before every commit
- **REST API:** Integrate into any workflow
- **BigQuery Analytics:** Track code quality over time

### 🌟 OMEGA Guardian

OMEGA Guardian adds production monitoring on top of Hefesto PRO:

- **IRIS Agent:** Real-time production monitoring
- **Auto-Correlation:** Links code issues to production incidents
- **Real-Time Alerts:** Get notified when code causes production failures
- **Unlimited Everything:** Repos, LOC, users - no limits

---

## 📖 The Dogfooding Story

**We used Hefesto to validate Hefesto itself.**

Before publishing v4.0.1 to PyPI, we ran OMEGA Guardian's self-validation on its own codebase. Here's what it caught:

### 🐛 Critical Bugs Found:

1. **Hardcoded Password** in test fixtures
   - Severity: CRITICAL
   - Location: `tests/fixtures/auth.py`
   - Could leak credentials to GitHub

2. **Dangerous `exec()` Call** without validation
   - Severity: HIGH
   - Location: `utils/dynamic_loader.py`
   - Remote code execution vulnerability

3. **155 Other Issues** including:
   - 23 code smells
   - 12 security warnings
   - 47 complexity violations
   - 73 best practice violations

### ✅ Result:

**We fixed everything before shipping.** v4.0.1 went to production clean.

This is meta-validation at its finest: **AI validating AI code.**

---

## 💰 Pricing - Launch Special

**🚀 Lock in Launch Pricing Forever**

First 100 customers get launch pricing locked permanently. Sign up now and your rate never increases.

| Feature | FREE | **PRO** | **OMEGA Guardian** |
|---------|------|---------|-------------------|
| **Price** | $0 | **$8/mo** | **$19/mo** |
| **Future Price** | $0 | $25/mo | $35/mo |
| **You Save** | - | $204/year | $192/year |
| | | | |
| Basic Analysis | ✅ | ✅ | ✅ |
| Pre-push Hooks | ✅ | ✅ | ✅ |
| CLI Commands | ✅ | ✅ | ✅ |
| **AI/ML Enhancement** | ❌ | ✅ | ✅ |
| **REST API** | ❌ | ✅ | ✅ |
| **BigQuery Integration** | ❌ | ✅ | ✅ |
| **IRIS Monitoring** | ❌ | ❌ | ✅ |
| **Production Correlation** | ❌ | ❌ | ✅ |
| **Real-time Alerts** | ❌ | ❌ | ✅ |
| Repos/LOC/Users | Limited | Unlimited | Unlimited |

### 🎁 14-Day Free Trial

Both PRO and OMEGA Guardian include **14 days free trial**. No credit card required upfront.

### Get Started Now

#### 💎 Hefesto PRO - $8/month

**AI-powered code quality with ML enhancement**

✅ SemanticAnalyzer (AI/ML)
✅ REST API (8 endpoints)
✅ BigQuery integration
✅ Unlimited analysis
✅ Priority support
✅ 14-day free trial

[**Start Free Trial →**](https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b)

---

#### 🌟 OMEGA Guardian - $19/month

**Everything in PRO + Production Monitoring**

✅ Everything in Hefesto PRO
✅ IRIS Agent monitoring
✅ Auto-correlation engine
✅ Real-time alerts
✅ Production incident tracking
✅ Unlimited everything
✅ 14-day free trial

[**Start Free Trial →**](https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c)

---

## 🚀 Quick Start

### Installation
```bash
# FREE tier
pip install hefesto-ai

# PRO tier ($8/month)
pip install hefesto-ai[pro]

# OMEGA Guardian ($19/month)
pip install hefesto-ai[omega]
```

### Basic Usage
```bash
# Analyze a single file
hefesto analyze main.py

# Analyze entire directory
hefesto analyze .

# With severity filter
hefesto analyze . --severity HIGH

# JSON output
hefesto analyze . --format json
```

### Activate PRO/OMEGA Features
```bash
# Set license key (from Stripe after purchase)
export HEFESTO_LICENSE_KEY="your-license-key-here"

# Verify activation
hefesto status

# Should show:
# License: PRO ✅  (or OMEGA ✅)
# ML Enhancement: ✅ Enabled
```

### Pre-Push Hook (Automatic Validation)
```bash
# Install git hook
hefesto install-hook

# Now every git push validates your code automatically
git add .
git commit -m "Add new feature"
git push  # ← Hefesto validates before pushing
```

---

## 🎯 Features

### FREE Tier

- ✅ **Static Analysis:** Complexity, code smells, best practices
- ✅ **Security Scanning:** Hardcoded secrets, injections (basic)
- ✅ **CLI Commands:** Analyze, status, install hooks
- ✅ **Pre-Push Hooks:** Automatic validation on git push
- ✅ **Multi-language:** Python, JavaScript, TypeScript, Go, Rust

### PRO Tier ($8/month)

Everything in FREE, plus:

- ✅ **SemanticAnalyzer:** AI-powered ML code understanding
- ✅ **Deep Security Scanning:** Advanced vulnerability detection
- ✅ **REST API:** 8 endpoints for CI/CD integration
- ✅ **BigQuery Integration:** Historical code quality analytics
- ✅ **Duplicate Detection:** Find copy-pasted code
- ✅ **Anti-Pattern Detection:** Identify design flaws
- ✅ **Priority Support:** Email support with 24h response

### OMEGA Guardian ($19/month)

Everything in PRO, plus:

- ✅ **IRIS Agent:** Production monitoring and alerting
- ✅ **HefestoEnricher:** Auto-correlate code issues → production failures
- ✅ **Real-Time Alerts:** Pub/Sub notifications when code causes incidents
- ✅ **BigQuery Analytics:** Track correlations over time
- ✅ **Production Dashboard:** Visualize code quality → production health
- ✅ **Unlimited Everything:** Repos, LOC, users, analysis
- ✅ **Priority Slack Support:** Direct Slack channel access

---

## 📊 REST API

Hefesto PRO includes a REST API for CI/CD integration:
```bash
# Start server
hefesto serve --port 8000

# Analyze code via API
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "def test(): pass", "severity": "MEDIUM"}'
```

### API Endpoints

- `POST /analyze` - Analyze code
- `GET /health` - Health check
- `POST /batch` - Batch analysis
- `GET /metrics` - Quality metrics
- `GET /history` - Analysis history
- `POST /webhook` - GitHub webhook integration
- `GET /stats` - Statistics
- `POST /validate` - Validate without storing

---

## 🔧 Configuration

### License Key

Set via environment variable:
```bash
export HEFESTO_LICENSE_KEY="your-key-here"
```

Or create `.hefesto.env`:
```bash
HEFESTO_LICENSE_KEY=your-key-here
HEFESTO_SEVERITY=MEDIUM
HEFESTO_OUTPUT=json
```

### Custom Rules

Create `.hefesto.yaml`:
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

  ml:
    enabled: true
    threshold: 0.7
```

---

## 🏗️ OMEGA Guardian Setup

OMEGA Guardian requires Docker for the IRIS Agent:

### 1. Install OMEGA Guardian
```bash
pip install hefesto-ai[omega]
export HEFESTO_LICENSE_KEY="your-omega-key"
```

### 2. Configure IRIS Agent

Create `iris_config.yaml`:
```yaml
project_id: your-gcp-project
dataset: omega_production
pubsub_topic: hefesto-alerts

alert_rules:
  - name: error_rate_spike
    query: |
      SELECT COUNT(*) as error_count
      FROM `production.logs`
      WHERE severity = 'ERROR'
      AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)
    threshold: 10

  - name: latency_increase
    query: |
      SELECT AVG(latency_ms) as avg_latency
      FROM `production.metrics`
      WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 MINUTE)
    threshold: 1000
```

### 3. Run IRIS Agent
```bash
# Via Docker (coming soon)
docker run -v ./iris_config.yaml:/config.yaml \
  narapa/iris-agent:latest

# Or via Python
python -m hefesto.omega.iris_agent --config iris_config.yaml
```

### 4. Verify Correlation
```bash
# Check that IRIS is correlating issues
hefesto omega status

# Should show:
# IRIS Agent: ✅ Running
# Correlations: 3 active
# Last Alert: 2 minutes ago
```

---

## 🧪 Testing & CI/CD

### GitHub Actions
```yaml
name: Hefesto Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Hefesto
        run: pip install hefesto-ai[pro]

      - name: Run Analysis
        env:
          HEFESTO_LICENSE_KEY: ${{ secrets.HEFESTO_LICENSE_KEY }}
        run: hefesto analyze . --severity HIGH --format json
```

### GitLab CI
```yaml
hefesto:
  stage: test
  script:
    - pip install hefesto-ai[pro]
    - export HEFESTO_LICENSE_KEY=$HEFESTO_LICENSE_KEY
    - hefesto analyze . --severity HIGH
```

### Pre-Commit Hook
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: hefesto
        name: Hefesto Analysis
        entry: hefesto analyze
        language: system
        pass_filenames: false
```

---

## 📈 Use Cases

### 1. **AI Coding Assistant Validation**

Use Hefesto to validate code generated by Claude, Cursor, or GitHub Copilot:
```bash
# After AI generates code
hefesto analyze generated_code.py --severity MEDIUM

# Before committing AI-generated code
git add .
git commit -m "AI-generated feature"
git push  # ← Hefesto validates automatically
```

### 2. **Production Monitoring (OMEGA)**

Correlate code quality issues with production failures:
```python
# IRIS detects production error spike
# HefestoEnricher correlates to recent code changes
# Alert sent: "High complexity function causing 500 errors"
```

### 3. **Team Code Reviews**

Run Hefesto before code review to catch obvious issues:
```bash
# Before opening PR
hefesto analyze feature_branch/ --format json > review.json

# Share review.json with team
```

### 4. **Technical Debt Tracking**

Track code quality over time with BigQuery:
```sql
-- Query code quality trends
SELECT
  DATE(analyzed_at) as date,
  AVG(complexity_score) as avg_complexity,
  COUNT(*) as issues_found
FROM hefesto_analytics.analyses
WHERE project = 'my-app'
GROUP BY date
ORDER BY date DESC
```

---

## 🛡️ Security

Hefesto helps find security vulnerabilities:

### What Hefesto Catches

- ✅ **Hardcoded Secrets:** API keys, passwords, tokens
- ✅ **SQL Injection:** Unsafe query construction
- ✅ **Command Injection:** Unsafe shell command execution
- ✅ **Path Traversal:** Unsafe file access
- ✅ **Unsafe Deserialization:** pickle, yaml.unsafe_load
- ✅ **XSS Vulnerabilities:** Unsafe HTML rendering
- ✅ **SSRF Attempts:** Unsafe URL requests

### Example
```python
# Hefesto catches this:
password = "admin123"  # ❌ Hardcoded secret
os.system(f"rm {user_input}")  # ❌ Command injection
query = f"SELECT * FROM users WHERE id={user_id}"  # ❌ SQL injection

# Hefesto suggests:
password = os.getenv("PASSWORD")  # ✅
subprocess.run(["rm", user_input], check=True)  # ✅
cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))  # ✅
```

---

## 📚 Documentation

- **Installation:** [Installation Guide](docs/INSTALLATION.md)
- **Configuration:** [Configuration Guide](docs/CONFIGURATION.md)
- **API Reference:** [API Docs](docs/API.md)
- **OMEGA Guardian:** [OMEGA Setup](docs/OMEGA_GUARDIAN.md)
- **Examples:** [Examples Directory](examples/)

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
```bash
# Clone repo
git clone https://github.com/artvepa80/Agents-Hefesto.git
cd Agents-Hefesto

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run Hefesto on itself (dogfooding)
hefesto analyze . --severity MEDIUM
```

---

## 📜 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

### Recent Releases

- **v4.2.1** (2025-10-31): Critical tier hierarchy bugfix
- **v4.2.0** (2025-10-31): OMEGA Guardian release
- **v4.1.0** (2025-10-31): Unified package architecture
- **v4.0.1** (2025-10-30): Production stability fixes

---

## ❓ FAQ

### Do I need a license for the FREE tier?

No, FREE tier works without any license key.

### How do I upgrade from FREE to PRO?

1. Purchase PRO: [Get PRO](https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b)
2. Set license key: `export HEFESTO_LICENSE_KEY="your-key"`
3. Features unlock automatically

### Can I try PRO/OMEGA before buying?

Yes! Both include 14-day free trials. No credit card required upfront.

### What happens after 100 launch customers?

Pricing increases to $25/mo (PRO) and $35/mo (OMEGA) for new customers.
Early customers keep their launch pricing forever.

### Is my code sent to external servers?

- FREE/PRO: Analysis runs locally, no code sent externally
- OMEGA: Only metadata sent to BigQuery for correlation
- Your actual code never leaves your infrastructure

### What if I have issues?

- Email: support@narapallc.com
- GitHub Issues: [Open an issue](https://github.com/artvepa80/Agents-Hefesto/issues)
- PRO/OMEGA: Priority support via email or Slack

---

## 📧 Contact

- **Support:** support@narapallc.com
- **General inquiries:** contact@narapallc.com
- **GitHub:** [@artvepa80](https://github.com/artvepa80)
- **Company:** Narapa LLC, Miami, Florida
- **Website:** Coming soon

---

## 📄 License

MIT License for core functionality. See [LICENSE](LICENSE) for details.

PRO and OMEGA Guardian features are licensed separately under commercial terms.

---

## 🙏 Acknowledgments

Built with:
- [Google Gemini](https://ai.google.dev/) for AI analysis
- [BigQuery](https://cloud.google.com/bigquery) for analytics
- [Pub/Sub](https://cloud.google.com/pubsub) for real-time alerts
- Love from Miami ☀️

---

**⭐ Star us on GitHub if Hefesto helped you catch bugs!**

---

*Hefesto: AI-powered code quality that caught 3 critical bugs in its own release. Now protecting your code.*

© 2025 Narapa LLC. All rights reserved.
