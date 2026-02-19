"""
Hefesto Analyzer Engine (Community Edition)

Main orchestration engine for code analysis.
Coordinates multiple analyzers with validation.

Pipeline:
1. Static Analysis: Run all analyzers (complexity, smells, security, best practices)
2. Validation: Filter by severity threshold
3. Report: Generate analysis report

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import time
from pathlib import Path
from typing import Any, List, Optional

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisReport,
    AnalysisSummary,
    FileAnalysisResult,
)
from hefesto.core.language_detector import Language, LanguageDetector
from hefesto.core.languages.registry import get_registry
from hefesto.core.parsers.parser_factory import ParserFactory

# Directories excluded by default to avoid noise from vendored/generated code.
# Users can add more via --exclude; these are always applied unless --no-default-excludes.
DEFAULT_EXCLUDES = [
    ".venv/",
    "venv/",
    ".tox/",
    "node_modules/",
    ".git/",
    "__pycache__/",
    "dist/",
    "build/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".eggs/",
    ".egg-info/",
]


class AnalyzerEngine:
    """Main analysis engine that orchestrates all analyzers."""

    def __init__(
        self,
        severity_threshold: str = "MEDIUM",
        verbose: bool = False,
    ):
        """
        Initialize analyzer engine.

        Args:
            severity_threshold: Minimum severity level to report (LOW/MEDIUM/HIGH/CRITICAL)
            verbose: Print detailed pipeline steps (default: False)
        """
        self.severity_threshold = AnalysisIssueSeverity(severity_threshold)
        self.analyzers: List[Any] = []
        self.verbose = verbose
        self._registry = get_registry()
        self.source_cache: dict = {}  # ML Enhancement: cache source for semantic analysis

    def register_analyzer(self, analyzer):
        """Register an analyzer instance."""
        self.analyzers.append(analyzer)

    def analyze_path(
        self, path: str, exclude_patterns: Optional[List[str]] = None
    ) -> AnalysisReport:
        """
        Analyze a file or directory with complete Phase 0+1 pipeline.

        Args:
            path: File or directory path to analyze
            exclude_patterns: List of patterns to exclude (e.g., ["tests/", "docs/"])

        Returns:
            AnalysisReport with all findings
        """
        start_time = time.time()

        if self.verbose:
            print("\n HEFESTO ANALYSIS PIPELINE")
            print("=" * 50)
            print()

        # Find supported files
        path_obj = Path(path)
        source_files = self._find_files(path_obj, exclude_patterns or [])

        if self.verbose:
            print(f"📁 Found {len(source_files)} file(s)")
            print()

        # STEP 1: Run static analyzers
        if self.verbose:
            print("Running static analyzers...")

        file_results = []
        all_issues = []

        for py_file in source_files:
            file_result = self._analyze_file(py_file)
            if file_result:
                file_results.append(file_result)
                all_issues.extend(file_result.issues)

        if self.verbose:
            print(f"   Found {len(all_issues)} potential issue(s)")
            print()

        # Calculate final statistics
        duration = time.time() - start_time
        summary = self._create_summary(file_results, duration)

        # Create report with metadata
        report = AnalysisReport(summary=summary, file_results=file_results)

        if self.verbose:
            print("Analysis complete!")
            print(f"   Duration: {duration:.2f}s")
            print()

        return report

    def _find_files(self, path: Path, exclude_patterns: List[str]) -> List[Path]:
        """Find all supported files in the given path."""
        # Merge default excludes with user-provided patterns
        all_excludes = list(DEFAULT_EXCLUDES) + list(exclude_patterns)

        def excluded(p: Path) -> bool:
            sp = str(p)
            return any(pattern in sp for pattern in all_excludes)

        # If a single file is provided, evaluate support with shebang-aware detection.
        if path.is_file():
            try:
                txt = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                txt = None
            return [path] if LanguageDetector.is_supported(path, txt) else []

        supported_files: List[Path] = []

        # Use registry-backed globs to discover files (Dockerfile.*, *.tf.json, etc.)
        for glob in LanguageDetector.get_supported_file_globs():
            for file in path.rglob(glob):
                if excluded(file) or not file.is_file():
                    continue
                supported_files.append(file)

        # Optional: keep a small fallback for common special filenames not yet in specs.
        fallback_names = ("Makefile", "makefile", "Containerfile", "containerfile")
        for name in fallback_names:
            for file in path.rglob(name):
                if excluded(file) or not file.is_file():
                    continue
                if LanguageDetector.is_supported(file):
                    supported_files.append(file)

        # Dedupe preserving order
        return list(dict.fromkeys(supported_files))

    def _analyze_file(self, file_path: Path) -> Optional[FileAnalysisResult]:
        """Analyze a single file (multi-language support)."""
        start_time = time.time()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            # Cache source for ML semantic analysis (Phase 1)
            self.source_cache[str(file_path)] = code

            # Detect language
            language = LanguageDetector.detect(file_path, code)
            if language == Language.UNKNOWN:
                return None

            # Calculate LOC early (for all languages including DevOps)
            loc = len(
                [ln for ln in code.split("\n") if ln.strip() and not ln.strip().startswith("#")]
            )

            # DevOps languages - use dedicated analyzers without TreeSitter parser
            if language == Language.YAML:
                from hefesto.analyzers.devops.yaml_analyzer import YamlAnalyzer

                yaml_issues = YamlAnalyzer().analyze(str(file_path), code)
                filtered_issues = self._filter_by_severity(yaml_issues)
                duration_ms = (time.time() - start_time) * 1000
                return FileAnalysisResult(
                    file_path=str(file_path),
                    issues=filtered_issues,
                    lines_of_code=loc,
                    analysis_duration_ms=duration_ms,
                    language=language.value,
                )

            elif language == Language.SHELL:
                from hefesto.analyzers.devops.shell_analyzer import ShellAnalyzer

                shell_issues = ShellAnalyzer().analyze(str(file_path), code)
                filtered_issues = self._filter_by_severity(shell_issues)
                duration_ms = (time.time() - start_time) * 1000
                return FileAnalysisResult(
                    file_path=str(file_path),
                    issues=filtered_issues,
                    lines_of_code=loc,
                    analysis_duration_ms=duration_ms,
                    language=language.value,
                )

            elif language == Language.DOCKERFILE:
                from hefesto.analyzers.devops.dockerfile_analyzer import DockerfileAnalyzer

                docker_issues = DockerfileAnalyzer().analyze(str(file_path), code)
                filtered_issues = self._filter_by_severity(docker_issues)
                duration_ms = (time.time() - start_time) * 1000
                return FileAnalysisResult(
                    file_path=str(file_path),
                    issues=filtered_issues,
                    lines_of_code=loc,
                    analysis_duration_ms=duration_ms,
                    language=language.value,
                )

            elif language == Language.TERRAFORM:
                from hefesto.analyzers.devops.terraform_analyzer import TerraformAnalyzer

                tf_issues = TerraformAnalyzer().analyze(str(file_path), code)
                filtered_issues = self._filter_by_severity(tf_issues)
                duration_ms = (time.time() - start_time) * 1000
                return FileAnalysisResult(
                    file_path=str(file_path),
                    issues=filtered_issues,
                    lines_of_code=loc,
                    analysis_duration_ms=duration_ms,
                    language=language.value,
                )

            elif language == Language.SQL:
                from hefesto.analyzers.devops.sql_analyzer import SqlAnalyzer

                sql_issues = SqlAnalyzer().analyze(str(file_path), code)
                filtered_issues = self._filter_by_severity(sql_issues)
                duration_ms = (time.time() - start_time) * 1000
                return FileAnalysisResult(
                    file_path=str(file_path),
                    issues=filtered_issues,
                    lines_of_code=loc,
                    analysis_duration_ms=duration_ms,
                    language=language.value,
                )

            try:
                parser = ParserFactory.get_parser(language)
                tree = parser.parse(code, str(file_path))
            except Exception:
                # File has syntax errors or unsupported language, skip it
                return None

            # LOC already calculated above

            # Run all analyzers
            all_issues = []
            for analyzer in self.analyzers:
                issues = analyzer.analyze(tree, str(file_path), code)
                all_issues.extend(issues)

            # Filter by severity threshold
            filtered_issues = self._filter_by_severity(all_issues)

            duration_ms = (time.time() - start_time) * 1000

            return FileAnalysisResult(
                file_path=str(file_path),
                issues=filtered_issues,
                lines_of_code=loc,
                analysis_duration_ms=duration_ms,
                language=language.value,
            )

        except Exception:
            # Skip files that can't be read or analyzed
            return None

    def _filter_by_severity(self, issues: List[AnalysisIssue]) -> List[AnalysisIssue]:
        """Filter issues by severity threshold."""
        severity_order = {
            AnalysisIssueSeverity.LOW: 0,
            AnalysisIssueSeverity.MEDIUM: 1,
            AnalysisIssueSeverity.HIGH: 2,
            AnalysisIssueSeverity.CRITICAL: 3,
        }

        threshold_value = severity_order[self.severity_threshold]

        return [issue for issue in issues if severity_order[issue.severity] >= threshold_value]

    def _create_summary(
        self, file_results: List[FileAnalysisResult], duration: float
    ) -> AnalysisSummary:
        """Create summary statistics from file results."""
        all_issues = []
        total_loc = 0

        for file_result in file_results:
            all_issues.extend(file_result.issues)
            total_loc += file_result.lines_of_code

        # Count by severity
        critical = sum(
            1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.CRITICAL
        )
        high = sum(1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.HIGH)
        medium = sum(1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.MEDIUM)
        low = sum(1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.LOW)

        return AnalysisSummary(
            files_analyzed=len(file_results),
            total_issues=len(all_issues),
            critical_issues=critical,
            high_issues=high,
            medium_issues=medium,
            low_issues=low,
            total_loc=total_loc,
            duration_seconds=duration,
        )


__all__ = ["AnalyzerEngine", "DEFAULT_EXCLUDES"]
