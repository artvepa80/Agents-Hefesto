"""
Test suite for tier hierarchy feature gates.

Validates that OMEGA users can access PRO features,
and PRO users can access FREE features (hierarchical access).

Copyright © 2025 Narapa LLC, Miami, Florida
"""

from unittest.mock import patch

import pytest

from hefesto.licensing.feature_gate import (
    TIER_HIERARCHY,
    FeatureAccessDenied,
    FeatureGate,
    get_tier_level,
    requires_omega,
    requires_pro,
)


class TestTierHierarchy:
    """Test tier hierarchy constants and helper functions."""

    def test_tier_hierarchy_levels(self):
        """Test that tier hierarchy has correct numeric levels."""
        assert TIER_HIERARCHY["free"] == 0
        assert TIER_HIERARCHY["professional"] == 1
        assert TIER_HIERARCHY["omega"] == 2

    def test_get_tier_level(self):
        """Test get_tier_level helper function."""
        assert get_tier_level("free") == 0
        assert get_tier_level("professional") == 1
        assert get_tier_level("omega") == 2
        assert get_tier_level("FREE") == 0  # Case insensitive
        assert get_tier_level("OMEGA") == 2
        assert get_tier_level("unknown") == 0  # Unknown defaults to 0


class TestFreeUserAccess:
    """Test FREE tier user access."""

    @patch.object(FeatureGate, "get_current_tier", return_value="free")
    def test_free_can_access_free(self, mock_tier):
        """FREE user can access FREE features."""

        @FeatureGate.requires_tier("free")
        def free_feature():
            return "success"

        # Should not raise
        result = free_feature()
        assert result == "success"

    @patch.object(FeatureGate, "get_current_tier", return_value="free")
    def test_free_blocked_from_pro(self, mock_tier):
        """FREE user blocked from PRO features."""

        @FeatureGate.requires_tier("professional")
        def pro_feature():
            return "should not execute"

        # Should raise FeatureAccessDenied
        with pytest.raises(FeatureAccessDenied) as exc_info:
            pro_feature()

        assert "Professional tier" in str(exc_info.value)
        assert "free" in str(exc_info.value).lower()

    @patch.object(FeatureGate, "get_current_tier", return_value="free")
    def test_free_blocked_from_omega(self, mock_tier):
        """FREE user blocked from OMEGA features."""

        @FeatureGate.requires_tier("omega")
        def omega_feature():
            return "should not execute"

        # Should raise FeatureAccessDenied
        with pytest.raises(FeatureAccessDenied) as exc_info:
            omega_feature()

        assert "OMEGA Guardian" in str(exc_info.value)


class TestProUserAccess:
    """Test PRO tier user access (hierarchical)."""

    @patch.object(FeatureGate, "get_current_tier", return_value="professional")
    def test_pro_can_access_free(self, mock_tier):
        """PRO user can access FREE features (hierarchy)."""

        @FeatureGate.requires_tier("free")
        def free_feature():
            return "success"

        # Should not raise (PRO >= FREE)
        result = free_feature()
        assert result == "success"

    @patch.object(FeatureGate, "get_current_tier", return_value="professional")
    def test_pro_can_access_pro(self, mock_tier):
        """PRO user can access PRO features."""

        @FeatureGate.requires_tier("professional")
        def pro_feature():
            return "success"

        # Should not raise
        result = pro_feature()
        assert result == "success"

    @patch.object(FeatureGate, "get_current_tier", return_value="professional")
    def test_pro_blocked_from_omega(self, mock_tier):
        """PRO user blocked from OMEGA features."""

        @FeatureGate.requires_tier("omega")
        def omega_feature():
            return "should not execute"

        # Should raise FeatureAccessDenied
        with pytest.raises(FeatureAccessDenied) as exc_info:
            omega_feature()

        assert "OMEGA Guardian" in str(exc_info.value)
        assert "professional" in str(exc_info.value).lower()


class TestOmegaUserAccess:
    """Test OMEGA tier user access (full hierarchy)."""

    @patch.object(FeatureGate, "get_current_tier", return_value="omega")
    def test_omega_can_access_free(self, mock_tier):
        """OMEGA user can access FREE features (hierarchy)."""

        @FeatureGate.requires_tier("free")
        def free_feature():
            return "success"

        # Should not raise (OMEGA >= FREE)
        result = free_feature()
        assert result == "success"

    @patch.object(FeatureGate, "get_current_tier", return_value="omega")
    def test_omega_can_access_pro(self, mock_tier):
        """OMEGA user can access PRO features (hierarchy) - CRITICAL TEST."""

        @FeatureGate.requires_tier("professional")
        def pro_feature():
            return "success"

        # Should not raise (OMEGA >= PRO)
        # This is the CRITICAL FIX: OMEGA users must access PRO features
        result = pro_feature()
        assert result == "success"

    @patch.object(FeatureGate, "get_current_tier", return_value="omega")
    def test_omega_can_access_omega(self, mock_tier):
        """OMEGA user can access OMEGA features."""

        @FeatureGate.requires_tier("omega")
        def omega_feature():
            return "success"

        # Should not raise
        result = omega_feature()
        assert result == "success"


class TestConvenienceDecorators:
    """Test convenience decorator functions."""

    @patch.object(FeatureGate, "get_current_tier", return_value="omega")
    def test_omega_can_use_requires_pro_decorator(self, mock_tier):
        """OMEGA user can use @requires_pro decorator (hierarchy)."""

        @requires_pro
        def pro_feature():
            return "success"

        # Should not raise (OMEGA >= PRO)
        result = pro_feature()
        assert result == "success"

    @patch.object(FeatureGate, "get_current_tier", return_value="omega")
    def test_omega_can_use_requires_omega_decorator(self, mock_tier):
        """OMEGA user can use @requires_omega decorator."""

        @requires_omega
        def omega_feature():
            return "success"

        # Should not raise
        result = omega_feature()
        assert result == "success"

    @patch.object(FeatureGate, "get_current_tier", return_value="professional")
    def test_pro_blocked_by_requires_omega_decorator(self, mock_tier):
        """PRO user blocked by @requires_omega decorator."""

        @requires_omega
        def omega_feature():
            return "should not execute"

        # Should raise
        with pytest.raises(FeatureAccessDenied):
            omega_feature()


class TestErrorMessages:
    """Test error messages for different upgrade paths."""

    @patch.object(FeatureGate, "get_current_tier", return_value="free")
    def test_free_to_pro_error_message(self, mock_tier):
        """Verify FREE->PRO upgrade message contains correct info."""

        @FeatureGate.requires_tier("professional")
        def pro_feature():
            pass

        with pytest.raises(FeatureAccessDenied) as exc_info:
            pro_feature()

        error_msg = str(exc_info.value)
        assert "Professional tier" in error_msg
        assert "free" in error_msg.lower()
        assert "buy.stripe.com" in error_msg  # Stripe link
        assert "$" in error_msg  # Pricing info

    @patch.object(FeatureGate, "get_current_tier", return_value="free")
    def test_free_to_omega_error_message(self, mock_tier):
        """Verify FREE->OMEGA upgrade message contains correct info."""

        @FeatureGate.requires_tier("omega")
        def omega_feature():
            pass

        with pytest.raises(FeatureAccessDenied) as exc_info:
            omega_feature()

        error_msg = str(exc_info.value)
        assert "OMEGA Guardian" in error_msg
        assert "free" in error_msg.lower()
        assert "IRIS Agent" in error_msg  # OMEGA-specific features
        assert "$35" in error_msg  # OMEGA pricing

    @patch.object(FeatureGate, "get_current_tier", return_value="professional")
    def test_pro_to_omega_error_message(self, mock_tier):
        """Verify PRO->OMEGA upgrade message contains correct info."""

        @FeatureGate.requires_tier("omega")
        def omega_feature():
            pass

        with pytest.raises(FeatureAccessDenied) as exc_info:
            omega_feature()

        error_msg = str(exc_info.value)
        assert "OMEGA Guardian" in error_msg
        assert "professional" in error_msg.lower()
        assert "production monitoring" in error_msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
