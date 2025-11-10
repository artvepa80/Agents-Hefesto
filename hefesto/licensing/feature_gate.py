"""
Feature Gating System (STUB - Public Version)
=============================================

⚠️  This is a public stub. Real implementation is in private repository.

The actual feature gating enforcement logic is proprietary.

Copyright © 2025 Narapa LLC
"""

import functools
from typing import Callable, Optional

from hefesto.licensing.license_validator import LicenseValidator

# Tier hierarchy: higher number = higher tier
TIER_HIERARCHY = {
    "free": 0,
    "professional": 1,
    "omega": 2,
}


def get_tier_level(tier: str) -> int:
    """
    Get numeric level for a tier name.

    Args:
        tier: Tier name ('free', 'professional', 'omega')

    Returns:
        Numeric tier level (0-2), defaults to 0 for unknown tiers
    """
    return TIER_HIERARCHY.get(tier.lower(), 0)


class FeatureGate:
    """
    Decorator and context manager for enforcing tier-based feature access.

    ⚠️  STUB: Public version provides basic interface only.
    Real enforcement logic is in private repository.
    """

    validator = LicenseValidator()

    @classmethod
    def get_current_license(cls) -> Optional[str]:
        """
        Get license key from config.

        ⚠️  STUB: Public version returns None.

        Returns:
            License key string or None if not activated
        """
        # Public version doesn't have access to config
        return None

    @classmethod
    def get_current_tier(cls) -> str:
        """
        Get current tier from license.

        ⚠️  STUB: Public version always returns 'free'.

        Returns:
            'free' (public version)
        """
        return "free"

    @classmethod
    def check_feature_access(cls, feature: str) -> tuple:
        """
        Check if current tier has access to feature.

        ⚠️  STUB: Public version denies all PRO features.

        Args:
            feature: Feature code (e.g., 'ml_semantic_analysis')

        Returns:
            (has_access, error_message)
        """
        license_key = cls.get_current_license()
        return cls.validator.check_feature_access(feature, license_key)

    @classmethod
    def requires(cls, feature: str, fallback: Optional[Callable] = None):
        """
        Decorator to require a specific feature tier.

        ⚠️  STUB: Public version denies access to all PRO features.

        Args:
            feature: Feature code from stripe_config.py
            fallback: Optional function to call if access denied

        Example:
            @FeatureGate.requires('ml_semantic_analysis')
            def run_ml_analysis():
                # This only runs for Pro tier
                pass

        Raises:
            FeatureAccessDenied: If user doesn't have access to feature
        """

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                has_access, error_msg = cls.check_feature_access(feature)

                if not has_access:
                    if fallback:
                        return fallback(*args, **kwargs)
                    else:
                        raise FeatureAccessDenied(error_msg)

                return func(*args, **kwargs)

            return wrapper

        return decorator

    @classmethod
    def requires_tier(cls, required_tier: str):
        """
        Decorator to require a minimum tier level.

        ⚠️  STUB: Public version denies all tiers above FREE.

        Args:
            required_tier: Minimum tier required ('free', 'professional', 'omega')

        Example:
            @FeatureGate.requires_tier('professional')
            def pro_only_function():
                # Accessible by PRO and OMEGA users
                pass

        Raises:
            FeatureAccessDenied: If user's tier level is below required level
        """

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                current_tier = cls.get_current_tier()
                user_level = get_tier_level(current_tier)
                required_level = get_tier_level(required_tier)

                # Public version: user is always FREE tier
                if user_level < required_level:
                    if required_tier.lower() == "omega":
                        upgrade_msg = (
                            f"❌ This feature requires OMEGA Guardian tier.\n"
                            f"   Current tier: {current_tier}\n"
                            f"\n"
                            f"   Upgrade to OMEGA Guardian:\n"
                            f"   → $19/month (launch pricing)\n"
                            f"   → https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c\n"
                            f"\n"
                            f"   ✨ Full production monitoring with IRIS Agent\n"
                            f"   ✨ Auto-correlation between code & production issues\n"
                            f"   ✨ All PRO features + ML enhancement\n"
                            f"\n"
                            f"   🚀 First 100 customers get pricing locked forever"
                        )
                    elif required_tier.lower() == "professional":
                        upgrade_msg = (
                            f"❌ This feature requires Professional tier.\n"
                            f"   Current tier: {current_tier}\n"
                            f"\n"
                            f"   Upgrade to Professional:\n"
                            f"   → $8/month (launch pricing)\n"
                            f"   → https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b\n"
                            f"\n"
                            f"   🚀 First 100 customers get pricing locked forever\n"
                            f"   → 14 days free trial, no credit card required"
                        )
                    else:
                        upgrade_msg = (
                            f"❌ This feature requires {required_tier} tier.\n"
                            f"   Current tier: {current_tier}"
                        )

                    raise FeatureAccessDenied(upgrade_msg)

                return func(*args, **kwargs)

            return wrapper

        return decorator

    @classmethod
    def get_tier_info(cls) -> dict:
        """
        Get information about current tier and limits.

        ⚠️  STUB: Public version returns FREE tier info.

        Returns:
            Dictionary with tier information
        """
        license_key = cls.get_current_license()
        return cls.validator.get_tier_info(license_key)


class FeatureAccessDenied(Exception):
    """
    Exception raised when user tries to access a feature not available in their tier.

    This exception includes a helpful error message with upgrade links.
    """

    pass


# Convenience decorators for common features
def requires_pro(func):
    """Require professional tier."""
    return FeatureGate.requires_tier("professional")(func)


def requires_omega(func):
    """Require OMEGA Guardian tier."""
    return FeatureGate.requires_tier("omega")(func)


def requires_ml_analysis(func):
    """Require ML semantic analysis feature."""
    return FeatureGate.requires("ml_semantic_analysis")(func)


def requires_ai_recommendations(func):
    """Require AI recommendations feature."""
    return FeatureGate.requires("ai_recommendations")(func)


def requires_security_scanning(func):
    """Require security scanning feature."""
    return FeatureGate.requires("security_scanning")(func)


def requires_automated_triage(func):
    """Require automated triage feature."""
    return FeatureGate.requires("automated_triage")(func)


def requires_integrations(func):
    """Require GitHub/GitLab/Bitbucket integrations."""
    return FeatureGate.requires("github_gitlab_bitbucket")(func)


def requires_priority_support(func):
    """Require priority support feature."""
    return FeatureGate.requires("priority_support")(func)


def requires_analytics(func):
    """Require analytics dashboard feature."""
    return FeatureGate.requires("analytics_dashboard")(func)
