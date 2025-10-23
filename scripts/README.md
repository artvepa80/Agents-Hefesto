# Hefesto Scripts

Utility scripts for development and operations.

## Available Scripts

### `test_e2e.sh`
End-to-end testing suite. Run before launch or after major changes.

```bash
./scripts/test_e2e.sh
```

**Tests:**
- Installation & setup
- Free tier functionality
- License key validation
- Professional tier activation
- License management (activate/deactivate)
- Feature gating
- Stripe configuration
- License key generation

**Expected output:**
- ✅ Passed: ~28 tests
- ❌ Failed: 0 tests

### `generate_key.py`
Manual license key generator for customer orders.

```bash
python scripts/generate_key.py customer@email.com sub_ABC123 true
```

**Arguments:**
1. Customer email address
2. Stripe subscription ID (starts with `sub_`)
3. Is founding member: `true` or `false`

**Output:**
- Generated license key
- Ready-to-send email template
- Customer details summary

**Examples:**
```bash
# Founding Member ($35/month forever)
python scripts/generate_key.py john@acme.com sub_1SKN true

# Regular Professional ($25/month (Hefesto) or $35/month (OMEGA Founding) or $49/month (OMEGA Pro))
python scripts/generate_key.py jane@startup.io sub_1SKP false
```

## Running Tests

### Full E2E Test Suite
```bash
cd /path/to/hefesto-standalone
./scripts/test_e2e.sh
```

### Single Test
```bash
# Test CLI installation
hefesto --help

# Test license activation
hefesto activate HFST-1234-5678-9ABC-DEF0-1234

# Check license status
hefesto status
```

## Adding New Scripts

1. Create script in `scripts/`
2. Make executable: `chmod +x scripts/your_script.sh`
3. Add entry points to `setup.py` if CLI command
4. Document here
5. Test thoroughly before committing

## Dependencies

Scripts may require:
- Python 3.10+
- Bash (for .sh scripts)
- Hefesto installed locally (`pip install -e .`)

## Troubleshooting

### "Command not found: hefesto"
```bash
pip install -e .
```

### "Permission denied"
```bash
chmod +x scripts/test_e2e.sh
chmod +x scripts/generate_key.py
```

### Tests failing?
1. Ensure you're in project root: `cd /path/to/hefesto-standalone`
2. Install package: `pip install -e .`
3. Check Python version: `python --version` (need 3.10+)
4. Clear license: `hefesto deactivate` then rerun tests

### `fulfill_order.py` ⭐ RECOMMENDED
**Automated fulfillment for Hefesto Pro orders with S3 distribution.**

Combines license key generation, S3 presigned URL creation, and email template generation in one command.

**Prerequisites:**
- AWS CLI configured: `aws configure`
- boto3 installed: `pip install boto3`
- S3 bucket `hefesto-pro-dist` with wheel uploaded

**Usage:**
```bash
# Founding Member ($35/month)
python scripts/fulfill_order.py john@acme.com sub_1ABC123XYZ true

# Regular Professional ($25/month (Hefesto) or $35/month (OMEGA Founding) or $49/month (OMEGA Pro))
python scripts/fulfill_order.py jane@startup.io sub_1XYZ789ABC false
```

**Output:**
1. Generates license key (HFST-XXXX-XXXX-XXXX-XXXX-XXXX)
2. Creates S3 presigned URL (7-day expiration)
3. Generates complete customer email with instructions
4. Saves email to file: `email_customer_at_domain_TIMESTAMP.txt`

**Fulfillment Workflow (2 minutes per customer):**

```
WHEN STRIPE PAYMENT ARRIVES:
1. Extract: customer email + subscription ID + amount
2. Determine tier: $25 = Hefesto, $35 = OMEGA Founding, $49 = OMEGA Pro
3. Run: python scripts/fulfill_order.py EMAIL SUB_ID TIER
4. Open: cat email_*.txt
5. Copy and send from support@narapallc.com
6. Log in tracking spreadsheet
```

**Note:** Old pricing ($59/$99) deprecated. Update fulfillment scripts accordingly.

**Time per customer:** ~2 minutes (fully automated key + URL + email)

**Example:**
```bash
$ python scripts/fulfill_order.py john@acme.com sub_1SKNC8ABC true

🚀 HEFESTO PRO - AUTOMATED FULFILLMENT
═══════════════════════════════════════

📝 Step 1/3: Generating license key...
✅ License key: HFST-A2F4-8B91-C3D7-E5F6-1234

🔗 Step 2/3: Generating download URL...
✅ Download URL generated (expires in 7 days)

📧 Step 3/3: Generating customer email...

✅ FULFILLMENT COMPLETE
Customer:           john@acme.com
License Key:        HFST-A2F4-8B91-C3D7-E5F6-1234
Founding Member:    Yes
Price:              $35/month locked
Email saved to:     email_john_at_acme_com_20251020_183045.txt
```

---

## Security Notes

- Never commit generated license keys to git
- Keep subscription IDs private
- Use `.env` files for sensitive data (already in `.gitignore`)
- Email files (email_*.txt) are generated locally and not tracked by git

---

For full documentation, see:
- [docs/MANUAL_FULFILLMENT.md](../docs/MANUAL_FULFILLMENT.md) - Customer fulfillment process
- [docs/STRIPE_SETUP.md](../docs/STRIPE_SETUP.md) - Stripe configuration
- [README.md](../README.md) - Main project README

