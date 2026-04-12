"""Operational Truth analyzers (Phase 1a).

Project-level analyzers that detect drift between what a project
declares about itself (dependencies, documented commands, packaging
metadata, install artifacts) and what its code actually does. Each
analyzer exposes ``analyze_project(project_root: Path) -> List[AnalysisIssue]``
and is registered on ``AnalyzerEngine`` via ``register_project_analyzer``.

Reuse vs new AnalysisIssueType — inventory rationale
---------------------------------------------------
Before adding new types we walked the existing ``AnalysisIssueType`` enum
(``hefesto/core/analysis_models.py``) and grouped entries by category:

    Complexity:         HIGH_COMPLEXITY, VERY_HIGH_COMPLEXITY
    Code smells:        LONG_FUNCTION, LONG_PARAMETER_LIST, DEEP_NESTING,
                        DUPLICATE_CODE, DEAD_CODE, MAGIC_NUMBER, GOD_CLASS,
                        INCOMPLETE_TODO
    Security:           HARDCODED_SECRET, SQL_INJECTION_RISK, COMMAND_INJECTION,
                        EVAL_USAGE, PICKLE_USAGE, ASSERT_IN_PRODUCTION, BARE_EXCEPT
    Best practices:     MISSING_DOCSTRING, POOR_NAMING, STYLE_VIOLATION
    DevOps (Ola 1-2):   YAML_*, TF_*, SHELL_*, PS_*, DOCKER_*, DOCKERFILE_*, SQL_*
    Cross-language:     INSECURE_COMMUNICATION, SECURITY_MISCONFIGURATION
    Reliability (E4):   RELIABILITY_UNBOUNDED_GLOBAL, ..._CACHE, ..._SESSION_LIFECYCLE,
                        ..._LOGGING_HANDLER_DUP, ..._THREAD_IN_REQUEST
    External:           EXTERNAL_FINDING

None of these captures "declared-vs-real drift" — the semantic domain is
orthogonal. The complaint is not about *code content* inside a single file
but about *agreement between artifacts*. Reusing e.g. STYLE_VIOLATION would
collapse actionable cues into a single bucket and break rule-id filtering.

Four new types were therefore added, one per analyzer, with distinct
rule_id prefixes under engine ``internal:operational_truth``:

    UNDECLARED_DEPENDENCY      — OT-IMPORTS-001  (ImportsVsDepsAnalyzer)
    DOCS_ENTRYPOINT_DRIFT      — OT-DOCS-001     (DocsVsEntrypointsAnalyzer)
    PACKAGING_VERSION_DRIFT    — OT-PKG-001/002  (PackagingParityAnalyzer)
    INSTALL_ARTIFACT_DRIFT     — OT-INSTALL-001/002 (InstallArtifactParityAnalyzer)

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from hefesto.analyzers.operational_truth.ci_parity import CiParityAnalyzer
from hefesto.analyzers.operational_truth.docs_vs_entrypoints import (
    DocsVsEntrypointsAnalyzer,
)
from hefesto.analyzers.operational_truth.imports_vs_deps import (
    ImportsVsDepsAnalyzer,
)
from hefesto.analyzers.operational_truth.install_artifact_parity import (
    InstallArtifactParityAnalyzer,
)
from hefesto.analyzers.operational_truth.packaging_parity import (
    PackagingParityAnalyzer,
)

__all__ = [
    "ImportsVsDepsAnalyzer",
    "DocsVsEntrypointsAnalyzer",
    "PackagingParityAnalyzer",
    "InstallArtifactParityAnalyzer",
    "CiParityAnalyzer",
]
