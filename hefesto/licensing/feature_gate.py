"""
Feature gating system for Hefesto.
Enforces tier-based access control at code execution level.

Usage:
    @FeatureGate.requires('ml_semantic_analysis')
    def some_pro_function():
        pass
"""

import functools
from typing import Optional, Callable
from hefesto.licensing.license_validator import LicenseValidator


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
            return config.get('license_key')
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
        Decorator to require a specific tier.
        
        Args:
            required_tier: 'free' or 'professional'
            
        Example:
            @FeatureGate.requires_tier('professional')
            def pro_only_function():
                pass
        
        Raises:
            FeatureAccessDenied: If user doesn't have required tier
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                current_tier = cls.get_current_tier()
                
                if current_tier != required_tier:
                    raise FeatureAccessDenied(
                        f"❌ This feature requires {required_tier} tier.\n"
                        f"   Current tier: {current_tier}\n"
                        f"   \n"
                        f"   Upgrade to Professional:\n"
                        f"   → https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04\n"
                        f"   \n"
                        f"   🚀 First 25 teams: $59/month forever (40% off)\n"
                        f"   → https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40"
                    )
                
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
requires_pro = lambda func: FeatureGate.requires_tier('professional')(func)
requires_ml_analysis = lambda func: FeatureGate.requires('ml_semantic_analysis')(func)
requires_ai_recommendations = lambda func: FeatureGate.requires('ai_recommendations')(func)
requires_security_scanning = lambda func: FeatureGate.requires('security_scanning')(func)
requires_automated_triage = lambda func: FeatureGate.requires('automated_triage')(func)
requires_integrations = lambda func: FeatureGate.requires('github_gitlab_bitbucket')(func)
requires_priority_support = lambda func: FeatureGate.requires('priority_support')(func)
requires_analytics = lambda func: FeatureGate.requires('analytics_dashboard')(func)

