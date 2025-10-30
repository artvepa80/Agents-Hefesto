# OMEGA Guardian - Internal Setup Guide

**Narapa LLC Internal Development License**
**Generated:** 2025-10-30
**Tier:** Professional (Founding Member)
**Price:** $35/month locked forever

---

## What is OMEGA Guardian?

OMEGA Guardian is Narapa LLC's complete DevOps intelligence platform combining three powerful components:

1. **Hefesto** - AI-powered code quality analysis
2. **Iris** - Production monitoring and incident correlation
3. **ML Correlation Engine** - Links code warnings to production incidents

This internal development license gives the Narapa LLC team permanent access to all OMEGA Guardian features.

---

## License Information

```bash
License Key: HFST-6F06-4D54-6402-B3B1-CF72
Tier: Professional (Founding Member)
Email: dev@narapallc.com
Subscription ID: sub_OMEGA_NARAPA_DEV
```

**Features Enabled:**
- ML Semantic Analysis
- Duplicate Code Detection
- BigQuery Analytics
- Iris Production Monitoring
- ML Correlation between code and incidents

---

## Installation Steps

### 1. Verify Private Repo Access

Ensure you have access to the private repository scripts:

```bash
ls private/scripts/generate_key.py
ls private/hefesto_pro/
```

### 2. Install Hefesto Package

```bash
# Install in development mode
pip install -e .

# Or install from PyPI (when published)
pip install hefesto
```

### 3. Configure Environment Variables

The `.env.omega` file has already been created with your license key:

```bash
# Location: .env.omega
# DO NOT COMMIT THIS FILE - Already added to .gitignore

source .env.omega  # Load environment variables
```

**Contents of .env.omega:**

```bash
# OMEGA Guardian - Narapa LLC Internal Development License
# Generated: 2025-10-30
# DO NOT SHARE - Internal use only

# License Configuration
HEFESTO_LICENSE_KEY=HFST-6F06-4D54-6402-B3B1-CF72
HEFESTO_TIER=professional
OMEGA_ENABLED=true

# Customer Information (Internal)
CUSTOMER_EMAIL=dev@narapallc.com
SUBSCRIPTION_ID=sub_OMEGA_NARAPA_DEV
FOUNDING_MEMBER=true

# Features Enabled
ML_SEMANTIC_ANALYSIS=true
DUPLICATE_DETECTION=true
BIGQUERY_ANALYTICS=true
IRIS_MONITORING=true
ML_CORRELATION=true

# API Configuration
# GEMINI_API_KEY=your_gemini_api_key_here  # Configure for ML features
# GCP_PROJECT_ID=your_gcp_project_id_here # Configure for BigQuery

# OMEGA Guardian Components
HEFESTO_ENABLED=true  # Code analysis
IRIS_ENABLED=true     # Production monitoring
CORRELATION_ENABLED=true  # ML correlation between code and incidents
```

### 4. Install Pre-Push Hooks

Install the enhanced git pre-push hook with Advanced Validation features:

```bash
python3 -m hefesto.cli.main install-hooks --force
```

**What the hook validates:**
1. Black formatting check
2. isort import sorting
3. **Flake8 linting** (NEW - prevents 20+ CI errors!)
4. pytest unit tests
5. Hefesto code analysis

---

## Usage Examples

### Basic Code Analysis

```bash
# Analyze a single file
hefesto analyze myfile.py

# Analyze entire directory
hefesto analyze src/

# Filter by severity
hefesto analyze . --severity HIGH

# Generate HTML report
hefesto analyze . --output html --save-html report.html

# Exclude directories
hefesto analyze . --exclude "tests/,docs/,build/"

# Verbose mode (show pipeline)
hefesto analyze . --verbose
```

### Advanced Validation Features

#### CI Parity Checker

Validates that your local environment matches CI configuration:

```bash
hefesto check-ci-parity
```

**What it checks:**
- Python version matches CI matrix
- Development tools installed (flake8, black, isort, pytest)
- Flake8 configuration parity (max-line-length, ignore rules)

#### Test Contradiction Detector

Finds contradictory test assertions:

```bash
hefesto check-test-contradictions tests/
```

**What it detects:**
- Same function + same inputs → different expected outputs
- Supports: assert statements, unittest assertions, method calls

---

## Validation Test Results

### Installation Validation

```bash
# Pre-push hooks installed successfully
✅ Pre-push hook installed successfully!
   Location: .git/hooks/pre-push

# Validator tests passing
✅ 34 passed, 5 skipped in 58.63s

# Code coverage: 86% (ci_parity.py), 61% (test_contradictions.py)
```

### CI Parity Check Results

**Current Environment Issues:**

```
🔥 HIGH Priority (4 issues)
- flake8 not found locally but used in CI
- black not found locally but used in CI
- isort not found locally but used in CI
- pytest not found locally but used in CI

⚠️  MEDIUM Priority (1 issue)
- Local Python 3.9 not in CI matrix [3.10, 3.11, 3.12]
```

**Recommended Actions:**

```bash
# Install missing development tools
pip install flake8 black isort pytest

# Consider upgrading Python version
pyenv install 3.11
pyenv local 3.11
```

### Hefesto Analysis Test

```bash
# Tested on hefesto/validators/ci_parity.py
✅ Analysis complete in 0.04s
📊 Found 5 HIGH severity issues:
   - 2 cyclomatic complexity warnings
   - 1 deep nesting warning
   - 2 false positive SQL injection warnings (f-strings, not SQL)
```

---

## Pre-Push Hook Behavior

The pre-push hook will **block pushes** if:
- Black formatting fails
- isort import ordering fails
- **Flake8 linting fails** (NEW!)
- Unit tests fail
- CRITICAL or HIGH severity Hefesto issues found

**Bypass the hook (use sparingly):**

```bash
git push --no-verify
```

---

## API Configuration (Optional)

### Enable ML Features

To enable ML-powered semantic analysis, configure Gemini API:

```bash
# Add to .env.omega
export GEMINI_API_KEY='your_gemini_api_key_here'
```

### Enable BigQuery Analytics

To enable BigQuery persistence and analytics:

```bash
# Add to .env.omega
export GCP_PROJECT_ID='your_gcp_project_id_here'
```

See `docs/API.md` for BigQuery setup guide.

---

## Troubleshooting

### Hook Not Running

```bash
# Verify hook is installed
ls -la .git/hooks/pre-push

# Reinstall hook
hefesto install-hooks --force

# Test hook manually
python3 .git/hooks/pre-push
```

### License Validation Errors

```bash
# Verify license key is loaded
echo $HEFESTO_LICENSE_KEY

# Should output: HFST-6F06-4D54-6402-B3B1-CF72

# Reload environment variables
source .env.omega

# Verify license with Hefesto
hefesto info
```

### Import Errors

```bash
# Verify Hefesto is installed
pip show hefesto

# Reinstall in development mode
pip install -e .

# Check Python path
python3 -c "import hefesto; print(hefesto.__file__)"
```

### CI Failures After Local Success

```bash
# Run CI parity checker
hefesto check-ci-parity

# Fix any HIGH priority issues
# Ensure local Python version matches CI matrix
```

---

## Security Notes

**NEVER commit these files:**
- `.env.omega` - Contains license key (already in .gitignore)
- Any file with `*secret*`, `*credentials*`, `*api_key*` patterns (already in .gitignore)

**Verify before pushing:**

```bash
# Check what will be committed
git status

# Verify .env.omega is not staged
git diff --cached --name-only | grep -i "env\|secret\|credential"
```

---

## Team Collaboration

### Sharing License with Team Members

Each developer should:

1. Clone the repository
2. Copy `.env.omega` to their local machine (via secure channel)
3. Run `source .env.omega` to load environment
4. Install hooks with `hefesto install-hooks --force`

**Do NOT commit `.env.omega` to Git!**

### Running Tests Locally

```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/validators/ -v  # Validator tests
pytest tests/api/ -v         # API tests

# Run with coverage
pytest tests/ --cov=hefesto --cov-report=html
```

---

## Resources

- **Documentation**: `docs/GETTING_STARTED.md`
- **API Reference**: `docs/API.md`
- **Advanced Validation**: `docs/ADVANCED_VALIDATION.md`
- **Analysis Rules**: `docs/ANALYSIS_RULES.md`
- **Integration Architecture**: `docs/INTEGRATION.md`

---

## Support

For questions or issues:
- **Internal Slack**: #omega-guardian
- **Email**: dev@narapallc.com
- **GitHub Issues**: https://github.com/artvepa80/Agents-Hefesto/issues

---

## License Summary

**OMEGA Guardian - Narapa LLC Internal Development License**

- **Tier**: Professional (Founding Member)
- **Price**: $35/month (locked forever)
- **Seats**: Unlimited (internal use only)
- **Support**: Priority support included
- **Validity**: Perpetual (as long as subscription active)

**Last Updated:** 2025-10-30
**Generated By:** Claude Code AI Assistant
