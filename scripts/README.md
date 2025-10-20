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
# Founding Member ($59/month forever)
python scripts/generate_key.py john@acme.com sub_1SKN true

# Regular Professional ($99/month)
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

## Security Notes

- Never commit generated license keys to git
- Keep subscription IDs private
- Use `.env` files for sensitive data (already in `.gitignore`)

---

For full documentation, see:
- [docs/MANUAL_FULFILLMENT.md](../docs/MANUAL_FULFILLMENT.md) - Customer fulfillment process
- [docs/STRIPE_SETUP.md](../docs/STRIPE_SETUP.md) - Stripe configuration
- [README.md](../README.md) - Main project README

