# REST API (PRO)

Moved from the README.


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

The API server starts with these defaults:

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
export HEFESTO_RATE_LIMIT_PER_MINUTE=60
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
