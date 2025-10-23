"""
Configuration manager for Hefesto.
Stores license keys and user preferences locally.
"""

import json
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """
    Manage Hefesto configuration and license storage.

    Config is stored in ~/.hefesto/config.json
    """

    def __init__(self):
        """Initialize config manager and ensure config directory exists."""
        self.config_dir = Path.home() / ".hefesto"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Create config directory and file if they don't exist."""
        self.config_dir.mkdir(exist_ok=True)
        if not self.config_file.exists():
            self._save_config({})

    def _load_config(self) -> dict:
        """
        Load config from file.

        Returns:
            Configuration dictionary
        """
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self, config: dict):
        """
        Save config to file.

        Args:
            config: Configuration dictionary to save
        """
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a config value.

        Args:
            key: Configuration key
            default: Default value if key doesn't exist

        Returns:
            Configuration value or default
        """
        config = self._load_config()
        return config.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set a config value.

        Args:
            key: Configuration key
            value: Value to store
        """
        config = self._load_config()
        config[key] = value
        self._save_config(config)

    def delete(self, key: str):
        """
        Delete a config value.

        Args:
            key: Configuration key to delete
        """
        config = self._load_config()
        if key in config:
            del config[key]
            self._save_config(config)

    def get_license_key(self) -> Optional[str]:
        """
        Get stored license key.

        Returns:
            License key string or None
        """
        return self.get("license_key")

    def set_license_key(self, key: str):
        """
        Store license key and set tier.

        Args:
            key: License key to store
        """
        self.set("license_key", key)
        self.set("tier", "professional")

    def clear_license(self):
        """Remove license key and reset to free tier."""
        self.delete("license_key")
        self.delete("tier")

    def get_tier(self) -> str:
        """
        Get current tier.

        Returns:
            'free' or 'professional'
        """
        return self.get("tier", "free")
