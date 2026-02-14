"""
Hefesto Configuration Settings (Community Edition)

Loads configuration from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """Hefesto configuration settings."""

    # Version
    version: str = "4.9.0"
    environment: str = "production"

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            version=os.getenv("HEFESTO_VERSION", "4.9.0"),
            environment=os.getenv("HEFESTO_ENV", "production"),
        )


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
