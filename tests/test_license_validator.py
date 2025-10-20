"""
Test suite for Hefesto License Validator.
Following OMEGA 4-Level Testing Pyramid: Unit → Smoke → Canary → Empirical
"""

import pytest
from hefesto.licensing import LicenseValidator, LicenseKeyGenerator
from hefesto.config.stripe_config import STRIPE_CONFIG


# ============================================================================
# LEVEL 1: UNIT TESTS - Individual License Validation Functions
# ============================================================================

class TestUnitLicenseValidation:
    """Test individual license validation functions."""
    
    def test_license_key_format_validation_valid(self):
        """Test valid license key format."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        assert validator.validate_key_format(valid_key) is True
    
    def test_license_key_format_validation_invalid_prefix(self):
        """Test invalid prefix is rejected."""
        validator = LicenseValidator()
        invalid_key = "XXXX-1234-5678-9ABC-DEF0-1234"
        assert validator.validate_key_format(invalid_key) is False
    
    def test_license_key_format_validation_wrong_length(self):
        """Test wrong segment count is rejected."""
        validator = LicenseValidator()
        invalid_key = "HFST-1234-5678"
        assert validator.validate_key_format(invalid_key) is False
    
    def test_tier_detection_no_key(self):
        """Test tier detection returns free for None key."""
        validator = LicenseValidator()
        tier = validator.get_tier_for_key(None)
        assert tier == 'free'
    
    def test_tier_detection_invalid_key(self):
        """Test tier detection returns free for invalid key."""
        validator = LicenseValidator()
        tier = validator.get_tier_for_key("invalid-key")
        assert tier == 'free'
    
    def test_tier_detection_valid_key(self):
        """Test tier detection returns professional for valid key."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        tier = validator.get_tier_for_key(valid_key)
        assert tier == 'professional'
    
    def test_get_limits_free_tier(self):
        """Test getting limits for free tier."""
        validator = LicenseValidator()
        limits = validator.get_limits(None)
        assert limits['tier'] == 'free'
        assert limits['repositories'] == 1
        assert limits['loc_monthly'] == 50000
        assert limits['analysis_runs'] == 10
    
    def test_get_limits_pro_tier(self):
        """Test getting limits for professional tier."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        limits = validator.get_limits(valid_key)
        assert limits['tier'] == 'professional'
        assert limits['repositories'] == 25
        assert limits['loc_monthly'] == 500000
        assert limits['analysis_runs'] == float('inf')


# ============================================================================
# LEVEL 2: SMOKE TESTS - Basic System Functionality Without Crashing
# ============================================================================

class TestSmokeLicenseSystem:
    """Test basic license system initialization and functionality."""
    
    def test_license_validator_initialization(self):
        """Test validator initializes without crashing."""
        validator = LicenseValidator()
        assert validator is not None
        assert validator.free_limits is not None
        assert validator.pro_limits is not None
    
    def test_stripe_config_loaded(self):
        """Test Stripe configuration loads correctly."""
        assert 'products' in STRIPE_CONFIG
        assert 'payment_links' in STRIPE_CONFIG
        assert 'limits' in STRIPE_CONFIG
        assert 'free' in STRIPE_CONFIG['limits']
        assert 'professional' in STRIPE_CONFIG['limits']
    
    def test_all_validator_methods_callable(self):
        """Test all validator methods are callable."""
        validator = LicenseValidator()
        
        # Test all public methods exist and are callable
        assert callable(validator.validate_key_format)
        assert callable(validator.get_tier_for_key)
        assert callable(validator.get_limits)
        assert callable(validator.check_repository_limit)
        assert callable(validator.check_loc_limit)
        assert callable(validator.check_analysis_runs_limit)
        assert callable(validator.check_feature_access)
        assert callable(validator.validate_before_analysis)
        assert callable(validator.get_tier_info)
    
    def test_key_generator_integration(self):
        """Test key generator integrates with validator."""
        # Generate a key
        key = LicenseKeyGenerator.generate(
            customer_email="test@example.com",
            tier="professional",
            subscription_id="sub_test123",
            is_founding_member=False
        )
        
        # Validate with validator
        validator = LicenseValidator()
        assert validator.validate_key_format(key) is True
        assert validator.get_tier_for_key(key) == 'professional'


# ============================================================================
# LEVEL 3: CANARY TESTS - Real License Validation Scenarios (Small Dataset)
# ============================================================================

class TestCanaryLicenseScenarios:
    """Test real-world license validation scenarios."""
    
    def test_free_tier_repository_limit_enforcement(self):
        """Test free tier repository limit is enforced correctly."""
        validator = LicenseValidator()
        
        # Within limit
        is_valid, msg = validator.check_repository_limit(1, None)
        assert is_valid is True
        assert msg == ""
        
        # Exceeds limit
        is_valid, msg = validator.check_repository_limit(2, None)
        assert is_valid is False
        assert "Free tier limited to 1 repository" in msg
        assert "https://buy.stripe.com/" in msg
    
    def test_pro_tier_repository_limit_enforcement(self):
        """Test professional tier repository limit."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        
        # Within limit
        is_valid, msg = validator.check_repository_limit(25, valid_key)
        assert is_valid is True
        
        # Exceeds limit
        is_valid, msg = validator.check_repository_limit(26, valid_key)
        assert is_valid is False
        assert "Professional tier limited to 25 repositories" in msg
    
    def test_free_tier_loc_limit_enforcement(self):
        """Test free tier LOC limit is enforced correctly."""
        validator = LicenseValidator()
        
        # Within limit
        is_valid, msg = validator.check_loc_limit(50000, None)
        assert is_valid is True
        
        # Exceeds limit
        is_valid, msg = validator.check_loc_limit(50001, None)
        assert is_valid is False
        assert "50,000 LOC/month" in msg
    
    def test_pro_tier_loc_limit_enforcement(self):
        """Test professional tier LOC limit."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        
        # Within limit
        is_valid, msg = validator.check_loc_limit(500000, valid_key)
        assert is_valid is True
        
        # Exceeds limit
        is_valid, msg = validator.check_loc_limit(500001, valid_key)
        assert is_valid is False
        assert "500,000 LOC/month" in msg
    
    def test_analysis_runs_limit_free_tier(self):
        """Test analysis runs limit for free tier."""
        validator = LicenseValidator()
        
        # Within limit
        is_valid, msg = validator.check_analysis_runs_limit(10, None)
        assert is_valid is True
        
        # Exceeds limit
        is_valid, msg = validator.check_analysis_runs_limit(11, None)
        assert is_valid is False
        assert "10 analysis runs/month" in msg
    
    def test_analysis_runs_unlimited_pro_tier(self):
        """Test unlimited analysis runs for professional tier."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        
        # Should always be valid
        is_valid, msg = validator.check_analysis_runs_limit(1000000, valid_key)
        assert is_valid is True
    
    def test_feature_access_free_tier(self):
        """Test feature access for free tier."""
        validator = LicenseValidator()
        
        # Free features
        is_valid, msg = validator.check_feature_access('basic_quality', None)
        assert is_valid is True
        
        is_valid, msg = validator.check_feature_access('pr_analysis', None)
        assert is_valid is True
        
        # Pro-only features
        is_valid, msg = validator.check_feature_access('ml_semantic_analysis', None)
        assert is_valid is False
        assert "ML Semantic Code Analysis" in msg
        assert "Professional tier" in msg
    
    def test_feature_access_pro_tier(self):
        """Test feature access for professional tier."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        
        # All free features
        is_valid, msg = validator.check_feature_access('basic_quality', valid_key)
        assert is_valid is True
        
        # Pro features
        is_valid, msg = validator.check_feature_access('ml_semantic_analysis', valid_key)
        assert is_valid is True
        
        is_valid, msg = validator.check_feature_access('security_scanning', valid_key)
        assert is_valid is True


# ============================================================================
# LEVEL 4: EMPIRICAL TESTS - Production-Like License Validation
# ============================================================================

class TestEmpiricalLicenseValidation:
    """Test production-like license validation scenarios."""
    
    def test_complete_validation_free_tier_success(self):
        """Test complete validation for valid free tier usage."""
        validator = LicenseValidator()
        
        is_valid, errors = validator.validate_before_analysis(
            license_key=None,
            repository_count=1,
            loc_count=40000,
            analysis_run_count=5,
            required_features=['basic_quality', 'pr_analysis']
        )
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_complete_validation_free_tier_all_limits_exceeded(self):
        """Test complete validation with all limits exceeded."""
        validator = LicenseValidator()
        
        is_valid, errors = validator.validate_before_analysis(
            license_key=None,
            repository_count=5,
            loc_count=100000,
            analysis_run_count=20,
            required_features=['ml_semantic_analysis']
        )
        
        assert is_valid is False
        assert len(errors) == 4  # repos + loc + runs + feature
        
        # Check all error messages are present
        error_text = ' '.join(errors)
        assert 'repository' in error_text.lower()
        assert 'loc' in error_text.lower()
        assert 'runs' in error_text.lower()
        assert 'ml semantic' in error_text.lower()
    
    def test_complete_validation_pro_tier_success(self):
        """Test complete validation for valid professional tier usage."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        
        is_valid, errors = validator.validate_before_analysis(
            license_key=valid_key,
            repository_count=20,
            loc_count=400000,
            analysis_run_count=1000,
            required_features=['ml_semantic_analysis', 'security_scanning']
        )
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_tier_info_retrieval_free(self):
        """Test tier info retrieval for free tier."""
        validator = LicenseValidator()
        info = validator.get_tier_info(None)
        
        assert info['tier'] == 'free'
        assert info['tier_display'] == 'Free'
        assert 'limits' in info
        assert 'upgrade_url' in info
        assert 'founding_url' in info
        assert 'buy.stripe.com' in info['upgrade_url']
    
    def test_tier_info_retrieval_pro(self):
        """Test tier info retrieval for professional tier."""
        validator = LicenseValidator()
        valid_key = "HFST-1234-5678-9ABC-DEF0-1234"
        info = validator.get_tier_info(valid_key)
        
        assert info['tier'] == 'professional'
        assert info['tier_display'] == 'Professional'
        assert info['limits']['repositories'] == 25
    
    def test_upgrade_messages_contain_payment_links(self):
        """Test that all upgrade messages contain valid Stripe payment links."""
        validator = LicenseValidator()
        
        # Test repository limit error
        _, msg = validator.check_repository_limit(2, None)
        assert 'https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04' in msg
        assert 'https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05' in msg
        
        # Test LOC limit error
        _, msg = validator.check_loc_limit(100000, None)
        assert 'https://buy.stripe.com/' in msg
        
        # Test feature access error
        _, msg = validator.check_feature_access('ml_semantic_analysis', None)
        assert 'https://buy.stripe.com/' in msg
    
    def test_founding_member_promotion_in_messages(self):
        """Test that Founding Member promotion appears in upgrade messages."""
        validator = LicenseValidator()
        
        _, msg = validator.check_repository_limit(2, None)
        assert '$59/month forever' in msg
        assert 'First 25 teams' in msg or 'Founding' in msg
    
    def test_multiple_validations_performance(self):
        """Test performance of multiple validation checks."""
        validator = LicenseValidator()
        
        # Run 100 validations
        for i in range(100):
            validator.validate_before_analysis(
                license_key=None,
                repository_count=1,
                loc_count=50000,
                analysis_run_count=10,
                required_features=['basic_quality']
            )
        
        # Should complete without errors
        assert True


# ============================================================================
# INTEGRATION TESTS - Stripe Config Integration
# ============================================================================

class TestStripeConfigIntegration:
    """Test integration with Stripe configuration."""
    
    def test_validator_uses_stripe_limits(self):
        """Test validator uses limits from Stripe config."""
        validator = LicenseValidator()
        
        # Verify limits match Stripe config
        assert validator.free_limits == STRIPE_CONFIG['limits']['free']
        assert validator.pro_limits == STRIPE_CONFIG['limits']['professional']
    
    def test_payment_links_in_config(self):
        """Test all payment links are present in Stripe config."""
        links = STRIPE_CONFIG['payment_links']
        
        assert 'monthly_trial' in links
        assert 'monthly_founding' in links
        assert 'annual' in links
        
        # Verify URLs are valid
        assert links['monthly_trial']['url'].startswith('https://buy.stripe.com/')
        assert links['monthly_founding']['url'].startswith('https://buy.stripe.com/')
        assert links['annual']['url'].startswith('https://buy.stripe.com/')
    
    def test_founding_member_coupon_in_config(self):
        """Test Founding Member coupon details are in config."""
        coupons = STRIPE_CONFIG['coupons']
        
        assert 'founding_member' in coupons
        founding = coupons['founding_member']
        
        assert founding['discount_percent'] == 40
        assert founding['duration'] == 'forever'
        assert founding['max_redemptions'] == 25


# ============================================================================
# EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_string_license_key(self):
        """Test empty string license key."""
        validator = LicenseValidator()
        tier = validator.get_tier_for_key("")
        assert tier == 'free'
    
    def test_zero_repositories(self):
        """Test zero repositories."""
        validator = LicenseValidator()
        is_valid, msg = validator.check_repository_limit(0, None)
        assert is_valid is True
    
    def test_zero_loc(self):
        """Test zero lines of code."""
        validator = LicenseValidator()
        is_valid, msg = validator.check_loc_limit(0, None)
        assert is_valid is True
    
    def test_negative_values(self):
        """Test negative values are handled."""
        validator = LicenseValidator()
        
        # Should not crash
        validator.check_repository_limit(-1, None)
        validator.check_loc_limit(-1, None)
        validator.check_analysis_runs_limit(-1, None)
    
    def test_empty_required_features_list(self):
        """Test validation with empty required features."""
        validator = LicenseValidator()
        
        is_valid, errors = validator.validate_before_analysis(
            license_key=None,
            repository_count=1,
            loc_count=10000,
            analysis_run_count=5,
            required_features=[]
        )
        
        assert is_valid is True
    
    def test_none_required_features(self):
        """Test validation with None required features."""
        validator = LicenseValidator()
        
        is_valid, errors = validator.validate_before_analysis(
            license_key=None,
            repository_count=1,
            loc_count=10000,
            analysis_run_count=5,
            required_features=None
        )
        
        assert is_valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

