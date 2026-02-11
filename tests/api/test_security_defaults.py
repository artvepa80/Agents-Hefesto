import pytest
from fastapi.testclient import TestClient

from hefesto.api.main import create_app
from hefesto.config.settings import Settings


@pytest.fixture
def client_factory(monkeypatch):
    """
    Factory that returns a TestClient with specific env vars set via monkeypatch.
    Ensures strict isolation from host environment.
    """

    def _create(env_vars):
        # Explicitly unset critical vars to ensure clean state if not provided
        # This prevents leakage from host environment (e.g. .env or local shell)
        critical_vars = [
            "HEFESTO_EXPOSE_DOCS",
            "HEFESTO_API_KEY",
            "HEFESTO_CORS_ORIGINS",
            "HEFESTO_CORS_ALLOW_CREDENTIALS",
            "HEFESTO_RATE_LIMIT_PER_MINUTE",
            "HEFESTO_WORKSPACE_ROOT",
        ]

        for k in critical_vars:
            monkeypatch.delenv(k, raising=False)

        # Apply requested env vars
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)

        # Force reload settings from the (now monkeypatched) env
        # create_app calls get_settings() -> Settings.from_env()
        # We must bypass the singleton cache if it exists, or just create fresh Settings
        settings = Settings.from_env()

        app = create_app(settings)
        return TestClient(app)

    return _create


def test_docs_disabled_by_default(client_factory):
    # Default: No env vars set (cleaned by factory)
    client = client_factory({})

    # Verify settings are clean
    assert Settings.from_env().expose_docs is False

    r = client.get("/docs")
    assert r.status_code == 404

    r = client.get("/redoc")
    assert r.status_code == 404

    r = client.get("/openapi.json")
    assert r.status_code == 404


def test_docs_enabled_via_env(client_factory):
    client = client_factory({"HEFESTO_EXPOSE_DOCS": "true"})

    r = client.get("/docs")
    assert r.status_code == 200


def test_api_key_enforced_when_set(client_factory):
    client = client_factory({"HEFESTO_API_KEY": "secret123"})

    # Unauthenticated -> 401
    r = client.get(
        "/api/v1/status"
    )  # Assuming valid endpoint exists or middleware catches before 404
    # Note: If endpoint doesn't exist, middleware usually runs first.
    # But if router handles 404, middleware dispatch might vary.
    # Let's rely on middleware returning 401 for ANY path not in bypass.
    if r.status_code == 404:
        # If it returns 404, it might be bypassing auth or auth not blocked.
        # But ApiKeyMiddleware returns 401 if key missing.
        # Let's verify middleware logic: checks path in BYPASS_PATHS.
        # /api/v1/status is NOT in bypass.
        assert r.status_code == 401
    else:
        assert r.status_code == 401

    # With key -> Not 401 (404 is fine if endpoint missing, 200 if present)
    r = client.get("/api/v1/status", headers={"X-API-Key": "secret123"})
    assert r.status_code != 401


def test_health_bypass_auth(client_factory):
    client = client_factory({"HEFESTO_API_KEY": "secret123"})
    r = client.get("/health")
    assert r.status_code == 200


def test_cors_restricts_origins(client_factory):
    client = client_factory(
        {"HEFESTO_CORS_ORIGINS": "https://trusted.com", "HEFESTO_CORS_ALLOW_CREDENTIALS": "false"}
    )

    # Preflight from evil
    r = client.options(
        "/health",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Origin not echoed
    assert (
        "access-control-allow-origin" not in r.headers
        or r.headers["access-control-allow-origin"] != "https://evil.com"
    )

    # Preflight from trusted
    r = client.options(
        "/health",
        headers={
            "Origin": "https://trusted.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers["access-control-allow-origin"] == "https://trusted.com"


def test_path_traversal_blocked(client_factory, tmp_path):
    root = str(tmp_path)
    client = client_factory({"HEFESTO_WORKSPACE_ROOT": root})

    # Simulate POST with path traversal in JSON body
    # Middleware intercepts before routing if body parsing succeeds
    r = client.post(
        "/api/v1/analyze",
        json={"path": "../secrets.txt"},
        headers={"Content-Type": "application/json"},
    )

    assert r.status_code == 403
    assert r.json()["error"] == "path_outside_workspace"


def test_rate_limit(client_factory):
    # Set limit to 1 per minute
    # Note: RateLimitMiddleware might not reset state between tests if using global state?
    # Middleware logic: self._windows = defaultdict(list) inside the middleware instance.
    # New middleware instance is created per app creation (client_factory creates new app).
    # So state should be fresh.

    client = client_factory({"HEFESTO_API_RATE_LIMIT_PER_MINUTE": "1"})

    # First request
    client.get("/health")

    # Second request should fail
    r = client.get("/health")
    assert r.status_code == 429
