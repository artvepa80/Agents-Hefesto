"""
HEFESTO v3.5 - License Validation for Pro Features

Purpose: Validate Stripe license keys for Phase 1 (Pro) features.
Location: hefesto/llm/license_validator.py

Pro Features (Commercial License Required):
- semantic_analyzer.py - ML-based code embeddings
- cicd_feedback_collector.py - Automated CI/CD feedback
- metrics.py - Advanced analytics dashboard

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import os
import logging
from typing import Optional, Set
from dataclasses import dataclass
from datetime import datetime

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
    tier: str  # 'free', 'pro', 'enterprise'
    expires_at: Optional[datetime] = None
    customer_email: Optional[str] = None


class LicenseValidator:
    """
    Validates Pro licenses for Phase 1 features.
    
    Phase 1 features require a valid Stripe license key.
    Set environment variable: HEFESTO_LICENSE_KEY='hef_xxxxx'
    
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
        'semantic_analysis',
        'cicd_feedback',
        'duplicate_detection',
        'metrics_dashboard',
        'code_embeddings',
        'ml_similarity',
    }
    
    # Valid license key prefixes (Stripe format)
    VALID_PREFIXES = {
        'hef_',  # Hefesto production keys
        'sk_',   # Stripe secret keys (for testing)
        'pk_',   # Stripe publishable keys
    }
    
    def __init__(self):
        """Initialize license validator."""
        self.license_key = os.getenv('HEFESTO_LICENSE_KEY')
        self.license_info = self._validate_key()
    
    def _validate_key(self) -> LicenseInfo:
        """
        Validate license key format and status.
        
        In production, this would:
        1. Call Stripe API to verify key
        2. Check subscription status
        3. Verify expiration date
        4. Get customer info
        
        For now, we do basic format validation.
        
        Returns:
            LicenseInfo with validation results
        """
        if not self.license_key:
            logger.debug("No license key found - running in Free mode")
            return LicenseInfo(
                is_valid=False,
                license_key=None,
                features_enabled=set(),
                tier='free',
            )
        
        # Check key format
        if not any(self.license_key.startswith(prefix) for prefix in self.VALID_PREFIXES):
            logger.warning(
                f"Invalid license key format. "
                f"Must start with: {', '.join(self.VALID_PREFIXES)}"
            )
            return LicenseInfo(
                is_valid=False,
                license_key=self.license_key,
                features_enabled=set(),
                tier='free',
            )
        
        # TODO: In production, call Stripe API:
        # import stripe
        # stripe.api_key = self.license_key
        # subscription = stripe.Subscription.retrieve('sub_xxxxx')
        # if subscription.status == 'active':
        #     return LicenseInfo(is_valid=True, ...)
        
        # For now, trust valid format = valid license
        logger.info("✅ Valid Pro license detected")
        return LicenseInfo(
            is_valid=True,
            license_key=self.license_key,
            features_enabled=self.PRO_FEATURES,
            tier='pro',
        )
    
    def is_pro(self) -> bool:
        """Check if Pro license is active."""
        return self.license_info.is_valid and self.license_info.tier == 'pro'
    
    def has_feature(self, feature: str) -> bool:
        """Check if specific feature is enabled."""
        return feature in self.license_info.features_enabled
    
    def require_pro(self, feature: str = "Pro"):
        """
        Raise LicenseError if Pro license not valid.
        
        Args:
            feature: Feature name for error message
        
        Raises:
            LicenseError: If license is not valid
        
        Example:
            >>> validator = LicenseValidator()
            >>> validator.require_pro('semantic_analysis')
            # Raises LicenseError if no valid license
        """
        if not self.is_pro():
            raise LicenseError(
                f"\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  🔒 HEFESTO PRO LICENSE REQUIRED\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"\n"
                f"Feature '{feature}' requires Hefesto Pro.\n"
                f"\n"
                f"✨ UNLOCK PRO FEATURES:\n"
                f"   • ML-based semantic code analysis\n"
                f"   • Duplicate suggestion detection\n"
                f"   • CI/CD feedback automation\n"
                f"   • Advanced analytics dashboard\n"
                f"\n"
                f"💰 PRICING: $99/month or $990/year (save 17%)\n"
                f"\n"
                f"🛒 PURCHASE:\n"
                f"   https://buy.stripe.com/hefesto-pro\n"
                f"\n"
                f"📧 ENTERPRISE:\n"
                f"   sales@narapallc.com\n"
                f"\n"
                f"After purchase, set your license key:\n"
                f"   export HEFESTO_LICENSE_KEY='hef_your_key_here'\n"
                f"\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
    
    def get_info(self) -> dict:
        """Get license information."""
        return {
            'tier': self.license_info.tier,
            'is_pro': self.is_pro(),
            'features_enabled': list(self.license_info.features_enabled),
            'license_key_set': self.license_key is not None,
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

