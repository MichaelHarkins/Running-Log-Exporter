"""Error handling utilities for standardized error handling."""

import logging
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Optional, Type, TypeVar, Union

import httpx

from runninglog.utils.console import get_console

# Create type variables for function typing
F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")

logger = logging.getLogger(__name__)
console = get_console()


class ErrorHandlingConfig:
    """Configuration for error handling."""

    LOG_HTTP_ERRORS = True
    LOG_NETWORK_ERRORS = True
    LOG_GENERAL_ERRORS = True
    PRINT_TO_CONSOLE = True
    RAISE_ERRORS = True  # Whether to re-raise errors after handling


def handle_http_error(e: httpx.HTTPStatusError, context: str = "") -> None:
    """
    Standard handling for HTTP errors.

    Args:
        e: The HTTP status error
        context: Additional context about where the error occurred
    """
    status = e.response.status_code
    url = e.request.url
    error_type = (
        "Server error"
        if status >= 500
        else "Client error" if status >= 400 else "HTTP error"
    )
    error_msg = f"{error_type} {status} on {url}"

    if context:
        error_msg = f"{context}: {error_msg}"

    if ErrorHandlingConfig.LOG_HTTP_ERRORS:
        if status >= 500 or status == 429:
            logger.warning(error_msg)
        elif status in (401, 403):
            logger.error(f"{error_msg} - Authentication error")
        else:
            logger.error(error_msg)

    if ErrorHandlingConfig.PRINT_TO_CONSOLE:
        console.print(f"[red]⚠️  {error_msg}[/red]")


def handle_network_error(e: httpx.RequestError, context: str = "") -> None:
    """
    Standard handling for network errors.

    Args:
        e: The network error
        context: Additional context about where the error occurred
    """
    error_msg = f"Network error: {type(e).__name__}: {e}"

    if context:
        error_msg = f"{context}: {error_msg}"

    if ErrorHandlingConfig.LOG_NETWORK_ERRORS:
        logger.warning(error_msg)

    if ErrorHandlingConfig.PRINT_TO_CONSOLE:
        console.print(f"[yellow]⚠️  {error_msg}[/yellow]")


def handle_general_error(
    e: Exception, context: str = "", show_traceback: bool = True
) -> None:
    """
    Standard handling for general errors.

    Args:
        e: The exception
        context: Additional context about where the error occurred
        show_traceback: Whether to include the traceback in the log
    """
    error_msg = f"Error: {type(e).__name__}: {e}"

    if context:
        error_msg = f"{context}: {error_msg}"

    if ErrorHandlingConfig.LOG_GENERAL_ERRORS:
        if show_traceback:
            logger.error(error_msg, exc_info=True)
        else:
            logger.error(error_msg)

    if ErrorHandlingConfig.PRINT_TO_CONSOLE:
        console.print(f"[red]⚠️  {error_msg}[/red]")


def with_error_handling(
    context: str = "",
    catch_exceptions: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
    show_traceback: bool = True,
    raise_error: Optional[bool] = None,
) -> Callable[[F], F]:
    """
    Decorator for standardized error handling.

    Args:
        context: Context description for error messages
        catch_exceptions: Exception type(s) to catch
        show_traceback: Whether to include traceback in logs
        raise_error: Whether to re-raise errors (overrides global setting)

    Returns:
        Decorated function with error handling
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                handle_http_error(e, context)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise
            except httpx.RequestError as e:
                handle_network_error(e, context)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise
            except catch_exceptions as e:
                handle_general_error(e, context, show_traceback)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise

        return wrapper  # type: ignore

    return decorator


def with_async_error_handling(
    context: str = "",
    catch_exceptions: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
    show_traceback: bool = True,
    raise_error: Optional[bool] = None,
) -> Callable[[F], F]:
    """
    Decorator for standardized error handling in async functions.

    Args:
        context: Context description for error messages
        catch_exceptions: Exception type(s) to catch
        show_traceback: Whether to include traceback in logs
        raise_error: Whether to re-raise errors (overrides global setting)

    Returns:
        Decorated async function with error handling
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                handle_http_error(e, context)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise
            except httpx.RequestError as e:
                handle_network_error(e, context)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise
            except catch_exceptions as e:
                handle_general_error(e, context, show_traceback)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise

        return wrapper  # type: ignore

    return decorator


def with_async_generator_error_handling(
    context: str = "",
    catch_exceptions: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception,
    show_traceback: bool = True,
    raise_error: Optional[bool] = None,
) -> Callable[[F], F]:
    """
    Decorator for standardized error handling in async generator functions.

    This specialized decorator properly handles async generators (functions that use
    'async def' with 'yield' inside) and preserves their iterator properties.

    Args:
        context: Context description for error messages
        catch_exceptions: Exception type(s) to catch
        show_traceback: Whether to include traceback in logs
        raise_error: Whether to re-raise errors (overrides global setting)

    Returns:
        Decorated async generator function with error handling
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
            try:
                async for item in func(*args, **kwargs):
                    yield item
            except httpx.HTTPStatusError as e:
                handle_http_error(e, context)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise
            except httpx.RequestError as e:
                handle_network_error(e, context)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise
            except catch_exceptions as e:
                handle_general_error(e, context, show_traceback)
                if raise_error or (
                    raise_error is None and ErrorHandlingConfig.RAISE_ERRORS
                ):
                    raise

        return wrapper  # type: ignore

    return decorator
