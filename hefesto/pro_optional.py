"""
Optional imports from hefesto_pro (PRO add-on).

OSS works without PRO installed. Each feature degrades to a no-op fallback
when PRO is absent: not installed (the missing module is ``hefesto_pro`` or
one of its submodules) or ``ProLicenseRequired``. A PRO install that is
present but broken (any other ImportError, including a ModuleNotFoundError
for one of PRO's own dependencies) degrades the same way and prints one
warning to stderr, so ``hefesto analyze`` keeps working.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _pro_absent(exc: ImportError) -> bool:
    """True when *exc* means PRO is not installed or not licensed (stay silent)."""
    if any(cls.__name__ == "ProLicenseRequired" for cls in type(exc).__mro__):
        return True
    if not isinstance(exc, ModuleNotFoundError):
        return False
    name = exc.name or ""
    return name == "hefesto_pro" or name.startswith("hefesto_pro.")


def _warn_broken_pro(feature: str, exc: ImportError) -> None:
    print(
        f"Warning: hefesto_pro is installed but {feature} failed to import "
        f"({type(exc).__name__}: {exc}); continuing without it.",
        file=sys.stderr,
    )


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
except ImportError as _exc:
    # PRO not installed, or ProLicenseRequired, stays silent.
    if not _pro_absent(_exc):
        _warn_broken_pro("scope gating", _exc)
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
except ImportError as _exc:
    # PRO not installed, or ProLicenseRequired, stays silent.
    if not _pro_absent(_exc):
        _warn_broken_pro("multi-language discovery", _exc)
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
except ImportError as _exc:
    # PRO not installed, or ProLicenseRequired, stays silent.
    if not _pro_absent(_exc):
        _warn_broken_pro("enrichment", _exc)
    HAS_ENRICHMENT = False
    EnrichmentConfig = None  # type: ignore[assignment, misc]
    EnrichmentInput = None  # type: ignore[assignment, misc]
    EnrichmentOrchestrator = None  # type: ignore[assignment, misc]

# Optional extras: older PRO builds may not export these names.
try:
    from hefesto_pro.enrichment import EnrichmentCache  # type: ignore[import-untyped]
except ImportError:
    EnrichmentCache = None  # type: ignore[assignment, misc]
try:
    from hefesto_pro.enrichment import EnrichmentProvider  # type: ignore[import-untyped]
except ImportError:
    EnrichmentProvider = None  # type: ignore[assignment, misc]


# ---------------------------------------------------------------------------
# API Hardening (Patch C)
# ---------------------------------------------------------------------------

try:
    from hefesto_pro.api_hardening import (  # type: ignore[import-untyped]
        HardeningSettings,
        apply_hardening,
    )

    HAS_API_HARDENING = True
except ImportError as _exc:
    # PRO not installed, or ProLicenseRequired, stays silent.
    if not _pro_absent(_exc):
        _warn_broken_pro("API hardening", _exc)
    HAS_API_HARDENING = False
    HardeningSettings = None  # type: ignore[assignment, misc]

    def apply_hardening(app: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        """No-op fallback: server runs without hardening."""
        pass
