"""
Optional imports from hefesto_pro (PRO add-on).

OSS works without PRO installed. Each feature degrades to a no-op fallback
when the corresponding PRO module is missing (ModuleNotFoundError).
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# EPIC 1 — Scope Gating
# ---------------------------------------------------------------------------

try:
    from hefesto_pro.scope_gating.classifier import (  # type: ignore[import-untyped]
        ScopeGatingConfig,
    )
    from hefesto_pro.scope_gating.orchestrator import (  # type: ignore[import-untyped]
        build_scope_summary,
        filter_paths,
    )

    HAS_SCOPE_GATING = True
except ModuleNotFoundError:
    HAS_SCOPE_GATING = False

    class ScopeGatingConfig:  # type: ignore[no-redef]
        """No-op fallback: all paths included, nothing skipped."""

        def __init__(self, **kwargs: Any) -> None:
            pass

    def filter_paths(  # type: ignore[misc]
        paths: List[Path], config: Any
    ) -> Tuple[List[Path], List[Any]]:
        return list(paths), []

    def build_scope_summary(skipped: List[Any]) -> Dict[str, Any]:  # type: ignore[misc]
        return {}


# ---------------------------------------------------------------------------
# EPIC 2 — Multi-Language Discovery
# ---------------------------------------------------------------------------

try:
    from hefesto_pro.multilang.parser import TsJsParser  # type: ignore[import-untyped]
    from hefesto_pro.multilang.skip_report import SkipReport  # type: ignore[import-untyped]

    HAS_MULTILANG = True
except ModuleNotFoundError:
    HAS_MULTILANG = False
    TsJsParser = None  # type: ignore[assignment, misc]
    SkipReport = None  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# EPIC 3 — Safe Enrichment
# ---------------------------------------------------------------------------

try:
    from hefesto_pro.enrichment import (  # type: ignore[import-untyped]
        EnrichmentConfig,
        EnrichmentInput,
        EnrichmentOrchestrator,
    )

    HAS_ENRICHMENT = True
except ModuleNotFoundError:
    HAS_ENRICHMENT = False
    EnrichmentConfig = None  # type: ignore[assignment, misc]
    EnrichmentInput = None  # type: ignore[assignment, misc]
    EnrichmentOrchestrator = None  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# API Hardening (Patch C)
# ---------------------------------------------------------------------------

try:
    from hefesto_pro.api_hardening import (  # type: ignore[import-untyped]
        HardeningSettings,
        apply_hardening,
    )

    HAS_API_HARDENING = True
except ModuleNotFoundError:
    HAS_API_HARDENING = False
    HardeningSettings = None  # type: ignore[assignment, misc]

    def apply_hardening(app: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        """No-op fallback: server runs without hardening."""
        pass
