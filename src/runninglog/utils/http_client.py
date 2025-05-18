"""HTTP client factory with standard configurations."""

import asyncio
import logging
import time
from typing import Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from runninglog.core.constants import _HEADER
from runninglog.utils.console import get_console
from runninglog.utils.error_handler import handle_http_error

logger = logging.getLogger(__name__)
console = get_console()


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, rate: int, per: float):
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            time_passed = now - self.last_update
            self.tokens = min(
                self.rate, self.tokens + time_passed * (self.rate / self.per)
            )
            self.last_update = now

            if self.tokens < 1:
                await asyncio.sleep((1 - self.tokens) * (self.per / self.rate))
                self.tokens = 1
            self.tokens -= 1


# ---------------------------------------------------------------------------
# HTTP Client Factory
# ---------------------------------------------------------------------------
class HttpClientFactory:
    """Factory for creating properly configured HTTP clients."""

    DEFAULT_TIMEOUT = 60.0
    DEFAULT_MAX_KEEPALIVE = 5
    DEFAULT_MAX_CONNECTIONS = 10
    DEFAULT_HEADERS = _HEADER

    @staticmethod
    def create_client(
        timeout: float = DEFAULT_TIMEOUT,
        max_keepalive: int = DEFAULT_MAX_KEEPALIVE,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        headers: Optional[Dict[str, str]] = None,
        follow_redirects: bool = True,
    ) -> httpx.AsyncClient:
        """
        Create a new HTTP client with standard configuration.

        Args:
            timeout: Request timeout in seconds
            max_keepalive: Maximum keepalive connections
            max_connections: Maximum connections
            headers: Custom headers (defaults to standard headers)
            follow_redirects: Whether to follow redirects

        Returns:
            Configured httpx.AsyncClient
        """
        return httpx.AsyncClient(
            follow_redirects=follow_redirects,
            timeout=timeout,
            limits=httpx.Limits(
                max_keepalive_connections=max_keepalive, max_connections=max_connections
            ),
            headers=headers or HttpClientFactory.DEFAULT_HEADERS,
        )


# ---------------------------------------------------------------------------
# Fetch Helper with Retry Logic
# ---------------------------------------------------------------------------
def _should_retry_fetch(exc: BaseException) -> bool:
    """Determines if an exception should trigger a retry."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code

        if status in [401, 403]:
            handle_http_error(exc, "_fetch")
            return False

        if status == 429 or status >= 500:
            logger.debug(f"RETRYING: {exc}, backing off before retry.")
            return True

        handle_http_error(exc, "_fetch")
        return False

    if isinstance(exc, (httpx.HTTPError, httpx.ReadTimeout)):
        logger.debug(
            f"RETRYING: Error {type(exc).__name__}: {exc}, backing off before retry."
        )
        return True

    logger.warning(
        f"NOT RETRYING: {type(exc).__name__}: {exc} (non-retriable error type)"
    )
    return False


def _log_final_retry_error(retry_state):
    """Log the final error after all retries have been exhausted."""
    exc = retry_state.outcome.exception()
    url = (
        getattr(retry_state.args[1], "url", None) if len(retry_state.args) > 1 else None
    )
    logger.warning(
        f"FAILED after all retries: {type(exc).__name__}: {exc} on {url if url else 'unknown URL'}"
    )


@retry(
    retry=retry_if_exception(_should_retry_fetch),
    stop=stop_after_attempt(10),  # Retry up to 10 times
    wait=wait_exponential(multiplier=1, min=15, max=60)
    + wait_random(0, 5),  # Start at 15s, up to 60s with randomness
    reraise=True,
    retry_error_callback=_log_final_retry_error,
)
async def fetch(
    client: httpx.AsyncClient, url: str, headers: Optional[Dict[str, str]] = None
) -> str:
    """
    Fetch a URL with retry logic.

    Args:
        client: The HTTP client to use
        url: The URL to fetch
        headers: Optional headers to use (falls back to client headers)

    Returns:
        The response text
    """
    logger.debug(f"Fetching {url}")
    start_time = time.monotonic()
    resp = await client.get(url, headers=headers, timeout=30)
    duration = time.monotonic() - start_time
    logger.debug(
        f"Fetch complete in {duration:.1f}s - Status: {resp.status_code} for {url}"
    )

    if "/athlete/login" in str(resp.url).lower() and not str(resp.url).lower().endswith(
        url.lower().split("?")[0].lower()
    ):
        logger.error(
            f"_fetch: Redirected to login page ({resp.url}) when fetching {url}. Raising as auth error."
        )
        mock_response_for_auth_redirect = httpx.Response(
            401, request=resp.request, content=b"Redirected to login"
        )
        raise httpx.HTTPStatusError(
            message="Redirected to login page, treated as auth failure.",
            request=resp.request,
            response=mock_response_for_auth_redirect,
        )

    # Check for too many redirects or unexpected redirects
    if resp.url != url and str(resp.url) != url:
        logger.warning(f"Redirected from {url} to {resp.url}")

    resp.raise_for_status()

    return resp.text


async def get_with_rate_limit(
    client: httpx.AsyncClient, url: str, rate_limiter: Optional[RateLimiter] = None
) -> str:
    """
    Get a URL with rate limiting.

    Args:
        client: The HTTP client to use
        url: The URL to fetch
        rate_limiter: Optional rate limiter (if None, no rate limiting is applied)

    Returns:
        The response text
    """
    if rate_limiter:
        await rate_limiter.acquire()
    return await fetch(client, url)
