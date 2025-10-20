"""
Stripe configuration for Hefesto Professional tier.
All IDs are from production Stripe account.

Copyright © 2025 Narapa LLC
"""

STRIPE_CONFIG = {
    # Product IDs
    'products': {
        'professional_monthly': {
            'product_id': 'prod_TGv2JCJzh2AjrE',
            'price_id': 'price_1SKNC8CKQFEi4zJFOVTpdD89',
            'amount': 99.00,
            'currency': 'usd',
            'interval': 'month',
            'trial_days': 14
        },
        'professional_annual': {
            'product_id': 'prod_TGvAoXzoRjWVCz',
            'price_id': 'price_1SKNK7CKQFEi4zJFzcUqh9kz',
            'amount': 990.00,
            'currency': 'usd',
            'interval': 'year',
            'trial_days': 0,
            'monthly_equivalent': 82.50,
            'savings': 198.00,
            'discount_percent': 16.7
        }
    },
    
    # Payment Links
    'payment_links': {
        'monthly_trial': {
            'url': 'https://buy.stripe.com/7sY00i0Zkaxbgmq4HseAg04',
            'link_id': 'plink_1SKNWfCKQFEi4zJFnns0YRqf',
            'description': 'Monthly $99 with 14-day trial',
            'tier': 'professional',
            'interval': 'month',
            'has_trial': True,
            'has_coupon': False
        },
        'monthly_founding': {
            'url': 'https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05?prefilled_promo_code=Founding40',
            'url_base': 'https://buy.stripe.com/dRm28q7nIcFjfimfm6eAg05',
            'link_id': 'plink_1SKO9JCKQFEi4zJFNfYyQpYK',
            'description': 'Founding Member: $59/month locked forever',
            'tier': 'professional',
            'interval': 'month',
            'has_trial': True,
            'has_coupon': True,
            'coupon_code': 'Founding40',
            'final_price': 59.00,
            'max_redemptions': 25
        },
        'annual': {
            'url': 'https://buy.stripe.com/9B69AS5fAfRv9Y2ei2eAg03',
            'link_id': 'plink_1SKNUWCKQFEi4zJFTVKVxFYV',
            'description': 'Annual $990 (save $198/year)',
            'tier': 'professional',
            'interval': 'year',
            'has_trial': False,
            'has_coupon': False
        }
    },
    
    # Coupon
    'coupons': {
        'founding_member': {
            'id': 'FoundingMember',
            'code': 'Founding40',
            'discount_percent': 40,
            'duration': 'forever',
            'max_redemptions': 25,
            'current_redemptions': 0,  # Update via Stripe API
            'prices': {
                'monthly': 59.00,
                'annual': 594.00
            }
        }
    },
    
    # Tier Limits
    'limits': {
        'free': {
            'tier': 'free',
            'users': 1,
            'repositories': 1,
            'loc_monthly': 50_000,
            'analysis_runs': 10,
            'features': [
                'basic_quality',
                'pr_analysis',
                'ide_integration'
            ]
        },
        'professional': {
            'tier': 'professional',
            'users': 10,
            'repositories': 25,
            'loc_monthly': 500_000,
            'analysis_runs': float('inf'),
            'features': [
                'ml_semantic_analysis',
                'ai_recommendations',
                'security_scanning',
                'automated_triage',
                'github_gitlab_bitbucket',
                'jira_slack_integration',
                'priority_support',
                'analytics_dashboard'
            ]
        }
    },
    
    # Webhooks (configure in Stripe dashboard)
    'webhooks': {
        'secret': '',  # Set via STRIPE_WEBHOOK_SECRET env var
        'events': [
            'checkout.session.completed',
            'customer.subscription.created',
            'customer.subscription.updated',
            'customer.subscription.deleted',
            'invoice.payment_succeeded',
            'invoice.payment_failed'
        ]
    }
}


def get_tier_from_price_id(price_id: str) -> str:
    """
    Determine tier from Stripe price ID.
    
    Args:
        price_id: Stripe price ID
        
    Returns:
        'professional' or 'free'
    """
    products = STRIPE_CONFIG['products']
    
    if price_id in [
        products['professional_monthly']['price_id'],
        products['professional_annual']['price_id']
    ]:
        return 'professional'
    
    return 'free'


def get_interval_from_price_id(price_id: str) -> str:
    """
    Get billing interval from price ID.
    
    Args:
        price_id: Stripe price ID
        
    Returns:
        'month', 'year', or None
    """
    products = STRIPE_CONFIG['products']
    
    if price_id == products['professional_monthly']['price_id']:
        return 'month'
    if price_id == products['professional_annual']['price_id']:
        return 'year'
    
    return None


def get_limits_for_tier(tier: str) -> dict:
    """
    Get usage limits for a specific tier.
    
    Args:
        tier: 'free' or 'professional'
        
    Returns:
        Dictionary with limits
    """
    return STRIPE_CONFIG['limits'].get(tier, STRIPE_CONFIG['limits']['free'])


def is_founding_member(coupon_id: str) -> bool:
    """
    Check if customer has founding member discount.
    
    Args:
        coupon_id: Stripe coupon ID
        
    Returns:
        True if founding member
    """
    return coupon_id == STRIPE_CONFIG['coupons']['founding_member']['id']


def calculate_final_price(price_id: str, has_founding_coupon: bool = False) -> float:
    """
    Calculate final price after applying discounts.
    
    Args:
        price_id: Stripe price ID
        has_founding_coupon: Whether founding member coupon applied
        
    Returns:
        Final price in USD
    """
    products = STRIPE_CONFIG['products']
    
    if price_id == products['professional_monthly']['price_id']:
        return 59.00 if has_founding_coupon else 99.00
    
    if price_id == products['professional_annual']['price_id']:
        return 594.00 if has_founding_coupon else 990.00
    
    return 0.00


def get_payment_link_by_type(link_type: str) -> dict:
    """
    Get payment link configuration by type.
    
    Args:
        link_type: 'trial', 'founding', or 'annual'
        
    Returns:
        Payment link configuration dict
    """
    links = STRIPE_CONFIG['payment_links']
    
    if link_type == 'trial':
        return links['monthly_trial']
    elif link_type == 'founding':
        return links['monthly_founding']
    elif link_type == 'annual':
        return links['annual']
    
    return links['monthly_trial']  # Default


__all__ = [
    'STRIPE_CONFIG',
    'get_tier_from_price_id',
    'get_interval_from_price_id',
    'get_limits_for_tier',
    'is_founding_member',
    'calculate_final_price',
    'get_payment_link_by_type',
]

