"""Centralized configuration management for the application."""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Configuration:
    """
    Centralized configuration management.

    This class provides a centralized way to access configuration values,
    with support for environment variables, config files, and defaults.
    """

    # Default configuration values
    _defaults = {
        # HTTP settings
        "http_timeout": 60.0,
        "http_max_keepalive": 5,
        "http_max_connections": 10,
        "http_follow_redirects": True,
        # Rate limiting
        "rate_limit_rate": 3,
        "rate_limit_per": 1.0,
        "page_rate_limit_rate": 1,
        "page_rate_limit_per": 5.0,
        # Export limits
        "max_pages_to_scrape_session": 1000,
        "max_concurrent_exports": 5,
        # File paths
        "default_state_file": "runninglog_state.json",
        "default_timezone": "UTC",
        # URLs
        "base_url": "http://running-log.com",
        # Performance
        "tenacity_retry_attempts": 10,
        "tenacity_min_wait": 15,
        "tenacity_max_wait": 60,
    }

    # Environment variable prefixes
    _env_prefix = "RUNNINGLOG_"

    # Instance for singleton pattern
    _instance = None

    @classmethod
    def get_instance(cls) -> "Configuration":
        """Get the singleton configuration instance."""
        if cls._instance is None:
            cls._instance = Configuration()
        return cls._instance

    def __init__(self):
        """Initialize configuration with defaults and environment variables."""
        self._config = dict(self._defaults)
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        for key in self._defaults.keys():
            env_key = f"{self._env_prefix}{key.upper()}"
            if env_key in os.environ:
                env_value = os.environ[env_key]
                # Convert to appropriate type based on default
                default_value = self._defaults[key]
                if isinstance(default_value, bool):
                    self._config[key] = env_value.lower() in (
                        "true",
                        "1",
                        "yes",
                        "y",
                        "t",
                    )
                elif isinstance(default_value, int):
                    try:
                        self._config[key] = int(env_value)
                    except ValueError:
                        logger.warning(
                            f"Invalid value for {env_key}: {env_value} (expected int)"
                        )
                elif isinstance(default_value, float):
                    try:
                        self._config[key] = float(env_value)
                    except ValueError:
                        logger.warning(
                            f"Invalid value for {env_key}: {env_value} (expected float)"
                        )
                else:
                    self._config[key] = env_value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value

    def as_dict(self) -> Dict[str, Any]:
        """
        Get configuration as dictionary.

        Returns:
            Dictionary of configuration values
        """
        return dict(self._config)


# Global helper functions for easy access to the configuration
def get_config(key: str, default: Any = None) -> Any:
    """
    Get a configuration value.

    Args:
        key: Configuration key
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    return Configuration.get_instance().get(key, default)


def set_config(key: str, value: Any) -> None:
    """
    Set a configuration value.

    Args:
        key: Configuration key
        value: Configuration value
    """
    Configuration.get_instance().set(key, value)


def get_all_config() -> Dict[str, Any]:
    """
    Get all configuration values.

    Returns:
        Dictionary of all configuration values
    """
    return Configuration.get_instance().as_dict()
