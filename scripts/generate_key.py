#!/usr/bin/env python3
"""
Quick license key generator for manual fulfillment.

Usage:
    python scripts/generate_key.py customer@email.com sub_1234567890 [true|false]

Examples:
    python scripts/generate_key.py john@acme.com sub_ABC123 true   # Founding Member
    python scripts/generate_key.py jane@startup.io sub_XYZ789 false  # Regular Pro
"""

import sys

from hefesto.licensing.key_generator import LicenseKeyGenerator


def main():
    if len(sys.argv) < 3:
        print("❌ Error: Missing required arguments\n")
        print("Usage: python generate_key.py <email> <subscription_id> [is_founding]")
        print("\nExamples:")
        print("  python generate_key.py john@acme.com sub_ABC123 true")
        print("  python generate_key.py jane@startup.io sub_XYZ789 false")
        sys.exit(1)

    email = sys.argv[1]
    subscription_id = sys.argv[2]
    is_founding = len(sys.argv) > 3 and sys.argv[3].lower() == "true"

    # Validate email format
    if "@" not in email or "." not in email:
        print(f"❌ Error: Invalid email format: {email}")
        sys.exit(1)

    # Validate subscription ID format
    if not subscription_id.startswith("sub_"):
        print(f"❌ Error: Invalid Stripe subscription ID format: {subscription_id}")
        print("   Expected format: sub_XXXXXXXXXX")
        sys.exit(1)

    # Generate license key
    try:
        license_key = LicenseKeyGenerator.generate(
            customer_email=email,
            tier="professional",
            subscription_id=subscription_id,
            is_founding_member=is_founding,
        )
    except Exception as e:
        print(f"❌ Error generating license key: {e}")
        sys.exit(1)

    # Display results
    print("\n" + "=" * 70)
    print("✅ LICENSE KEY GENERATED SUCCESSFULLY")
    print("=" * 70)
    print(f"Customer Email:    {email}")
    print(f"Subscription ID:   {subscription_id}")
    print("Tier:              Professional")
    print(f"Founding Member:   {'Yes' if is_founding else 'No'}")
    price = (
        "$35/month (locked forever)"
        if is_founding
        else "$25/month (Hefesto) or $35/month (OMEGA Founding) or " "$49/month (OMEGA Pro)"
    )
    print(f"Price:             {price}")
    print("\n" + "=" * 70)
    print(f"LICENSE KEY:       {license_key}")
    print("=" * 70 + "\n")

    # Email template
    print("📧 EMAIL TEMPLATE FOR CUSTOMER:")
    print("-" * 70)
    print(generate_email_template(email, license_key, is_founding))
    print("-" * 70 + "\n")


def generate_email_template(email, license_key, is_founding):
    """Generate email template for customer."""
    name = email.split("@")[0].title()

    template = f"""Subject: ✅ Your Hefesto Professional License Key

Hi {name},

Welcome to Hefesto! 🎉

Your 14-day trial has started. Here's your license key:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LICENSE KEY: {license_key}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUICK START:

1. Install Hefesto:
   pip install hefesto-ai

2. Activate your license:
   hefesto activate {license_key}

3. Initialize in your project:
   cd your-project
   hefesto init

4. Start analyzing:
   hefesto analyze --project .

YOU NOW HAVE ACCESS TO:
✓ ML semantic code analysis
✓ AI-powered code recommendations
✓ Security vulnerability scanning
✓ Automated issue triage
✓ Full Git integrations (GitHub, GitLab, Bitbucket)
✓ Jira & Slack integration
✓ Priority support (4-8 hour response time)
✓ Usage analytics dashboard

NEED HELP?
Just reply to this email or check our docs:
→ Documentation: https://github.com/artvepa80/Agents-Hefesto
→ Landing Page: https://hefesto.narapallc.com

Cheers,
The Hefesto Team
support@narapallc.com"""

    if is_founding:
        template += """

P.S. You're a Founding Member! 🚀
Your price is locked at $35/month forever, even when we raise prices.
Thank you for being an early supporter!"""

    return template


if __name__ == "__main__":
    main()
