"""SEC-05 regression tests: the HTML report escapes every value it interpolates.

``hefesto analyze --output html`` / ``--save-html`` wrote ``file_path``,
``message`` and ``function_name`` into the page unescaped (only
``suggestion`` was escaped). Those values come from the analyzed repository
(file and directory names, text derived from source code), so a malicious
repo could get script executed in the browser of whoever opened the report
(stored XSS).

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple

import pytest

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
    AnalysisReport,
    AnalysisSummary,
    FileAnalysisResult,
)
from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.reports.html_reporter import HTMLReporter

SCRIPT = "<script>alert(1)</script>"
ATTR_BREAK = '"><img src=x onerror=alert(1)>'
SINGLE_QUOTE_BREAK = "' onmouseover='alert(1)"


class _TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: List[Tuple[str, List[Tuple[str, str | None]]]] = []

    def handle_starttag(self, tag, attrs):  # type: ignore[no-untyped-def]
        self.tags.append((tag, attrs))


def _parse(html: str) -> _TagCollector:
    collector = _TagCollector()
    collector.feed(html)
    return collector


def _report(issues: List[AnalysisIssue]) -> AnalysisReport:
    by_sev = {s: sum(1 for i in issues if i.severity == s) for s in AnalysisIssueSeverity}
    summary = AnalysisSummary(
        files_analyzed=1,
        total_issues=len(issues),
        critical_issues=by_sev.get(AnalysisIssueSeverity.CRITICAL, 0),
        high_issues=by_sev.get(AnalysisIssueSeverity.HIGH, 0),
        medium_issues=by_sev.get(AnalysisIssueSeverity.MEDIUM, 0),
        low_issues=by_sev.get(AnalysisIssueSeverity.LOW, 0),
        total_loc=10,
        duration_seconds=0.01,
    )
    fr = FileAnalysisResult(
        file_path=issues[0].file_path if issues else "x.py",
        issues=issues,
        lines_of_code=10,
        analysis_duration_ms=1.0,
    )
    return AnalysisReport(summary=summary, file_results=[fr])


def _malicious_issue(severity: AnalysisIssueSeverity) -> AnalysisIssue:
    return AnalysisIssue(
        file_path=f"src/{ATTR_BREAK}/{SCRIPT}.py",
        line=3,
        column=7,
        issue_type=AnalysisIssueType.HARDCODED_SECRET,
        severity=severity,
        message=f"Found {SCRIPT} and {SINGLE_QUOTE_BREAK}",
        function_name=f"fn{ATTR_BREAK}",
        suggestion=f"</pre>{SCRIPT}",
    )


@pytest.mark.parametrize("severity", list(AnalysisIssueSeverity))
def test_malicious_fields_are_escaped(severity: AnalysisIssueSeverity) -> None:
    out = HTMLReporter().generate(_report([_malicious_issue(severity)]))

    # The raw payloads never reach the page...
    assert SCRIPT not in out
    assert ATTR_BREAK not in out
    assert SINGLE_QUOTE_BREAK not in out
    assert "</pre><script>" not in out

    # ...they are rendered as text instead.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;" in out
    assert "&#x27; onmouseover=&#x27;alert(1)" in out

    # The parsed document contains no injected elements or event handlers.
    parsed = _parse(out)
    tag_names = {tag for tag, _ in parsed.tags}
    assert "script" not in tag_names
    assert "img" not in tag_names
    for _tag, attrs in parsed.tags:
        for name, _value in attrs:
            assert not name.startswith("on"), f"injected event handler attribute: {name}"


def test_issue_card_markup_is_intact() -> None:
    out = HTMLReporter().generate(_report([_malicious_issue(AnalysisIssueSeverity.CRITICAL)]))
    parsed = _parse(out)
    card_classes = [dict(attrs).get("class") for tag, attrs in parsed.tags if tag == "div"]
    assert "issue-card CRITICAL" in card_classes
    assert "issue-location" in card_classes
    assert "issue-message" in card_classes
    assert "Type:</strong> HARDCODED_SECRET" in out
    assert ":3:7" in out


def test_ampersand_is_escaped_once() -> None:
    issue = AnalysisIssue(
        file_path="a&b.py",
        line=1,
        column=0,
        issue_type=AnalysisIssueType.EVAL_USAGE,
        severity=AnalysisIssueSeverity.HIGH,
        message="x &lt; y",
        suggestion=None,
    )
    out = HTMLReporter().generate(_report([issue]))
    assert "a&amp;b.py:1" in out
    assert "x &amp;lt; y" in out


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, ""),
        (SCRIPT, "&lt;script&gt;alert(1)&lt;/script&gt;"),
        ('a"b', "a&quot;b"),
        ("a'b", "a&#x27;b"),
        ("a&b", "a&amp;b"),
        (42, "42"),
    ],
)
def test_escape_html_helper(value, expected) -> None:  # type: ignore[no-untyped-def]
    assert HTMLReporter._escape_html(value) == expected


def test_end_to_end_directory_name_with_script_tag(tmp_path: Path) -> None:
    """A real finding in a directory literally named ``<script>alert(1)</script>``."""
    target_dir = tmp_path / "<script>alert(1)<" / "script>"
    target_dir.mkdir(parents=True)
    (target_dir / "app.py").write_text("def run(x):\n    return eval(x)\n", encoding="utf-8")

    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    engine.register_analyzer(SecurityAnalyzer())
    report = engine.analyze_path(str(tmp_path))

    issues = report.get_all_issues()
    assert any(SCRIPT in i.file_path for i in issues), issues

    out = HTMLReporter().generate(report)
    assert SCRIPT not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;/app.py" in out
    assert "script" not in {tag for tag, _ in _parse(out).tags}
