"""
API Routers

Endpoints organized by domain:
- health: Health checks and system status
- analysis: Code analysis endpoints (Phase 2)
- findings: Findings management (Phase 3)
- iris: Iris integration (Phase 4)
- metrics: Metrics & analytics (Phase 5)
- config: Configuration (Phase 6)
"""

from hefesto.api.routers import analysis, health

__all__ = ["health", "analysis"]
