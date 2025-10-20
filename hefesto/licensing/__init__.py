"""
Hefesto licensing module.

Handles license key generation, validation, and tier enforcement.
"""

from hefesto.licensing.key_generator import LicenseKeyGenerator
from hefesto.licensing.license_validator import LicenseValidator
from hefesto.licensing.feature_gate import (
    FeatureGate,
    FeatureAccessDenied,
    requires_pro,
    requires_ml_analysis,
    requires_ai_recommendations,
    requires_security_scanning,
    requires_automated_triage,
    requires_integrations,
    requires_priority_support,
    requires_analytics
)

__all__ = [
    'LicenseKeyGenerator',
    'LicenseValidator',
    'FeatureGate',
    'FeatureAccessDenied',
    'requires_pro',
    'requires_ml_analysis',
    'requires_ai_recommendations',
    'requires_security_scanning',
    'requires_automated_triage',
    'requires_integrations',
    'requires_priority_support',
    'requires_analytics'
]

