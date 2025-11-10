"""
License Key Generator (STUB - Public Version)
==============================================

⚠️  This is a public stub. Real implementation is in private repository.

The actual license key generation logic contains proprietary algorithms
and business rules that are not open source.

For access to the full implementation:
- PRO/OMEGA customers: Contact support@narapallc.com
- Enterprise: Contact sales@narapallc.com

Copyright © 2025 Narapa LLC
"""

import hashlib
from dataclasses import dataclass
from typing import Dict


@dataclass
class LicenseMetadata:
    """License metadata structure."""

    customer_email: str
    tier: str
    subscription_id: str
    price_id: str
    is_founding_member: bool
    limits: Dict
    created_at: str
    status: str  # 'active', 'cancelled', 'expired'


class LicenseKeyGenerator:
    """
    Generate and validate Hefesto license keys.

    ⚠️  STUB: This public version does not contain the actual implementation.

    License key format: HFST-XXXX-XXXX-XXXX-XXXX-XXXX
    """

    PREFIX = "HFST"
    KEY_LENGTH = 20

    @classmethod
    def generate(
        cls, customer_email: str, tier: str, subscription_id: str, is_founding_member: bool = False
    ) -> str:
        """
        Generate a unique license key.

        ⚠️  STUB: Real implementation in private repository.

        This public version returns a placeholder for demonstration purposes only.
        Actual key generation uses proprietary algorithms.

        Args:
            customer_email: Stripe customer email
            tier: 'free' or 'professional'
            subscription_id: Stripe subscription ID
            is_founding_member: Whether customer has founding member discount

        Returns:
            License key string (demo mode)
        """
        raise NotImplementedError(
            "❌ License key generation is not available in the public version.\n"
            "\n"
            "This functionality is part of Hefesto's proprietary backend.\n"
            "\n"
            "For PRO/OMEGA customers:\n"
            "  → License keys are generated automatically via Stripe webhook\n"
            "  → Check your email after purchase for your license key\n"
            "\n"
            "For Enterprise/Self-hosted:\n"
            "  → Contact: sales@narapallc.com\n"
            "  → Private repository access available\n"
        )

    @classmethod
    def validate_format(cls, key: str) -> bool:
        """
        Validate license key format.

        This basic validation is available in the public version.

        Args:
            key: License key to validate

        Returns:
            True if format is valid

        Example:
            >>> LicenseKeyGenerator.validate_format("HFST-A1B2-C3D4-E5F6-G7H8-I9J0")
            True
            >>> LicenseKeyGenerator.validate_format("invalid-key")
            False
        """
        if not key or not isinstance(key, str):
            return False

        parts = key.split("-")

        # Check structure: PREFIX-XXXX-XXXX-XXXX-XXXX-XXXX (6 parts)
        if len(parts) != 6:
            return False

        if parts[0] != cls.PREFIX:
            return False

        # Check each segment is 4 hexadecimal characters
        for part in parts[1:]:
            if len(part) != 4:
                return False
            if not all(c in "0123456789ABCDEF" for c in part):
                return False

        return True

    @classmethod
    def create_license_metadata(
        cls,
        customer_email: str,
        tier: str,
        subscription_id: str,
        price_id: str,
        is_founding_member: bool,
    ) -> LicenseMetadata:
        """
        Create license metadata to store in database.

        ⚠️  STUB: Real implementation in private repository.

        Args:
            customer_email: Customer email
            tier: Tier name
            subscription_id: Stripe subscription ID
            price_id: Stripe price ID
            is_founding_member: Founding member status

        Returns:
            LicenseMetadata object
        """
        raise NotImplementedError(
            "❌ License metadata creation is not available in the public version.\n"
            "This is handled automatically by the Hefesto backend service.\n"
        )

    @classmethod
    def hash_key(cls, key: str) -> str:
        """
        Hash license key for secure storage.

        This utility function is available in the public version.

        Args:
            key: License key to hash

        Returns:
            SHA-256 hash of key
        """
        return hashlib.sha256(key.encode()).hexdigest()


__all__ = [
    "LicenseKeyGenerator",
    "LicenseMetadata",
]
