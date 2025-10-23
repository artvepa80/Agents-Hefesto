"""
Stripe Configuration (STUB)
============================

⚠️  THIS IS A STUB - Real Stripe configuration is in private repository.

This stub provides public pricing information without exposing
sensitive Stripe product IDs, webhook secrets, or API keys.

Real Stripe integration requires private key access and is handled
by the licensing system in the private repository.

Copyright © 2025 Narapa LLC
"""

# Public pricing information only
STRIPE_CONFIG = {
    # Public pricing (no sensitive IDs)
    "public_pricing": {
        "hefesto_professional": {
            "name": "Hefesto Professional",
            "amount": 25.00,
            "currency": "usd",
            "interval": "month",
            "trial_days": 14,
            "checkout_url": "https://buy.stripe.com/bJeeVc8rM7kZgmq5LweAg08",
        },
        "omega_founding_members": {
            "name": "OMEGA Guardian Founding Members",
            "amount": 35.00,
            "currency": "usd",
            "interval": "month",
            "trial_days": 0,
            "checkout_url": "https://buy.stripe.com/bJe9AScI25cR0ns4HseAg06",
        },
        "omega_professional": {
            "name": "OMEGA Guardian Professional",
            "amount": 49.00,
            "currency": "usd",
            "interval": "month",
            "trial_days": 0,
            "checkout_url": "https://buy.stripe.com/bJe3cugYiaxb4DIgqaeAg07",
        },
    },
    # Payment Links - DEPRECATED (Removed obsolete plans)
    # Only keeping active plans:
    # - Hefesto Professional: $25/month
    # - OMEGA Founding Members: $35/month
    # - OMEGA Professional: $49/month
    "payment_links": {},
    # Coupons - DEPRECATED
    "coupons": {},
    # Tier Limits
    "limits": {
        "free": {
            "tier": "free",
            "users": 1,
            "repositories": 1,
            "loc_monthly": 50_000,
            "analysis_runs": 10,
            "features": ["basic_quality", "pr_analysis", "ide_integration"],
        },
        "professional": {
            "tier": "professional",
            "users": 10,
            "repositories": 25,
            "loc_monthly": 500_000,
            "analysis_runs": float("inf"),
            "features": [
                "ml_semantic_analysis",
                "ai_recommendations",
                "security_scanning",
                "automated_triage",
                "github_gitlab_bitbucket",
                "jira_slack_integration",
                "priority_support",
                "analytics_dashboard",
            ],
        },
    },
    # Webhooks (configure in Stripe dashboard)
    "webhooks": {
        "secret": "",  # Set via STRIPE_WEBHOOK_SECRET env var
        "events": [
            "checkout.session.completed",
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.payment_succeeded",
            "invoice.payment_failed",
        ],
    },
}


def get_tier_from_price_id(price_id: str) -> str:
    """
    Determine tier from Stripe price ID.

    Args:
        price_id: Stripe price ID

    Returns:
        'professional' or 'free'
    """
    products = STRIPE_CONFIG["products"]

    if price_id in [
        products["professional_monthly"]["price_id"],
        products["professional_annual"]["price_id"],
    ]:
        return "professional"

    return "free"


def get_interval_from_price_id(price_id: str) -> str:
    """
    Get billing interval from price ID.

    Args:
        price_id: Stripe price ID

    Returns:
        'month', 'year', or None
    """
    products = STRIPE_CONFIG["products"]

    if price_id == products["professional_monthly"]["price_id"]:
        return "month"
    if price_id == products["professional_annual"]["price_id"]:
        return "year"

    return None


def get_limits_for_tier(tier: str) -> dict:
    """
    Get usage limits for a specific tier.

    Args:
        tier: 'free' or 'professional'

    Returns:
        Dictionary with limits
    """
    return STRIPE_CONFIG["limits"].get(tier, STRIPE_CONFIG["limits"]["free"])


def is_founding_member(coupon_id: str) -> bool:
    """
    DEPRECATED: Founding member discount is no longer active.

    Args:
        coupon_id: Stripe coupon ID

    Returns:
        Always False (feature deprecated)
    """
    return False


def calculate_final_price(price_id: str, has_founding_coupon: bool = False) -> float:
    """
    DEPRECATED: Calculate final price (simplified).

    Current active prices:
    - Hefesto Professional: $25/month
    - OMEGA Founding Members: $35/month
    - OMEGA Professional: $49/month

    Args:
        price_id: Stripe price ID
        has_founding_coupon: Ignored (deprecated)

    Returns:
        Final price in USD
    """
    # Return default prices from public_pricing
    for plan_key, plan_info in STRIPE_CONFIG["public_pricing"].items():
        if price_id in str(plan_info):
            return plan_info["amount"]

    return 0.00


def get_payment_link_by_type(link_type: str) -> dict:
    """
    DEPRECATED: Get payment link configuration.

    Use direct checkout URLs from public_pricing instead.

    Args:
        link_type: Link type (deprecated)

    Returns:
        Empty dict (feature deprecated)
    """
    return {}


__all__ = [
    "STRIPE_CONFIG",
    "get_tier_from_price_id",
    "get_interval_from_price_id",
    "get_limits_for_tier",
    "is_founding_member",
    "calculate_final_price",
    "get_payment_link_by_type",
]
