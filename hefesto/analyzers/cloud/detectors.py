import re
from typing import List, Tuple


class SecretDetector:
    """Shared logic for detecting secrets in cloud templates."""

    # Patterns that are almost certainly secrets (CRITICAL)
    CRITICAL_PATTERNS: List[Tuple[str, str]] = [
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
        (r"-----BEGIN [A-Z ]+ PRIVATE KEY-----", "Private Key found"),
        (r"(?i)xox[baprs]-[0-9A-Za-z-]{10,}", "Slack Token"),
        (r"(?i)ghp_[0-9A-Za-z]{30,}", "GitHub Token"),
        (r"(?i)AIza[0-9A-Za-z\-_]{30,}", "Google API Key"),
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
            return False

        # Common template vars
        if "${" in value or "{{" in value or (value.startswith("[") and value.endswith("]")):
            return False

        # CloudFormation dynamic references
        if "{{resolve:" in value:
            return False

        # CloudFormation short tags (often preserved as strings depending on loader)
        val_stripped = value.lstrip()
        if (
            val_stripped.startswith("!Ref")
            or val_stripped.startswith("!Sub")
            or val_stripped.startswith("!Join")
            or val_stripped.startswith("!GetAtt")
        ):
            return False

        return True
