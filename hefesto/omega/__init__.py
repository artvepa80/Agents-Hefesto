"""
HEFESTO OMEGA Guardian
======================

Complete monitoring and correlation suite:
- Hefesto PRO (all features + ML enhancement)
- IRIS Agent (production monitoring and alerts)
- Auto-correlation between code findings and production issues

Copyright © 2025 Narapa LLC, Miami, Florida
"""

__version__ = "4.2.0"

# IRIS integration
try:
    from hefesto.omega.hefesto_enricher import HefestoEnricher
    from hefesto.omega.iris_alert_manager import IrisAgent

    IRIS_AVAILABLE = True
except ImportError:
    IRIS_AVAILABLE = False
    IrisAgent = None
    HefestoEnricher = None

__all__ = [
    "IrisAgent",
    "HefestoEnricher",
    "IRIS_AVAILABLE",
]
