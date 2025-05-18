"""Standardized logging configuration for the application."""

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from runninglog.utils.console import get_console


def configure_logging(
    level: str = "INFO",
    debug: bool = False,
    console: Optional[Console] = None,
    show_path: bool = False,
    rich_tracebacks: bool = True,
    silence_libs: bool = True,
    log_format: str = "%(message)s",
    date_format: str = "[%X]",
) -> None:
    """
    Configure logging with standardized settings.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        debug: Whether to enable debug mode (overrides level)
        console: Rich console to use (falls back to singleton)
        show_path: Whether to show file paths in logs
        rich_tracebacks: Whether to use rich tracebacks
        silence_libs: Whether to silence common libraries
        log_format: Log format string
        date_format: Date format string
    """
    # Determine log level
    chosen_level_str = "DEBUG" if debug else level.upper()
    chosen_level_int = getattr(logging, chosen_level_str, logging.INFO)

    # Get console instance
    console_instance = console or get_console()

    # Remove any existing handlers from the root logger to avoid duplicate messages
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Basic configuration
    logging.basicConfig(
        level=chosen_level_int,
        format=log_format,
        datefmt=date_format,
        handlers=[
            RichHandler(
                console=console_instance,
                show_path=show_path,
                rich_tracebacks=rich_tracebacks,
                markup=True,
                log_time_format=date_format,
            )
        ],
    )

    # Silence common libraries if requested
    if silence_libs:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    This ensures all loggers are created in a standardized way.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
