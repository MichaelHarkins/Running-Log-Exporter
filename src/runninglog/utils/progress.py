"""Progress reporting utilities with fallback to basic logging."""

import logging
from typing import Any, Optional

from rich.console import Console
from rich.progress import Progress

from runninglog.utils.console import get_console

logger = logging.getLogger(__name__)


class ProgressReporter:
    """
    Progress reporting interface with fallbacks.

    This class provides a unified interface for progress reporting,
    using rich.progress when available but falling back to console
    or logging when needed.
    """

    def __init__(
        self,
        progress_bar: Optional[Progress] = None,
        console: Optional[Console] = None,
        description: str = "Progress",
        total: int = 100,
        disable_progress_bar: bool = False,
    ):
        """
        Initialize progress reporter.

        Args:
            progress_bar: Optional Rich Progress instance
            console: Optional Rich Console instance (falls back to singleton)
            description: Default description for the progress bar
            total: Total steps for the progress
            disable_progress_bar: Whether to disable the progress bar (use console/logging only)
        """
        self.progress_bar = progress_bar
        self.console = console or get_console()
        self.description = description
        self.total = total
        self.disable_progress_bar = disable_progress_bar
        self.task_id = None
        self._current = 0

        # Create a task if we have a progress bar and it's not disabled
        if self.progress_bar and not self.disable_progress_bar:
            self.task_id = self.progress_bar.add_task(
                description, total=total, visible=True
            )

    def update(
        self,
        advance: Optional[int] = None,
        current: Optional[int] = None,
        description: Optional[str] = None,
        refresh: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Update progress.

        Args:
            advance: Number of steps to advance (if None, current is used)
            current: Current progress value (if None, advance is used)
            description: New description (if None, use existing)
            refresh: Whether to refresh the display
            **kwargs: Additional kwargs passed to progress_bar.update
        """
        # Update internal state
        if current is not None:
            self._current = current
        elif advance is not None:
            self._current += advance

        # Use current description if none provided
        desc = description or self.description

        # Update progress bar if available
        if self.progress_bar and self.task_id and not self.disable_progress_bar:
            update_kwargs = {"refresh": refresh}
            if description:
                update_kwargs["description"] = description

            if current is not None:
                update_kwargs["completed"] = current
            elif advance is not None:
                update_kwargs["advance"] = advance

            # Add any additional kwargs
            update_kwargs.update(kwargs)

            # Update the progress bar
            self.progress_bar.update(self.task_id, **update_kwargs)

            # Force console refresh if specified
            if (
                refresh
                and hasattr(self.progress_bar, "console")
                and hasattr(self.progress_bar.console, "file")
            ):
                self.progress_bar.console.file.flush()
        # Fall back to console
        elif self.console and (
            current is not None or advance is not None or description is not None
        ):
            # Only show percent if we know the total
            percent = (
                f" [{self._current/self.total*100:.1f}%]" if self.total > 0 else ""
            )
            self.console.print(
                f"{desc}{percent} ({self._current}/{self.total if self.total > 0 else '?'})"
            )
        # Ultimate fallback to logging
        elif current is not None or advance is not None or description is not None:
            # Only show percent if we know the total
            percent = (
                f" [{self._current/self.total*100:.1f}%]" if self.total > 0 else ""
            )
            logger.info(
                f"{desc}{percent} ({self._current}/{self.total if self.total > 0 else '?'})"
            )

    def complete(self, description: Optional[str] = None) -> None:
        """
        Mark the progress as complete.

        Args:
            description: Final description for the completed progress
        """
        if self.progress_bar and self.task_id and not self.disable_progress_bar:
            self.progress_bar.update(
                self.task_id,
                completed=self.total,
                description=description or f"{self.description} - Complete",
            )
        elif self.console:
            self.console.print(
                f"{description or f'{self.description} - Complete'} (100%)"
            )
        else:
            logger.info(f"{description or f'{self.description} - Complete'} (100%)")

    def print(self, message: str) -> None:
        """
        Print a message in the context of this progress.

        Args:
            message: Message to print
        """
        if self.console:
            self.console.print(message)
        else:
            logger.info(message)

    def log_error(self, message: str) -> None:
        """
        Log an error message in the context of this progress.

        Args:
            message: Error message
        """
        if self.console:
            self.console.print(f"[red]{message}[/red]")
        else:
            logger.error(message)

    def log_warning(self, message: str) -> None:
        """
        Log a warning message in the context of this progress.

        Args:
            message: Warning message
        """
        if self.console:
            self.console.print(f"[yellow]{message}[/yellow]")
        else:
            logger.warning(message)
