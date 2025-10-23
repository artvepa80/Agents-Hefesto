"""
Text Reporter for Terminal Output

Generates formatted text output for the terminal with colors and structure.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

from typing import Dict, List

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisReport,
)


class TextReporter:
    """Generates formatted text reports for terminal display."""

    # ANSI color codes
    COLORS = {
        "CRITICAL": "\033[91m",  # Red
        "HIGH": "\033[93m",  # Yellow
        "MEDIUM": "\033[94m",  # Blue
        "LOW": "\033[92m",  # Green
        "RESET": "\033[0m",  # Reset
        "BOLD": "\033[1m",  # Bold
    }

    # Severity icons
    ICONS = {
        AnalysisIssueSeverity.CRITICAL: "🔥",
        AnalysisIssueSeverity.HIGH: "❌",
        AnalysisIssueSeverity.MEDIUM: "⚠️",
        AnalysisIssueSeverity.LOW: "💡",
    }

    def generate(self, report: AnalysisReport) -> str:
        """
        Generate formatted text report.

        Args:
            report: AnalysisReport to format

        Returns:
            Formatted text string
        """
        lines = []

        # Header
        lines.append(self._format_header())
        lines.append("")

        # Summary
        lines.append(self._format_summary(report.summary))
        lines.append("")

        # Issues by severity
        all_issues = report.get_all_issues()

        if report.summary.critical_issues > 0:
            lines.append(
                self._format_severity_section(
                    AnalysisIssueSeverity.CRITICAL,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.CRITICAL],
                )
            )

        if report.summary.high_issues > 0:
            lines.append(
                self._format_severity_section(
                    AnalysisIssueSeverity.HIGH,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.HIGH],
                )
            )

        if report.summary.medium_issues > 0:
            lines.append(
                self._format_severity_section(
                    AnalysisIssueSeverity.MEDIUM,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.MEDIUM],
                )
            )

        if report.summary.low_issues > 0:
            lines.append(
                self._format_severity_section(
                    AnalysisIssueSeverity.LOW,
                    [i for i in all_issues if i.severity == AnalysisIssueSeverity.LOW],
                )
            )

        # Footer
        lines.append("")
        lines.append(self._format_footer(report))

        return "\n".join(lines)

    def _format_header(self) -> str:
        """Format report header."""
        return (
            f"{self.COLORS['BOLD']}🔨 HEFESTO CODE ANALYSIS{self.COLORS['RESET']}\n"
            "========================"
        )

    def _format_summary(self, summary) -> str:
        """Format summary section."""
        lines = [f"{self.COLORS['BOLD']}📊 Summary:{self.COLORS['RESET']}"]
        lines.append(f"   Files analyzed: {summary.files_analyzed}")
        lines.append(f"   Issues found: {summary.total_issues}")

        if summary.total_issues > 0:
            lines.append(f"   Critical: {self._colorize('CRITICAL', summary.critical_issues)}")
            lines.append(f"   High: {self._colorize('HIGH', summary.high_issues)}")
            lines.append(f"   Medium: {self._colorize('MEDIUM', summary.medium_issues)}")
            lines.append(f"   Low: {self._colorize('LOW', summary.low_issues)}")

        return "\n".join(lines)

    def _format_severity_section(
        self, severity: AnalysisIssueSeverity, issues: List[AnalysisIssue]
    ) -> str:
        """Format a section for a specific severity level."""
        if not issues:
            return ""

        icon = self.ICONS.get(severity, "•")
        color = self.COLORS.get(severity.value, "")
        reset = self.COLORS["RESET"]

        lines = [
            "",
            f"{color}{icon} {severity.value} Issues ({len(issues)}):{reset}",
            "",
        ]

        for issue in issues:
            lines.append(self._format_issue(issue))
            lines.append("")

        return "\n".join(lines)

    def _format_issue(self, issue: AnalysisIssue) -> str:
        """Format a single issue."""
        lines = []

        # File and location
        location = f"{issue.file_path}:{issue.line}"
        if issue.column:
            location += f":{issue.column}"
        lines.append(f"  📄 {location}")

        # Issue details
        lines.append(f"  ├─ Issue: {issue.message}")

        if issue.function_name:
            lines.append(f"  ├─ Function: {issue.function_name}")

        lines.append(f"  ├─ Type: {issue.issue_type.value}")
        lines.append(f"  ├─ Severity: {issue.severity.value}")

        # Suggestion
        if issue.suggestion:
            suggestion_lines = issue.suggestion.split("\n")
            lines.append(f"  └─ Suggestion: {suggestion_lines[0]}")
            for sug_line in suggestion_lines[1:]:
                lines.append(f"     {sug_line}")

        return "\n".join(lines)

    def _format_footer(self, report: AnalysisReport) -> str:
        """Format report footer."""
        duration = f"{report.summary.duration_seconds:.2f}s"

        lines = ["========================"]

        if report.summary.total_issues == 0:
            lines.append(f"✅ No issues found! Analysis complete in {duration}")
        else:
            lines.append(f"✅ Analysis complete in {duration}")

        return "\n".join(lines)

    def _colorize(self, severity: str, value: int) -> str:
        """Colorize a value based on severity."""
        color = self.COLORS.get(severity, "")
        reset = self.COLORS["RESET"]
        return f"{color}{value}{reset}"


__all__ = ["TextReporter"]
