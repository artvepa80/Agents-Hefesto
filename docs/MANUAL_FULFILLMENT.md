# Manual License Fulfillment Guide

Quick reference for processing customer orders manually during launch phase.

## Process Overview

```
Stripe Email → Generate Key → Send Welcome Email → Log
   (30s)          (30s)            (2 min)         (30s)
```

**Total time per customer: ~4 minutes**

---

## Step-by-Step Instructions

### Step 1: Stripe Payment Notification (30 seconds)

When you receive a Stripe payment email, extract:

- ✅ **Customer email**: The buyer's email address
- ✅ **Subscription ID**: Starts with `sub_` (e.g., `sub_1SKNC8CKQFEi4zJF...`)
- ✅ **Amount**: 
  - `$59.40` = Founding Member (40% discount applied)
  - `$99.00` = Regular Professional

---

### Step 2: Generate License Key (30 seconds)

Open terminal and run:

```bash
cd ~/Agents-Hefesto

# For Founding Member ($59/month):
python scripts/generate_key.py customer@email.com sub_ABC123XYZ true

# For Regular Pro ($99/month):
python scripts/generate_key.py customer@email.com sub_ABC123XYZ false
```

**Output:**
- License key in format: `HFST-XXXX-XXXX-XXXX-XXXX-XXXX`
- Ready-to-send email template

---

### Step 3: Send Welcome Email (2 minutes)

1. **Copy** the email template from terminal output
2. **Open** Gmail or your email client
3. **Send from**: support@narapallc.com
4. **To**: Customer's email
5. **Paste** template and verify:
   - License key is correct
   - Name is personalized
   - Founding Member note (if applicable)
6. **Send**

---

### Step 4: Log the Transaction (30 seconds)

Add row to tracking spreadsheet:

| Date | Email | License Key | Subscription ID | Tier | Notes |
|------|-------|-------------|-----------------|------|-------|
| 2025-10-20 | john@acme.com | HFST-1234... | sub_ABC123 | Founding | First customer! |

---

## Troubleshooting

### Customer didn't receive email?

1. Check spam folder (ask them to check)
2. Verify you sent from support@narapallc.com
3. Resend from different email if needed
4. Provide license key via Stripe dashboard message

### License key not working?

1. Verify format: `HFST-XXXX-XXXX-XXXX-XXXX-XXXX`
2. Check they're using latest version: `pip install --upgrade hefesto-ai`
3. Have them try: `hefesto status` to see current tier
4. Generate new key if needed

### Customer wants refund?

1. Go to Stripe Dashboard
2. Find subscription
3. Cancel subscription + issue refund
4. Customer's license will deactivate automatically

---

## Quick Reference

### Command Cheat Sheet

```bash
# Generate key (Founding)
python scripts/generate_key.py EMAIL SUB_ID true

# Generate key (Regular)
python scripts/generate_key.py EMAIL SUB_ID false

# Test key locally
hefesto activate HFST-XXXX-XXXX-XXXX-XXXX-XXXX
hefesto status
```

### Email Addresses

- **Send from**: support@narapallc.com
- **CC**: Your personal email (for tracking)
- **BCC**: Do not use (GDPR/privacy)

### Response Times

- **Founding Members**: 2-4 hours (priority)
- **Regular Pro**: 4-8 hours
- **Free tier**: 24-48 hours

---

## Automation Trigger

Switch to automated fulfillment when:
- ✅ You have 10+ customers
- ✅ Taking more than 1 hour/day on fulfillment
- ✅ Missing customers due to manual delays

At that point, implement webhook automation.

