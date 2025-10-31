"""
License key generation and validation for Hefesto Professional tier.
Keys are generated when Stripe webhook confirms payment.

Copyright © 2025 Narapa LLC
"""

import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass, asdict


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
    
    License key format: HFST-XXXX-XXXX-XXXX-XXXX-XXXX
    
    Example:
        >>> generator = LicenseKeyGenerator()
        >>> key = generator.generate(
        ...     customer_email="user@example.com",
        ...     tier="professional",
        ...     subscription_id="sub_xxxxx",
        ...     is_founding_member=True
        ... )
        >>> print(key)
        HFST-A1B2-C3D4-E5F6-G7H8-I9J0
    """
    
    PREFIX = "HFST"
    KEY_LENGTH = 20  # Total characters excluding prefix and hyphens
    
    @classmethod
    def generate(
        cls,
        customer_email: str,
        tier: str,
        subscription_id: str,
        is_founding_member: bool = False
    ) -> str:
        """
        Generate a unique license key.
        
        Format: HFST-XXXX-XXXX-XXXX-XXXX-XXXX
        
        Args:
            customer_email: Stripe customer email
            tier: 'free' or 'professional'
            subscription_id: Stripe subscription ID
            is_founding_member: Whether customer has founding member discount
            
        Returns:
            License key string (30 characters total)
            
        Example:
            >>> key = LicenseKeyGenerator.generate(
            ...     customer_email="customer@example.com",
            ...     tier="professional",
            ...     subscription_id="sub_1234567890",
            ...     is_founding_member=False
            ... )
            >>> assert key.startswith("HFST-")
            >>> assert len(key) == 29  # HFST-XXXX-XXXX-XXXX-XXXX-XXXX
        """
        # Generate random key part (16 hex characters)
        random_bytes = secrets.token_bytes(8)
        random_part = random_bytes.hex().upper()
        
        # Create checksum from customer data for verification
        checksum_data = f"{customer_email}:{tier}:{subscription_id}".encode()
        checksum = hashlib.sha256(checksum_data).hexdigest()[:4].upper()
        
        # Combine random + checksum (20 chars total)
        key_chars = random_part + checksum
        
        # Format as HFST-XXXX-XXXX-XXXX-XXXX-XXXX
        formatted_key = (
            f"{cls.PREFIX}-"
            f"{key_chars[0:4]}-"
            f"{key_chars[4:8]}-"
            f"{key_chars[8:12]}-"
            f"{key_chars[12:16]}-"
            f"{key_chars[16:20]}"
        )
        
        return formatted_key
    
    @classmethod
    def validate_format(cls, key: str) -> bool:
        """
        Validate license key format.
        
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
        
        parts = key.split('-')
        
        # Check structure: PREFIX-XXXX-XXXX-XXXX-XXXX-XXXX (6 parts)
        if len(parts) != 6:
            return False
        
        if parts[0] != cls.PREFIX:
            return False
        
        # Check each segment is 4 hexadecimal characters
        for part in parts[1:]:
            if len(part) != 4:
                return False
            if not all(c in '0123456789ABCDEF' for c in part):
                return False
        
        return True
    
    @classmethod
    def create_license_metadata(
        cls,
        customer_email: str,
        tier: str,
        subscription_id: str,
        price_id: str,
        is_founding_member: bool
    ) -> LicenseMetadata:
        """
        Create license metadata to store in database.
        
        Args:
            customer_email: Customer email
            tier: Tier name
            subscription_id: Stripe subscription ID
            price_id: Stripe price ID
            is_founding_member: Founding member status
            
        Returns:
            LicenseMetadata object
        """
        from hefesto.config.stripe_config import get_limits_for_tier
        
        limits = get_limits_for_tier(tier)
        
        return LicenseMetadata(
            customer_email=customer_email,
            tier=tier,
            subscription_id=subscription_id,
            price_id=price_id,
            is_founding_member=is_founding_member,
            limits=limits,
            created_at=datetime.utcnow().isoformat(),
            status='active'
        )
    
    @classmethod
    def hash_key(cls, key: str) -> str:
        """
        Hash license key for secure storage.
        
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

