#!/usr/bin/env python3
"""
Automated order fulfillment for Hefesto Pro.
Generates license key, S3 presigned URL, and customer email in one command.

Usage:
    python scripts/fulfill_order.py customer@email.com sub_ABC123 true
    python scripts/fulfill_order.py customer@email.com sub_ABC123 false
"""

import os
import sys
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hefesto.licensing.key_generator import LicenseKeyGenerator  # noqa: E402


def generate_presigned_url(bucket: str, key: str, expiration: int = 604800) -> str:
    """
    Generate S3 presigned URL.

    Args:
        bucket: S3 bucket name
        key: Object key (file path in bucket)
        expiration: URL expiration in seconds (default 7 days)

    Returns:
        Presigned URL string
    """
    s3_client = boto3.client("s3", region_name="us-east-1")

    try:
        url = s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        print(f"❌ Error generating presigned URL: {e}")
        print("   Make sure AWS credentials are configured: aws configure")
        sys.exit(1)


def generate_customer_email(
    email: str, license_key: str, download_url: str, is_founding: bool
) -> str:
    """Generate customer welcome email with all instructions."""
    name = email.split("@")[0].title()

    template = f"""Subject: ✅ Your Hefesto Professional License - Download & Activate

Hi {name},

Welcome to Hefesto Professional! 🎉

Your 14-day trial has started. Follow these 4 simple steps:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1: INSTALL BASE PACKAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pip install hefesto-ai

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2: DOWNLOAD PROFESSIONAL FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Download link (expires in 7 days):
{download_url}

Or use wget:
wget -O hefesto_pro.whl "{download_url}"

Or use curl:
curl -L -o hefesto_pro.whl "{download_url}"

Then install:
pip install hefesto_pro.whl

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3: ACTIVATE YOUR LICENSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LICENSE KEY: {license_key}

Run:
hefesto activate {license_key}

Verify:
hefesto status

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4: START USING PRO FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cd your-project
hefesto init
hefesto analyze --project . --semantic-ml --ai-recommendations

YOU NOW HAVE ACCESS TO:
✓ ML semantic code analysis
✓ AI-powered code recommendations
✓ Security vulnerability scanning
✓ Automated issue triage
✓ Full Git integrations (GitHub, GitLab, Bitbucket)
✓ Jira & Slack integration
✓ Priority email support ({'2-4 hour' if is_founding else '4-8 hour'} response)
✓ Usage analytics dashboard

NEED HELP?
Reply to this email: support@narapallc.com
Documentation: https://github.com/artvepa80/Agents-Hefesto

Cheers,
The Hefesto Team
support@narapallc.com"""

    if is_founding:
        template += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P.S. YOU'RE A FOUNDING MEMBER! 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your price is locked at $35/month FOREVER, even when we raise prices.

Thank you for being an early supporter! As a Founding Member, you get:
• Priority support (2-4 hour response time)
• Lifetime discount (save $480/year forever)
• Direct input on roadmap
• Early access to new features

Welcome to the founding team! 🎉"""

    return template


def fulfill_order(email: str, subscription_id: str, is_founding: bool):
    """
    Complete order fulfillment.

    Args:
        email: Customer email
        subscription_id: Stripe subscription ID
        is_founding: Whether customer is Founding Member
    """
    print("\n" + "=" * 70)
    print("🚀 HEFESTO PRO - AUTOMATED FULFILLMENT")
    print("=" * 70)

    # 1. Generate license key
    print("\n📝 Step 1/3: Generating license key...")
    license_key = LicenseKeyGenerator.generate(
        customer_email=email,
        tier="professional",
        subscription_id=subscription_id,
        is_founding_member=is_founding,
    )
    print(f"✅ License key: {license_key}")

    # 2. Generate S3 presigned URL
    print("\n🔗 Step 2/3: Generating download URL...")
    bucket = "hefesto-pro-dist"
    key = "wheels/hefesto_pro-1.0.0-py3-none-any.whl"
    download_url = generate_presigned_url(bucket, key, expiration=604800)
    print("✅ Download URL generated (expires in 7 days)")

    # 3. Generate email
    print("\n📧 Step 3/3: Generating customer email...")
    email_content = generate_customer_email(email, license_key, download_url, is_founding)

    # Save email to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"email_{email.replace('@', '_at_').replace('.', '_')}_{timestamp}.txt"
    with open(filename, "w") as f:
        f.write(email_content)

    # Print summary
    print("\n" + "=" * 70)
    print("✅ FULFILLMENT COMPLETE")
    print("=" * 70)
    print(f"Customer:           {email}")
    print(f"Subscription:       {subscription_id}")
    print(f"License Key:        {license_key}")
    print(f"Founding Member:    {'Yes' if is_founding else 'No'}")
    price = (
        "$35/month locked"
        if is_founding
        else "$25/month (Hefesto) or $35/month (OMEGA Founding) or " "$49/month (OMEGA Pro)"
    )
    print(f"Price:              {price}")
    print(f"Download expires:   {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M')}")
    print(f"Email saved to:     {filename}")
    print("=" * 70)

    print("\n📋 NEXT STEPS:")
    print(f"1. Open email file: cat {filename}")
    print("2. Copy content")
    print("3. Send from support@narapallc.com to customer")
    print("4. Log in tracking spreadsheet")
    print("\n" + "=" * 70 + "\n")


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("❌ Usage: python scripts/fulfill_order.py <email> <subscription_id> [is_founding]")
        print("\nExamples:")
        print("  python scripts/fulfill_order.py john@acme.com sub_ABC123 true")
        print("  python scripts/fulfill_order.py jane@startup.io sub_XYZ789 false")
        sys.exit(1)

    email = sys.argv[1]
    subscription_id = sys.argv[2]
    is_founding = len(sys.argv) > 3 and sys.argv[3].lower() == "true"

    # Validate
    if "@" not in email or "." not in email.split("@")[1]:
        print(f"❌ Invalid email format: {email}")
        sys.exit(1)

    if not subscription_id.startswith("sub_"):
        print(f"❌ Invalid Stripe subscription ID: {subscription_id}")
        print("   Expected format: sub_XXXXXXXXXX")
        sys.exit(1)

    # Fulfill
    try:
        fulfill_order(email, subscription_id, is_founding)
    except Exception as e:
        print(f"\n❌ Error during fulfillment: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
