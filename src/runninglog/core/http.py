"""HTTP utilities for fetching data, including rate limiting and retry logic."""

import asyncio
import logging
import time

import httpx
from rich.console import Console
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from runninglog.utils.http_client import fetch, get_with_rate_limit

from .constants import _HEADER

# Re-export the utilities from http_client for backward compatibility
__all__ = ["RateLimiter", "fetch", "get_with_rate_limit"]

logger = logging.getLogger(__name__)  # Use module-specific logger
console_http_utils = Console()  # Renamed to avoid conflict if imported elsewhere


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
# Network Fetching Helper with Retry
# ---------------------------------------------------------------------------
def _should_retry_fetch(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        url = exc.request.url
        error_type = (
            "Server error"
            if status >= 500
            else "Client error" if status >= 400 else "HTTP error"
        )

        if status in [401, 403]:
            logger.warning(f"{error_type} {status} on {url}")
            logger.warning(
                f"_fetch: Auth error {status}, not retrying at _fetch level."
            )
            return False

        if status == 429 or status >= 500:
            logger.debug(f"{error_type} {status} on {url} (will retry)")
            logger.debug(
                f"RETRYING: {error_type} {status} on {url}, backing off 15-60 seconds before retry."
            )
            return True

        # For other client errors (e.g., 404, 400), log as warning and do not retry
        logger.warning(f"{error_type} {status} on {url}")

    if isinstance(exc, (httpx.HTTPError, httpx.ReadTimeout)):
        logger.debug(
            f"RETRYING: Error {type(exc).__name__}: {exc}, backing off 15-60 seconds before retry."
        )
        return True

    logger.warning(
        f"NOT RETRYING: {type(exc).__name__}: {exc} (non-retriable error type)"
    )
    return False


def _log_final_retry_error(retry_state):
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
async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    logger.debug(f"Fetching {url}")
    start_time = time.monotonic()
    resp = await client.get(url, headers=_HEADER, timeout=30)
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
