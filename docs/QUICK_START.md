# Hefesto Quick Start Guide

Get up and running with Hefesto in 5 minutes.

## 1. Install Hefesto

```bash
pip install hefesto
```

## 2. Set API Key

```bash
export GEMINI_API_KEY='your_gemini_api_key'
# Get key: https://aistudio.google.com/app/apikey
```

## 3. Start Server

```bash
hefesto serve
```

Server starts at: **http://localhost:8080**

## 4. Test the API

### Health Check

```bash
curl http://localhost:8080/ping
```

Expected response:
```json
{
  "ok": true,
  "version": "3.5.0",
  "env": "production"
}
```

### Get Refactoring Suggestion

```bash
curl -X POST http://localhost:8080/suggest/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "code": "password = \"hardcoded123\"",
    "issue": {
      "type": "security",
      "severity": "HIGH",
      "line": 1,
      "description": "Hardcoded password"
    },
    "file_path": "config.py"
  }'
```

Expected response:
```json
{
  "diff": "- password = \"hardcoded123\"\n+ password = os.environ.get('PASSWORD')",
  "confidence": 0.95,
  "safety_score": 0.82,
  "auto_apply": false,
  "reasoning": "Replaces hardcoded password with environment variable",
  "validation_passed": true,
  "suggestion_id": "SUG-A1B2C3D4E5F6"
}
```

## 5. Python Integration

```python
from hefesto import get_validator

# Validate a suggestion
validator = get_validator()
result = validator.validate(
    original_code="password = 'secret'",
    suggested_code="password = os.environ.get('PASSWORD')",
    issue_type="security"
)

print(f"Confidence: {result.confidence:.2%}")
print(f"Safe: {result.safe_to_apply}")
```

## 6. Monitor Budget

```bash
# Check budget usage
curl http://localhost:8080/budget/usage?period=today

# Check if budget available
curl http://localhost:8080/budget/check?period=today
```

## 7. Upgrade to Pro (Optional)

For ML-based semantic analysis and duplicate detection:

```bash
# Purchase license
# Visit: https://buy.stripe.com/hefesto-pro

# Install Pro features
pip install hefesto[pro]

# Set license key
export HEFESTO_LICENSE_KEY='hef_your_pro_key'

# Verify
hefesto info
# Should show: "Pro Features: ✅ Enabled"
```

## Common Use Cases

### Pre-Commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
hefesto analyze --severity HIGH $(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')
```

### CI/CD Pipeline

Add to `.github/workflows/quality.yml`:

```yaml
- name: Code Quality
  run: |
    pip install hefesto
    hefesto serve &
    sleep 5
    # Your CI tests here
```

### Budget Monitoring

```python
from hefesto import get_budget_tracker

tracker = get_budget_tracker(daily_limit_usd=10.0)

if not tracker.check_budget_available():
    print("⚠️  Budget exceeded, skipping LLM call")
```

## Next Steps

- Review [API Reference](API_REFERENCE.md) for complete endpoint documentation
- Check [Examples](../examples/) for advanced usage
- Read [Architecture](../README.md#architecture) to understand the system

## Troubleshooting

**Server won't start**:
```bash
# Check if port is in use
lsof -i :8080

# Use different port
hefesto serve --port 9000
```

**LLM requests failing**:
```bash
# Verify API key
echo $GEMINI_API_KEY

# Test key
python -c "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); print('✅ Valid')"
```

**Tests failing**:
```bash
# Run specific test
pytest tests/test_suggestion_validator.py -v

# Skip BigQuery tests
pytest -m "not bigquery"
```

---

**Need help?** support@narapa.com

