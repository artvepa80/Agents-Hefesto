"""
Stripe payment configuration for Hefesto AI.

Contains payment links, pricing information, and feature definitions
for all subscription tiers (FREE, PRO, OMEGA Guardian).
"""

# Stripe Payment Links (with 14-day free trial)
PAYMENT_LINKS = {
    "pro": "https://buy.stripe.com/4gM00i6jE6gV3zE4HseAg0b",
    "omega": "https://buy.stripe.com/14A9AS23o20Fgmqb5QeAg0c",
}

# Launch Pricing (first 100 customers - locked forever)
LAUNCH_PRICES = {
    "pro": 8,  # $8/month
    "omega": 19,  # $19/month
}

# Future Pricing (after launch period)
FUTURE_PRICES = {
    "pro": 25,  # $25/month
    "omega": 35,  # $35/month
}

# Free Trial Period
FREE_TRIAL_DAYS = 14

# Feature Matrix
FEATURES = {
    "free": {
        "price": 0,
        "features": [
            "Basic Analysis",
            "Pre-push Hooks",
            "CLI Commands",
            "Multi-language Support",
            "Security Scanning (basic)",
        ],
        "limits": {
            "repos": 1,
            "lines_of_code": 10000,
            "users": 1,
        },
    },
    "pro": {
        "price": LAUNCH_PRICES["pro"],
        "future_price": FUTURE_PRICES["pro"],
        "payment_link": PAYMENT_LINKS["pro"],
        "features": [
            "Everything in FREE",
            "AI/ML Enhancement (SemanticAnalyzer)",
            "REST API (8 endpoints)",
            "BigQuery Integration",
            "Deep Security Scanning",
            "Duplicate Detection",
            "Anti-Pattern Detection",
            "Priority Support",
        ],
        "limits": {
            "repos": "unlimited",
            "lines_of_code": "unlimited",
            "users": "unlimited",
        },
    },
    "omega": {
        "price": LAUNCH_PRICES["omega"],
        "future_price": FUTURE_PRICES["omega"],
        "payment_link": PAYMENT_LINKS["omega"],
        "features": [
            "Everything in PRO",
            "IRIS Agent (Production Monitoring)",
            "HefestoEnricher (Auto-correlation)",
            "Real-time Alerts (Pub/Sub)",
            "Production Dashboard",
            "BigQuery Analytics",
            "Priority Slack Support",
        ],
        "limits": {
            "repos": "unlimited",
            "lines_of_code": "unlimited",
            "users": "unlimited",
        },
    },
}

# Backward compatibility: STRIPE_CONFIG structure
STRIPE_CONFIG = {
    "public_pricing": {
        "hefesto_professional": {
            "name": "Hefesto Professional",
            "amount": LAUNCH_PRICES["pro"],
            "currency": "usd",
            "interval": "month",
            "trial_days": FREE_TRIAL_DAYS,
            "checkout_url": PAYMENT_LINKS["pro"],
        },
        "omega_guardian": {
            "name": "OMEGA Guardian",
            "amount": LAUNCH_PRICES["omega"],
            "currency": "usd",
            "interval": "month",
            "trial_days": FREE_TRIAL_DAYS,
            "checkout_url": PAYMENT_LINKS["omega"],
        },
    },
    "limits": {
        "free": {
            "tier": "free",
            "users": 1,
            "repositories": 1,
            "loc_monthly": 50_000,
            "loc_per_analysis": 10_000,
            "api_requests_daily": 100,
            "bigquery_gb_monthly": 0,
            "analysis_runs": 100,
            "features": [
                "basic_quality",
                "pr_analysis",
            ],
        },
        "professional": {
            "tier": "professional",
            "users": "unlimited",
            "repositories": "unlimited",
            "loc_monthly": "unlimited",
            "loc_per_analysis": "unlimited",
            "api_requests_daily": "unlimited",
            "bigquery_gb_monthly": 100,
            "analysis_runs": float("inf"),
            "features": [
                "basic_quality",
                "pr_analysis",
                "ide_integration",
                "ml_semantic_analysis",
                "ai_recommendations",
                "security_scanning",
            ],
        },
        "omega": {
            "tier": "omega",
            "users": "unlimited",
            "repositories": "unlimited",
            "loc_monthly": "unlimited",
            "loc_per_analysis": "unlimited",
            "api_requests_daily": "unlimited",
            "bigquery_gb_monthly": "unlimited",
            "analysis_runs": float("inf"),
            "features": [
                "basic_quality",
                "pr_analysis",
                "ide_integration",
                "ml_semantic_analysis",
                "ai_recommendations",
                "security_scanning",
                "iris_monitoring",
                "auto_correlation",
                "jira_slack_integration",
                "priority_support",
                "analytics_dashboard",
            ],
        },
    },
}


def get_payment_link(tier: str) -> str:
    """
    Get Stripe payment link for a tier.

    Args:
        tier: Subscription tier ('pro' or 'omega')

    Returns:
        Stripe payment link URL

    Raises:
        ValueError: If tier is invalid
    """
    if tier.lower() not in PAYMENT_LINKS:
        raise ValueError(f"Invalid tier: {tier}. Must be 'pro' or 'omega'")
    return PAYMENT_LINKS[tier.lower()]


def get_launch_price(tier: str) -> int:
    """
    Get launch pricing for a tier.

    Args:
        tier: Subscription tier ('pro' or 'omega')

    Returns:
        Price in USD per month

    Raises:
        ValueError: If tier is invalid
    """
    if tier.lower() not in LAUNCH_PRICES:
        raise ValueError(f"Invalid tier: {tier}. Must be 'pro' or 'omega'")
    return LAUNCH_PRICES[tier.lower()]


def get_future_price(tier: str) -> int:
    """
    Get future pricing for a tier.

    Args:
        tier: Subscription tier ('pro' or 'omega')

    Returns:
        Price in USD per month

    Raises:
        ValueError: If tier is invalid
    """
    if tier.lower() not in FUTURE_PRICES:
        raise ValueError(f"Invalid tier: {tier}. Must be 'pro' or 'omega'")
    return FUTURE_PRICES[tier.lower()]


def get_savings(tier: str) -> int:
    """
    Calculate annual savings with launch pricing.

    Args:
        tier: Subscription tier ('pro' or 'omega')

    Returns:
        Annual savings in USD

    Raises:
        ValueError: If tier is invalid
    """
    launch = get_launch_price(tier)
    future = get_future_price(tier)
    return (future - launch) * 12


def get_features(tier: str) -> dict:
    """
    Get feature list and limits for a tier.

    Args:
        tier: Subscription tier ('free', 'pro', or 'omega')

    Returns:
        Dictionary with features and limits

    Raises:
        ValueError: If tier is invalid
    """
    if tier.lower() not in FEATURES:
        raise ValueError(f"Invalid tier: {tier}. Must be 'free', 'pro', or 'omega'")
    return FEATURES[tier.lower()]


def get_trial_days() -> int:
    """
    Get free trial duration in days.

    Returns:
        Number of free trial days
    """
    return FREE_TRIAL_DAYS


def get_limits_for_tier(tier: str) -> dict:
    """
    Get usage limits for a specific tier (backward compatibility).

    Args:
        tier: 'free', 'professional', or 'omega'

    Returns:
        Dictionary with limits
    """
    return STRIPE_CONFIG["limits"].get(tier, STRIPE_CONFIG["limits"]["free"])
