# Hefesto API Reference

Complete API documentation for Hefesto v4.7.

## Base URL

```
http://127.0.0.1:8000  (local, default)
https://your-hefesto.run.app  (production)
```

## Authentication

API key authentication is available when `HEFESTO_API_KEY` is set:

```bash
export HEFESTO_API_KEY="your-secret-key"
```

All requests (except `/health`, `/ping`, `/`) must include:
```
X-API-Key: your-secret-key
```

If `HEFESTO_API_KEY` is not set, no authentication is required.

## CORS

Default: Only `http://localhost:*` and `http://127.0.0.1:*` origins allowed.

```bash
# Allow specific origins
export HEFESTO_CORS_ORIGINS="https://app.example.com,https://admin.example.com"
```

## API Documentation

Swagger/Redoc endpoints are **disabled by default**:

```bash
# Enable /docs, /redoc, /openapi.json
export HEFESTO_EXPOSE_DOCS=true
```

---

## Endpoints

### Health & Status

#### `GET /ping`

Ultra-fast health check (<10ms).

**Response 200**:
```json
{
  "ok": true,
  "version": "3.5.0",
  "env": "production",
  "timestamp": "2025-10-20T12:00:00Z"
}
```

#### `GET /readiness`

Kubernetes readiness probe.

**Response 200**:
```json
{
  "ready": true,
  "version": "3.5.0",
  "timestamp": "2025-10-20T12:00:00Z"
}
```

---

### Code Refactoring

#### `POST /suggest/refactor`

Generate intelligent refactoring suggestion.

**Request Body**:
```json
{
  "code": "password = 'hardcoded'",
  "issue": {
    "type": "security",
    "severity": "HIGH",
    "line": 1,
    "description": "Hardcoded password",
    "rule_id": "hardcoded-secret"
  },
  "file_path": "config.py",
  "dry_run": true
}
```

**Response 200**:
```json
{
  "diff": "- password = 'hardcoded'\n+ password = os.environ.get('PASSWORD')",
  "confidence": 0.95,
  "safety_score": 0.85,
  "auto_apply": false,
  "reasoning": "Replaces hardcoded password with environment variable",
  "safety_notes": ["Ensure PASSWORD env var is set"],
  "estimated_fix_time_hours": 0.25,
  "test_recommendations": ["Add test for env var", "Manual review"],
  "validation_passed": true,
  "validation_confidence": 0.95,
  "similarity_score": 0.72,
  "semantic_similarity": 0.88,
  "is_duplicate": false,
  "suggestion_id": "SUG-A1B2C3D4E5F6"
}
```

**Response 400** (Validation Failed):
```json
{
  "error": "ValidationFailed",
  "message": "LLM suggestion failed safety validation",
  "issues": ["Dangerous pattern: eval() detected"],
  "confidence": 0.3
}
```

**Response 429** (Budget Exceeded):
```json
{
  "error": "BudgetExceeded",
  "message": "Daily LLM budget limit reached",
  "current_usage": {
    "cost_usd": 10.50,
    "limit_usd": 10.0,
    "remaining_usd": 0.0
  }
}
```

---

### Feedback

#### `POST /feedback/suggestion`

Submit user feedback on a suggestion.

**Request Body**:
```json
{
  "suggestion_id": "SUG-A1B2C3D4E5F6",
  "accepted": true,
  "applied_successfully": true,
  "time_to_apply_seconds": 45,
  "user_comment": "Worked perfectly!"
}
```

**Response 200**:
```json
{
  "success": true,
  "message": "Feedback recorded successfully",
  "suggestion_id": "SUG-A1B2C3D4E5F6",
  "accepted": true
}
```

#### `GET /feedback/metrics`

Get suggestion acceptance rates.

**Query Parameters**:
- `issue_type` (optional): Filter by issue type
- `severity` (optional): Filter by severity
- `days` (default: 30): Number of days to include

**Response 200**:
```json
{
  "total": 150,
  "accepted": 112,
  "rejected": 25,
  "pending": 13,
  "acceptance_rate": 0.817,
  "avg_confidence": 0.85,
  "avg_similarity": 0.72,
  "avg_time_to_apply": 45.3
}
```

---

### Budget

#### `GET /budget/usage`

Get budget usage for a period.

**Query Parameters**:
- `period` (default: "today"): "today", "month", "7d", "30d"

**Response 200**:
```json
{
  "period": "Today",
  "request_count": 42,
  "total_tokens": 125000,
  "estimated_cost_usd": 0.35,
  "budget_limit_usd": 10.0,
  "budget_remaining_usd": 9.65,
  "budget_utilization_pct": 3.5
}
```

#### `GET /budget/check`

Check if budget available.

**Query Parameters**:
- `period` (default: "today"): "today" or "month"

**Response 200**:
```json
{
  "budget_available": true,
  "status": {
    "level": "OK",
    "message": "Budget OK (15.5% used)",
    "utilization_pct": 15.5,
    "cost_usd": 1.55,
    "limit_usd": 10.0,
    "remaining_usd": 8.45
  },
  "current_usage": {
    "period": "Today",
    "request_count": 28,
    "total_tokens": 87500,
    "estimated_cost_usd": 1.55
  }
}
```

---

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 400 | Bad Request | Check request body format |
| 401 | Unauthorized | Missing or invalid API key |
| 429 | Rate Limit Exceeded | Too many requests, try again later |
| 500 | Internal Error | Check logs, report bug |
| 503 | Service Unavailable | Check GEMINI_API_KEY is set |

---

## Rate Limits

Rate limiting uses a sliding-window algorithm, keyed by API key (if set) or client IP.

```bash
# Enable with 60 requests per minute
export HEFESTO_API_RATE_LIMIT_PER_MINUTE=60
```

When enabled, exceeding the limit returns `429 Too Many Requests`:
```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

Set to `0` (default) to disable rate limiting.

---

## Python SDK

### Initialize Client

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# Health check
response = client.get("/ping")
print(response.json())
```

### Suggest Refactoring

```python
response = client.post("/suggest/refactor", json={
    "code": "API_KEY = 'sk-test'",
    "issue": {
        "type": "security",
        "severity": "HIGH",
        "line": 1,
        "description": "Hardcoded API key"
    },
    "file_path": "config.py"
})

suggestion = response.json()
print(f"Confidence: {suggestion['confidence']}")
print(f"Diff:\n{suggestion['diff']}")
```

---

For more examples, see the [examples/](../examples/) directory.

