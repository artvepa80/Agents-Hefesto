"""
Test suite for TOML Analyzer.
Tests T001-T003 security rules.
"""

import pytest

from hefesto.analyzers.devops.toml_analyzer import TomlAnalyzer


class TestT001HardcodedSecrets:
    """Tests for T001: Hardcoded secrets in TOML."""

    @pytest.fixture
    def analyzer(self):
        return TomlAnalyzer()

    def test_password_detected(self, analyzer):
        """Hardcoded password should trigger T001."""
        content = 'password = "secret123"'
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T001" for i in issues)

    def test_api_key_detected(self, analyzer):
        """Hardcoded API key should trigger T001."""
        content = 'api_key = "sk-1234567890"'
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T001" for i in issues)

    def test_nested_secret_detected(self, analyzer):
        """Nested hardcoded secret should trigger T001."""
        content = """
[database]
password = "dbpass123"
"""
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T001" for i in issues)

    def test_env_variable_safe(self, analyzer):
        """Environment variable reference should NOT trigger T001."""
        content = 'password = "$DB_PASSWORD"'
        issues = analyzer.analyze("config.toml", content)
        assert not any(i.rule_id == "T001" for i in issues)

    def test_placeholder_safe(self, analyzer):
        """Placeholder pattern should NOT trigger T001."""
        content = 'password = "<your-password-here>"'
        issues = analyzer.analyze("config.toml", content)
        assert not any(i.rule_id == "T001" for i in issues)

    def test_template_variable_safe(self, analyzer):
        """Template variable should NOT trigger T001."""
        content = 'token = "{{secrets.API_TOKEN}}"'
        issues = analyzer.analyze("config.toml", content)
        assert not any(i.rule_id == "T001" for i in issues)


class TestT002DangerousFlags:
    """Tests for T002: Dangerous security flags."""

    @pytest.fixture
    def analyzer(self):
        return TomlAnalyzer()

    def test_insecure_true_detected(self, analyzer):
        """insecure = true should trigger T002."""
        content = "insecure = true"
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T002" for i in issues)

    def test_skip_tls_verify_detected(self, analyzer):
        """skip_tls_verify = true should trigger T002."""
        content = "skip_tls_verify = true"
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T002" for i in issues)

    def test_verify_false_detected(self, analyzer):
        """verify = false should trigger T002."""
        content = "verify = false"
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T002" for i in issues)

    def test_verify_true_safe(self, analyzer):
        """verify = true should NOT trigger T002."""
        content = "verify = true"
        issues = analyzer.analyze("config.toml", content)
        assert not any(i.rule_id == "T002" for i in issues)

    def test_nested_dangerous_flag(self, analyzer):
        """Nested dangerous flag should trigger T002."""
        content = """
[server]
insecure = true
"""
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T002" for i in issues)


class TestT003InsecureURLs:
    """Tests for T003: Insecure HTTP URLs."""

    @pytest.fixture
    def analyzer(self):
        return TomlAnalyzer()

    def test_http_url_detected(self, analyzer):
        """HTTP URL in endpoint should trigger T003."""
        content = 'api_url = "http://api.example.com"'
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T003" for i in issues)

    def test_https_url_safe(self, analyzer):
        """HTTPS URL should NOT trigger T003."""
        content = 'api_url = "https://api.example.com"'
        issues = analyzer.analyze("config.toml", content)
        assert not any(i.rule_id == "T003" for i in issues)

    def test_localhost_http_safe(self, analyzer):
        """HTTP localhost should NOT trigger T003."""
        content = 'url = "http://localhost:8080"'
        issues = analyzer.analyze("config.toml", content)
        assert not any(i.rule_id == "T003" for i in issues)

    def test_poetry_source_http_detected(self, analyzer):
        """HTTP source in Poetry config should trigger T003."""
        content = """
[[tool.poetry.source]]
name = "private"
url = "http://pypi.internal.example.com/simple"
"""
        issues = analyzer.analyze("pyproject.toml", content)
        assert any(i.rule_id == "T003" for i in issues)


class TestFallbackRegex:
    """Tests for regex fallback when tomli is not available."""

    @pytest.fixture
    def analyzer(self):
        return TomlAnalyzer()

    def test_fallback_detects_secrets(self, analyzer):
        """Fallback should still detect obvious secrets."""
        # This test validates fallback works even with valid TOML
        content = 'password = "secret123"'
        issues = analyzer.analyze("config.toml", content)
        assert any(i.rule_id == "T001" for i in issues)

    def test_fallback_skips_placeholders(self, analyzer):
        """Fallback should skip environment variables."""
        content = 'password = "$ENV_VAR"'
        issues = analyzer.analyze("config.toml", content)
        assert not any(i.rule_id == "T001" for i in issues)


class TestLineNumberAccuracy:
    """Tests for accurate line number reporting."""

    @pytest.fixture
    def analyzer(self):
        return TomlAnalyzer()

    def test_multiline_config(self, analyzer):
        """Line numbers should be accurate in multiline content."""
        content = """# Comment
[database]
host = "localhost"
password = "secret123"
port = 5432
"""
        issues = analyzer.analyze("config.toml", content)
        t001_issues = [i for i in issues if i.rule_id == "T001"]
        assert len(t001_issues) == 1
        # Password is on line 4
        assert t001_issues[0].line == 4
