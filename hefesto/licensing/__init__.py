"""
Hefesto licensing module.

Handles license key generation, validation, and tier enforcement.
"""

from hefesto.licensing.feature_gate import (
    FeatureAccessDenied,
    FeatureGate,
    requires_ai_recommendations,
    requires_analytics,
    requires_automated_triage,
    requires_integrations,
    requires_ml_analysis,
    requires_priority_support,
    requires_pro,
    requires_security_scanning,
)
from hefesto.licensing.key_generator import LicenseKeyGenerator
from hefesto.licensing.license_validator import LicenseValidator

__all__ = [
    "LicenseKeyGenerator",
    "LicenseValidator",
    "FeatureGate",
    "FeatureAccessDenied",
    "requires_pro",
    "requires_ml_analysis",
    "requires_ai_recommendations",
    "requires_security_scanning",
    "requires_automated_triage",
    "requires_integrations",
    "requires_priority_support",
    "requires_analytics",
]
