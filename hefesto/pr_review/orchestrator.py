"""PR review orchestrator — wires diff parsing, scoped analysis and dedup.

Contract:
- ``run_pr_review(project_root, base, head, strict=False)`` → ``PrReviewResult``
- Shells out to ``git`` for diff retrieval and SHA resolution. This is
  the only impure step; everything else is pure-functional and unit-
  testable without a live git repo.
- Never posts to GitHub. The returned ``PrReviewResult`` is serialised
  to JSON by the CLI and consumed downstream by ``gh`` CLI or workflow
  pipelines that handle authentication, rate limiting, and dedup
  enforcement against existing PR comments.

Default filtering: findings are reported **only** when their line falls
inside a hunk from the diff. Strict mode additionally surfaces findings
anywhere in the touched files (file-level context). Project-level
findings (operational truth, CI parity) are filtered to the set of
touched files to avoid leaking findings anchored to files the PR does
not modify.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hefesto.core.analyzer_engine import AnalyzerEngine
from hefesto.pr_review.dedup import compute_dedup_key
from hefesto.pr_review.diff import parse_unified_diff

logger = logging.getLogger(__name__)

PR_REVIEW_VERSION = 1


@dataclass
class PrReviewResult:
    pr_review_version: int
    base_sha: Optional[str]
    head_sha: Optional[str]
    changed_files: List[str]
    findings: List[Dict[str, Any]]
    strict: bool = False
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- git helpers


def _run_git(args: List[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={result.returncode}): " f"{result.stderr.strip()}"
        )
    return result.stdout


def _resolve_sha(ref: str, cwd: Path) -> Optional[str]:
    try:
        return _run_git(["rev-parse", ref], cwd).strip() or None
    except Exception:
        return None


def _default_base_and_head(cwd: Path) -> "tuple[str, str]":
    """Return sensible (base, head) refs when the caller omits them.

    Preference order:
    1. GitHub Actions env (``GITHUB_BASE_REF``, ``GITHUB_SHA``)
    2. ``git merge-base HEAD origin/main``
    3. Hardcoded fallback to ``HEAD~1..HEAD`` (last commit)
    """
    env_base = os.environ.get("GITHUB_BASE_REF")
    env_head = os.environ.get("GITHUB_SHA")
    if env_base and env_head:
        return f"origin/{env_base}", env_head

    for main_ref in ("origin/main", "main", "origin/master", "master"):
        try:
            base = _run_git(["merge-base", "HEAD", main_ref], cwd).strip()
            if base:
                return base, "HEAD"
        except Exception:
            continue

    logger.warning(
        "hefesto pr-review: no main-like branch found; falling back to "
        "HEAD~1..HEAD (reviewing only the most recent commit). Pass "
        "--base explicitly to review against a different base."
    )
    return "HEAD~1", "HEAD"


def _get_diff(base: str, head: str, cwd: Path) -> str:
    return _run_git(
        ["diff", "--no-color", "--no-ext-diff", f"{base}...{head}"],
        cwd,
    )


# ---------------------------------------------------------------- main entry


def run_pr_review(
    project_root: Path,
    base: Optional[str] = None,
    head: Optional[str] = None,
    strict: bool = False,
    engine: Optional[AnalyzerEngine] = None,
) -> PrReviewResult:
    """Generate a PR review JSON for the diff between ``base`` and ``head``.

    ``project_root`` should be the top-level directory of the repo.
    ``engine`` is injectable for tests; when omitted the CLI
    instantiates the standard ``_setup_analyzer_engine``.
    """
    project_root = Path(project_root).resolve()
    if base is None or head is None:
        resolved_base, resolved_head = _default_base_and_head(project_root)
        base = base or resolved_base
        head = head or resolved_head

    diff_text = _get_diff(base, head, project_root)
    file_diffs = parse_unified_diff(diff_text)

    changed_line_map: Dict[str, set] = {}
    for fd in file_diffs:
        if fd.is_binary or fd.is_deleted_file:
            continue
        if not fd.new_path or fd.new_path == "/dev/null":
            continue
        changed_line_map[fd.new_path] = fd.changed_lines

    changed_files = sorted(changed_line_map.keys())

    abs_paths: List[str] = []
    for rel in changed_files:
        abs_path = (project_root / rel).resolve()
        if abs_path.exists() and abs_path.is_file():
            abs_paths.append(str(abs_path))

    if engine is None:
        engine = _build_default_engine()

    report = engine.analyze_files(abs_paths, project_root=str(project_root))

    findings_json = _filter_and_serialize(
        report,
        project_root,
        changed_line_map,
        strict,
    )

    return PrReviewResult(
        pr_review_version=PR_REVIEW_VERSION,
        base_sha=_resolve_sha(base, project_root),
        head_sha=_resolve_sha(head, project_root),
        changed_files=changed_files,
        findings=findings_json,
        strict=strict,
        diagnostics={
            "files_scanned": len(abs_paths),
            "files_in_diff": len(changed_files),
            "raw_issues": len(report.get_all_issues()),
        },
    )


# ---------------------------------------------------------------- filtering


def _filter_and_serialize(
    report,
    project_root: Path,
    changed_line_map: Dict[str, set],
    strict: bool,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    changed_file_set = set(changed_line_map.keys())

    for file_result in report.file_results:
        rel_path = _relative_path(file_result.file_path, project_root)

        # Project analyzer findings live in synthetic file results that
        # point at anchor files (pyproject.toml, CHANGELOG.md, etc.).
        # Only surface them when that anchor file is part of the PR.
        is_synthetic = file_result.metadata.get("synthetic", False)
        if is_synthetic and rel_path not in changed_file_set:
            continue

        # Files that are NOT in the diff scope — ignore entirely. This
        # guards against ``_analyze_file`` side-effects that might have
        # included neighbours.
        if rel_path not in changed_file_set and not is_synthetic:
            continue

        diff_lines = changed_line_map.get(rel_path, set())

        for issue in file_result.issues:
            in_hunk = issue.line in diff_lines
            if not in_hunk and not strict:
                # Default policy: only changed-line findings surface.
                # Strict mode additionally surfaces file-level context.
                continue

            out.append(
                {
                    "file": rel_path,
                    "line": issue.line,
                    "column": issue.column,
                    "type": issue.issue_type.value,
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                    "dedup_key": compute_dedup_key(issue, relative_path=rel_path),
                    "in_hunk": in_hunk,
                    "engine": issue.engine,
                    "rule_id": issue.rule_id,
                }
            )

    return out


def _relative_path(abs_path: str, project_root: Path) -> str:
    try:
        return str(Path(abs_path).resolve().relative_to(project_root.resolve()))
    except ValueError:
        return abs_path


def _build_default_engine() -> AnalyzerEngine:
    """Mirror ``hefesto/cli/main.py::_setup_analyzer_engine`` without the
    CLI-side click logging. Kept thin — any future analyzer registered
    in the CLI setup should also be registered here."""
    from hefesto.analyzers import (
        BestPracticesAnalyzer,
        CodeSmellAnalyzer,
        ComplexityAnalyzer,
        SecurityAnalyzer,
    )
    from hefesto.analyzers.operational_truth import (
        CiParityAnalyzer,
        DocsVsEntrypointsAnalyzer,
        ImportsVsDepsAnalyzer,
        InstallArtifactParityAnalyzer,
        PackagingParityAnalyzer,
    )
    from hefesto.security.packs.resource_safety_v1 import ResourceSafetyAnalyzer

    engine = AnalyzerEngine(severity_threshold="LOW", verbose=False)
    engine.register_analyzer(ComplexityAnalyzer())
    engine.register_analyzer(CodeSmellAnalyzer())
    engine.register_analyzer(SecurityAnalyzer())
    engine.register_analyzer(BestPracticesAnalyzer())
    engine.register_analyzer(ResourceSafetyAnalyzer())
    engine.register_project_analyzer(ImportsVsDepsAnalyzer())
    engine.register_project_analyzer(DocsVsEntrypointsAnalyzer())
    engine.register_project_analyzer(PackagingParityAnalyzer())
    engine.register_project_analyzer(InstallArtifactParityAnalyzer())
    engine.register_project_analyzer(CiParityAnalyzer())
    return engine


__all__ = ["PrReviewResult", "run_pr_review", "PR_REVIEW_VERSION"]
