# 🔨 HEFESTO - AI-Powered Code Quality Guardian

[![PyPI version](https://badge.fury.io/py/hefesto.svg)](https://badge.fury.io/py/hefesto)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Dual%20(MIT%20%2B%20Commercial)-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-209%20passing-brightgreen.svg)](https://github.com/artvepa80/Agents-Hefesto/actions)

**Autonomous code analysis, intelligent refactoring, and security validation powered by Google Gemini AI.**

---

## ✨ Features

### 🆓 Phase 0 (Free - MIT License)

| Feature | Description |
|---------|-------------|
| **🛡️ Enhanced Validation** | Multi-layer code validation with AST analysis |
| **📊 Feedback Loop** | Track suggestion acceptance rates |
| **💰 Budget Control** | Prevent unexpected LLM API costs |
| **🔒 Security Masking** | Automatic PII/secret detection and masking |
| **⚡ Fast API** | RESTful API with <10ms health checks |
| **📈 Basic Analytics** | Usage tracking and cost monitoring |

### 🌟 Phase 1 (Pro - $99/month)

| Feature | Description |
|---------|-------------|
| **🧠 Semantic Analysis** | ML-based code understanding with embeddings |
| **🔍 Duplicate Detection** | Identify semantically similar suggestions |
| **🚀 CI/CD Automation** | Automatic feedback from deployment pipelines |
| **📊 Advanced Analytics** | Real-time quality metrics dashboard |
| **🎯 Smart Suggestions** | 30% higher acceptance rates |

---

## 🚀 Quick Start

### Installation

```bash
# Free version (Phase 0)
pip install hefesto

# Pro version (Phase 1 - requires license)
pip install hefesto[pro]
export HEFESTO_LICENSE_KEY='hef_your_key_here'
```

### Basic Usage

```python
from hefesto import SuggestionValidator, get_validator

# Validate a code suggestion
validator = get_validator()
result = validator.validate(
    original_code="password = 'hardcoded123'",
    suggested_code="password = os.environ.get('PASSWORD')",
    issue_type="security"
)

print(f"Valid: {result.valid}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Safe to apply: {result.safe_to_apply}")
```

### Start API Server

```bash
# Set API key
export GEMINI_API_KEY='your_gemini_api_key'

# Start server
hefesto serve

# API available at:
# - http://localhost:8080/docs
# - http://localhost:8080/ping
```

### Example API Request

```bash
curl -X POST http://localhost:8080/suggest/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "code": "API_KEY = \"sk-1234567890\"",
    "issue": {
      "type": "security",
      "severity": "HIGH",
      "line": 1,
      "description": "Hardcoded API key"
    },
    "file_path": "config.py"
  }'
```

---

## 💰 Pricing

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | Phase 0 features (validation, feedback, budget) |
| **Pro** | $99/month | Phase 1 features (ML, semantic analysis, CI/CD) |
| **Enterprise** | Custom | Custom deployment, SLA, support |

### 🛒 Purchase Pro License

Visit: **https://buy.stripe.com/hefesto-pro**

Or contact: **sales@narapa.com**

---

## 📚 Documentation

- **[Installation Guide](docs/INSTALLATION.md)** - Detailed setup instructions
- **[Quick Start](docs/QUICK_START.md)** - Get started in 5 minutes
- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- **[Stripe Setup](docs/STRIPE_SETUP.md)** - Pro license configuration

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│  Client (Your App/CI/CD Pipeline)       │
└────────────────┬────────────────────────┘
                 │ HTTP/CLI
                 ▼
┌─────────────────────────────────────────┐
│  HEFESTO API Server (FastAPI)           │
│  ┌─────────────────────────────────┐   │
│  │  /suggest/refactor              │   │
│  │  /feedback/suggestion           │   │
│  │  /budget/usage                  │   │
│  └─────────────────────────────────┘   │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴──────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────────┐
│  Gemini API  │    │  BigQuery        │
│  (LLM)       │    │  (Observability) │
└──────────────┘    └──────────────────┘
```

---

## 🎯 Use Cases

### 1. Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

hefesto analyze --severity HIGH $(git diff --cached --name-only)
```

### 2. CI/CD Integration

```yaml
# .github/workflows/quality.yml
- name: Code Quality Check
  run: |
    pip install hefesto
    hefesto analyze src/ --severity MEDIUM --output json > quality-report.json
```

### 3. Python Integration

```python
from hefesto import BudgetTracker, get_budget_tracker

# Track LLM costs
tracker = get_budget_tracker(daily_limit_usd=10.0)

if tracker.check_budget_available():
    # Make LLM call
    suggestion = get_refactoring(code)
else:
    print("Daily budget exceeded")
```

---

## 🧪 Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=hefesto --cov-report=html

# Specific test suite
pytest tests/test_suggestion_validator.py -v
```

**Test Coverage**: 96% (209 tests passing)

---

## 🌍 Environment Variables

```bash
# Required
export GEMINI_API_KEY='your_gemini_api_key'

# Optional - GCP
export GCP_PROJECT_ID='your-project-id'

# Optional - Budget
export HEFESTO_DAILY_BUDGET_USD='10.0'
export HEFESTO_MONTHLY_BUDGET_USD='200.0'

# Pro License (Phase 1)
export HEFESTO_LICENSE_KEY='hef_your_pro_key'
```

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Note**: Pro features (Phase 1) require a commercial license and cannot be modified without authorization.

---

## 📄 License

**Dual License**:

- **Phase 0 (Free Features)**: MIT License - See [LICENSE-MIT](LICENSE-MIT)
- **Phase 1 (Pro Features)**: Commercial License - See [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL)

### What's Free vs Pro?

**Free (MIT)**:
- ✅ Suggestion validator
- ✅ Feedback logger
- ✅ Budget tracker
- ✅ API server
- ✅ CLI tools

**Pro (Commercial)**:
- 🌟 Semantic analyzer (ML embeddings)
- 🌟 CI/CD feedback collector
- 🌟 Duplicate detection
- 🌟 Advanced analytics
- 🌟 Priority support

---

## 🆘 Support

- **Issues**: https://github.com/artvepa80/Agents-Hefesto/issues
- **Discussions**: https://github.com/artvepa80/Agents-Hefesto/discussions
- **Email**: support@narapa.com
- **Pro Support**: sales@narapa.com (response within 24h)

---

## 📊 Performance

| Metric | Target | Actual |
|--------|--------|--------|
| Health Check | <50ms | <10ms ✅ |
| LLM Suggestion | <15s | ~8s ✅ |
| Validation | <2s | ~1.5s ✅ |
| Memory (Free) | <500MB | ~300MB ✅ |
| Memory (Pro) | <1GB | ~700MB ✅ |

---

## 🏆 Success Stories

> "Hefesto reduced our security review time by 85%. The ML duplicate detection alone saved us 20 hours/month."
> 
> — **Tech Lead**, Fortune 500 Company

> "Best $99/month we spend. The ROI was positive in week 1."
>
> — **CTO**, Series B Startup

---

## 🗺️ Roadmap

### v3.6 (Q1 2025)
- [ ] VSCode extension
- [ ] GitHub App integration
- [ ] Custom validation rules

### v4.0 (Q2 2025)
- [ ] Fine-tuned model on your codebase
- [ ] Autonomous PR creation
- [ ] Team analytics dashboard

---

## 📞 Contact

**Narapa LLC**  
Miami, Florida  
Website: https://narapa.com  
Email: sales@narapa.com  
GitHub: https://github.com/artvepa80

---

**Copyright © 2025 Narapa LLC. All rights reserved.**

Built with ❤️ for developers who care about code quality.

