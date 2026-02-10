import re
from typing import List, Tuple


class SecretDetector:
    """Shared logic for detecting secrets in cloud templates."""

    # Patterns that are almost certainly secrets (CRITICAL)
    CRITICAL_PATTERNS: List[Tuple[str, str]] = [
        (r"(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])", "Potential AWS Access Key ID"),  # Naive AKIA check
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
        (r"-----BEGIN [A-Z ]+ PRIVATE KEY-----", "Private Key found"),
        (r"xox[baprs]-([0-9a-zA-Z]{10,48})", "Slack Token"),
    ]

    # Patterns for key names that suggest the value is a secret (suspicious)
    SUSPICIOUS_KEY_NAMES = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "secretkey",
        "secret_key",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "accesskey",
        "private_key",
        "privatekey",
        "client_secret",
        "clientsecret",
        "masteruserpassword",
        "db_password",
        "dbpassword",
    ]

    @staticmethod
    def check_value(value: str) -> List[str]:
        """Check a string value for critical secret patterns."""
        if not isinstance(value, str) or not value.strip():
            return []

        findings = []
        for pattern, desc in SecretDetector.CRITICAL_PATTERNS:
            if re.search(pattern, value):
                findings.append(desc)
        return findings

    @staticmethod
    def is_suspicious_key(key: str) -> bool:
        """Check if a key name suggests a secret."""
        key_lower = key.lower()
        return any(s in key_lower for s in SecretDetector.SUSPICIOUS_KEY_NAMES)

    @staticmethod
    def is_hardcoded_value(value: str) -> bool:
        """Heuristic to check if a value looks like a hardcoded string (not a ref/param)."""
        if not isinstance(value, str):
            # If it's a number/bool, it's hardcoded but usually safe (unless password=12345)
            # For secrets, we mostly care about strings.
            return False

        # If it looks like a template variable/fn, it's likely NOT a hardcoded secret
        # CloudFormation: {"Ref": ...} or !Ref ... (if parsed as obj, not str)
        # Helm: {{ ... }}
        # Serverless: ${...}
        # ARM: [...]
        
        # Simple string checks for template syntax
        if "${" in value or "{{" in value or (value.startswith("[") and value.endswith("]")):
            return False

        return True
