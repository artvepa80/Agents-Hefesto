"""
Text Reporter for Terminal Output

Generates formatted text output for the terminal with colors and structure.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

from typing import Any, Dict, List, Optional

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
        lines.append(self._format_summary(report.summary, report.meta))
        lines.append("")

        # Issues by severity
        all_issues = report.get_all_issues()

        if report.summary.critical_issues > 0:
            critical = [i for i in all_issues if i.severity == AnalysisIssueSeverity.CRITICAL]
            lines.append(self._format_severity_section(AnalysisIssueSeverity.CRITICAL, critical))

        if report.summary.high_issues > 0:
            high = [i for i in all_issues if i.severity == AnalysisIssueSeverity.HIGH]
            lines.append(self._format_severity_section(AnalysisIssueSeverity.HIGH, high))

        if report.summary.medium_issues > 0:
            medium = [i for i in all_issues if i.severity == AnalysisIssueSeverity.MEDIUM]
            lines.append(self._format_severity_section(AnalysisIssueSeverity.MEDIUM, medium))

        if report.summary.low_issues > 0:
            low = [i for i in all_issues if i.severity == AnalysisIssueSeverity.LOW]
            lines.append(self._format_severity_section(AnalysisIssueSeverity.LOW, low))

        lines.extend(self._notes_block(report))

        # Footer
        lines.append("")
        lines.append(self._format_footer(report))

        return "\n".join(lines)

    @staticmethod
    def _not_analyzed_lines(meta: Optional[Dict[str, Any]]) -> List[str]:
        """Found files that could not be analyzed (``meta.not_analyzed``)."""
        entries = (meta or {}).get("not_analyzed") or []
        if not entries:
            return []
        from hefesto.core.analyzer_engine import not_analyzed_message

        lines = [f"   Not analyzed: {len(entries)}"]
        lines.extend(f"   - {not_analyzed_message(entry)}" for entry in entries[:10])
        if len(entries) > 10:
            lines.append(f"   ... and {len(entries) - 10} more (see meta.not_analyzed in JSON)")
        return lines

    @staticmethod
    def _fallback_lines(meta: Optional[Dict[str, Any]]) -> List[str]:
        """Files that are not valid UTF-8 and were analyzed after a fallback decode."""
        entries = (meta or {}).get("decoded_with_fallback") or []
        if not entries:
            return []
        encoding = entries[0].get("encoding")
        lines = [f"   Decoded with fallback ({encoding}): {len(entries)}"]
        lines.extend(f"   - {entry.get('path')}" for entry in entries[:10])
        if len(entries) > 10:
            lines.append(
                f"   ... and {len(entries) - 10} more (see meta.decoded_with_fallback in JSON)"
            )
        return lines

    def _format_header(self) -> str:
        """Format report header."""
        bold = self.COLORS["BOLD"]
        reset = self.COLORS["RESET"]
        return f"{bold}🔨 HEFESTO CODE ANALYSIS{reset}\n" "========================"

    def _format_summary(self, summary, meta: Optional[Dict[str, Any]] = None) -> str:
        """Format summary section."""
        bold = self.COLORS["BOLD"]
        reset = self.COLORS["RESET"]
        lines = [f"{bold}📊 Summary:{reset}"]
        lines.append(f"   Files analyzed: {summary.files_analyzed}")
        vendored = (meta or {}).get("vendored_skipped") or {}
        if vendored.get("count"):
            from hefesto.core.analyzer_engine import vendored_skip_message

            lines.append(f"   {vendored_skip_message(vendored['count'])}")
        lines.extend(self._not_analyzed_lines(meta))
        lines.extend(self._fallback_lines(meta))
        lines.append(f"   Issues found: {summary.total_issues}")

        if summary.total_issues > 0:
            critical = self._colorize("CRITICAL", summary.critical_issues)
            lines.append(f"   Critical: {critical}")
            high = self._colorize("HIGH", summary.high_issues)
            lines.append(f"   High: {high}")
            medium = self._colorize("MEDIUM", summary.medium_issues)
            lines.append(f"   Medium: {medium}")
            low = self._colorize("LOW", summary.low_issues)
            lines.append(f"   Low: {low}")

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

        # Issue details (rule id inline when the analyzer set one, e.g. [J001])
        rule = f"[{issue.rule_id}] " if issue.rule_id else ""
        lines.append(f"  ├─ Issue: {rule}{issue.message}")

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

    def _notes_block(self, report: AnalysisReport) -> List[str]:
        notes = self._format_notes(report)
        return ["", notes] if notes else []

    def _format_notes(self, report: AnalysisReport) -> str:
        """Notes that are not findings (e.g. COBOL source format inferred as free)."""
        cobol = (report.meta or {}).get("cobol_format_notices") or {}
        files = cobol.get("inferred_free") or []
        if not files:
            return ""
        bold = self.COLORS["BOLD"]
        reset = self.COLORS["RESET"]
        lines = [f"{bold}ℹ️  Notes:{reset}"]
        lines.append(
            f"   {len(files)} COBOL file(s) read as free format: {cobol.get('message', '')}"
        )
        for path in files[:10]:
            lines.append(f"   - {path}")
        if len(files) > 10:
            lines.append(
                f"   ... and {len(files) - 10} more (see meta.cobol_format_notices in JSON)"
            )
        return "\n".join(lines)

    def _format_footer(self, report: AnalysisReport) -> str:
        """Format report footer."""
        duration = f"{report.summary.duration_seconds:.2f}s"

        lines = ["========================"]

        if report.summary.files_analyzed == 0:
            lines.append(f"⚠️  No files were analyzed. Analysis complete in {duration}")
        elif report.summary.total_issues == 0:
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
