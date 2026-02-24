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

import logging
import time
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

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
        scope_config: Any = None,
        enrich_config: Any = None,
    ):
        """
        Initialize analyzer engine.

        Args:
            severity_threshold: Minimum severity level to report (LOW/MEDIUM/HIGH/CRITICAL)
            verbose: Print detailed pipeline steps (default: False)
            scope_config: Optional ScopeGatingConfig (PRO feature, None = no gating)
            enrich_config: Optional EnrichmentConfig (PRO feature, None = no enrichment)
        """
        self.severity_threshold = AnalysisIssueSeverity(severity_threshold)
        self.analyzers: List[Any] = []
        self.verbose = verbose
        self._registry = get_registry()
        self.source_cache: dict = {}  # ML Enhancement: cache source for semantic analysis
        self._scope_config = scope_config
        self._enrich_config = enrich_config
        self._enrich_orchestrator: Any = None
        self._scope_skipped: list = []
        self._multilang_skip_report: Any = None
        self._tsjs_parser: Any = None

        # Initialize enrichment orchestrator if config provided
        if enrich_config is not None:
            from hefesto.pro_optional import HAS_ENRICHMENT, EnrichmentOrchestrator

            if HAS_ENRICHMENT and EnrichmentOrchestrator is not None:
                self._enrich_orchestrator = EnrichmentOrchestrator([])

        # Initialize multilang parser + skip report if available
        from hefesto.pro_optional import HAS_MULTILANG, SkipReport, TsJsParser

        if HAS_MULTILANG and TsJsParser is not None:
            self._tsjs_parser = TsJsParser()
        if HAS_MULTILANG and SkipReport is not None:
            self._multilang_skip_report = SkipReport()

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

        # Scope gating (PRO EPIC 1): filter before reading file contents
        scope_skipped_here = []
        if self._scope_config is not None:
            from hefesto.pro_optional import filter_paths

            source_files, scope_skipped_here = filter_paths(source_files, self._scope_config)
            self._scope_skipped.extend(scope_skipped_here)

        if self.verbose:
            print(f"📁 Found {len(source_files)} file(s)")
            if scope_skipped_here:
                print(f"   ({len(scope_skipped_here)} skipped by scope gating)")
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

        # Enrichment (PRO EPIC 3): per-finding metadata attachment
        if self._enrich_orchestrator is not None and self._enrich_config is not None:
            self._enrich_findings(file_results)

        if self.verbose:
            print(f"   Found {len(all_issues)} potential issue(s)")
            print()

        # Calculate final statistics
        duration = time.time() - start_time
        summary = self._create_summary(file_results, duration)

        # Create report (meta is assembled by CLI from engine state)
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
            except Exception as exc:
                logger.debug("Skipping %s: parse failed (%s)", file_path, exc)
                return None

            # LOC already calculated above

            # Multilang symbol extraction (PRO EPIC 2): TS/JS metadata
            file_meta = self._extract_multilang_symbols(file_path, code, language)

            # Run all analyzers
            all_issues = []
            for analyzer in self.analyzers:
                issues = analyzer.analyze(tree, str(file_path), code)
                all_issues.extend(issues)

            # Filter by severity threshold
            filtered_issues = self._filter_by_severity(all_issues)

            duration_ms = (time.time() - start_time) * 1000

            result = FileAnalysisResult(
                file_path=str(file_path),
                issues=filtered_issues,
                lines_of_code=loc,
                analysis_duration_ms=duration_ms,
                language=language.value,
            )
            if file_meta:
                result.metadata = file_meta
            return result

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

    # ------------------------------------------------------------------
    # PRO feature helpers
    # ------------------------------------------------------------------

    _TSJS_EXTENSIONS = frozenset([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"])

    def _extract_multilang_symbols(self, file_path: Path, code: str, language: "Language") -> dict:
        """Extract TS/JS symbols via PRO multilang parser (EPIC 2).

        Returns symbol dict to attach as file metadata, or empty dict.
        Does NOT re-read the file — uses ``code`` already in memory.
        """
        if self._tsjs_parser is None:
            return {}

        suffix = file_path.suffix.lower()
        if suffix not in self._TSJS_EXTENSIONS:
            return {}

        result = self._tsjs_parser.parse_text(file_path, code)

        if result.skipped:
            if self._multilang_skip_report is not None:
                self._multilang_skip_report.add(
                    file_path, result.skip_reason or "unsupported_language"
                )
            return {}

        return {
            "symbols": {
                "imports": sorted(result.imports),
                "functions": sorted(result.functions),
                "classes": sorted(result.classes),
                "exports": sorted(result.exports),
            }
        }

    def _enrich_findings(self, file_results: "List[FileAnalysisResult]") -> None:
        """Attach enrichment metadata to each finding (EPIC 3).

        Mutates ``issue.metadata["enrichment"]`` in-place.
        Orchestrator never raises — errors become status=error in the dict.
        """
        from hefesto.pro_optional import EnrichmentInput

        if EnrichmentInput is None:
            return

        orch = self._enrich_orchestrator
        config = self._enrich_config

        for file_result in file_results:
            for issue in file_result.issues:
                inp = EnrichmentInput(
                    file_path=issue.file_path,
                    finding_summary=issue.message,
                    language=file_result.language,
                    snippet=issue.code_snippet,
                )
                result = orch.run(inp, config)
                issue.metadata["enrichment"] = result.to_dict()

    def _build_meta(self) -> dict:
        """Assemble the ``meta`` dict for the report from PRO features."""
        meta: dict = {}

        # Scope gating summary (EPIC 1)
        if self._scope_config is not None and self._scope_skipped:
            from hefesto.pro_optional import build_scope_summary

            meta["scope"] = build_scope_summary(self._scope_skipped)

        # Multilang skip report (EPIC 2)
        if self._multilang_skip_report is not None:
            skip_dict = self._multilang_skip_report.to_dict()
            if skip_dict.get("total_skipped", 0) > 0:
                meta["multilang"] = {"skipped": skip_dict}

        return meta


__all__ = ["AnalyzerEngine", "DEFAULT_EXCLUDES"]
