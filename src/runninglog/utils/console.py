"""Console service for centralized console management."""

from rich.console import Console

# Global singleton console instance
_console_instance = None


def get_console() -> Console:
    """
    Get the global console instance.

    Returns:
        Console: The global Rich console instance
    """
    global _console_instance
    if _console_instance is None:
        _console_instance = Console()
    return _console_instance
