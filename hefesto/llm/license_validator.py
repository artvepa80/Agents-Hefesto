"""
HEFESTO License Validation for Pro Features (STUB - Public Version)
====================================================================

⚠️  This is a public stub. Real implementation is in private repository.

Purpose: Validate Stripe license keys for Pro/OMEGA features.

Pro/OMEGA Features (Commercial License Required):
- semantic_analyzer.py - ML-based code embeddings
- cicd_feedback_collector.py - Automated CI/CD feedback
- metrics.py - Advanced analytics dashboard
- IRIS Agent - Production monitoring
- OMEGA Guardian - Alert correlation

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Set

logger = logging.getLogger(__name__)


class LicenseError(Exception):
    """Exception raised when license validation fails."""

    pass


@dataclass
class LicenseInfo:
    """License information."""

    is_valid: bool
    license_key: Optional[str]
    features_enabled: Set[str]
    tier: str  # 'free', 'pro', 'omega'
    expires_at: Optional[datetime] = None
    customer_email: Optional[str] = None


class LicenseValidator:
    """
    Validates Pro licenses for Phase 1 features.

    ⚠️  STUB: Public version provides basic interface only.
    Real validation logic is in private repository.

    Usage:
        >>> validator = LicenseValidator()
        >>> if validator.is_pro():
        ...     # Enable semantic analysis
        ...     analyzer = SemanticAnalyzer()
        ... else:
        ...     raise LicenseError("Semantic analysis requires Pro license")
    """

    # Features that require Pro license
    PRO_FEATURES = {
        "semantic_analysis",
        "cicd_feedback",
        "duplicate_detection",
        "metrics_dashboard",
        "code_embeddings",
        "ml_similarity",
    }

    # Valid license key prefixes (Stripe format)
    VALID_PREFIXES = {
        "HFST-",  # OMEGA Guardian format (HFST-XXXX-XXXX-XXXX-XXXX-XXXX)
        "hef_",  # Hefesto production keys (legacy)
        "sk_",  # Stripe secret keys (for testing)
        "pk_",  # Stripe publishable keys
    }

    def __init__(self):
        """
        Initialize license validator.

        ⚠️  STUB: Public version always returns FREE tier.
        """
        self.license_key = os.getenv("HEFESTO_LICENSE_KEY")
        self.license_info = self._validate_key()

    def _validate_key(self) -> LicenseInfo:
        """
        Validate license key format and status.

        ⚠️  STUB: Public version does not validate against Stripe API.
        Real validation is server-side only.

        Returns:
            LicenseInfo with validation results (always FREE in public version)
        """
        # Try to use real validator from hefesto-pro package if installed
        try:
            from hefesto_pro.licensing.license_validator import LicenseValidator as ProValidator

            pro_validator = ProValidator()
            tier = pro_validator.get_tier_for_key(self.license_key)

            if tier in ["professional", "omega"]:
                is_pro = tier in ["professional", "omega"]
                features = self.PRO_FEATURES if is_pro else set()
                return LicenseInfo(
                    is_valid=True,
                    license_key=self.license_key,
                    features_enabled=features,
                    tier=tier,
                )
        except ImportError:
            pass  # Fall back to stub behavior

        if not self.license_key:
            logger.debug("No license key found - running in Free mode")
            return LicenseInfo(
                is_valid=False,
                license_key=None,
                features_enabled=set(),
                tier="free",
            )

        # Check key format
        if not any(self.license_key.startswith(prefix) for prefix in self.VALID_PREFIXES):
            logger.warning(
                f"Invalid license key format. " f"Must start with: {', '.join(self.VALID_PREFIXES)}"
            )
            return LicenseInfo(
                is_valid=False,
                license_key=self.license_key,
                features_enabled=set(),
                tier="free",
            )

        # ⚠️  STUB: Public version cannot validate licenses
        # Real validation requires Stripe API access (private repository)
        logger.warning(
            "⚠️  License validation not available in public version. "
            "Running in FREE mode. "
            "To activate PRO/OMEGA features, subscribe at: "
            "https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b"
        )

        return LicenseInfo(
            is_valid=False,
            license_key=self.license_key,
            features_enabled=set(),
            tier="free",
        )

    def is_pro(self) -> bool:
        """
        Check if Pro license is active.

        ⚠️  STUB: Always returns False in public version unless hefesto-pro installed.
        """
        return self.license_info.tier in ["professional", "omega"]

    def has_feature(self, feature: str) -> bool:
        """
        Check if specific feature is enabled.

        ⚠️  STUB: Always returns False in public version.
        """
        return False

    def require_pro(self, feature: str = "Pro"):
        """
        Raise LicenseError if Pro license not valid.

        ⚠️  STUB: Always raises error in public version.

        Args:
            feature: Feature name for error message

        Raises:
            LicenseError: Always (public version)

        Example:
            >>> validator = LicenseValidator()
            >>> validator.require_pro('semantic_analysis')
            # Raises LicenseError (public version)
        """
        raise LicenseError(
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🔒 HEFESTO PRO LICENSE REQUIRED\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"Feature '{feature}' requires Hefesto Pro or OMEGA Guardian.\n"
            f"\n"
            f"✨ PRO FEATURES ($8/month launch pricing):\n"
            f"   • ML-based semantic code analysis\n"
            f"   • Duplicate suggestion detection\n"
            f"   • CI/CD feedback automation\n"
            f"   • Advanced analytics dashboard\n"
            f"   • REST API (8 endpoints)\n"
            f"   • BigQuery integration\n"
            f"\n"
            f"✨ OMEGA GUARDIAN FEATURES ($19/month launch pricing):\n"
            f"   • Everything in PRO +\n"
            f"   • IRIS Agent (production monitoring)\n"
            f"   • Auto-correlation (alerts + code findings)\n"
            f"   • Real-time alerts (Pub/Sub)\n"
            f"   • Production dashboard\n"
            f"   • Priority Slack support\n"
            f"\n"
            f"🚀 FIRST 100 CUSTOMERS: Launch pricing locked forever!\n"
            f"\n"
            f"🛒 SUBSCRIBE:\n"
            f"   PRO: https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b\n"
            f"   OMEGA: https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c\n"
            f"\n"
            f"📧 ENTERPRISE:\n"
            f"   sales@narapallc.com\n"
            f"\n"
            f"After purchase, you'll receive your license key via email.\n"
            f"Then set: export HEFESTO_LICENSE_KEY='your_key_here'\n"
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

    def get_info(self) -> dict:
        """
        Get license information.

        ⚠️  STUB: Always returns FREE tier in public version unless hefesto-pro installed.
        """
        return {
            "tier": self.license_info.tier,
            "is_pro": self.license_info.tier in ["professional", "omega"],
            "features_enabled": list(self.license_info.features_enabled),
            "license_key_set": self.license_key is not None,
            "upgrade_url_pro": "https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b",
            "upgrade_url_omega": "https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c",
        }


# Singleton instance
_license_validator: Optional[LicenseValidator] = None


def get_license_validator() -> LicenseValidator:
    """Get singleton LicenseValidator instance."""
    global _license_validator
    if _license_validator is None:
        _license_validator = LicenseValidator()
    return _license_validator


def require_pro(feature: str = "Pro"):
    """
    Decorator to require Pro license for a function.

    ⚠️  STUB: Always blocks in public version.

    Usage:
        @require_pro("semantic_analysis")
        def analyze_semantic_similarity(code1, code2):
            # This function requires Pro license
            ...
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            validator = get_license_validator()
            validator.require_pro(feature)
            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "LicenseValidator",
    "LicenseError",
    "LicenseInfo",
    "get_license_validator",
    "require_pro",
]
