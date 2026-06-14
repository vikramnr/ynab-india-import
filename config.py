"""
Configuration Management Module
================================

Loads configuration from:
1. config.yml (local file)
2. Environment variables (override)
3. Defaults (fallback)
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


class Config:
    """Manages application configuration from multiple sources."""

    def __init__(self, config_file: str = "config.yml"):
        """
        Initialize config from file and environment.

        Args:
            config_file: Path to YAML config file. Defaults to "config.yml" in repo root.

        Raises:
            ConfigError: If config file doesn't exist or is malformed.
        """
        self.config_file = Path(config_file)
        self.config_data: Dict[str, Any] = {}

        # Load from file if it exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config_data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ConfigError(f"Invalid YAML in {self.config_file}: {e}")
        else:
            raise ConfigError(
                f"Config file not found: {self.config_file}\n"
                f"Please create a config.yml file. See README.md for format."
            )

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Get a config value by dot-notation key.

        Args:
            key: Configuration key, e.g. "ynab.api_token" or "import.dry_run"
            default: Default value if key not found

        Returns:
            Configuration value or default if not found.

        Example:
            >>> config.get("ynab.budget_id", "last-used")
            >>> config.get("ynab.api_token")
        """
        # Check environment variable first (takes precedence)
        env_key = key.upper().replace(".", "_")
        if env_key in os.environ:
            return os.environ[env_key]

        # Then check config file
        keys = key.split(".")
        value = self.config_data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def get_required(self, key: str) -> Any:
        """
        Get a required config value. Raises if not found.

        Args:
            key: Configuration key

        Returns:
            Configuration value

        Raises:
            ConfigError: If key not found in config or environment.
        """
        value = self.get(key)
        if value is None:
            env_key = key.upper().replace(".", "_")
            raise ConfigError(
                f"Required configuration '{key}' not found.\n"
                f"Set it in config.yml or via environment variable {env_key}"
            )
        return value

    # ── Convenience methods for common config values ──

    @property
    def ynab_api_token(self) -> str:
        """Get YNAB API token (required)."""
        return self.get_required("ynab.api_token")

    @property
    def ynab_budget_id(self) -> str:
        """Get YNAB budget ID. Defaults to 'last-used'."""
        return self.get("ynab.budget_id", "last-used")

    @property
    def ynab_base_url(self) -> str:
        """Get YNAB base URL."""
        return f"https://api.youneedabudget.com/v1/budgets/{self.ynab_budget_id}"

    @property
    def import_account_id(self) -> Optional[str]:
        """Get default import account ID (optional)."""
        return self.get("import.account_id")

    @property
    def import_dry_run(self) -> bool:
        """Get dry-run flag. Defaults to False."""
        return self.get("import.dry_run", False)

    @property
    def max_batch_size(self) -> int:
        """Get max transactions per API request. Defaults to 1000."""
        return self.get("import.max_batch_size", 1000)

    def __repr__(self) -> str:
        """String representation showing loaded config path."""
        return f"<Config from {self.config_file}>"


# Global config instance
_config: Optional[Config] = None


def load_config(config_file: str = "config.yml") -> Config:
    """
    Load or get the global config instance.

    Args:
        config_file: Path to config file (only used on first call)

    Returns:
        Global Config instance
    """
    global _config
    if _config is None:
        _config = Config(config_file)
    return _config


def get_config() -> Config:
    """Get the global config instance. Must call load_config() first."""
    global _config
    if _config is None:
        raise ConfigError("Config not loaded. Call load_config() first.")
    return _config
