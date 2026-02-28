# License Gates - Developer Guide

## Overview

Hefesto uses license gates to protect PRO and OMEGA Guardian features.
All advanced features are included in the PyPI package but require
valid license keys to function.

## Example: Basic Feature Gate
```python
from hefesto.licensing import LicenseValidator

class ProFeature:
    def __init__(self, license_key: Optional[str] = None):
        self.validator = LicenseValidator(license_key)

        if not self.validator.is_pro():
            raise ProFeatureError(
                "This feature requires Hefesto PRO license.\n"
                "Upgrade at: https://buy.stripe.com/4gMfZg4bw48N3zEgqaeAg0a"
            )

    def execute(self):
        # Feature code only runs with valid license
        return self._protected_logic()
```

## Example: OMEGA Guardian Gate
```python
from hefesto.licensing import LicenseValidator

class OmegaFeature:
    def __init__(self, license_key: Optional[str] = None):
        self.validator = LicenseValidator(license_key)

        if not self.validator.is_omega():
            raise OmegaFeatureError(
                "This feature requires OMEGA Guardian license.\n"
                "Upgrade at: https://buy.stripe.com/omega-link"
            )

    def execute(self):
        # OMEGA-only code
        return self._omega_logic()
```

## Tier Detection
```python
validator = LicenseValidator()

# Check tier
if validator.is_free():
    # Basic features only
    pass
elif validator.is_pro():
    # PRO features enabled
    pass
elif validator.is_omega():
    # OMEGA Guardian features enabled
    pass
```

## Error Messages

Always provide helpful error messages with upgrade links:
```python
if not validator.is_pro():
    raise ProFeatureError(
        "ML Enhancement requires Hefesto PRO license.\n\n"
        "Upgrade options:\n"
        "• PRO: $8/month - https://buy.stripe.com/pro-link\n"
        "• OMEGA Guardian: $19/month - https://buy.stripe.com/omega-link\n"
        "• Details: https://hefesto.ai/pricing\n\n"
        "Questions? support@narapa.com"
    )
```

## Testing License Gates
```bash
# Test without license (should fail gracefully)
unset HEFESTO_LICENSE_KEY
hefesto analyze .  # Should show upgrade message

# Test with PRO license
export HEFESTO_LICENSE_KEY="HFST-xxxx-xxxx-xxxx-xxxx"
hefesto analyze .  # Should work

# Test tier detection
hefesto status  # Should show: License: PRO
```

## Best Practices

1. **Always validate license before executing protected code**
2. **Provide clear upgrade paths in error messages**
3. **Test with and without license keys**
4. **Use informative error messages**
5. **Don't leak implementation details in errors**

---

© 2025 Narapa LLC - OMEGA Guardian Suite
