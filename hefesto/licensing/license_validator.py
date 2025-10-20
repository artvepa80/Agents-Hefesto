"""
License validation for Hefesto Professional tier.
Validates license keys and enforces tier limits.
"""

from typing import Optional, Dict, Tuple
from hefesto.config.stripe_config import (
    STRIPE_CONFIG,
    get_limits_for_tier,
    get_tier_from_price_id
)
from hefesto.licensing.key_generator import LicenseKeyGenerator


class LicenseValidator:
    """Validate Hefesto license keys and enforce limits."""
    
    def __init__(self):
        """Initialize validator with tier limits from Stripe config."""
        self.free_limits = STRIPE_CONFIG['limits']['free']
        self.pro_limits = STRIPE_CONFIG['limits']['professional']
    
    def validate_key_format(self, license_key: str) -> bool:
        """
        Validate license key format.
        
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
        
        Args:
            license_key: License key string or None
            
        Returns:
            'free' or 'professional'
        """
        if not license_key:
            return 'free'
        
        if not self.validate_key_format(license_key):
            return 'free'
        
        # TODO: Validate with backend API when available
        # For now, if format is valid, assume professional
        return 'professional'
    
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
        self,
        current_repos: int,
        license_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if repository count is within limits.
        
        Args:
            current_repos: Number of repositories being analyzed
            license_key: Optional license key
            
        Returns:
            (is_valid, error_message)
        """
        limits = self.get_limits(license_key)
        max_repos = limits['repositories']
        
        if current_repos > max_repos:
            tier = self.get_tier_for_key(license_key)
            if tier == 'free':
                return (
                    False,
                    f"❌ Free tier limited to {max_repos} repository.\n"
                    f"   Currently analyzing: {current_repos} repositories\n"
                    f"   \n"
                    f"   Upgrade to Professional for 25 repositories:\n"
                    f"   → https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04\n"
                    f"   \n"
                    f"   🚀 First 25 teams: $59/month forever (40% off)\n"
                    f"   → https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40"
                )
            else:
                return (
                    False,
                    f"❌ Professional tier limited to {max_repos} repositories.\n"
                    f"   Currently analyzing: {current_repos} repositories\n"
                    f"   \n"
                    f"   Add repository expansion pack:\n"
                    f"   → +25 repos for $29/month\n"
                    f"   → Contact: support@narapallc.com"
                )
        
        return (True, "")
    
    def check_loc_limit(
        self,
        current_loc: int,
        license_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if lines of code is within monthly limit.
        
        Args:
            current_loc: Total lines of code being analyzed
            license_key: Optional license key
            
        Returns:
            (is_valid, error_message)
        """
        limits = self.get_limits(license_key)
        max_loc = limits['loc_monthly']
        
        if current_loc > max_loc:
            tier = self.get_tier_for_key(license_key)
            if tier == 'free':
                return (
                    False,
                    f"❌ Free tier limited to {max_loc:,} LOC/month.\n"
                    f"   Current codebase: {current_loc:,} LOC\n"
                    f"   \n"
                    f"   Upgrade to Professional for 500K LOC/month:\n"
                    f"   → https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04\n"
                    f"   \n"
                    f"   🚀 First 25 teams: $59/month forever (40% off)\n"
                    f"   → https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40"
                )
            else:
                return (
                    False,
                    f"❌ Professional tier limited to {max_loc:,} LOC/month.\n"
                    f"   Current codebase: {current_loc:,} LOC\n"
                    f"   \n"
                    f"   Add LOC expansion pack:\n"
                    f"   → +250K LOC for $19/month\n"
                    f"   → Contact: support@narapallc.com"
                )
        
        return (True, "")
    
    def check_analysis_runs_limit(
        self,
        current_runs: int,
        license_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if analysis runs is within monthly limit.
        
        Args:
            current_runs: Number of analysis runs this month
            license_key: Optional license key
            
        Returns:
            (is_valid, error_message)
        """
        limits = self.get_limits(license_key)
        max_runs = limits['analysis_runs']
        
        # Professional has unlimited runs
        if max_runs == float('inf'):
            return (True, "")
        
        if current_runs > max_runs:
            return (
                False,
                f"❌ Free tier limited to {max_runs} analysis runs/month.\n"
                f"   Current usage: {current_runs} runs\n"
                f"   \n"
                f"   Upgrade to Professional for unlimited runs:\n"
                f"   → https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04\n"
                f"   \n"
                f"   🚀 First 25 teams: $59/month forever (40% off)\n"
                f"   → https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40"
            )
        
        return (True, "")
    
    def check_feature_access(
        self,
        feature: str,
        license_key: Optional[str] = None
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
        available_features = limits['features']
        
        if feature in available_features:
            return (True, "")
        
        # Map feature codes to user-friendly names
        pro_only_features = {
            'ml_semantic_analysis': 'ML Semantic Code Analysis',
            'ai_recommendations': 'AI-Powered Code Recommendations',
            'security_scanning': 'Security Vulnerability Scanning',
            'automated_triage': 'Automated Issue Triage',
            'github_gitlab_bitbucket': 'Full Git Integrations',
            'jira_slack_integration': 'Jira & Slack Integration',
            'priority_support': 'Priority Email Support',
            'analytics_dashboard': 'Usage Analytics Dashboard'
        }
        
        feature_name = pro_only_features.get(feature, feature)
        
        return (
            False,
            f"❌ {feature_name} is only available in Professional tier.\n"
            f"   \n"
            f"   Start your 14-day free trial:\n"
            f"   → https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04\n"
            f"   \n"
            f"   🚀 First 25 teams: $59/month forever (40% off)\n"
            f"   → https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40"
        )
    
    def validate_before_analysis(
        self,
        license_key: Optional[str],
        repository_count: int,
        loc_count: int,
        analysis_run_count: int,
        required_features: Optional[list] = None
    ) -> Tuple[bool, list]:
        """
        Run all validations before starting analysis.
        
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
        
        # Check analysis runs limit
        is_valid, msg = self.check_analysis_runs_limit(analysis_run_count, license_key)
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
            'tier': tier,
            'tier_display': tier.title(),
            'limits': limits,
            'upgrade_url': STRIPE_CONFIG['payment_links']['monthly_trial']['url'],
            'founding_url': STRIPE_CONFIG['payment_links']['monthly_founding']['url']
        }

