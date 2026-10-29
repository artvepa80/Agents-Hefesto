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
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisReport,
    AnalysisSummary,
    FileAnalysisResult,
)
from hefesto.core.config_parse import parse_scope
from hefesto.core.language_detector import Language, LanguageDetector
from hefesto.core.languages.registry import get_registry
from hefesto.core.parsers.parser_factory import ParserFactory

logger = logging.getLogger(__name__)

# Directories excluded by default to avoid noise from vendored/generated code.
# Users can add more via --exclude; these are always applied.
COBOL_INFERRED_FREE_NOTICE = (
    "Read as free-format COBOL because a division header or level-01/77 entry starts "
    "before column 8 and there is no >>SOURCE FORMAT directive. Add the directive "
    "if this is wrong."
)

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
    # Generated lockfiles. A directory walk skips the filename. Naming the
    # file on the command line still analyzes it (the single-file branch
    # does not apply these patterns).
    "package-lock.json",
    "npm-shrinkwrap.json",
    "composer.lock",
    "poetry.lock",
    "Cargo.lock",
    "uv.lock",
    "Pipfile.lock",
    "packages.lock.json",
    "flake.lock",
    "deno.lock",
    "bun.lock",
]

# Analyzers that take (path, content) and return AnalysisIssue.
_TEXT_ANALYZERS = {
    Language.POWERSHELL: (
        "hefesto.analyzers.devops.powershell_analyzer",
        "PowerShellAnalyzer",
    ),
    Language.JSON: ("hefesto.analyzers.devops.json_analyzer", "JsonAnalyzer"),
    Language.TOML: ("hefesto.analyzers.devops.toml_analyzer", "TomlAnalyzer"),
    Language.MAKEFILE: (
        "hefesto.analyzers.devops.makefile_analyzer",
        "MakefileAnalyzer",
    ),
    Language.GROOVY: (
        "hefesto.analyzers.devops.groovy_jenkins_analyzer",
        "GroovyJenkinsAnalyzer",
    ),
}

# Cloud analyzers take (content, path) and return CloudFinding.
_CLOUD_ANALYZERS = {
    Language.CLOUDFORMATION: (
        "hefesto.analyzers.cloud.cloudformation",
        "CloudFormationAnalyzer",
    ),
    Language.ARM: ("hefesto.analyzers.cloud.arm", "ArmAnalyzer"),
    Language.HELM: ("hefesto.analyzers.cloud.helm", "HelmAnalyzer"),
    Language.SERVERLESS: (
        "hefesto.analyzers.cloud.serverless",
        "ServerlessAnalyzer",
    ),
}


def _pattern_parts(pattern: str) -> Tuple[List[str], bool]:
    """Components of an exclude pattern and whether it only names directories."""
    text = pattern.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return [part for part in text.split("/") if part], text.endswith("/")


def path_is_excluded(
    rel_parts: Sequence[str], patterns: Iterable[str], is_dir: bool = False
) -> bool:
    """True if a path below the analysis root matches an exclude pattern.

    ``rel_parts`` are the components of the path relative to the analysis
    root, so directories above the root never match. A pattern is a sequence
    of whole components: ``build/`` matches a ``build`` directory at any
    depth (not ``rebuild/``), ``src/legacy/`` matches those two consecutive
    directories, ``evil.py`` matches a file or directory with that name. A
    trailing ``/`` restricts the pattern to directories; set ``is_dir`` when
    ``rel_parts`` names a directory. ``.egg-info/`` matches directories whose
    name ends with ``.egg-info`` (``pkg.egg-info/``).
    """
    parts = tuple(rel_parts)
    for pattern in patterns:
        wanted, dir_only = _pattern_parts(pattern)
        if not wanted:
            continue
        candidates = parts if (is_dir or not dir_only) else parts[:-1]
        size = len(wanted)
        for start in range(len(candidates) - size + 1):
            window = candidates[start : start + size]
            if all(_component_matches(name, want) for name, want in zip(window, wanted)):
                return True
    return False


def _component_matches(name: str, wanted: str) -> bool:
    if wanted in _SUFFIX_EXCLUDES:
        return name.endswith(wanted) and name != wanted
    return name == wanted


# Default excludes that name a suffix of a directory (``pkg.egg-info``).
_SUFFIX_EXCLUDES = frozenset({".egg-info"})


# Vendored and minified JavaScript, skipped by default (``--include-vendored``
# analyzes it). Only JavaScript files are affected; a Go or PHP ``vendor/``
# tree stays in scope.
_JS_SUFFIXES = (".js", ".mjs", ".cjs")
# Directories that only ever hold copied or installed third-party packages.
_VENDOR_DIRS = frozenset({"vendor", "vendors", "bower_components", "jspm_packages"})
# Web static-asset roots, and the library directories that hold copied
# libraries when they sit below one (``static/js/libs/``, ``public/lib/``).
_STATIC_DIRS = frozenset({"static", "assets", "public", "wwwroot"})
_STATIC_LIB_DIRS = frozenset({"lib", "libs", "plugins", "third_party", "thirdparty"})


# How many example paths ``meta.vendored_skipped`` lists.
VENDORED_EXAMPLES = 20


def vendored_skip_message(count: int) -> str:
    """One-line report of the files left out as vendored or minified JavaScript."""
    noun = "file" if count == 1 else "files"
    return f"{count} {noun} skipped as vendored (use --include-vendored)"


# latin-1 maps every byte 0x00-0xff to one code point, so decoding never fails
# and ASCII text is unchanged: https://docs.python.org/3/library/codecs.html#encodings-and-unicode
FALLBACK_ENCODING = "latin-1"


def decoded_with_fallback_message(entry: Dict[str, Any]) -> str:
    """``<path>: decoded with fallback (latin-1)`` for reports."""
    return f"{entry.get('path')}: decoded with fallback ({entry.get('encoding')})"


def _not_analyzed_reason(entry: Dict[str, Any]) -> str:
    """One-line reason for a ``meta.not_analyzed`` entry."""
    what = "could not be read" if entry.get("reason") == "read_error" else "analyzer failed"
    return f"{what} ({entry.get('exception')})"


def not_analyzed_message(entry: Dict[str, Any]) -> str:
    """``<path>: not analyzed, <reason>`` for reports."""
    return f"{entry.get('path')}: not analyzed, {_not_analyzed_reason(entry)}"


def is_vendored_js(rel_parts: Sequence[str]) -> bool:
    """True for a JavaScript file that is minified or copied in from a library.

    ``rel_parts`` are the components of the file path relative to the
    analysis root, so directories above the root never count. Matched,
    case-insensitively:

    - a minified file name: ``*.min.js`` or ``*-min.js`` (also ``.mjs``/``.cjs``);
    - a file inside a ``vendor``, ``vendors``, ``bower_components`` or
      ``jspm_packages`` directory, at any depth;
    - a file inside a ``lib``, ``libs``, ``plugins``, ``third_party`` or
      ``thirdparty`` directory that is itself below a ``static``, ``assets``,
      ``public`` or ``wwwroot`` directory (``static/js/libs/ace.js``).

    A top-level ``lib/`` or ``plugins/`` (a package's own code) is not matched.
    """
    if not rel_parts:
        return False
    name = rel_parts[-1].lower()
    stem = None
    for suffix in _JS_SUFFIXES:
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            break
    if not stem:
        return False
    if stem.endswith(".min") or stem.endswith("-min"):
        return True
    dirs = [part.lower() for part in rel_parts[:-1]]
    if any(part in _VENDOR_DIRS for part in dirs):
        return True
    seen_static = False
    for part in dirs:
        if seen_static and part in _STATIC_LIB_DIRS:
            return True
        if part in _STATIC_DIRS:
            seen_static = True
    return False


def _relative_parts(path: Path, root: Path) -> Tuple[str, ...]:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return path.parts


_SEVERITY_RANK = {
    AnalysisIssueSeverity.LOW: 1,
    AnalysisIssueSeverity.MEDIUM: 2,
    AnalysisIssueSeverity.HIGH: 3,
    AnalysisIssueSeverity.CRITICAL: 4,
}


class AnalyzerEngine:
    """Main analysis engine that orchestrates all analyzers."""

    def __init__(
        self,
        severity_threshold: str = "MEDIUM",
        verbose: bool = False,
        scope_config: Any = None,
        enrich_config: Any = None,
        quiet: bool = False,
        enrich_min_severity: str = "MEDIUM",
        enrich_max_findings: int = 50,
    ):
        """
        Initialize analyzer engine.

        Args:
            severity_threshold: Minimum severity level to report (LOW/MEDIUM/HIGH/CRITICAL)
            verbose: Print detailed pipeline steps (default: False)
            scope_config: Optional ScopeGatingConfig (PRO feature, None = no gating)
            enrich_config: Optional EnrichmentConfig (PRO feature, None = no enrichment)
            quiet: Suppress non-essential stderr output, including parser-skip warnings
            enrich_min_severity: Only findings at or above this severity are enriched
            enrich_max_findings: At most this many findings are enriched per run
                (highest severity first; 0 disables enrichment calls)
        """
        self.severity_threshold = AnalysisIssueSeverity(severity_threshold)
        self.analyzers: List[Any] = []
        self._project_analyzers: List[Any] = []
        self.verbose = verbose
        self._quiet = quiet
        self._registry = get_registry()
        self.source_cache: dict = {}  # ML Enhancement: cache source for semantic analysis
        self._scope_config = scope_config
        self._enrich_config = enrich_config
        self._enrich_orchestrator: Any = None
        self._enrich_min_severity = AnalysisIssueSeverity(enrich_min_severity)
        self._enrich_max_findings = max(0, int(enrich_max_findings))
        self._scope_skipped: list = []
        self._multilang_skip_report: Any = None
        self._tsjs_parser: Any = None
        self._all_file_results: list = []  # EPIC 4: accumulated for _build_meta
        self._parser_failures: List[Dict[str, Any]] = []  # files skipped due to parser errors
        # Found files that could not be read or whose analyzer raised
        self._not_analyzed: List[Dict[str, Any]] = []
        # Found files that are not valid UTF-8, read with FALLBACK_ENCODING
        self._decoded_with_fallback: List[Dict[str, Any]] = []
        # COBOL COPY index (COBOL007/COBOL015). Set for the whole run by
        # prepare_cobol_index(); otherwise built per analyze_path() call.
        self._cobol_index: Any = None
        self._cobol_index_pinned = False
        # Copybook directories outside the scan (copybook_paths / --copybook-path)
        self._copybook_paths: List[Path] = []
        self._copybook_library_names: Optional[Dict[str, str]] = None
        # COBOL files whose source format was inferred as free (no directive)
        self._cobol_inferred_free: List[str] = []
        # Analyze vendored/minified JavaScript too (--include-vendored)
        self._include_vendored = False
        # Files left out as vendored/minified JavaScript, for the skip report
        self._vendored_skipped: Set[str] = set()

        # Initialize enrichment orchestrator if config provided
        if enrich_config is not None:
            self._enrich_orchestrator = self._build_enrich_orchestrator(enrich_config)

        # Initialize multilang parser + skip report if available
        from hefesto.pro_optional import HAS_MULTILANG, SkipReport, TsJsParser

        if HAS_MULTILANG and TsJsParser is not None:
            self._tsjs_parser = TsJsParser()
        if HAS_MULTILANG and SkipReport is not None:
            self._multilang_skip_report = SkipReport()

    def set_include_vendored(self, include: bool) -> None:
        """Also analyze vendored and minified JavaScript (see ``is_vendored_js``)."""
        self._include_vendored = bool(include)

    def set_copybook_paths(self, paths: List[str]) -> None:
        """Extra copybook directories for COBOL015 (names there resolve COPY).

        Their files are not analyzed; they only tell the index which copybook
        names exist outside the scanned tree.
        """
        self._copybook_paths = [Path(p).resolve() for p in paths]
        self._copybook_library_names = None  # walked again on next build

    def prepare_cobol_index(self, paths: List[str], exclude_patterns: List[str]) -> None:
        """Index COPY statements across every path of the run (COBOL007/COBOL015)."""
        files: List[Path] = []
        roots: List[Path] = []
        for path in paths:
            root = Path(path).resolve()
            roots.append(root)
            files.extend(self._find_files(root, exclude_patterns))
        index = self._build_cobol_index(files, roots, exclude_patterns)
        if index is not None:
            self._cobol_index = index
            self._cobol_index_pinned = True

    def _build_cobol_index(
        self, files: List[Path], roots: List[Path], exclude_patterns: List[str]
    ) -> Any:
        """COPY index for the COBOL files in ``files`` (None if there are none)."""
        cobol = [f for f in files if self._is_cobol_path(f)]
        if not cobol:
            return None
        from hefesto.analyzers.devops.cobol_project_index import (
            CobolProjectIndex,
            library_copybook_files,
        )

        extra: List[Path] = []
        for root in roots:
            extra.extend(self._extra_copybook_candidates(root, exclude_patterns))
        if self._copybook_library_names is None:
            # walked once per engine: analyze_path on several paths reuses it
            self._copybook_library_names = (
                library_copybook_files(self._copybook_paths) if self._copybook_paths else {}
            )
        return CobolProjectIndex.from_paths(
            cobol, extra, library_names=self._copybook_library_names
        )

    @staticmethod
    def _extra_copybook_candidates(root: Path, exclude_patterns: List[str]) -> List[Path]:
        """Files under ``root`` that may be copybooks without a COBOL extension."""
        from hefesto.analyzers.devops.cobol_project_index import is_extra_copybook_candidate

        if not root.is_dir():
            return []
        excludes = list(DEFAULT_EXCLUDES) + list(exclude_patterns)
        found: List[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = _relative_parts(Path(dirpath), root)
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".")
                and not path_is_excluded(rel_dir + (d,), excludes, is_dir=True)
            ]
            for name in filenames:
                candidate = Path(dirpath) / name
                if is_extra_copybook_candidate(candidate) and not path_is_excluded(
                    rel_dir + (name,), excludes
                ):
                    found.append(candidate)
        return found

    def _with_indexed_copybooks(self, source_files: List[Path], root: Path) -> List[Path]:
        """Add copybooks the index found without a COBOL extension (under ``root``)."""
        if self._cobol_index is None or not self._cobol_index.copybook_files:
            return source_files
        known = {str(f) for f in source_files}
        extra = sorted(
            Path(p)
            for p in self._cobol_index.copybook_files
            if p not in known and (Path(p) == root or root in Path(p).parents)
        )
        return source_files + extra

    @staticmethod
    def _is_cobol_path(path: Path) -> bool:
        return path.suffix.lower() in (".cbl", ".cob", ".cobol", ".cpy", ".pco")

    def register_analyzer(self, analyzer):
        """Register an analyzer instance."""
        self.analyzers.append(analyzer)

    def register_project_analyzer(self, analyzer):
        """Register a project-level analyzer.

        Project analyzers run once per ``analyze_path`` call with the project
        root as input. They must expose ``analyze_project(project_root: Path)
        -> List[AnalysisIssue]``. Findings are folded into file results by
        their ``file_path`` attribute.
        """
        self._project_analyzers.append(analyzer)

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

        # Find supported files — resolve to canonical absolute path.
        path_obj = Path(path).resolve()
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

        if not self._cobol_index_pinned:
            self._cobol_index = self._build_cobol_index(
                source_files, [path_obj], exclude_patterns or []
            )
        source_files = self._with_indexed_copybooks(source_files, path_obj)

        not_analyzed_before = len(self._not_analyzed)
        fallback_before = len(self._decoded_with_fallback)
        for py_file in source_files:
            file_result = self._analyze_file(py_file)
            if file_result:
                file_results.append(file_result)
                all_issues.extend(file_result.issues)
        self._emit_not_analyzed(not_analyzed_before)
        self._emit_decoded_with_fallback(fallback_before)

        # Project-level analyzers (Phase 1a — Operational Truth)
        if self._project_analyzers:
            project_issues = self._run_project_analyzers(path_obj)
            if project_issues:
                self._fold_project_issues(file_results, project_issues)
                all_issues.extend(project_issues)

        # Enrichment (PRO EPIC 3): per-finding metadata attachment
        if self._enrich_orchestrator is not None and self._enrich_config is not None:
            self._enrich_findings(file_results)

        if self.verbose:
            print(f"   Found {len(all_issues)} potential issue(s)")
            print()

        # Calculate final statistics
        duration = time.time() - start_time
        summary = self._create_summary(file_results, duration)

        # Accumulate for _build_meta (EPIC 4)
        self._all_file_results.extend(file_results)

        # Create report (meta is assembled by CLI from engine state)
        report = AnalysisReport(summary=summary, file_results=file_results)

        # Surface silent parser skips before the CLI renders the report.
        self._emit_skip_summary()

        if self.verbose:
            print("Analysis complete!")
            print(f"   Duration: {duration:.2f}s")
            print()

        return report

    def analyze_files(
        self,
        paths: List[str],
        project_root: Optional[str] = None,
    ) -> AnalysisReport:
        """Analyze an explicit list of files without filesystem discovery.

        Used by Phase 2 PR review where the set of files to analyze is
        already known from the diff and ``_find_files`` would be either
        wasteful (re-globbing the entire repo) or wrong (picking up
        untouched files).

        Project-level analyzers still run once against ``project_root``
        so cross-file findings (operational truth, CI parity) remain
        available — the PR review orchestrator filters them afterwards
        by ``finding.file_path`` membership in the diff set.
        """
        start_time = time.time()

        file_path_objs = [Path(p).resolve() for p in paths]
        if project_root is not None:
            root_obj = Path(project_root).resolve()
        else:
            # No heuristic fallback to ``file_path_objs[0].parent`` — that
            # silently mis-roots project analyzers onto a subdirectory
            # when the caller forgets to pass ``project_root``. Default
            # to CWD and warn if project analyzers are registered so the
            # failure mode is loud, not silent.
            root_obj = Path.cwd()
            if self._project_analyzers:
                logger.warning(
                    "analyze_files() called without project_root while %d "
                    "project analyzer(s) are registered; using CWD=%s as "
                    "project root. Pass project_root explicitly to silence "
                    "this warning.",
                    len(self._project_analyzers),
                    root_obj,
                )

        # Scope gating (PRO EPIC 1) — applied in the same order as analyze_path
        scope_skipped_here: list = []
        if self._scope_config is not None:
            from hefesto.pro_optional import filter_paths

            file_path_objs, scope_skipped_here = filter_paths(file_path_objs, self._scope_config)
            self._scope_skipped.extend(scope_skipped_here)

        file_results: List[FileAnalysisResult] = []
        all_issues: List[AnalysisIssue] = []

        not_analyzed_before = len(self._not_analyzed)
        fallback_before = len(self._decoded_with_fallback)
        for py_file in file_path_objs:
            if not py_file.exists() or not py_file.is_file():
                continue
            file_result = self._analyze_file(py_file)
            if file_result:
                file_results.append(file_result)
                all_issues.extend(file_result.issues)
        self._emit_not_analyzed(not_analyzed_before)
        self._emit_decoded_with_fallback(fallback_before)

        # Project-level analyzers (Phase 1a/1b) run once against the project root.
        if self._project_analyzers:
            project_issues = self._run_project_analyzers(root_obj)
            if project_issues:
                self._fold_project_issues(file_results, project_issues)
                all_issues.extend(project_issues)

        if self._enrich_orchestrator is not None and self._enrich_config is not None:
            self._enrich_findings(file_results)

        duration = time.time() - start_time
        summary = self._create_summary(file_results, duration)

        self._all_file_results.extend(file_results)

        self._emit_skip_summary()
        return AnalysisReport(summary=summary, file_results=file_results)

    def _find_files(self, path: Path, exclude_patterns: List[str]) -> List[Path]:
        """Find all supported files in the given path."""
        # Merge default excludes with user-provided patterns
        all_excludes = list(DEFAULT_EXCLUDES) + list(exclude_patterns)

        include_vendored = self._include_vendored

        def excluded(p: Path) -> bool:
            rel = _relative_parts(p, path)
            if path_is_excluded(rel, all_excludes):
                return True
            if not include_vendored and is_vendored_js(rel):
                # counted only when no exclude pattern already drops the file
                if p.is_file():
                    self._vendored_skipped.add(str(p))
                return True
            return False

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
        file_path = file_path.resolve()
        stage = "read"
        language: Optional[Language] = None

        try:
            code = self._read_source(file_path)
            stage = "analyze"
            with parse_scope():
                return self._analyze_source(file_path, code, start_time)
        except Exception as exc:
            # Never drop a found file silently: it is reported as not analyzed
            # (text, JSON and SARIF) and fails --fail-on unless opted out.
            self._not_analyzed.append(
                {
                    "path": str(file_path),
                    "language": language.value if language is not None else None,
                    "reason": "read_error" if stage == "read" else "analyzer_error",
                    "exception": type(exc).__name__,
                }
            )
            logger.debug("Not analyzed: %s (%s)", file_path, exc, exc_info=True)
            return None

    def _analyze_source(
        self, file_path: Path, code: str, start_time: float
    ) -> Optional[FileAnalysisResult]:
        """Detect the language and run its analyzers. One YAML/JSON parse is shared."""
        language: Optional[Language] = None
        try:
            # Cache source for ML semantic analysis (Phase 1)
            self.source_cache[str(file_path)] = code

            # Detect language (copybooks without a COBOL extension come from the index)
            language = LanguageDetector.detect(file_path, code)
            if self._cobol_index is not None and str(file_path) in self._cobol_index.copybook_files:
                language = Language.COBOL
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

            elif language == Language.COBOL:
                from hefesto.analyzers.devops.cobol_governance_analyzer import (
                    CobolGovernanceAnalyzer,
                )

                cobol_analyzer = CobolGovernanceAnalyzer(index=self._cobol_index)
                cobol_issues = cobol_analyzer.analyze(str(file_path), code)
                filtered_issues = self._filter_by_severity(cobol_issues)
                duration_ms = (time.time() - start_time) * 1000
                cobol_meta: Dict[str, Any] = {}
                if cobol_analyzer.last_format_reason == "inferred-free":
                    self._cobol_inferred_free.append(str(file_path))
                    cobol_meta["cobol_source_format"] = "inferred-free"
                return FileAnalysisResult(
                    file_path=str(file_path),
                    issues=filtered_issues,
                    lines_of_code=loc,
                    analysis_duration_ms=duration_ms,
                    language=language.value,
                    metadata=cobol_meta,
                )

            dispatched = self._analyze_dispatched(language, file_path, code, loc, start_time)
            if dispatched is not None:
                return dispatched

            try:
                parser = ParserFactory.get_parser(language)
                tree = parser.parse(code, str(file_path))
            except Exception as exc:
                self._parser_failures.append(
                    {
                        "path": str(file_path),
                        "language": language.value,
                        "category": self._categorize_parser_failure(exc, language),
                        "exception": type(exc).__name__,
                    }
                )
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

        except Exception as exc:
            # Never drop a found file silently: it is reported as not analyzed
            # (text, JSON and SARIF) and fails --fail-on unless opted out.
            self._not_analyzed.append(
                {
                    "path": str(file_path),
                    "language": language.value if language is not None else None,
                    "reason": "analyzer_error",
                    "exception": type(exc).__name__,
                }
            )
            logger.debug("Not analyzed: %s (%s)", file_path, exc, exc_info=True)
            return None

    def _read_source(self, file_path: Path) -> str:
        """UTF-8, else FALLBACK_ENCODING (never fails to decode); the file is listed."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            pass
        with open(file_path, "r", encoding=FALLBACK_ENCODING) as f:
            code = f.read()
        self._decoded_with_fallback.append({"path": str(file_path), "encoding": FALLBACK_ENCODING})
        return code

    def _run_project_analyzers(self, project_root: Path) -> List[AnalysisIssue]:
        """Run registered project-level analyzers once against the project root.

        Individual analyzer failures are logged and skipped — they must not
        break file-level analysis.
        """
        issues: List[AnalysisIssue] = []
        for panalyzer in self._project_analyzers:
            name = type(panalyzer).__name__
            try:
                result = panalyzer.analyze_project(project_root) or []
            except Exception as exc:
                logger.debug("Project analyzer %s failed: %s", name, exc)
                continue
            issues.extend(result)
        return self._filter_by_severity(issues)

    def _fold_project_issues(
        self,
        file_results: List[FileAnalysisResult],
        project_issues: List[AnalysisIssue],
    ) -> None:
        """Attach project-level findings to file results.

        Issues that target an existing FileAnalysisResult are appended there.
        Issues that target a file not in the regular scan (e.g. README.md,
        pyproject.toml) get a synthetic FileAnalysisResult.
        """
        by_path = {fr.file_path: fr for fr in file_results}
        synthetic: Dict[str, FileAnalysisResult] = {}
        for issue in project_issues:
            target = by_path.get(issue.file_path) or synthetic.get(issue.file_path)
            if target is None:
                target = FileAnalysisResult(
                    file_path=issue.file_path,
                    issues=[],
                    lines_of_code=0,
                    analysis_duration_ms=0.0,
                    language=None,
                    metadata={"synthetic": True, "source": "operational_truth"},
                )
                synthetic[issue.file_path] = target
                file_results.append(target)
            target.issues.append(issue)

    def _analyze_dispatched(
        self,
        language: Language,
        file_path: Path,
        code: str,
        loc: int,
        start_time: float,
    ) -> Optional[FileAnalysisResult]:
        """Run a text or cloud analyzer. ``None`` means this language is not one of them.

        A supported file with zero findings still returns a result, so a clean
        ``tsconfig.json`` counts as analyzed.
        """
        import importlib

        text = _TEXT_ANALYZERS.get(language)
        cloud = _CLOUD_ANALYZERS.get(language)
        if text is not None:
            module_name, class_name = text
            analyzer = getattr(importlib.import_module(module_name), class_name)()
            issues = analyzer.analyze(str(file_path), code)
        elif cloud is not None:
            module_name, class_name = cloud
            analyzer = getattr(importlib.import_module(module_name), class_name)()
            from hefesto.analyzers.cloud.adapt import cloud_findings_to_issues

            issues = cloud_findings_to_issues(analyzer.analyze(code, str(file_path)))
        else:
            return None
        duration_ms = (time.time() - start_time) * 1000
        return FileAnalysisResult(
            file_path=str(file_path),
            issues=self._filter_by_severity(issues),
            lines_of_code=loc,
            analysis_duration_ms=duration_ms,
            language=language.value,
        )

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

    def _categorize_parser_failure(
        self, exc: Exception, language: Optional["Language"] = None
    ) -> str:
        """Classify parser failure for the skip summary.

        Strong signal first: if ``language`` requires tree-sitter (i.e., is in
        ``ParserFactory.GRAMMAR_NAMES``) AND the prebuilt grammar pack is not
        available (``USE_PREBUILT=False``), then any failure during parser
        instantiation/parse is definitionally a missing-pack situation —
        regardless of exception type or message. This catches API drift in the
        ``tree-sitter`` core library (e.g., ``TypeError`` from the deprecated
        manual ``Language(path, name)`` fallback that no longer matches
        current ``tree-sitter`` signatures).

        Fallback heuristic: when no language context is supplied (unit-test
        callers) or the language is not tree-sitter-dependent, classify by
        exception type / message. Conservative: ambiguous cases default to
        ``"parse_error"`` so we never suggest installing ``[multilang]`` when
        the real issue is something else (encoding, syntax). Full traceback
        goes to DEBUG for diagnostics.
        """
        if language is not None:
            from hefesto.core.parsers.parser_factory import ParserFactory
            from hefesto.core.parsers.treesitter_parser import USE_PREBUILT

            if not USE_PREBUILT and language in ParserFactory.GRAMMAR_NAMES:
                return "parser_unavailable"

        if isinstance(exc, (ImportError, OSError)):
            return "parser_unavailable"
        msg = str(exc).lower()
        if "languages.so" in msg or "tree_sitter_language_pack" in msg:
            return "parser_unavailable"
        logger.debug("Uncategorized parser failure (defaulting to parse_error)", exc_info=True)
        return "parse_error"

    def _emit_not_analyzed(self, start: int) -> None:
        """Warn on stderr about files of this call that could not be analyzed.

        Printed even with ``--quiet`` (like the no-files warning): a file the
        gate did not check must never look like a clean pass.
        """
        entries = self._not_analyzed[start:]
        if not entries:
            return
        import click

        click.echo(
            f"Warning: {len(entries)} file(s) could not be analyzed (see 'Not analyzed' in the"
            " report; meta.not_analyzed in JSON):",
            err=True,
        )
        for entry in entries[:10]:
            click.echo(f"   - {entry['path']}: {_not_analyzed_reason(entry)}", err=True)
        if len(entries) > 10:
            click.echo(f"   ... and {len(entries) - 10} more", err=True)

    def _emit_decoded_with_fallback(self, start: int) -> None:
        """Warn on stderr (also with ``--quiet``) about files read with the fallback."""
        entries = self._decoded_with_fallback[start:]
        if not entries:
            return
        import click

        click.echo(
            f"Warning: {len(entries)} file(s) are not valid UTF-8 and were decoded with fallback"
            f" ({FALLBACK_ENCODING}); they were analyzed:",
            err=True,
        )
        for entry in entries[:10]:
            click.echo(f"   - {entry['path']}", err=True)
        if len(entries) > 10:
            click.echo(f"   ... and {len(entries) - 10} more", err=True)

    def _emit_skip_summary(self) -> None:
        """Emit categorized parser-skip warnings to stderr.

        Suppressed when ``self._quiet`` is True (respects the ``--quiet`` CLI
        contract). Both categories are emitted independently when both are
        present; the actionable one (``parser_unavailable``) goes first.

        Output goes to stderr so it does not contaminate stdout when the user
        passes ``--output json`` (per cli/main.py policy: stdout is pure JSON).
        """
        if self._quiet or not self._parser_failures:
            return

        import click

        unavailable = [f for f in self._parser_failures if f["category"] == "parser_unavailable"]
        parse_errors = [f for f in self._parser_failures if f["category"] == "parse_error"]

        if unavailable:
            langs = sorted({f["language"] for f in unavailable})
            click.echo(
                f"⚠️  Skipped {len(unavailable)} file(s) — parser unavailable for: "
                f"{', '.join(langs)}\n"
                f"   To analyze these languages: pip install hefesto-ai[multilang]",
                err=True,
            )
        if parse_errors:
            sample = ", ".join(f["path"] for f in parse_errors[:3])
            more = f" (+{len(parse_errors) - 3} more)" if len(parse_errors) > 3 else ""
            click.echo(
                f"⚠️  Skipped {len(parse_errors)} file(s) — parse error in: "
                f"{sample}{more}\n"
                f"   Run with --verbose for details.",
                err=True,
            )

    def _create_summary(
        self, file_results: List[FileAnalysisResult], duration: float
    ) -> AnalysisSummary:
        """Create summary statistics from file results."""
        all_issues = []
        total_loc = 0

        for file_result in file_results:
            all_issues.extend(file_result.issues)
            total_loc += file_result.lines_of_code

        # Exclude synthetic project-level results from the files_analyzed count.
        real_files = sum(1 for fr in file_results if not fr.metadata.get("synthetic"))

        # Count by severity
        critical = sum(
            1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.CRITICAL
        )
        high = sum(1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.HIGH)
        medium = sum(1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.MEDIUM)
        low = sum(1 for issue in all_issues if issue.severity == AnalysisIssueSeverity.LOW)

        return AnalysisSummary(
            files_analyzed=real_files,
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

    @staticmethod
    def _build_enrich_orchestrator(enrich_config: Any) -> Any:
        """Build the PRO orchestrator with the providers named in the config.

        Providers come from the ``hefesto.enrichment_providers`` entry points;
        only names listed in ``enrich_config.providers`` are loaded.
        """
        from hefesto.core.enrichment_providers import load_enrichment_providers
        from hefesto.pro_optional import (
            HAS_ENRICHMENT,
            EnrichmentCache,
            EnrichmentOrchestrator,
            EnrichmentProvider,
        )

        if not HAS_ENRICHMENT or EnrichmentOrchestrator is None:
            return None
        names = list(getattr(enrich_config, "providers", None) or [])
        providers = load_enrichment_providers(names, EnrichmentProvider) if names else []
        cache = None
        if EnrichmentCache is not None:
            cache = EnrichmentCache(
                ttl=enrich_config.cache_ttl_seconds,
                max_size=enrich_config.cache_max_size,
            )
        return EnrichmentOrchestrator(providers, cache=cache)

    def _enrich_targets(self, file_results: "List[FileAnalysisResult]") -> List[Tuple[Any, Any]]:
        """Findings to enrich: at or above the severity floor, capped, highest first."""
        floor = _SEVERITY_RANK[self._enrich_min_severity]
        candidates = [
            (file_result, issue)
            for file_result in file_results
            for issue in file_result.issues
            if _SEVERITY_RANK.get(issue.severity, 0) >= floor
        ]
        candidates.sort(key=lambda pair: -_SEVERITY_RANK.get(pair[1].severity, 0))
        return candidates[: self._enrich_max_findings]

    def _enrich_findings(self, file_results: "List[FileAnalysisResult]") -> None:
        """Attach enrichment metadata to selected findings (EPIC 3).

        Mutates ``issue.metadata["enrichment"]`` in-place. Only findings chosen
        by ``_enrich_targets`` are sent; the others get no ``enrichment`` key.
        Orchestrator never raises — errors become status=error in the dict.
        Enrichment never changes severities, the finding list, or the exit code.
        """
        from hefesto.pro_optional import EnrichmentInput

        if EnrichmentInput is None:
            return

        orch = self._enrich_orchestrator
        config = self._enrich_config

        for file_result, issue in self._enrich_targets(file_results):
            inp = EnrichmentInput(
                file_path=issue.file_path,
                finding_summary=issue.message,
                language=file_result.language,
                snippet=issue.code_snippet,
            )
            result = orch.run(inp, config)
            issue.metadata["enrichment"] = result.to_dict()

    def _file_records(self) -> Dict[str, Any]:
        """Per-file records for ``meta``; empty lists are left out."""
        records = {
            "parser_failures": self._parser_failures,
            "not_analyzed": self._not_analyzed,
            "decoded_with_fallback": self._decoded_with_fallback,
        }
        return {key: list(entries) for key, entries in records.items() if entries}

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

        # Reliability pack summary (EPIC 4)
        reliability_issues = [
            issue
            for fr in self._all_file_results
            for issue in fr.issues
            if issue.engine == "internal:resource_safety_v1"
        ]
        if reliability_issues:
            by_rule: dict = {}
            for issue in reliability_issues:
                rid = issue.rule_id or "unknown"
                by_rule[rid] = by_rule.get(rid, 0) + 1
            meta["reliability_pack_summary"] = {
                "pack": "resource_safety_v1",
                "total": len(reliability_issues),
                "by_rule": by_rule,
            }

        # Parser failures (silent skips of tree-sitter-dependent languages),
        # files not analyzed, files decoded with the fallback encoding
        meta.update(self._file_records())

        # Vendored/minified JavaScript left out of the run (--include-vendored)
        if self._vendored_skipped:
            meta["vendored_skipped"] = {
                "count": len(self._vendored_skipped),
                "examples": sorted(self._vendored_skipped)[:VENDORED_EXAMPLES],
            }

        # COBOL sources read as free format because of the layout, not a directive
        if self._cobol_inferred_free:
            meta["cobol_format_notices"] = {
                "inferred_free": list(dict.fromkeys(self._cobol_inferred_free)),
                "message": COBOL_INFERRED_FREE_NOTICE,
            }

        return meta


__all__ = [
    "AnalyzerEngine",
    "COBOL_INFERRED_FREE_NOTICE",
    "DEFAULT_EXCLUDES",
    "is_vendored_js",
    "vendored_skip_message",
    "path_is_excluded",
]
