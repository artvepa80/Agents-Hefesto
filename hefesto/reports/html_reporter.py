"""
HTML Reporter

Generates interactive HTML reports with basic styling.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

from typing import List

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisReport,
)


class HTMLReporter:
    """Generates HTML reports."""

    def generate(self, report: AnalysisReport) -> str:
        """
        Generate HTML report.

        Args:
            report: AnalysisReport to format

        Returns:
            HTML string
        """
        html_parts = []

        # HTML header
        html_parts.append(self._generate_header())

        # Summary section
        html_parts.append(self._generate_summary(report))

        # Issues by severity
        all_issues = report.get_all_issues()

        if report.summary.critical_issues > 0:
            html_parts.append(
                self._generate_issues_section(
                    AnalysisIssueSeverity.CRITICAL,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.CRITICAL],
                )
            )

        if report.summary.high_issues > 0:
            html_parts.append(
                self._generate_issues_section(
                    AnalysisIssueSeverity.HIGH,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.HIGH],
                )
            )

        if report.summary.medium_issues > 0:
            html_parts.append(
                self._generate_issues_section(
                    AnalysisIssueSeverity.MEDIUM,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.MEDIUM],
                )
            )

        if report.summary.low_issues > 0:
            html_parts.append(
                self._generate_issues_section(
                    AnalysisIssueSeverity.LOW,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.LOW],
                )
            )

        # Footer
        html_parts.append(self._generate_footer(report))

        return "\n".join(html_parts)

    def _generate_header(self) -> str:
        """Generate HTML header with CSS."""
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Hefesto Analysis Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .summary {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .summary-item {
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 5px;
        }
        .summary-value {
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }
        .summary-label {
            color: #666;
            font-size: 14px;
        }
        .severity-section {
            margin: 30px 0;
        }
        .severity-header {
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 20px;
            font-weight: bold;
        }
        .severity-CRITICAL { background: #f44336; color: white; }
        .severity-HIGH { background: #ff9800; color: white; }
        .severity-MEDIUM { background: #2196F3; color: white; }
        .severity-LOW { background: #4CAF50; color: white; }
        .issue-card {
            background: #f9f9f9;
            padding: 20px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #ddd;
        }
        .issue-card.CRITICAL { border-left-color: #f44336; }
        .issue-card.HIGH { border-left-color: #ff9800; }
        .issue-card.MEDIUM { border-left-color: #2196F3; }
        .issue-card.LOW { border-left-color: #4CAF50; }
        .issue-location {
            font-family: monospace;
            color: #666;
            font-size: 14px;
        }
        .issue-message {
            font-size: 16px;
            margin: 10px 0;
            color: #333;
        }
        .issue-suggestion {
            background: #fff;
            padding: 15px;
            margin-top: 10px;
            border-radius: 3px;
            border-left: 3px solid #4CAF50;
        }
        .issue-suggestion-title {
            font-weight: bold;
            color: #4CAF50;
            margin-bottom: 5px;
        }
        pre {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 3px;
            overflow-x: auto;
        }
        .footer {
            text-align: center;
            padding: 20px;
            color: #666;
            border-top: 1px solid #ddd;
            margin-top: 40px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔨 HEFESTO Code Analysis Report</h1>
"""

    def _generate_summary(self, report: AnalysisReport) -> str:
        """Generate summary section."""
        summary = report.summary
        return f"""
        <div class="summary">
            <h2>Summary</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-label">Files Analyzed</div>
                    <div class="summary-value">{summary.files_analyzed}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Total Issues</div>
                    <div class="summary-value">{summary.total_issues}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Critical</div>
                    <div class="summary-value" style="color: #f44336;">
                        {summary.critical_issues}
                    </div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">High</div>
                    <div class="summary-value" style="color: #ff9800;">{summary.high_issues}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Medium</div>
                    <div class="summary-value" style="color: #2196F3;">{summary.medium_issues}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Low</div>
                    <div class="summary-value" style="color: #4CAF50;">{summary.low_issues}</div>
                </div>
            </div>
        </div>
"""

    def _generate_issues_section(
        self, severity: AnalysisIssueSeverity, issues: List[AnalysisIssue]
    ) -> str:
        """Generate section for issues of a specific severity."""
        if not issues:
            return ""

        icon = {"CRITICAL": "🔥", "HIGH": "❌", "MEDIUM": "⚠️", "LOW": "💡"}.get(severity.value, "•")

        html = f"""
        <div class="severity-section">
            <div class="severity-header severity-{severity.value}">
                {icon} {severity.value} Issues ({len(issues)})
            </div>
"""

        for issue in issues:
            html += self._generate_issue_card(issue)

        html += "        </div>\n"
        return html

    def _generate_issue_card(self, issue: AnalysisIssue) -> str:
        """Generate HTML for a single issue."""
        location = f"{issue.file_path}:{issue.line}"
        if issue.column:
            location += f":{issue.column}"

        html = f"""
            <div class="issue-card {issue.severity.value}">
                <div class="issue-location">📄 {location}</div>
                <div class="issue-message">{issue.message}</div>
"""

        if issue.function_name:
            html += f"                <div><strong>Function:</strong> {issue.function_name}</div>\n"

        html += f"                <div><strong>Type:</strong> {issue.issue_type.value}</div>\n"

        if issue.suggestion:
            html += f"""
                <div class="issue-suggestion">
                    <div class="issue-suggestion-title">💡 Suggestion:</div>
                    <pre>{self._escape_html(issue.suggestion)}</pre>
                </div>
"""

        html += "            </div>\n"
        return html

    def _generate_footer(self, report: AnalysisReport) -> str:
        """Generate HTML footer."""
        duration = f"{report.summary.duration_seconds:.2f}s"
        timestamp = report.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        return f"""
        <div class="footer">
            <p>Analysis completed in {duration} at {timestamp}</p>
            <p>Generated by Hefesto AI Code Quality Guardian</p>
            <p>© 2025 Narapa LLC, Miami, Florida</p>
        </div>
    </div>
</body>
</html>
"""

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


__all__ = ["HTMLReporter"]
