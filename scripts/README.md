# Hefesto Scripts

Utility scripts for development and operations.

## Available Scripts

### `lineage_timing_protocol.py`
Pre-registered timing protocol for the JCL part of `--lineage`: seeded synthetic trees (2k/4k/8k/16k jobs, seed 7), a flag-off check against a main checkout (identical JSON and SARIF, no JCL opened), 1 warm-up + 21 shuffled rounds timed with `perf_counter_ns`, the growth exponent `k` with a 10,000-resample bootstrap, and a PASS/FAIL verdict. It prints the commit SHA and its own sha256, and writes `result.txt`, `rounds.csv` and `summary.json`. It never passes `timeout=` to a subprocess (that quantises timings at about 50 ms); run it under an outside watchdog:

```bash
timeout 14400 python scripts/lineage_timing_protocol.py --repo . --main ../main \
  --python /path/to/venv/bin/python --workdir /tmp/lt --out /tmp/lt/result
```

Amendment 7.3 (measurement conditions only; criteria, sizes, seeds, rounds and the single run are unchanged): `result.txt` has a `cpu model` line and `--expect-cpu MODEL` makes a run on another CPU INVALID; before every round a quiet gate waits until the 1-minute load is at most 0.25 x cores, for up to 30 minutes, else the run is INVALID (exit 2, no statistics); the flag-off check runs in its own process so the launcher of the timed runs stays small; peak RSS is reported only. Give the watchdog room for the gate.

`--smoke` uses tiny sizes and 2 rounds to check the script (and skips the quiet gate); its output is not a measurement.

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
# PRO $8/mo or OMEGA $19/mo
python scripts/generate_key.py john@acme.com sub_1SKN true

# PRO $8/mo or OMEGA $19/mo
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
- Python 3.11+
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
3. Check Python version: `python --version` (need 3.11+)
4. Clear license: `hefesto deactivate` then rerun tests

---

## ⚠️  Private Scripts

Some internal scripts are in the **private repository** for security:

- **`generate_key.py`** - Real implementation in `private/scripts/`
- **`fulfill_order.py`** - Real implementation in `private/scripts/`

These scripts contain proprietary business logic and require credentials.

### Access Private Scripts

```bash
# Initialize private repository submodule
git submodule update --init

# Run private scripts
python private/scripts/generate_key.py [email] [sub_id] [is_founding]
python private/scripts/fulfill_order.py [email] [sub_id] [is_founding]
```

For access to the private repository, contact: **sales@narapallc.com**

---

### `fulfill_order.py` (PRIVATE) ⭐ RECOMMENDED
**Automated fulfillment for Hefesto Pro orders with S3 distribution.**

Combines license key generation, S3 presigned URL creation, and email template generation in one command.

**Prerequisites:**
- AWS CLI configured: `aws configure`
- boto3 installed: `pip install boto3`
- S3 bucket `hefesto-pro-dist` with wheel uploaded

**Usage:**
```bash
# PRO $8/mo or OMEGA $19/mo
python scripts/fulfill_order.py john@acme.com sub_1ABC123XYZ true

# PRO $8/mo or OMEGA $19/mo
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
2. Determine tier from the Stripe price: PRO $8/mo, OMEGA $19/mo
3. Run: python scripts/fulfill_order.py EMAIL SUB_ID TIER
4. Open: cat email_*.txt
5. Copy and send from support@narapallc.com
6. Log in tracking spreadsheet
```

**Note:** Current pricing: PRO $8/mo, OMEGA $19/mo. Older prices are deprecated.

**Time per customer:** ~2 minutes (fully automated key + URL + email)

**Example:**
```bash
$ python scripts/fulfill_order.py john@acme.com sub_1SKNC8ABC true

🚀 HEFESTO PRO - AUTOMATED FULFILLMENT
═══════════════════════════════════════

📝 Step 1/3: Generating license key...
✅ License key: HFST-XXXX-XXXX-XXXX-XXXX-XXXX

🔗 Step 2/3: Generating download URL...
✅ Download URL generated (expires in 7 days)

📧 Step 3/3: Generating customer email...

✅ FULFILLMENT COMPLETE
Customer:           john@acme.com
License Key:        HFST-XXXX-XXXX-XXXX-XXXX-XXXX
Founding Member:    Yes
Price:              $8/mo (PRO) or $19/mo (OMEGA)
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

