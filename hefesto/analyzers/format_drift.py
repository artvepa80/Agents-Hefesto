"""
Format Drift Check (opt-in via ``hefesto analyze --format-check``)

Runs Black in check mode (in-process, no files are modified) against the
Python files that ``hefesto analyze`` already selected, and reports every file
Black would reformat as one ``FORMAT_DRIFT`` finding.

- Black is optional. When it is not importable the CLI prints a one-line
  warning and analysis continues without format findings.
- Black configuration is read the same way the ``black`` CLI reads it: the
  nearest ``pyproject.toml`` with a ``[tool.black]`` table (line-length,
  target-version, skip-string-normalization, skip-magic-trailing-comma,
  preview, force-exclude / extend-exclude, ...).
- Findings are LOW severity, carry a truncated unified diff in
  ``code_snippet`` and line-change counts in ``metadata``.

Copyright 2026 Narapa LLC, Miami, Florida
"""

import difflib
import importlib.util
import logging
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
    FileAnalysisResult,
)

logger = logging.getLogger(__name__)

BLACK_MISSING_WARNING = (
    'Warning: --format-check needs black: pip install "hefesto-ai[format]" '
    "(or pip install black); skipping format check."
)

ENGINE_NAME = "internal:format_drift"
PYTHON_SUFFIXES = (".py", ".pyi")
MAX_DIFF_LINES = 60


def is_black_available() -> bool:
    """Return True when the ``black`` package can be imported."""
    try:
        return importlib.util.find_spec("black") is not None
    except (ImportError, ValueError):
        return False


@dataclass
class FormatCheckStats:
    """Counters for one format-check run."""

    checked: int = 0
    drifted: int = 0
    skipped: int = 0
    errors: int = 0
    black_version: str = ""
    warnings: List[str] = field(default_factory=list)

    def summary_line(self) -> str:
        """One-line human summary for text output."""
        line = (
            f"Format check (black {self.black_version}): {self.checked} file(s) checked,"
            f" {self.drifted} would be reformatted"
        )
        if self.errors:
            line += f", {self.errors} could not be checked"
        return line


class FormatDriftChecker:
    """Check Python sources against Black and build FORMAT_DRIFT findings."""

    def __init__(self, black_module: Any = None):
        if black_module is None:
            import black as black_module  # optional dependency

        self._black = black_module
        self.stats = FormatCheckStats(black_version=str(getattr(black_module, "__version__", "")))
        # pyproject path (or None) -> (config dict, project root or None)
        self._config_by_pyproject: Dict[Optional[str], Tuple[Dict[str, Any], Optional[Path]]] = {}
        # directory -> pyproject path (or None)
        self._pyproject_by_dir: Dict[Path, Optional[str]] = {}
        self._mode_cache: Dict[Tuple[Optional[str], bool], Any] = {}
        self._bad_configs: set = set()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _warn(self, message: str) -> None:
        if message not in self.stats.warnings:
            self.stats.warnings.append(message)

    def _find_pyproject(self, path: Path) -> Optional[str]:
        directory = path.parent
        if directory not in self._pyproject_by_dir:
            try:
                found = self._black.find_pyproject_toml((str(path),))
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("black could not locate pyproject.toml for %s: %s", path, exc)
                found = None
            self._pyproject_by_dir[directory] = found
        return self._pyproject_by_dir[directory]

    def _load_config(self, path: Path) -> Tuple[Optional[str], Dict[str, Any], Optional[Path]]:
        pyproject = self._find_pyproject(path)
        if pyproject not in self._config_by_pyproject:
            config: Dict[str, Any] = {}
            root: Optional[Path] = None
            if pyproject:
                root = Path(pyproject).resolve().parent
                try:
                    config = self._black.parse_pyproject_toml(pyproject) or {}
                except Exception as exc:
                    self._bad_configs.add(pyproject)
                    self._warn(f"--format-check: could not read Black config in {pyproject}: {exc}")
            self._config_by_pyproject[pyproject] = (config, root)
            self._check_required_version(pyproject, config)
        config, root = self._config_by_pyproject[pyproject]
        return pyproject, config, root

    def _check_required_version(self, pyproject: Optional[str], config: Dict[str, Any]) -> None:
        required = config.get("required_version")
        installed = self.stats.black_version
        if not required or not installed:
            return
        required = str(required)
        # Black accepts either a full version or a major version ("24").
        if installed == required or installed.split(".")[0] == required:
            return
        self._warn(
            f"--format-check: {pyproject} pins black required-version {required} "
            f"but black {installed} is installed; results may differ from your CI."
        )

    def _build_mode(self, pyproject: Optional[str], config: Dict[str, Any], is_pyi: bool) -> Any:
        key = (pyproject, is_pyi)
        if key in self._mode_cache:
            return self._mode_cache[key]

        black = self._black
        target_versions = config.get("target_version") or []
        if isinstance(target_versions, str):
            target_versions = [target_versions]
        kwargs: Dict[str, Any] = {
            "target_versions": {black.TargetVersion[str(v).upper()] for v in target_versions},
            "line_length": int(config.get("line_length", black.DEFAULT_LINE_LENGTH)),
            "string_normalization": not config.get("skip_string_normalization", False),
            "magic_trailing_comma": not config.get("skip_magic_trailing_comma", False),
            "skip_source_first_line": bool(config.get("skip_source_first_line", False)),
            "preview": bool(config.get("preview", False)),
            "unstable": bool(config.get("unstable", False)),
            "is_pyi": is_pyi,
        }
        features = config.get("enable_unstable_feature") or []
        if features:
            kwargs["enabled_features"] = {black.Preview[str(f)] for f in features}

        # Only pass fields this Black version knows about.
        allowed = {f.name for f in fields(black.Mode)}
        mode = black.Mode(**{k: v for k, v in kwargs.items() if k in allowed})
        self._mode_cache[key] = mode
        return mode

    @staticmethod
    def _compile_regex(pattern: str) -> "re.Pattern[str]":
        # Same rule as black's re_compile_maybe_verbose.
        if "\n" in pattern:
            pattern = "(?x)" + pattern
        return re.compile(pattern)

    def _is_excluded(self, path: Path, config: Dict[str, Any], root: Optional[Path]) -> bool:
        """Honor Black's force-exclude and extend-exclude settings."""
        if root is None:
            return False
        try:
            relative = "/" + path.resolve().relative_to(root).as_posix()
        except ValueError:
            return False
        patterns = [config.get(key) for key in ("force_exclude", "extend_exclude")]
        return any(self._regex_matches(str(p), relative) for p in patterns if p)

    def _regex_matches(self, pattern: str, relative: str) -> bool:
        try:
            return bool(self._compile_regex(pattern).search(relative))
        except re.error as exc:
            self._warn(f"--format-check: invalid Black exclude regex {pattern!r}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Checking
    # ------------------------------------------------------------------
    def check_file(self, file_path: str, source: Optional[str] = None) -> Optional[AnalysisIssue]:
        """Return a FORMAT_DRIFT issue if Black would reformat ``file_path``."""
        path = Path(file_path)
        pyproject, config, root = self._load_config(path)
        if pyproject in self._bad_configs or self._is_excluded(path, config, root):
            self.stats.skipped += 1
            return None

        try:
            if source is None:
                source = path.read_text(encoding="utf-8")
            mode = self._build_mode(pyproject, config, path.suffix == ".pyi")
            formatted = self._black.format_file_contents(source, fast=True, mode=mode)
        except self._black.NothingChanged:
            self.stats.checked += 1
            return None
        except Exception as exc:
            # Invalid syntax for Black, unreadable file, bad config value...
            self.stats.errors += 1
            logger.debug("format check skipped %s: %s", file_path, exc)
            return None

        self.stats.checked += 1
        self.stats.drifted += 1
        return self._build_issue(file_path, source, formatted)

    def _build_issue(self, file_path: str, source: str, formatted: str) -> AnalysisIssue:
        diff_lines = list(
            difflib.unified_diff(
                source.splitlines(keepends=True),
                formatted.splitlines(keepends=True),
                fromfile=f"{file_path} (current)",
                tofile=f"{file_path} (black)",
            )
        )
        added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))
        first_line = _first_changed_line(diff_lines)

        truncated = len(diff_lines) > MAX_DIFF_LINES
        snippet_lines = [ln if ln.endswith("\n") else ln + "\n" for ln in diff_lines]
        snippet = "".join(snippet_lines[:MAX_DIFF_LINES])
        if truncated:
            snippet += f"... ({len(diff_lines) - MAX_DIFF_LINES} more diff lines)\n"

        version = self.stats.black_version
        return AnalysisIssue(
            file_path=file_path,
            line=first_line,
            column=0,
            issue_type=AnalysisIssueType.FORMAT_DRIFT,
            severity=AnalysisIssueSeverity.LOW,
            message=f"Black would reformat this file ({added} line(s) added, {removed} removed)",
            suggestion=f"Run: black {file_path}",
            code_snippet=snippet,
            metadata={
                "formatter": "black",
                "formatter_version": version,
                "lines_added": added,
                "lines_removed": removed,
                "diff_truncated": truncated,
            },
            engine=ENGINE_NAME,
        )


def _first_changed_line(diff_lines: List[str]) -> int:
    """Line number (1-based, original file) of the first changed line in a unified diff."""
    hunk = re.compile(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@")
    current = None
    for ln in diff_lines:
        match = hunk.match(ln)
        if match:
            current = int(match.group(1))
            continue
        if current is None or ln.startswith(("---", "+++")):
            continue
        if ln.startswith(("-", "+")):
            return max(current, 1)
        current += 1
    return 1


def _is_python_result(result: FileAnalysisResult) -> bool:
    if result.metadata.get("synthetic"):
        return False
    return result.language == "python" or Path(result.file_path).suffix in PYTHON_SUFFIXES


def run_format_check(
    file_results: Iterable[FileAnalysisResult],
    source_cache: Optional[Dict[str, str]] = None,
    checker: Optional[FormatDriftChecker] = None,
) -> Tuple[List[AnalysisIssue], FormatCheckStats]:
    """Run Black in check mode over the Python files in ``file_results``.

    Findings are appended to the matching ``FileAnalysisResult`` and also
    returned. Requires Black to be importable (see ``is_black_available``).
    """
    checker = checker or FormatDriftChecker()
    cache = source_cache or {}
    issues: List[AnalysisIssue] = []
    for result in file_results:
        if not _is_python_result(result):
            continue
        issue = checker.check_file(result.file_path, cache.get(result.file_path))
        if issue is not None:
            result.issues.append(issue)
            issues.append(issue)
    return issues, checker.stats


__all__ = [
    "BLACK_MISSING_WARNING",
    "FormatCheckStats",
    "FormatDriftChecker",
    "is_black_available",
    "run_format_check",
]
