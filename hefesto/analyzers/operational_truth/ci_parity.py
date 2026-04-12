"""CiParityAnalyzer — Phase 1b (ci_parity unification).

Adapter that surfaces findings from ``hefesto.validators.ci_parity`` in the
main ``AnalyzerEngine`` pipeline as ``AnalysisIssue`` objects.

Convergence strategy (not a rewrite)
------------------------------------
The detection logic remains the single source of truth in
``hefesto/validators/ci_parity.py`` (``CIParityChecker.check_all()``).
This analyzer only *adapts* its output to the unified issue model so that
``hefesto analyze`` can report CI drift alongside every other finding type.
The legacy ``hefesto check-ci-parity`` CLI command continues to work
unchanged and calls the same checker directly.

Mapping from ``ParityIssue.category`` to rule id + severity:

    "Python Version"     → OT-CI-001  (MEDIUM)  — CI matrix drift
    "Tool Installation"  → OT-CI-002  (LOW)     — local env missing tool
    "Flake8 Config"      → OT-CI-003  (HIGH)    — lint config drift

"Tool Installation" is intentionally demoted from the legacy HIGH to LOW:
the condition describes the developer's machine, not the repository, and
inflating it to HIGH would fail the BP-7 false-positive budget for users
who legitimately run Hefesto without every CI tool installed locally.

Target file resolution
----------------------
Findings are routed to the offending artifact, not the project root:

- Python version drift → the CI workflow YAML (``checker.ci_workflow``)
- Flake8 config drift  → first local config that exists, in priority order
  ``.flake8`` → ``setup.cfg`` → ``pyproject.toml``
- Missing local tool   → ``pyproject.toml`` (where users would add extras)

Performance policy (BP-8)
-------------------------
``check_all()`` on the legacy checker unconditionally shells out four
``subprocess.run`` invocations — one per linter tool — every single time
``hefesto analyze`` runs. That adds ~650ms of fixed startup cost on a clean
no-CI project and breaches the BP-8 latency budget.

This adapter avoids the problem by invoking the three sub-checks
individually and gating only the expensive one:

- ``check_python_version``  — cheap (reads CI YAML), always run.
- ``check_flake8_config``   — cheap (reads CI YAML + local config), always run.
- ``check_tool_versions``   — expensive (4× subprocess.run), **only run when
  a CI workflow exists**. With no workflow there is nothing to parity
  against, so the subprocess spawn is pure waste.

The decision of *when* to invoke each check lives in the adapter, not in
``CIParityChecker`` — the checker stays the single source of truth for
*how* each check works.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)

logger = logging.getLogger(__name__)


_CATEGORY_TO_RULE = {
    "Python Version": ("OT-CI-001", AnalysisIssueSeverity.MEDIUM),
    "Tool Installation": ("OT-CI-002", AnalysisIssueSeverity.LOW),
    "Flake8 Config": ("OT-CI-003", AnalysisIssueSeverity.HIGH),
}


class CiParityAnalyzer:
    """Project-level analyzer: adapts ci_parity findings to AnalysisIssue."""

    def analyze_project(self, project_root: Path) -> List[AnalysisIssue]:
        project_root = Path(project_root).resolve()
        if not project_root.is_dir():
            return []

        try:
            from hefesto.validators.ci_parity import CIParityChecker
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("ci_parity import failed: %s", exc)
            return []

        try:
            checker = CIParityChecker(project_root)
        except Exception as exc:
            logger.debug("CIParityChecker init failed: %s", exc)
            return []

        parity_issues: list = []
        # Cheap checks: parse YAML + read local config, no subprocess.
        try:
            parity_issues.extend(checker.check_python_version())
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("check_python_version failed: %s", exc)
        try:
            parity_issues.extend(checker.check_flake8_config())
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("check_flake8_config failed: %s", exc)

        # Expensive check: 4 subprocess.run invocations. Only run when
        # a CI workflow exists — otherwise there is nothing to parity
        # against and we would burn ~650ms for zero signal (BP-8).
        if checker.ci_workflow is not None:
            try:
                parity_issues.extend(checker.check_tool_versions())
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("check_tool_versions failed: %s", exc)

        pyproject = project_root / "pyproject.toml"
        flake8_target = self._find_flake8_target(project_root)
        workflow_target = checker.ci_workflow

        issues: List[AnalysisIssue] = []
        for parity in parity_issues:
            category = parity.category
            rule_id, severity = _CATEGORY_TO_RULE.get(
                category, ("OT-CI-000", AnalysisIssueSeverity.LOW)
            )

            if category == "Python Version":
                target = workflow_target or pyproject
            elif category == "Flake8 Config":
                target = flake8_target or pyproject
            else:  # Tool Installation and fallback
                target = pyproject

            if target is None or not Path(target).exists():
                # Skip findings we cannot anchor to a real artifact — keeps
                # the unified report trustworthy.
                continue

            issues.append(
                AnalysisIssue(
                    file_path=str(target),
                    line=1,
                    column=0,
                    issue_type=AnalysisIssueType.CI_CONFIG_DRIFT,
                    severity=severity,
                    message=f"[{category}] {parity.message}",
                    suggestion=parity.fix_suggestion,
                    engine="internal:operational_truth",
                    rule_id=rule_id,
                    confidence=0.9,
                    metadata={
                        "parity_category": category,
                        "local_value": parity.local_value,
                        "ci_value": parity.ci_value,
                    },
                )
            )
        return issues

    @staticmethod
    def _find_flake8_target(project_root: Path) -> Optional[Path]:
        for name in (".flake8", "setup.cfg", "pyproject.toml"):
            candidate = project_root / name
            if candidate.exists():
                return candidate
        return None


__all__ = ["CiParityAnalyzer"]
