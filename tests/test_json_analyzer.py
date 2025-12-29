"""
Test suite for JSON and TOML Analyzers.
"""

import pytest

from hefesto.analyzers.devops.json_analyzer import JsonAnalyzer


class TestJ001HardcodedSecrets:
    """Tests for J001: Hardcoded secrets in JSON."""

    @pytest.fixture
    def analyzer(self):
        return JsonAnalyzer()

    def test_password_detected(self, analyzer):
        """Hardcoded password should trigger J001."""
        content = '{"password": "secret123"}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J001" for i in issues)

    def test_api_key_detected(self, analyzer):
        """Hardcoded API key should trigger J001."""
        content = '{"api_key": "sk-1234567890"}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J001" for i in issues)

    def test_token_detected(self, analyzer):
        """Hardcoded token should trigger J001."""
        content = '{"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J001" for i in issues)

    def test_nested_secret_detected(self, analyzer):
        """Nested hardcoded secret should trigger J001."""
        content = '{"database": {"password": "dbpass123"}}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J001" for i in issues)

    def test_env_variable_safe(self, analyzer):
        """Environment variable reference should NOT trigger J001."""
        content = '{"password": "$DB_PASSWORD"}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J001" for i in issues)

    def test_env_variable_braces_safe(self, analyzer):
        """Environment variable with braces should NOT trigger J001."""
        content = '{"password": "${DB_PASSWORD}"}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J001" for i in issues)

    def test_placeholder_safe(self, analyzer):
        """Placeholder pattern should NOT trigger J001."""
        content = '{"password": "<your-password-here>"}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J001" for i in issues)

    def test_template_variable_safe(self, analyzer):
        """Template variable should NOT trigger J001."""
        content = '{"token": "{{secrets.API_TOKEN}}"}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J001" for i in issues)


class TestJ002InsecureURLs:
    """Tests for J002: Insecure HTTP URLs."""

    @pytest.fixture
    def analyzer(self):
        return JsonAnalyzer()

    def test_http_url_detected(self, analyzer):
        """HTTP URL in endpoint should trigger J002."""
        content = '{"api_url": "http://api.example.com"}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J002" for i in issues)

    def test_https_url_safe(self, analyzer):
        """HTTPS URL should NOT trigger J002."""
        content = '{"api_url": "https://api.example.com"}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J002" for i in issues)

    def test_localhost_http_safe(self, analyzer):
        """HTTP localhost should NOT trigger J002."""
        content = '{"url": "http://localhost:8080"}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J002" for i in issues)


class TestJ004DockerCreds:
    """Tests for J004: Docker registry credentials."""

    @pytest.fixture
    def analyzer(self):
        return JsonAnalyzer()

    def test_docker_auth_detected(self, analyzer):
        """Docker config.json auth should trigger J004."""
        content = """{
            "auths": {
                "https://index.docker.io/v1/": {
                    "auth": "dXNlcm5hbWU6cGFzc3dvcmQ="
                }
            }
        }"""
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J004" for i in issues)

    def test_no_auth_safe(self, analyzer):
        """Docker config without auth should NOT trigger J004."""
        content = '{"auths": {}}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J004" for i in issues)


class TestJ005DangerousFlags:
    """Tests for J005: Dangerous security flags."""

    @pytest.fixture
    def analyzer(self):
        return JsonAnalyzer()

    def test_insecure_true_detected(self, analyzer):
        """insecure: true should trigger J005."""
        content = '{"insecure": true}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J005" for i in issues)

    def test_skip_tls_verify_detected(self, analyzer):
        """skipTlsVerify: true should trigger J005."""
        content = '{"skipTlsVerify": true}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J005" for i in issues)

    def test_verify_false_detected(self, analyzer):
        """verify: false should trigger J005."""
        content = '{"verify": false}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J005" for i in issues)

    def test_verify_true_safe(self, analyzer):
        """verify: true should NOT trigger J005."""
        content = '{"verify": true}'
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J005" for i in issues)

    def test_node_tls_reject_detected(self, analyzer):
        """NODE_TLS_REJECT_UNAUTHORIZED: 0 should trigger J005."""
        content = '{"NODE_TLS_REJECT_UNAUTHORIZED": "0"}'
        issues = analyzer.analyze("config.json", content)
        assert any(i.rule_id == "J005" for i in issues)


class TestFallbackRegex:
    """Tests for regex fallback on invalid JSON."""

    @pytest.fixture
    def analyzer(self):
        return JsonAnalyzer()

    def test_invalid_json_fallback(self, analyzer):
        """Should use regex fallback for invalid JSON."""
        content = '{"password": "secret123"'  # Missing closing brace
        issues = analyzer.analyze("config.json", content)
        # Should still detect the secret with lower confidence
        assert any(i.rule_id == "J001" for i in issues)

    def test_fallback_skips_placeholders(self, analyzer):
        """Regex fallback should skip placeholders."""
        content = '{"password": "$ENV_VAR"'  # Invalid JSON + placeholder
        issues = analyzer.analyze("config.json", content)
        assert not any(i.rule_id == "J001" for i in issues)
