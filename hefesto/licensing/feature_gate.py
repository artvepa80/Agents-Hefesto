"""
Feature gating system for Hefesto.
Enforces tier-based access control at code execution level.

Usage:
    @FeatureGate.requires('ml_semantic_analysis')
    def some_pro_function():
        pass
"""

import functools
from typing import Callable, Optional

from hefesto.licensing.license_validator import LicenseValidator

# Tier hierarchy: higher number = higher tier
# OMEGA (2) includes all PRO (1) features
# PRO (1) includes all FREE (0) features
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

    This class provides decorators to restrict function execution based on
    the user's license tier and available features.
    """

    validator = LicenseValidator()

    @classmethod
    def get_current_license(cls) -> Optional[str]:
        """
        Get license key from config.

        Returns:
            License key string or None if not activated
        """
        try:
            from hefesto.config.config_manager import ConfigManager

            config = ConfigManager()
            return config.get("license_key")
        except Exception:
            return None

    @classmethod
    def get_current_tier(cls) -> str:
        """
        Get current tier from license.

        Returns:
            'free' or 'professional'
        """
        license_key = cls.get_current_license()
        return cls.validator.get_tier_for_key(license_key)

    @classmethod
    def check_feature_access(cls, feature: str) -> tuple:
        """
        Check if current tier has access to feature.

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

        Uses tier hierarchy: OMEGA (2) >= PRO (1) >= FREE (0)
        Higher tiers have access to all lower tier features.

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

                # Hierarchy check: user must have tier >= required tier
                if user_level < required_level:
                    # Build appropriate upgrade message based on required tier
                    if required_tier.lower() == "omega":
                        upgrade_msg = (
                            f"❌ This feature requires OMEGA Guardian tier.\n"
                            f"   Current tier: {current_tier}\n"
                            f"\n"
                            f"   Upgrade to OMEGA Guardian ($35/month):\n"
                            f"   → Full production monitoring with IRIS Agent\n"
                            f"   → Auto-correlation between code & production issues\n"
                            f"   → All PRO features + ML enhancement\n"
                            f"   → BigQuery integration & real-time alerts\n"
                            f"\n"
                            f"   Contact: sales@hefesto.ai"
                        )
                    elif required_tier.lower() == "professional":
                        upgrade_msg = (
                            f"❌ This feature requires Professional tier.\n"
                            f"   Current tier: {current_tier}\n"
                            f"\n"
                            f"   Upgrade to Professional ($25/month):\n"
                            f"   → https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04\n"
                            f"\n"
                            f"   🚀 First 25 teams: $59/month forever (40% off)\n"
                            f"   → https://buy.stripe.com/"
                            f"dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40\n"
                            f"\n"
                            f"   Or upgrade to OMEGA Guardian ($35/month):\n"
                            f"   → All PRO + production monitoring + IRIS Agent\n"
                            f"   Contact: sales@hefesto.ai"
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
def requires_pro(func):  # noqa: E731
    """Require professional tier."""
    return FeatureGate.requires_tier("professional")(func)


def requires_omega(func):  # noqa: E731
    """Require OMEGA Guardian tier."""
    return FeatureGate.requires_tier("omega")(func)


def requires_ml_analysis(func):  # noqa: E731
    """Require ML semantic analysis feature."""
    return FeatureGate.requires("ml_semantic_analysis")(func)


def requires_ai_recommendations(func):  # noqa: E731
    """Require AI recommendations feature."""
    return FeatureGate.requires("ai_recommendations")(func)


def requires_security_scanning(func):  # noqa: E731
    """Require security scanning feature."""
    return FeatureGate.requires("security_scanning")(func)


def requires_automated_triage(func):  # noqa: E731
    """Require automated triage feature."""
    return FeatureGate.requires("automated_triage")(func)


def requires_integrations(func):  # noqa: E731
    """Require GitHub/GitLab/Bitbucket integrations."""
    return FeatureGate.requires("github_gitlab_bitbucket")(func)


def requires_priority_support(func):  # noqa: E731
    """Require priority support feature."""
    return FeatureGate.requires("priority_support")(func)


def requires_analytics(func):  # noqa: E731
    """Require analytics dashboard feature."""
    return FeatureGate.requires("analytics_dashboard")(func)
