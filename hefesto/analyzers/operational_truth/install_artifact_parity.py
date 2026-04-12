"""InstallArtifactParityAnalyzer — Phase 1a Operational Truth.

Detects drift between install artifacts and the real repo:
- ``action.yml`` inputs that are never referenced as ``INPUT_<NAME>``
  in ``scripts/action_entrypoint.sh``.
- ``Dockerfile.action`` ``COPY`` sources that do not exist in the repo.

Conservative scope: all findings are concrete, high-confidence checks.
Finding points at the offending line in the offending artifact.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

logger = logging.getLogger(__name__)

try:
    import yaml  # type: ignore
except ModuleNotFoundError:
    yaml = None  # type: ignore


class InstallArtifactParityAnalyzer:
    """Project-level analyzer: install artifacts vs real repo layout."""

    def analyze_project(self, project_root: Path) -> List[AnalysisIssue]:
        project_root = Path(project_root).resolve()
        issues: List[AnalysisIssue] = []
        issues.extend(self._check_action_inputs(project_root))
        issues.extend(self._check_dockerfile_copies(project_root))
        return issues

    def _check_action_inputs(self, project_root: Path) -> List[AnalysisIssue]:
        action = project_root / "action.yml"
        entrypoint = project_root / "scripts" / "action_entrypoint.sh"
        if not action.exists() or not entrypoint.exists() or yaml is None:
            return []
        try:
            data = yaml.safe_load(action.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("action.yml parse failed: %s", exc)
            return []
        inputs = (data or {}).get("inputs") or {}
        if not isinstance(inputs, dict) or not inputs:
            return []

        try:
            script = entrypoint.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        issues: List[AnalysisIssue] = []
        for name in inputs.keys():
            env_var = f"INPUT_{name.upper()}"
            if env_var in script:
                continue
            line = self._find_yaml_key_line(action, name)
            issues.append(
                AnalysisIssue(
                    file_path=str(action),
                    line=line,
                    column=0,
                    issue_type=AnalysisIssueType.INSTALL_ARTIFACT_DRIFT,
                    severity=AnalysisIssueSeverity.MEDIUM,
                    message=(
                        f"action.yml declares input '{name}' but "
                        f"scripts/action_entrypoint.sh never reads {env_var}."
                    ),
                    suggestion=(
                        f"Either consume {env_var} in action_entrypoint.sh or "
                        f"remove the unused input from action.yml."
                    ),
                    engine="internal:operational_truth",
                    rule_id="OT-INSTALL-001",
                    confidence=0.9,
                )
            )
        return issues

    def _check_dockerfile_copies(self, project_root: Path) -> List[AnalysisIssue]:
        dockerfile = project_root / "Dockerfile.action"
        if not dockerfile.exists():
            return []
        try:
            lines = dockerfile.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []

        issues: List[AnalysisIssue] = []
        copy_re = re.compile(r"^\s*COPY\s+(?!--from)(.+?)\s+(\S+)\s*$")
        for idx, text in enumerate(lines, start=1):
            m = copy_re.match(text)
            if not m:
                continue
            sources = m.group(1).split()
            for src in sources:
                if src.startswith("--") or "*" in src or "$" in src:
                    continue
                candidate = (project_root / src).resolve()
                try:
                    candidate.relative_to(project_root)
                except ValueError:
                    continue
                if candidate.exists():
                    continue
                issues.append(
                    AnalysisIssue(
                        file_path=str(dockerfile),
                        line=idx,
                        column=0,
                        issue_type=AnalysisIssueType.INSTALL_ARTIFACT_DRIFT,
                        severity=AnalysisIssueSeverity.HIGH,
                        message=(
                            f"Dockerfile.action COPY source '{src}' "
                            f"does not exist in the repository."
                        ),
                        suggestion=(f"Remove the COPY line or restore the missing path '{src}'."),
                        engine="internal:operational_truth",
                        rule_id="OT-INSTALL-002",
                        confidence=0.95,
                    )
                )
        return issues

    @staticmethod
    def _find_yaml_key_line(action: Path, key: str) -> int:
        try:
            for idx, line in enumerate(action.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith(f"{key}:"):
                    return idx
        except Exception:
            pass
        return 1


__all__ = ["InstallArtifactParityAnalyzer"]
