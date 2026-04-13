"""Tests for NarrowSemanticAnalyzer — Phase 4.

Covers:
- Check 1 (ATTRIBUTE_NAME_MISMATCH): typo detection via difflib
- Check 2 (SILENT_EXCEPTION_SWALLOW): broad except with trivially silent body
- Precision: no false positives on clean code, dynamic attrs, bare except
- Canary: dogfood on hefesto/ codebase
"""

import textwrap
from pathlib import Path

import pytest

from hefesto.analyzers.narrow_semantic import NarrowSemanticAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTree:
    """Minimal stand-in for GenericAST — only ``language`` is read."""

    def __init__(self, language: str = "python"):
        self.language = language


def _run(code: str, language: str = "python"):
    """Analyze ``code`` and return the list of AnalysisIssue."""
    analyzer = NarrowSemanticAnalyzer()
    tree = _FakeTree(language)
    return analyzer.analyze(tree, "test.py", textwrap.dedent(code))


# ===================================================================
# Check 1 — ATTRIBUTE_NAME_MISMATCH
# ===================================================================


class TestAttributeNameMismatch:
    """Tests for NS-ATTR-001."""

    def test_simple_typo(self):
        code = """\
        class Foo:
            def __init__(self):
                self.counter = 0

            def increment(self):
                self.conter += 1
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 1
        assert "conter" in attr_issues[0].message
        assert "counter" in attr_issues[0].message
        assert attr_issues[0].rule_id == "NS-ATTR-001"

    def test_no_false_positive_on_correct_attrs(self):
        code = """\
        class Foo:
            def __init__(self):
                self.name = ""
                self.value = 0

            def get_name(self):
                return self.name

            def get_value(self):
                return self.value
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_attr_set_outside_init(self):
        """Attributes set in other methods should not cause FPs."""
        code = """\
        class Foo:
            def __init__(self):
                self.name = ""

            def setup(self):
                self.extra = 42

            def run(self):
                return self.extra
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_skip_class_with_getattr(self):
        code = """\
        class Dynamic:
            def __init__(self):
                self.data = {}

            def __getattr__(self, name):
                return self.data.get(name)

            def run(self):
                return self.dta
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_skip_class_with_setattr_call(self):
        code = """\
        class Dynamic:
            def __init__(self):
                self.items = []

            def add(self, key, val):
                setattr(self, key, val)

            def run(self):
                return self.itmes
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_skip_class_with_dict_access(self):
        code = """\
        class Dynamic:
            def __init__(self):
                self.x = 1

            def from_kwargs(self, **kw):
                self.__dict__.update(kw)

            def run(self):
                return self.y
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_no_init_means_no_findings(self):
        code = """\
        class NoInit:
            def run(self):
                return self.whatever
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_distant_names_no_match(self):
        """Names too distant from any init attr should not trigger."""
        code = """\
        class Foo:
            def __init__(self):
                self.alpha = 1

            def run(self):
                return self.zebra
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_annotated_assign_in_init(self):
        """Annotated assignments (self.x: int = 0) should be collected."""
        code = """\
        class Foo:
            def __init__(self):
                self.counter: int = 0

            def run(self):
                return self.conter
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 1

    def test_severity_is_medium(self):
        code = """\
        class Foo:
            def __init__(self):
                self.counter = 0

            def run(self):
                return self.conter
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert attr_issues[0].severity.value == "MEDIUM"

    def test_property_not_flagged(self):
        """@property exposes self.<name> as a valid attribute."""
        code = """\
        class Client:
            def __init__(self):
                self._timeout = 30

            @property
            def timeout(self):
                return self._timeout

            def get_timeout(self):
                return self.timeout
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_property_with_setter_not_flagged(self):
        """Properties with setters should also be valid."""
        code = """\
        class Config:
            def __init__(self):
                self._encoding = "utf-8"

            @property
            def encoding(self):
                return self._encoding

            @encoding.setter
            def encoding(self, value):
                self._encoding = value

            def display(self):
                return self.encoding
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_custom_decorator_not_flagged(self):
        """Custom decorators like @reify, @cached_property should be valid."""
        code = """\
        class Request:
            def __init__(self):
                self._headers = {}

            @reify
            def headers(self):
                return self._headers

            def get_host(self):
                return self.headers.get("Host")
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_method_reference_as_callback_not_flagged(self):
        """self.method passed as callback (not called) should not flag."""
        code = """\
        class WebSocket:
            def __init__(self, loop):
                self._loop = loop
                self._heartbeat_when = 0
                self._heartbeat_cb = loop.call_at(0, self._send_heartbeat)

            def _send_heartbeat(self):
                self._heartbeat_cb = self._loop.call_at(
                    self._heartbeat_when, self._send_heartbeat
                )
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 0

    def test_real_typo_still_caught(self):
        """Methods don't suppress real typos on data attributes."""
        code = """\
        class Counter:
            def __init__(self):
                self.request_count = 0

            def increment(self):
                self.reqeust_count += 1
        """
        issues = _run(code)
        attr_issues = [
            i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH
        ]
        assert len(attr_issues) == 1
        assert "reqeust_count" in attr_issues[0].message


# ===================================================================
# Check 2 — SILENT_EXCEPTION_SWALLOW
# ===================================================================


class TestSilentExceptionSwallow:
    """Tests for NS-SWALLOW-001."""

    def test_except_exception_pass(self):
        code = """\
        try:
            do_something()
        except Exception:
            pass
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1
        assert "Exception" in swallow[0].message
        assert swallow[0].rule_id == "NS-SWALLOW-001"

    def test_except_base_exception_return_none(self):
        code = """\
        def foo():
            try:
                return compute()
            except BaseException:
                return None
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1
        assert "BaseException" in swallow[0].message

    def test_except_exception_return_empty_list(self):
        code = """\
        def foo():
            try:
                return get_items()
            except Exception:
                return []
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1

    def test_except_exception_return_empty_dict(self):
        code = """\
        def foo():
            try:
                return load_config()
            except Exception:
                return {}
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1

    def test_except_exception_return_zero(self):
        code = """\
        def foo():
            try:
                return count()
            except Exception:
                return 0
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1

    def test_except_exception_return_false(self):
        code = """\
        def foo():
            try:
                return check()
            except Exception:
                return False
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1

    def test_bare_except_not_flagged(self):
        """Bare except is BARE_EXCEPT territory — no duplicate."""
        code = """\
        try:
            do_something()
        except:
            pass
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 0

    def test_specific_exception_not_flagged(self):
        """Catching ValueError: pass is intentional and narrow — no flag."""
        code = """\
        try:
            int("abc")
        except ValueError:
            pass
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 0

    def test_exception_with_logging_not_flagged(self):
        """Handler that logs is not trivially silent."""
        code = """\
        import logging
        logger = logging.getLogger(__name__)

        try:
            do_something()
        except Exception as e:
            logger.error("Failed: %s", e)
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 0

    def test_exception_with_reraise_not_flagged(self):
        code = """\
        try:
            do_something()
        except Exception:
            raise
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 0

    def test_multi_statement_body_not_flagged(self):
        """If the body has >1 statement, it's not trivially silent."""
        code = """\
        def foo():
            try:
                do_something()
            except Exception:
                x = 1
                return None
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 0

    def test_tuple_exception_with_broad(self):
        """except (ValueError, Exception): pass → flagged (Exception is broad)."""
        code = """\
        try:
            do_something()
        except (ValueError, Exception):
            pass
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1

    def test_severity_is_medium(self):
        code = """\
        try:
            do_something()
        except Exception:
            pass
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert swallow[0].severity.value == "MEDIUM"

    def test_return_empty_string(self):
        code = """\
        def foo():
            try:
                return read()
            except Exception:
                return ""
        """
        issues = _run(code)
        swallow = [i for i in issues if i.issue_type == AnalysisIssueType.SILENT_EXCEPTION_SWALLOW]
        assert len(swallow) == 1


# ===================================================================
# Cross-cutting
# ===================================================================


class TestCrossCutting:
    """Non-Python files, syntax errors, etc."""

    def test_non_python_skipped(self):
        issues = _run("function foo() { return 1; }", language="javascript")
        assert len(issues) == 0

    def test_syntax_error_skipped(self):
        issues = _run("def broken(:\n")
        assert len(issues) == 0

    def test_empty_code_skipped(self):
        issues = _run("")
        assert len(issues) == 0


# ===================================================================
# Canary — dogfood on hefesto/ codebase
# ===================================================================


class TestCanary:
    """Run the analyzer on a real Hefesto source file to catch regressions."""

    def test_dogfood_security_analyzer(self):
        """SecurityAnalyzer is a real file with classes — must not crash
        or produce spurious ATTRIBUTE_NAME_MISMATCH findings."""
        repo_root = Path(__file__).resolve().parent.parent
        target = repo_root / "hefesto" / "analyzers" / "security.py"
        if not target.exists():
            pytest.skip("security.py not found — running outside repo")

        code = target.read_text(encoding="utf-8")
        issues = _run(code)

        # No attribute-mismatch FPs on a clean, passing codebase
        attr_fps = [i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH]
        assert len(attr_fps) == 0, (
            f"Unexpected ATTRIBUTE_NAME_MISMATCH on security.py: "
            f"{[i.message for i in attr_fps]}"
        )

    def test_dogfood_analyzer_engine(self):
        """analyzer_engine.py is a large file — must not crash."""
        repo_root = Path(__file__).resolve().parent.parent
        target = repo_root / "hefesto" / "core" / "analyzer_engine.py"
        if not target.exists():
            pytest.skip("analyzer_engine.py not found")

        code = target.read_text(encoding="utf-8")
        issues = _run(code)

        attr_fps = [i for i in issues if i.issue_type == AnalysisIssueType.ATTRIBUTE_NAME_MISMATCH]
        assert len(attr_fps) == 0, (
            f"Unexpected ATTRIBUTE_NAME_MISMATCH on analyzer_engine.py: "
            f"{[i.message for i in attr_fps]}"
        )
