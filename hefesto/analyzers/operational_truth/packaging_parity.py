"""PackagingParityAnalyzer — Phase 1a Operational Truth.

Detects version drift across packaging artifacts that must agree:
- ``[project].version`` in pyproject.toml
- Top-level version entry in CHANGELOG.md
- README.md version badges / install snippets

Conservative scope:
- Only emits when a version string is clearly present in another artifact
  and disagrees with pyproject.toml (which is treated as ground truth).
- Missing artifacts are not findings (no CHANGELOG is valid).
- Finding points at the offending artifact, not pyproject.toml.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ProjectIdentity:
    version: Optional[str]
    name: Optional[str]
    github_slug: Optional[str]


try:  # pragma: no cover - py311+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - py310
    try:
        import tomli as _toml  # type: ignore
    except ModuleNotFoundError:
        _toml = None  # type: ignore


_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+(?:[.\-][A-Za-z0-9]+)?)")
_CHANGELOG_HEADER = re.compile(
    r"^\s*##\s*\[?v?(\d+\.\d+\.\d+(?:[.\-][A-Za-z0-9]+)?)\]?",
    re.MULTILINE,
)


class PackagingParityAnalyzer:
    """Project-level analyzer: version consistency across packaging files."""

    def analyze_project(self, project_root: Path) -> List[AnalysisIssue]:
        project_root = Path(project_root).resolve()
        pyproject = project_root / "pyproject.toml"
        if not pyproject.exists() or _toml is None:
            return []

        identity = self._read_identity(pyproject)
        if not identity.version:
            return []

        issues: List[AnalysisIssue] = []
        issues.extend(self._check_changelog(project_root, identity.version))
        issues.extend(self._check_readme(project_root, identity))
        return issues

    def _read_identity(self, pyproject: Path) -> "_ProjectIdentity":
        try:
            with open(pyproject, "rb") as f:
                data = _toml.load(f)
        except Exception as exc:
            logger.debug("pyproject.toml parse failed: %s", exc)
            return _ProjectIdentity(None, None, None)
        project = data.get("project", {}) or {}
        version = project.get("version")
        name = project.get("name")
        slug: Optional[str] = None
        urls = project.get("urls", {}) or {}
        for url in urls.values():
            m = re.search(r"github\.com/([^/\s#?]+/[^/\s#?]+)", str(url))
            if m:
                slug = m.group(1).rstrip("/")
                if slug.endswith(".git"):
                    slug = slug[: -len(".git")]
                break
        return _ProjectIdentity(
            version=str(version) if version else None,
            name=str(name) if name else None,
            github_slug=slug,
        )

    def _check_changelog(self, project_root: Path, canonical: str) -> List[AnalysisIssue]:
        changelog = project_root / "CHANGELOG.md"
        if not changelog.exists():
            return []
        try:
            text = changelog.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        match = _CHANGELOG_HEADER.search(text)
        if not match:
            return []
        top = match.group(1)
        if top == canonical:
            return []

        line = text[: match.start()].count("\n") + 1
        return [
            AnalysisIssue(
                file_path=str(changelog),
                line=line,
                column=0,
                issue_type=AnalysisIssueType.PACKAGING_VERSION_DRIFT,
                severity=AnalysisIssueSeverity.MEDIUM,
                message=(
                    f"CHANGELOG top entry is '{top}' but pyproject.toml "
                    f"declares version '{canonical}'."
                ),
                suggestion=(
                    f"Add a CHANGELOG entry for '{canonical}' or align "
                    f"pyproject.toml version with CHANGELOG."
                ),
                engine="internal:operational_truth",
                rule_id="OT-PKG-001",
                confidence=0.85,
            )
        ]

    def _check_readme(
        self, project_root: Path, identity: "_ProjectIdentity"
    ) -> List[AnalysisIssue]:
        readme = project_root / "README.md"
        if not readme.exists():
            return []
        try:
            text = readme.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        canonical = identity.version or ""
        if not canonical:
            return []

        patterns: List[tuple[str, str]] = []
        if identity.github_slug:
            patterns.append(
                (
                    rf"{re.escape(identity.github_slug)}@v?(\d+\.\d+\.\d+)",
                    "GitHub Action tag",
                )
            )
        if identity.name:
            patterns.append(
                (
                    rf"pip install {re.escape(identity.name)}(?:\[[^\]]*\])?==(\d+\.\d+\.\d+)",
                    "pip install command",
                )
            )
        patterns.append((r"CLI Reference \(v?(\d+\.\d+\.\d+)\)", "CLI Reference heading"))
        patterns.append((r"version-(\d+\.\d+\.\d+)-", "version badge"))
        issues: List[AnalysisIssue] = []
        for pattern, label in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            found = match.group(1)
            if found == canonical:
                continue
            line = text[: match.start()].count("\n") + 1
            issues.append(
                AnalysisIssue(
                    file_path=str(readme),
                    line=line,
                    column=0,
                    issue_type=AnalysisIssueType.PACKAGING_VERSION_DRIFT,
                    severity=AnalysisIssueSeverity.MEDIUM,
                    message=(
                        f"README {label} shows '{found}' but pyproject.toml "
                        f"declares '{canonical}'."
                    ),
                    suggestion=f"Update README {label} to '{canonical}'.",
                    engine="internal:operational_truth",
                    rule_id="OT-PKG-002",
                    confidence=0.85,
                )
            )
        return issues


__all__ = ["PackagingParityAnalyzer"]
