# 🔨 HEFESTO - AI-Powered Code Quality Guardian

[![PyPI version](https://img.shields.io/pypi/v/hefesto-ai.svg)](https://pypi.org/project/hefesto-ai/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT%20%2F%20Commercial-green.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/hefesto-ai.svg)](https://pypi.org/project/hefesto-ai/)
[![Code Quality](https://img.shields.io/badge/code%20quality-A+-brightgreen.svg)](https://github.com/artvepa80/Agents-Hefesto)

**Stop bad code before it reaches production. Hefesto is your autonomous code quality guardian with integrated static analysis, ML-powered validation, and intelligent refactoring.**

---

## 🎯 Why Hefesto?

Traditional linters find syntax errors. Hefesto finds **architectural problems, security risks, and code smells** that impact your team's velocity and product quality.

```bash
# Before every push, Hefesto validates:
✅ Cyclomatic complexity        ✅ Security vulnerabilities
✅ Code smells (8 types)        ✅ Best practices violations
✅ False positive filtering     ✅ ML-powered suggestions (PRO)
```

**Result:** Catch issues in development, not in code review or production.

---

## ⚡ Quick Start (30 seconds)

```bash
# Install
pip install hefesto-ai

# Analyze your code
hefesto analyze .

# Install pre-push hook (recommended)
hefesto install-hook

# Done! Now every git push is validated ✅
```

---

## ✨ Features

### 🆓 FREE Tier (MIT License)

| Analyzer | Detects | Severity Levels |
|----------|---------|-----------------|
| **Complexity** | Functions too complex (cyclomatic >10) | MEDIUM → CRITICAL |
| **Code Smells** | Long functions, deep nesting, magic numbers, god classes, TODOs | LOW → HIGH |
| **Security** | Hardcoded secrets, SQL injection, eval(), pickle, bare except | HIGH → CRITICAL |
| **Best Practices** | Missing docstrings, poor naming, PEP 8 violations | LOW → MEDIUM |

**Phase 0 Validation:**
- False positive filtering
- Multi-layer code validation
- AST-based analysis
- Budget tracking
- Security masking

**Output Formats:**
- Terminal (colorized)
- JSON (machine-readable)
- HTML (interactive report)

### 🌟 PRO Tier ($20/month)

Everything in FREE, plus:

| Feature | Description |
|---------|-------------|
| **ML Semantic Analysis** | Understand code meaning, not just syntax |
| **Duplicate Detection** | Find semantically similar code across your codebase |
| **Confidence Boosting** | ML learns from your codebase patterns |
| **BigQuery Analytics** | Track trends, identify bottlenecks |
| **Priority Support** | 4-8 hour response time |

---

## 📊 What Hefesto Detects

### Complexity Issues

```python
# ❌ BAD: Cyclomatic complexity = 15 (HIGH)
def process_data(data, options):
    if data:
        if options.get('validate'):
            if options.get('transform'):
                if options.get('cache'):
                    # ... 4 levels of nesting

# ✅ GOOD: Refactored to complexity = 4
def process_data(data, options):
    if not data:
        return None

    validated = validate(data) if options.get('validate') else data
    transformed = transform(validated) if options.get('transform') else validated
    return cache(transformed) if options.get('cache') else transformed
```

**Detection:** Flags functions with complexity >10 (HIGH), >20 (CRITICAL)

### Security Vulnerabilities

```python
# 🔥 CRITICAL: Hardcoded API key detected
API_KEY = "sk-proj-abc123def456"  # Hefesto blocks this in pre-push

# ✅ GOOD: Environment variable
API_KEY = os.getenv("API_KEY")
```

**Detects:**
- Hardcoded secrets (API keys, passwords, tokens)
- SQL injection risks
- Dangerous eval() usage
- Unsafe pickle deserialization
- Production assert statements
- Bare except clauses

### Code Smells

```python
# ⚠️ MEDIUM: Function too long (78 lines)
def process_everything(a, b, c, d, e, f, g):  # ⚠️ MEDIUM: Too many parameters
    result = a * 3.14159  # 💡 LOW: Magic number
    # TODO: Optimize this  # 💡 LOW: Incomplete TODO
    # ... 70 more lines
```

**Detects:**
- Long functions (>50 lines)
- Long parameter lists (>5 params)
- Deep nesting (>4 levels)
- Magic numbers
- God classes (>500 lines)
- Incomplete TODOs/FIXMEs

---

## 🚀 Usage

### CLI Commands

```bash
# Basic analysis
hefesto analyze myfile.py

# Analyze directory with severity filter
hefesto analyze src/ --severity HIGH

# Generate HTML report
hefesto analyze . --output html --save-html report.html

# Exclude directories
hefesto analyze . --exclude "tests/,docs/,build/"

# JSON output for CI/CD
hefesto analyze . --output json > analysis.json
```

### Pre-Push Hook (Recommended)

```bash
# Install once
hefesto install-hook

# Now every git push runs:
1. Black formatting
2. isort imports
3. flake8 linting
4. pytest tests
5. Hefesto analyze ⭐
```

**If CRITICAL issues found:**
- ❌ Push is blocked
- 📄 Detailed report shown
- 💡 Fix suggestions provided
- 🔧 `--no-verify` to bypass (not recommended)

### Python SDK

```python
from hefesto import get_validator, SuggestionValidator
from hefesto.analyzers import ComplexityAnalyzer
from hefesto.core.analyzer_engine import AnalyzerEngine

# Validate AI suggestions
validator = get_validator()
result = validator.validate(
    original_code="x = eval(user_input)",
    suggested_code="x = json.loads(user_input)",
    issue_type="security"
)

print(f"Confidence: {result.confidence:.0%}")
print(f"Safe to apply: {result.safe_to_apply}")

# Run analyzers programmatically
engine = AnalyzerEngine(severity_threshold="HIGH")
engine.register_analyzer(ComplexityAnalyzer())

report = engine.analyze_path("src/")
print(f"Issues found: {report.summary.total_issues}")
```

### API Server

```bash
# Set API key
export GEMINI_API_KEY='your_gemini_api_key'

# Start server
hefesto serve --port 8080

# Test endpoint
curl http://localhost:8080/ping
# Response: {"status": "ok", "version": "1.0.0"}
```

---

## 📈 Example Output

### Terminal (FREE)

```
🔨 HEFESTO ANALYSIS PIPELINE
==================================================
License: FREE
ML Enhancement: ❌ Disabled
==================================================

📁 Found 12 Python file(s)

🔍 Step 1/3: Running static analyzers...
   Found 23 potential issue(s)

✅ Step 2/3: Validation layer (Phase 0)...
   23 issue(s) validated

⏭️  Step 3/3: ML enhancement skipped (FREE tier)
   💡 Upgrade to PRO for ML-powered analysis

📊 Summary:
   Files analyzed: 12
   Issues found: 23
   Critical: 2
   High: 5
   Medium: 11
   Low: 5

🔥 CRITICAL Issues (2):

  📄 auth.py:45
  ├─ Issue: Hardcoded API key detected
  ├─ Severity: CRITICAL
  └─ Suggestion: Move to environment variable:
     API_KEY = os.getenv('API_KEY')
```

### HTML Report

<img width="800" alt="HTML Report Example" src="docs/screenshots/html-report.png">

**Features:**
- Executive summary with charts
- Filterable issue list
- Syntax-highlighted code snippets
- Fix suggestions with examples
- Export to PDF

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         HEFESTO ANALYZER                │
├─────────────────────────────────────────┤
│  Static Analyzers (FREE)                │
│  • Complexity                           │
│  • Code Smells                          │
│  • Security                             │
│  • Best Practices                       │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│  PHASE 0: Validation Layer (FREE)       │
│  • False positive filtering             │
│  • AST validation                       │
│  • Confidence scoring                   │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│  PHASE 1: ML Enhancement (PRO)          │
│  • Semantic analysis                    │
│  • Duplicate detection                  │
│  • Pattern learning                     │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│  OUTPUT                                 │
│  Text • JSON • HTML                     │
└─────────────────────────────────────────┘
```

**Learn more:** [Integration Architecture](docs/INTEGRATION.md)

---

## 💰 Pricing

| Feature | FREE | PRO ($20/mo) |
|---------|------|--------------|
| Static Analysis | ✅ | ✅ |
| 22+ Quality Checks | ✅ | ✅ |
| Phase 0 Validation | ✅ | ✅ |
| Pre-Push Hook | ✅ | ✅ |
| Text/JSON/HTML Reports | ✅ | ✅ |
| ML Semantic Analysis | ❌ | ✅ |
| Duplicate Detection | ❌ | ✅ |
| BigQuery Analytics | ❌ | ✅ |
| Priority Support (4-8h) | ❌ | ✅ |

---

### 🆓 FREE Tier
```bash
pip install hefesto-ai
hefesto analyze .
```

Perfect for individual developers and open-source projects.

**Includes:**
- All static analyzers (Complexity, Security, Code Smells, Best Practices)
- Phase 0 validation layer with false positive filtering
- Pre-commit hook integration
- Multiple report formats: Text, JSON, HTML
- MIT License (commercial use allowed)

---

### 💎 PRO Tier - $20/month

[![Start 14-Day Free Trial](https://img.shields.io/badge/Start%2014--Day%20Free%20Trial-5469d4?style=for-the-badge&logo=stripe&logoColor=white)](https://buy.stripe.com/4gMfZg4bw48N3zEgqaeAg0a)

**Everything in FREE, plus:**
- 🧠 **ML Semantic Analysis** - Understand code meaning, not just syntax
- 🔍 **Duplicate Detection** - Find semantically similar code across your codebase
- 📊 **BigQuery Analytics** - Track quality trends and identify bottlenecks
- 🚀 **Priority Support** - 4-8 hour response time
- 📈 **Pattern Learning** - ML learns from your codebase patterns

**✨ 14-day free trial • No credit card required • Cancel anytime**

---

### 🎁 FOUNDING MEMBER OFFER

**🔥 Limited to first 50 customers only! 🔥**

[![Become a Founding Member](https://img.shields.io/badge/Become%20a%20Founding%20Member-FFD700?style=for-the-badge&logo=stripe&logoColor=black)](https://buy.stripe.com/4gMfZg4bw48N3zEgqaeAg0a)

**Exclusive benefits:**
- 💰 **40% OFF Forever** - Use code `FOUNDING100` at checkout
- 💵 **$20/month → $12/month** - Grandfathered permanently
- 🎯 **All PRO features** included
- 🌟 **Priority feature requests** - Your voice shapes the roadmap
- 👥 **Direct access** to founding team
- 🏆 **Founding Member badge** in dashboard

**How to claim:**
1. Click "Become a Founding Member" button above
2. Enter code `FOUNDING100` at checkout
3. Enjoy 40% OFF forever!

⏰ **Only 50 spots available • Offer expires Dec 31, 2025**

---

### 💳 Payment & Security

**Accepted payment methods:**
- 💳 Credit/Debit Cards (Visa, Mastercard, Amex, Discover)
- 🍎 Apple Pay
- 🤖 Google Pay
- 💸 Klarna (Buy Now, Pay Later)
- 🔗 Link (Stripe's one-click checkout)
- 💵 Cash App Pay
- 📦 Amazon Pay

**Secure checkout powered by Stripe** • **PCI DSS compliant** • **Cancel anytime, no questions asked**

---

### ❓ Frequently Asked Questions

**Q: What happens after the 14-day trial?**
A: You'll be charged $20/month (or $12/month with FOUNDING100 code). Cancel anytime before the trial ends with no charge.

**Q: Can I cancel anytime?**
A: Yes! No contracts, no penalties. Cancel with one click from your dashboard.

**Q: Is the Founding Member discount really forever?**
A: Yes! Your rate is locked at $12/month for as long as you remain a customer, even if prices increase later.

**Q: Do I need a credit card for the trial?**
A: Yes, but you won't be charged until after the 14-day trial period.

**Q: What if I'm not satisfied?**
A: Contact us within 30 days for a full refund, no questions asked.

**Q: What about OMEGA Guardian?**
A: OMEGA Guardian (Hefesto + Iris production monitoring + ML correlation) is planned for Q1 2026. Start with Hefesto now and upgrade when available!

---

## 📚 Documentation

- [Getting Started](docs/GETTING_STARTED.md) - 5-minute tutorial
- [Analysis Rules](docs/ANALYSIS_RULES.md) - All 22+ checks explained
- [Integration Guide](docs/INTEGRATION.md) - Phase 0+1 architecture
- [API Reference](docs/API_REFERENCE.md) - Complete API documentation
- [CLI Reference](docs/CLI_REFERENCE.md) - All commands
- [Changelog](CHANGELOG.md) - Version history

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas we need help:**
- Additional analyzers (maintainability, performance)
- Language support (JavaScript, TypeScript, Go)
- IDE integrations (VS Code, PyCharm)
- Documentation improvements

---

## 📊 Stats

- **22+ code quality checks**
- **4 analyzer modules**
- **3 output formats**
- **~3,500 lines of code**
- **~85% test coverage**
- **<100ms analysis per file**

---

## 🛠️ Tech Stack

- **Analysis:** AST parsing, radon, bandit, vulture, pylint
- **ML (PRO):** Sentence Transformers, PyTorch
- **API:** FastAPI, Uvicorn
- **Storage:** BigQuery (PRO)
- **AI:** Google Gemini API
- **Testing:** pytest, pytest-cov, mypy

---

## 🔒 Private Repository

Some internal tools and documentation are in a **private repository** for security:

```bash
# For team members with access:
git submodule update --init
cd private/

# Available private resources:
# - scripts/generate_key.py - License key generator
# - scripts/fulfill_order.py - Order fulfillment with AWS S3
# - docs/MANUAL_FULFILLMENT.md - Internal processes
# - deployment/ - Production deployment configs
```

**Access:** Contact **team@narapallc.com**

See [SECURITY.md](SECURITY.md) for our security policy.

---

## 📄 License

**Dual License:**
- FREE tier: MIT License (commercial use allowed)
- PRO tier: Commercial License

See [LICENSE](LICENSE) for details.

---

## 💬 Support

- **Community:** [GitHub Discussions](https://github.com/artvepa80/Agents-Hefesto/discussions)
- **Issues:** [GitHub Issues](https://github.com/artvepa80/Agents-Hefesto/issues)
- **Email:** sales@narapallc.com (PRO customers: priority support)

---

## 🛣️ Roadmap

### ✅ Available Now (v4.0.0)
- Complete static analysis suite
- ML semantic analysis
- Pre-commit hook integration
- Multiple report formats
- BigQuery analytics

### 🔜 Coming Q1 2026: OMEGA Guardian Suite

The complete DevOps intelligence platform combining:
- **Hefesto** (Code Quality) - Already available
- **Iris** (Production Monitoring) - In development
- **ML Correlation Engine** - Automatically links code warnings to production incidents

**OMEGA Guardian will answer:** "Which ignored code warnings caused production incidents and what did they cost?"

Interested in early access? [Join the waitlist](mailto:sales@narapallc.com?subject=OMEGA%20Guardian%20Early%20Access)

### 🎯 Future Enhancements
- Auto-fix for simple issues
- VS Code extension
- GitHub App integration
- Custom rule creation
- Team analytics dashboard
- JavaScript/TypeScript support

**Vote on features:** [Roadmap Discussion](https://github.com/artvepa80/Agents-Hefesto/discussions/categories/roadmap)

---

## ⭐ Show Your Support

If Hefesto helps you write better code, please star the repo!

[![GitHub stars](https://img.shields.io/github/stars/artvepa80/Agents-Hefesto?style=social)](https://github.com/artvepa80/Agents-Hefesto/stargazers)

---

<div align="center">

**Built with ❤️ by [Narapa LLC](https://narapallc.com)**

Miami, Florida • Copyright © 2025

[Website](https://hefesto.dev) • [Twitter](https://twitter.com/hefestoai) • [LinkedIn](https://linkedin.com/company/hefesto)

</div>
