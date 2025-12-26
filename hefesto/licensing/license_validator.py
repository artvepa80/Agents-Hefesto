"""
License Validator (STUB - Public Version)
=========================================

⚠️  This is a public stub. Real implementation is in private repository.

The actual license validation logic contains proprietary enforcement
mechanisms that are not open source.

For access to the full implementation:
- PRO/OMEGA customers: Validation happens automatically
- Enterprise: Contact sales@narapallc.com

Copyright © 2025 Narapa LLC
"""

from typing import Dict, Optional, Tuple

from hefesto.config.stripe_config import STRIPE_CONFIG, get_limits_for_tier
from hefesto.licensing.key_generator import LicenseKeyGenerator


class LicenseValidator:
    """
    Validate Hefesto license keys and enforce limits.

    ⚠️  STUB: This public version provides basic validation only.
    Full enforcement logic is in the private repository.
    """

    def __init__(self):
        """Initialize validator with tier limits from Stripe config."""
        self.free_limits = STRIPE_CONFIG["limits"]["free"]
        self.pro_limits = STRIPE_CONFIG["limits"]["professional"]
        self.omega_limits = STRIPE_CONFIG["limits"]["omega"]

    def validate_key_format(self, license_key: str) -> bool:
        """
        Validate license key format.

        This basic format validation is available publicly.

        Format: HFST-XXXX-XXXX-XXXX-XXXX-XXXX

        Args:
            license_key: The license key to validate

        Returns:
            True if format is valid, False otherwise
        """
        return LicenseKeyGenerator.validate_format(license_key)

    def get_tier_for_key(self, license_key: Optional[str]) -> str:
        """
        Determine tier from license key.

        ⚠️  STUB: This public version does basic format checking only.
        Real validation against Stripe backend is in private repository.

        Args:
            license_key: License key string or None

        Returns:
            'free', 'professional', or 'omega'
        """
        # Try to use the real validator if hefesto-pro is installed
        try:
            from hefesto_pro.licensing.license_validator import LicenseValidator as ProValidator

            pro_validator = ProValidator()
            return pro_validator.get_tier_for_key(license_key)
        except ImportError:
            pass  # Fall back to stub behavior

        if not license_key:
            return "free"

        if not self.validate_key_format(license_key):
            return "free"

        # Basic format check only - real validation is server-side
        if license_key.startswith("HFST-"):
            # In production, this queries Stripe API
            # Public version cannot determine tier from key alone
            return "free"

        return "free"

    def get_limits(self, license_key: Optional[str] = None) -> Dict:
        """
        Get usage limits for the current license.

        Args:
            license_key: Optional license key

        Returns:
            Dictionary with tier limits
        """
        tier = self.get_tier_for_key(license_key)
        return get_limits_for_tier(tier)

    def check_repository_limit(
        self, current_repos: int, license_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if repository count is within limits.

        ⚠️  STUB: Basic check only. Real enforcement is server-side.

        Args:
            current_repos: Number of repositories being analyzed
            license_key: Optional license key

        Returns:
            (is_valid, error_message)
        """
        limits = self.get_limits(license_key)
        max_repos = limits["repositories"]

        if isinstance(max_repos, int) and current_repos > max_repos:
            return (
                False,
                f"❌ Free tier limited to {max_repos} repository.\n"
                f"   Currently analyzing: {current_repos} repositories\n"
                f"   \n"
                f"   Upgrade to PRO for unlimited repositories:\n"
                f"   → https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b\n"
                f"   \n"
                f"   🚀 Launch pricing: $8/month (first 100 customers)\n"
                f"   → 14 days free trial, no credit card required",
            )

        return (True, "")

    def check_loc_limit(
        self, current_loc: int, license_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if lines of code is within monthly limit.

        ⚠️  STUB: Basic check only. Real enforcement is server-side.

        Args:
            current_loc: Total lines of code being analyzed
            license_key: Optional license key

        Returns:
            (is_valid, error_message)
        """
        limits = self.get_limits(license_key)
        max_loc = limits["loc_monthly"]

        if isinstance(max_loc, int) and current_loc > max_loc:
            return (
                False,
                f"❌ Free tier limited to {max_loc:,} LOC/month.\n"
                f"   Current codebase: {current_loc:,} LOC\n"
                f"   \n"
                f"   Upgrade to PRO for unlimited LOC:\n"
                f"   → https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b\n"
                f"   \n"
                f"   🚀 Launch pricing: $8/month (first 100 customers)\n"
                f"   → 14 days free trial, no credit card required",
            )

        return (True, "")

    def check_analysis_runs_limit(
        self, current_runs: int, license_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if analysis runs is within monthly limit.

        ⚠️  STUB: Not enforced in public version.

        Args:
            current_runs: Number of analysis runs this month
            license_key: Optional license key

        Returns:
            (is_valid, error_message)
        """
        # Public version doesn't enforce run limits
        return (True, "")

    def check_feature_access(
        self, feature: str, license_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if feature is available in current tier.

        Args:
            feature: Feature name (e.g., 'ml_semantic_analysis')
            license_key: Optional license key

        Returns:
            (has_access, error_message)
        """
        limits = self.get_limits(license_key)
        available_features = limits.get("features", [])

        if feature in available_features:
            return (True, "")

        # Map feature codes to user-friendly names
        pro_only_features = {
            "ml_semantic_analysis": "ML Semantic Code Analysis",
            "ai_recommendations": "AI-Powered Code Recommendations",
            "security_scanning": "Security Vulnerability Scanning",
            "automated_triage": "Automated Issue Triage",
            "github_gitlab_bitbucket": "Full Git Integrations",
            "jira_slack_integration": "Jira & Slack Integration",
            "priority_support": "Priority Email Support",
            "analytics_dashboard": "Usage Analytics Dashboard",
        }

        feature_name = pro_only_features.get(feature, feature)

        return (
            False,
            f"❌ {feature_name} requires PRO or OMEGA tier.\n"
            f"   \n"
            f"   PRO: $8/month (launch pricing)\n"
            f"   → https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b\n"
            f"   \n"
            f"   OMEGA Guardian: $19/month (launch pricing)\n"
            f"   → https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c\n"
            f"   \n"
            f"   🚀 First 100 customers get launch pricing locked forever\n"
            f"   → 14 days free trial, no credit card required",
        )

    def validate_before_analysis(
        self,
        license_key: Optional[str],
        repository_count: int,
        loc_count: int,
        analysis_run_count: int,
        required_features: Optional[list] = None,
    ) -> Tuple[bool, list]:
        """
        Run all validations before starting analysis.

        ⚠️  STUB: Basic validation only in public version.

        Args:
            license_key: Optional license key
            repository_count: Number of repositories
            loc_count: Total lines of code
            analysis_run_count: Number of runs this month
            required_features: List of required feature codes

        Returns:
            (is_valid, list_of_error_messages)
        """
        errors = []

        # Check repository limit
        is_valid, msg = self.check_repository_limit(repository_count, license_key)
        if not is_valid:
            errors.append(msg)

        # Check LOC limit
        is_valid, msg = self.check_loc_limit(loc_count, license_key)
        if not is_valid:
            errors.append(msg)

        # Check required features
        if required_features:
            for feature in required_features:
                is_valid, msg = self.check_feature_access(feature, license_key)
                if not is_valid:
                    errors.append(msg)

        return (len(errors) == 0, errors)

    def get_tier_info(self, license_key: Optional[str] = None) -> Dict:
        """
        Get detailed information about current tier.

        Args:
            license_key: Optional license key

        Returns:
            Dictionary with tier information
        """
        tier = self.get_tier_for_key(license_key)
        limits = self.get_limits(license_key)

        return {
            "tier": tier,
            "tier_display": tier.title(),
            "limits": limits,
            "upgrade_url": "https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b",
            "founding_url": "https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05",
        }
