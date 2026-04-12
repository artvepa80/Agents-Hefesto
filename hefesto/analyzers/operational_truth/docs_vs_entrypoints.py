"""DocsVsEntrypointsAnalyzer — Phase 1a Operational Truth.

Detects drift between documented CLI commands in README.md and the
actual entrypoints declared in ``pyproject.toml`` ``[project.scripts]``.

Conservative scope:
- Only emits findings for scripts declared in pyproject.toml that never
  appear in README.md. The reverse direction (README mentions a command
  not in pyproject) is too noisy on free-form prose.
- README command detection uses fenced code blocks and backtick spans.
- Finding points at ``[project.scripts]`` in pyproject.toml.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Set

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

logger = logging.getLogger(__name__)

try:  # pragma: no cover - py311+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - py310
    try:
        import tomli as _toml  # type: ignore
    except ModuleNotFoundError:
        _toml = None  # type: ignore


_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE = re.compile(r"`([^`\n]+)`")


class DocsVsEntrypointsAnalyzer:
    """Project-level analyzer: documented commands vs declared entrypoints."""

    def analyze_project(self, project_root: Path) -> List[AnalysisIssue]:
        project_root = Path(project_root).resolve()
        pyproject = project_root / "pyproject.toml"
        readme = project_root / "README.md"

        if not pyproject.exists() or _toml is None:
            return []

        scripts, scripts_line = self._read_scripts(pyproject)
        if not scripts:
            return []

        readme_text = ""
        if readme.exists():
            try:
                readme_text = readme.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                readme_text = ""

        mentioned = self._extract_mentioned_commands(readme_text)

        issues: List[AnalysisIssue] = []
        for script, target in scripts.items():
            if script in mentioned:
                continue
            issues.append(
                AnalysisIssue(
                    file_path=str(pyproject),
                    line=scripts_line,
                    column=0,
                    issue_type=AnalysisIssueType.DOCS_ENTRYPOINT_DRIFT,
                    severity=AnalysisIssueSeverity.LOW,
                    message=(
                        f"Entrypoint '{script}' ({target}) is declared in "
                        f"[project.scripts] but is not mentioned in README.md."
                    ),
                    suggestion=(
                        f"Document '{script}' in README.md or remove it from "
                        f"[project.scripts] if it is no longer supported."
                    ),
                    engine="internal:operational_truth",
                    rule_id="OT-DOCS-001",
                    confidence=0.7,
                )
            )
        return issues

    def _read_scripts(self, pyproject: Path) -> tuple[Dict[str, str], int]:
        scripts: Dict[str, str] = {}
        line = 1
        try:
            with open(pyproject, "rb") as f:
                data = _toml.load(f)
        except Exception as exc:
            logger.debug("pyproject.toml parse failed: %s", exc)
            return scripts, line

        raw = data.get("project", {}).get("scripts", {}) or {}
        for name, target in raw.items():
            scripts[str(name)] = str(target)

        try:
            with open(pyproject, "r", encoding="utf-8") as f:
                for idx, text in enumerate(f, start=1):
                    if text.strip().startswith("[project.scripts]"):
                        line = idx
                        break
        except Exception:
            pass

        return scripts, line

    def _extract_mentioned_commands(self, readme_text: str) -> Set[str]:
        if not readme_text:
            return set()
        mentioned: Set[str] = set()
        for block in _FENCE.findall(readme_text):
            for token in re.findall(r"\b([a-zA-Z][a-zA-Z0-9_\-]*)\b", block):
                mentioned.add(token)
        for inline in _INLINE.findall(readme_text):
            first = inline.strip().split()
            if first:
                mentioned.add(first[0])
        return mentioned


__all__ = ["DocsVsEntrypointsAnalyzer"]
