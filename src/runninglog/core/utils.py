"""Core utility functions for the runninglog exporter."""

import logging
import re
from typing import Any, List

from bs4 import BeautifulSoup

from runninglog.utils.http_client import get_with_rate_limit

logger = logging.getLogger(__name__)

# Pre-compiled regex for better performance
DATE_PATTERN = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s*(?P<year>\d{4})\s*\((?P<tod>Morning|Afternoon|Night)\)$"
)


async def _get(client: Any, url: str, rate_limiter: Any) -> str:
    """
    Centralized HTTP fetch with rate limiting.

    Deprecated: Use get_with_rate_limit from http_client instead.
    """
    logger.warning("Deprecated: Use get_with_rate_limit from http_client instead")
    return await get_with_rate_limit(client, url, rate_limiter)


def _parse_time(txt: str) -> int:
    """Parses HH:MM:SS or MM:SS into seconds."""
    if not txt:
        return 0
    try:
        parts = list(map(int, txt.split(":")))
    except ValueError:
        return 0

    if len(parts) == 3:  # HH:MM:SS
        h, m, s = parts
    elif len(parts) == 2:  # MM:SS
        h = 0
        m, s = parts
    else:
        return 0
    return h * 3600 + m * 60 + s


def gather_date_strings(soup: BeautifulSoup) -> List[str]:
    """
    STRICT DATE EXTRACTION:
    Assumes the workout date will ALWAYS be found in the text of the first <p> tag
    that is an immediate sibling following the first <h3> tag on the page.
    This <h3> tag is assumed to be the workout title.
    No other locations or formats are checked. Returns a list with at most one string.
    """
    candidates = []
    # Find the first <h3> tag, assumed to be the workout title.
    main_h3_title = soup.find("h3")

    if main_h3_title:
        # Find the immediate next sibling <p> tag.
        next_p_tag = main_h3_title.find_next_sibling("p")
        if next_p_tag:
            date_text = next_p_tag.get_text(strip=True)
            if date_text:  # Ensure the text is not empty
                # CRITICAL ASSUMPTION: This <p> tag contains the date.
                # No further validation of content (e.g. "Exercise Type:") is done here.
                # Date parsing itself is handled by dateparser in the calling function.
                candidates.append(date_text)
                logger.debug(
                    f"Strict date extraction: Found candidate '{date_text}' from p after h3."
                )
            else:
                logger.warning(
                    "Strict date extraction: First <p> after <h3> was empty."
                )
        else:
            logger.warning(
                "Strict date extraction: No <p> tag found immediately after the first <h3>."
            )
    else:
        logger.warning("Strict date extraction: No <h3> tag found on the page.")

    if not candidates:
        logger.warning(
            "Strict date extraction: Did not find a date candidate based on the h3 -> p structure."
        )

    return candidates
