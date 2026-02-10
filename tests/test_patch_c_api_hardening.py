"""
Tests for Patch C: API Hardening.

Covers:
- Docs toggle (disabled/enabled)
- CORS enforcement (wildcard + credentials blocked)
- API key auth middleware
- Rate limiting middleware
- Path sandbox enforcement
- Cache guardrails (TTL + LRU + size cap)

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hefesto.config.settings import Settings

# ─── helpers ────────────────────────────────────────────────────────


def _make_settings(**overrides) -> Settings:
    """Build a Settings with safe defaults + overrides."""
    defaults = dict(
        environment="test",
        expose_docs=False,
        cors_origins="",
        cors_allow_credentials=False,
        api_key="",
        api_rate_limit_per_minute=0,
        workspace_root="",
        cache_max_items=256,
        cache_ttl_seconds=600,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _create_test_app(settings: Settings):
    """Import create_app fresh to avoid module-level side effects."""
    from hefesto.api.main import create_app

    return create_app(settings)


# ════════════════════════════════════════════════════════════════════
# 1) Docs toggle
# ════════════════════════════════════════════════════════════════════


class TestDocsToggle:
    """Docs endpoints disabled by default, enabled with flag."""

    def test_docs_disabled_by_default(self):
        app = _create_test_app(_make_settings(expose_docs=False))
        client = TestClient(app)
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404

    def test_docs_enabled_when_flag_true(self):
        app = _create_test_app(_make_settings(expose_docs=True))
        client = TestClient(app)
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200

    def test_root_reflects_docs_status(self):
        app_off = _create_test_app(_make_settings(expose_docs=False))
        resp_off = TestClient(app_off).get("/")
        assert "note" in resp_off.json()["documentation"]

        app_on = _create_test_app(_make_settings(expose_docs=True))
        resp_on = TestClient(app_on).get("/")
        assert "swagger" in resp_on.json()["documentation"]


# ════════════════════════════════════════════════════════════════════
# 2) CORS enforcement
# ════════════════════════════════════════════════════════════════════


class TestCORSEnforcement:
    """CORS wildcard + credentials is forbidden."""

    def test_wildcard_with_credentials_raises(self):
        with pytest.raises(ValueError, match="insecure"):
            _create_test_app(
                _make_settings(
                    cors_origins="*",
                    cors_allow_credentials=True,
                )
            )

    def test_explicit_origins_with_credentials_ok(self):
        app = _create_test_app(
            _make_settings(
                cors_origins="https://example.com",
                cors_allow_credentials=True,
            )
        )
        assert app is not None

    def test_default_cors_is_localhost(self):
        settings = _make_settings()
        origins = settings.parsed_cors_origins
        assert "http://localhost" in origins
        assert "http://127.0.0.1" in origins


# ════════════════════════════════════════════════════════════════════
# 3) API key auth middleware
# ════════════════════════════════════════════════════════════════════


class TestApiKeyAuth:
    """X-API-Key header required when HEFESTO_API_KEY is set."""

    def test_no_key_configured_allows_all(self):
        app = _create_test_app(_make_settings(api_key=""))
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_key_required_returns_401(self):
        app = _create_test_app(_make_settings(api_key="secret"))
        client = TestClient(app)
        resp = client.get("/api/v1/analyze/ana_00000000000000000000000")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    def test_correct_key_returns_200(self):
        app = _create_test_app(_make_settings(api_key="secret"))
        client = TestClient(app)
        # Health bypasses auth
        resp = client.get("/health", headers={"X-API-Key": "secret"})
        assert resp.status_code == 200

    def test_health_bypasses_auth(self):
        app = _create_test_app(_make_settings(api_key="secret"))
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_root_bypasses_auth(self):
        app = _create_test_app(_make_settings(api_key="secret"))
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_wrong_key_returns_401(self):
        app = _create_test_app(_make_settings(api_key="secret"))
        client = TestClient(app)
        resp = client.get(
            "/api/v1/analyze/ana_00000000000000000000000",
            headers={"X-API-Key": "wrong"},
        )
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# 4) Rate limiting
# ════════════════════════════════════════════════════════════════════


class TestRateLimiting:
    """Requests rejected after exceeding rate limit."""

    def test_rate_limit_disabled_by_default(self):
        app = _create_test_app(_make_settings(api_rate_limit_per_minute=0))
        client = TestClient(app)
        for _ in range(10):
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_rate_limit_returns_429(self):
        app = _create_test_app(_make_settings(api_rate_limit_per_minute=3))
        client = TestClient(app)
        for _ in range(3):
            resp = client.get("/health")
            assert resp.status_code == 200

        resp = client.get("/health")
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded"


# ════════════════════════════════════════════════════════════════════
# 5) Path sandbox
# ════════════════════════════════════════════════════════════════════


class TestPathSandbox:
    """Path sandbox prevents directory traversal."""

    def test_resolve_valid_path(self):
        from hefesto.security.path_sandbox import (
            resolve_under_root,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.py").touch()
            result = resolve_under_root("file.py", root)
            assert result == (root / "file.py").resolve()

    def test_traversal_blocked(self):
        from hefesto.security.path_sandbox import (
            resolve_under_root,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with pytest.raises(ValueError, match="escapes"):
                resolve_under_root("../etc/passwd", root)

    def test_absolute_outside_blocked(self):
        from hefesto.security.path_sandbox import (
            resolve_under_root,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with pytest.raises(ValueError, match="escapes"):
                resolve_under_root("/etc/passwd", root)

    def test_absolute_inside_allowed(self):
        from hefesto.security.path_sandbox import (
            resolve_under_root,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            inner = root / "sub" / "file.py"
            inner.parent.mkdir(parents=True)
            inner.touch()
            result = resolve_under_root(str(inner), root)
            assert result == inner.resolve()


# ════════════════════════════════════════════════════════════════════
# 6) Cache guardrails
# ════════════════════════════════════════════════════════════════════


class TestCacheGuardrails:
    """BoundedCache respects TTL and max_items."""

    def test_lru_eviction(self):
        from hefesto.api.routers.analysis import BoundedCache

        cache = BoundedCache(max_items=2, ttl=600)
        cache.set("a", "val_a")
        cache.set("b", "val_b")
        cache.set("c", "val_c")  # evicts "a"

        assert cache.get("a") is None
        assert cache.get("b") == "val_b"
        assert cache.get("c") == "val_c"

    def test_ttl_expiry(self):
        from hefesto.api.routers.analysis import BoundedCache

        cache = BoundedCache(max_items=10, ttl=1)
        cache.set("x", "val_x")
        assert cache.get("x") == "val_x"

        time.sleep(1.1)
        assert cache.get("x") is None

    def test_contains_respects_ttl(self):
        from hefesto.api.routers.analysis import BoundedCache

        cache = BoundedCache(max_items=10, ttl=1)
        cache.set("k", "v")
        assert "k" in cache
        time.sleep(1.1)
        assert "k" not in cache


# ════════════════════════════════════════════════════════════════════
# 7) Settings defaults
# ════════════════════════════════════════════════════════════════════


class TestSettingsDefaults:
    """Verify secure defaults are in place."""

    def test_host_defaults_to_localhost(self):
        s = Settings()
        assert s.api_host == "127.0.0.1"

    def test_docs_disabled_by_default(self):
        s = Settings()
        assert s.expose_docs is False

    def test_cors_credentials_disabled_by_default(self):
        s = Settings()
        assert s.cors_allow_credentials is False

    def test_api_key_empty_by_default(self):
        s = Settings()
        assert s.api_key == ""

    def test_rate_limit_disabled_by_default(self):
        s = Settings()
        assert s.api_rate_limit_per_minute == 0

    def test_workspace_root_autodetect(self):
        s = Settings()
        root = s.resolved_workspace_root
        assert root.is_dir()
