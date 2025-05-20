"""Scraping logic for running-log.com, including workout details and WID lists."""

import asyncio
import datetime as dt
import logging
import re
from pathlib import Path
from typing import List, Optional, Set

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress

from runninglog.utils.config import get_config
from runninglog.utils.console import get_console
from runninglog.utils.error_handler import with_async_error_handling
from runninglog.utils.http_client import RateLimiter, fetch, get_with_rate_limit
from runninglog.utils.progress import ProgressReporter

from .constants import BASE, WO_URL
from .state import ExportState
from .types import Workout, WorkoutSegment
from .utils import _parse_time, gather_date_strings

logger = logging.getLogger(__name__)
console = get_console()  # Use singleton console

WID_RE = re.compile(r"/workouts/(\d+)(?:[?#&]|$)")


def extract_wids_from_soup(soup: BeautifulSoup) -> List[int]:
    links = (
        a["href"]
        for a in soup.select("table.content a[href*='/workouts/']")
        if not a.find_parents("div", class_="pagination")
    )
    wids = {
        int(m.group(1))
        for href in links
        if (m := WID_RE.search(href)) and "/new" not in href and "/edit" not in href
    }
    if not wids:
        logger.warning(
            "extract_wids_from_soup: No WIDs found on page. Check selector and HTML structure."
        )
    return sorted(wids)


def parse_workout_date(
    soup: BeautifulSoup, wid: int, effective_athlete_id_for_debug: Optional[int] = None
) -> dt.datetime:
    """
    Parses the workout date from the BeautifulSoup object of a workout page.
    Relies on a fixed 'Month DD, YYYY (TimeOfDay)' format.
    """
    candidate_date_strings = gather_date_strings(soup)
    if not candidate_date_strings or not candidate_date_strings[0]:
        err_msg = f"WID {wid}: Date string not found at the expected location."
        logger.error(err_msg)
        raise ValueError(err_msg)
    raw = candidate_date_strings[0].strip()
    normalized = " ".join(raw.split())
    pattern = r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s*(?P<year>\d{4})\s*\((?P<tod>Morning|Afternoon|Night)\)$"
    m = re.match(pattern, normalized)
    if not m:
        err_msg = f"WID {wid}: Date string '{raw}' did not match expected format."
        logger.error(err_msg)
        raise ValueError(err_msg)
    month, day, year, tod = (
        m.group("month"),
        int(m.group("day")),
        int(m.group("year")),
        m.group("tod").lower(),
    )
    try:
        month_num = dt.datetime.strptime(month, "%B").month
    except Exception as e:
        err_msg = f"WID {wid}: Invalid month '{month}': {e}"
        logger.error(err_msg)
        raise ValueError(err_msg)
    hour = {"morning": 8, "afternoon": 14, "night": 20}.get(tod, 12)
    from zoneinfo import ZoneInfo
    naive_dt = dt.datetime(year, month_num, day, hour, 0, 0)
    aware_dt = naive_dt.replace(tzinfo=ZoneInfo("America/New_York"))
    logger.debug(f"WID {wid}: Parsed '{raw}' to datetime {aware_dt.isoformat()}")
    return aware_dt


@with_async_error_handling(context="scrape_workout", show_traceback=True)
async def scrape_workout(
    client: httpx.AsyncClient,
    aid: int,
    wid: int,
    effective_athlete_id_for_debug: Optional[int] = None,
) -> Workout:
    url = WO_URL.format(wid=wid, aid=aid)
    logger.debug(f"Scraping workout WID: {wid}, URL: {url}")
    html = ""
    try:
        html = await fetch(client, url)
    except httpx.HTTPStatusError as e_http:
        console.print(
            f"[red]⚠️  HTTP error {e_http.response.status_code} for workout {wid} ({url}): {e_http}[/red]"
        )
        logger.error(
            f"Failed to fetch workout page WID {wid} URL {url} with HTTP status {e_http.response.status_code}: {e_http}",
            exc_info=True,
        )
        raise
    except httpx.RequestError as e_req:
        console.print(f"[red]⚠️  Request error for workout {wid} ({url}): {e_req}[/red]")
        logger.error(
            f"Request error for workout page WID {wid} URL {url}: {e_req}",
            exc_info=True,
        )
        raise
    try:
        soup = BeautifulSoup(html, "lxml")
        logger.debug(f"WID {wid}: BeautifulSoup parsing complete")

        # Date parsing is now strict and can raise ValueError
        date = parse_workout_date(
            soup,
            wid=wid,
            effective_athlete_id_for_debug=effective_athlete_id_for_debug,
        )

        logger.debug(
            f"WID {wid}: Date parsing complete ({date}), proceeding to exercise type/comments/table parsing"
        )
        # Extract all relevant fields into meta_fields
        meta_fields = {}
        # Comments, exercise_type, weather, title from <p> fields
        for p in soup.find_all("p"):
            txt = p.get_text().strip()
            if txt.startswith("Exercise Type:"):
                meta_fields["exercise_type"] = txt.split(":", 1)[1].strip()
            elif txt.startswith("Weather:"):
                meta_fields["weather"] = txt.split(":", 1)[1].strip()
            elif txt.startswith("Comments:"):
                meta_fields["comments"] = txt.split(":", 1)[1].strip()
        # Shoes from table
        shoes_found = set()
        table = soup.find("table", class_="content")
        if table:
            for row in table.find_all("tr")[1:]:
                if row.parent and row.parent.name == "tfoot":
                    continue
                cols = [c.get_text(strip=True) for c in row.find_all("td")]
                if len(cols) >= 5:
                    shoes_val = cols[4]
                    if shoes_val and shoes_val != "\xa0":
                        shoes_found.add(shoes_val)
        if shoes_found:
            meta_fields["shoes"] = ", ".join(sorted(shoes_found))
        # Title from <input id="workout_title">
        from bs4 import Tag

        title_input = None
        for inp in soup.find_all("input"):
            if isinstance(inp, Tag) and inp.get("id") == "workout_title":
                title_input = inp
                break
        if title_input and title_input.get("value"):
            meta_fields["title"] = title_input.get("value").strip()
        # If no title from input, get from <h3>
        if "title" not in meta_fields:
            h3 = soup.find("h3")
            if h3 and h3.get_text(strip=True):
                meta_fields["title"] = h3.get_text(strip=True)
        # Description from meta tag
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            meta_fields["description"] = meta_desc["content"].strip()

        # Always include date in meta_fields
        meta_fields["date"] = date

        # Parse segments (old logic, direct port)
        segments = []
        segments_yielded_count = 0
        yielded_any = False
        if not table:
            logger.debug(f"No workout found for WID {wid} ({url}).")
            comment = meta_fields.get("comments", "")
            if not comment:
                logger.warning(f"No workout or note found for WID {wid} ({url}).")
        else:
            logger.debug(
                f"WID {wid}: Entering segment table parsing, number of rows (excluding header): {len(table.find_all('tr'))-1}"
            )
            for idx, row in enumerate(table.find_all("tr")[1:], 1):
                logger.debug(f"WID {wid}: Parsing segment row {idx}")
                if row.parent and row.parent.name == "tfoot":
                    continue
                cols = [c.get_text(strip=True) for c in row.find_all("td")]
                if len(cols) < 2:
                    continue
                dist_txt, dur_txt = cols[0], cols[1]
                miles = 0.0
                if dist_txt:
                    try:
                        parts = dist_txt.split()
                        val = float(parts[0])
                        unit = parts[1].lower() if len(parts) > 1 else ""
                        if "meter" in unit:
                            miles = val / 1609.34
                        elif (
                            "kilometer" in unit
                            or "km" == unit
                            or "kms" == unit
                            or "kilometers" in unit
                        ):
                            miles = val / 1.60934
                        else:
                            miles = val
                    except (ValueError, IndexError):
                        miles = 0.0
                interval_type = ""
                if len(cols) > 3 and cols[3]:
                    interval_type = cols[3]
                secs = _parse_time(dur_txt) if dur_txt else 0
                if miles == 0 and secs == 0:
                    logger.debug(
                        f"WID {wid if wid else 'Unknown'}: Skipping segment because both miles and seconds are 0."
                    )
                    continue
                seg_meta_fields = dict(meta_fields)
                if interval_type:
                    seg_meta_fields["interval_type"] = interval_type
                segments.append(
                    WorkoutSegment(
                        distance_miles=miles,
                        duration_seconds=secs,
                        interval_type=seg_meta_fields.get("interval_type"),
                        shoes=seg_meta_fields.get("shoes"),
                        pace=None
                    )
                )
                segments_yielded_count += 1
                yielded_any = True
        if not yielded_any:
            logger.info(
                f"WID {wid}: No workout or note found or no segments. Logging as 0-mile run for export completeness."
            )
            segments = [
                WorkoutSegment(
                    distance_miles=0.0,
                    duration_seconds=0,
                    interval_type=meta_fields.get("interval_type"),
                    shoes=meta_fields.get("shoes"),
                    pace=None
                )
            ]
        workout = Workout(
            title=meta_fields.get("title"),
            date=meta_fields.get("date"),
            exercise_type=meta_fields.get("exercise_type"),
            weather=meta_fields.get("weather"),
            comments=meta_fields.get("comments"),
            total_distance_miles=sum(s.distance_miles for s in segments),
            total_duration_seconds=sum(s.duration_seconds or 0 for s in segments),
            segments=segments,
            exported_from="running-log"
        )
        return workout
    except Exception as e_parse:
        console.print(
            f"[red]⚠️  Error parsing segments for workout {wid} ({url}) (after date parsing): {e_parse}[/red]"
        )
        logger.error(
            f"Error parsing segments for WID {wid} ({url}), HTML was fetched, date was parsed. Error: {e_parse}",
            exc_info=True,
        )
        raise  # Re-raise so the decorator can handle it


# --- Refactored scrape_all_wids_from_workout_list_pages ---
async def scrape_all_wids_from_workout_list_pages(
    client: httpx.AsyncClient,
    athlete_id: str,
    rate_limiter: RateLimiter,
    state: ExportState,
    progress_bar: Optional[Progress] = None,
    console_for_messages: Optional[Console] = None,
    concurrency: int = 5,
) -> Set[int]:
    _wids_found_this_session_for_progress = set()
    url = f"{BASE}/workouts?athleteid={athlete_id}&page=1"
    max_page_num = None

    # Create a progress reporter
    progress_reporter = ProgressReporter(
        progress_bar=progress_bar,
        console=console_for_messages or console,
        description=f"[cyan]Discovering WIDs (Athlete {athlete_id})",
        total=0,  # Will be updated once we know the total
    )

    try:
        # Get first page outside the page loop to determine total pagination
        logger.info(f"Fetching first page to determine pagination: {url}")
        html_content = await get_with_rate_limit(client, url, rate_limiter)
        soup = BeautifulSoup(html_content, "html.parser")
        pagination_divs = soup.find_all("div", class_="pagination")
        page_nums = []
        for div in pagination_divs:
            for a in div.find_all("a", href=True):
                m = re.search(r"page=(\d+)", a["href"])
                if m:
                    page_nums.append(int(m.group(1)))
        if page_nums:
            max_page_num = max(page_nums)
            logger.info(f"Detected total number of workout pages: {max_page_num}")
        else:
            logger.error(
                "Could not determine total number of workout pages from pagination controls."
            )
            raise RuntimeError(
                "Failed to detect total number of workout pages from the first page."
            )
    except Exception as e:
        logger.error(f"Failed to fetch or parse first workout page for pagination: {e}")
        raise RuntimeError(
            f"Failed to fetch or parse first workout page for pagination: {e}"
        )

    if not hasattr(state, "discovered_pages"):
        state.discovered_pages = set()
    expected_pages = set(range(1, max_page_num + 1))

    if not hasattr(state, "processed_workout_list_pages"):
        state.processed_workout_list_pages = set()

    already_processed_pages = state.discovered_pages.union(
        state.processed_workout_list_pages
    )

    missing_pages = sorted(expected_pages - already_processed_pages)
    logger.info(
        f"Total workout pages detected: {max_page_num}. Pages missing from state: {missing_pages}"
    )

    pages_to_fetch = missing_pages
    pages_to_fetch_total = len(pages_to_fetch)

    # Update progress reporter with total
    progress_reporter.total = pages_to_fetch_total

    # Print the list of pages we'll actually fetch (or first 20 if many)
    if pages_to_fetch:
        pages_preview = str(pages_to_fetch[:20]) + (
            "..." if len(pages_to_fetch) > 20 else ""
        )
        logger.info(f"Will fetch {len(pages_to_fetch)} pages: {pages_preview}")
    else:
        logger.info("No new pages to fetch - all workout list pages already processed")

    if pages_to_fetch_total > 0:
        progress_reporter.print(
            f"Beginning discovery of {pages_to_fetch_total} pages for athlete {athlete_id}..."
        )

    MAX_PAGES_TO_SCRAPE_SESSION = get_config("max_pages_to_scrape_session", 1000)
    pages_scraped_this_call = 0

    # Use a faster rate limiter for page processing (page discovery is not as sensitive)
    page_rate_limit_rate = 10
    page_rate_limit_per = 1.0
    page_rate_limiter = RateLimiter(rate=page_rate_limit_rate, per=page_rate_limit_per)
    logger.info(
        f"Using faster rate limiting ({page_rate_limit_rate} requests per {page_rate_limit_per} seconds) for page discovery"
    )

    semaphore = asyncio.Semaphore(concurrency)
    progress_lock = asyncio.Lock()

    async def fetch_and_process_page(page_num):
        nonlocal pages_scraped_this_call
        async with semaphore:
            if pages_scraped_this_call >= MAX_PAGES_TO_SCRAPE_SESSION:
                return  # Respect session limit

            url = f"{BASE}/workouts?athleteid={athlete_id}&page={page_num}"
            logger.debug(f"Fetching WID list page: {url}")

            # Use a more conservative rate limiter for page discovery
            wids_on_this_page_count = 0
            html_content_for_debug = ""

            try:
                # Wait for the conservative rate limiter
                await page_rate_limiter.acquire()
                logger.debug(f"Rate limiter approved request for page {page_num}")
                html_content = await get_with_rate_limit(client, url, rate_limiter)
                html_content_for_debug = html_content
                soup = BeautifulSoup(html_content, "html.parser")

                wids_on_this_page = extract_wids_from_soup(soup)
                for wid in wids_on_this_page:
                    if wid not in state.discovered_wids:
                        state.discovered_wids.add(wid)
                        _wids_found_this_session_for_progress.add(wid)
                        wids_on_this_page_count += 1
                logger.debug(
                    f"Found {wids_on_this_page_count} new unique WIDs on page {page_num} (added to state.discovered_wids)."
                )

                if pages_scraped_this_call == 0 and wids_on_this_page_count == 0:
                    # Always use debug_dir from state.output_dir
                    athlete_debug_dir = Path(getattr(state, "output_dir", "debug"))
                    athlete_debug_dir.mkdir(parents=True, exist_ok=True)
                    debug_html_filename = (
                        athlete_debug_dir
                        / f"debug_athlete_{athlete_id}_page_{page_num}_content.html"
                    )
                    try:
                        with open(
                            debug_html_filename, "w", encoding="utf-8"
                        ) as f_debug:
                            f_debug.write(html_content_for_debug)
                        logger.info(
                            f"Debug: HTML content of page {page_num} (athlete {athlete_id}), which yielded no WIDs on first page processed this run, saved to '{debug_html_filename}'."
                        )
                    except Exception as e_save:
                        logger.error(
                            f"Failed to save debug HTML for page {page_num}: {e_save}"
                        )

                state.discovered_pages.add(page_num)
                if not hasattr(state, "processed_workout_list_pages"):
                    state.processed_workout_list_pages = set()
                state.processed_workout_list_pages.add(page_num)
                await state.save()  # Save state after processing page data
                logger.debug(
                    f"Page {page_num} processed for WID discovery. State saved."
                )

                async with progress_lock:
                    pages_scraped_this_call += 1
                    # Update progress using the progress reporter
                    percent = (
                        (pages_scraped_this_call / pages_to_fetch_total) * 100
                        if pages_to_fetch_total > 0
                        else 0
                    )
                    fun_msgs = [
                        "[magenta]Keep going![/magenta]",
                        "[green]You're crushing it![/green]",
                        "[yellow]Almost there![/yellow]",
                        "[cyan]Data is flying![/cyan]",
                        "[bold blue]Exporting like a pro![/bold blue]",
                    ]
                    fun_msg = fun_msgs[pages_scraped_this_call % len(fun_msgs)]
                    # Update progress reporter
                    progress_reporter.update(
                        advance=1,
                        description=f"[cyan]Discovering WIDs:[/cyan] {fun_msg} ({pages_scraped_this_call}/{pages_to_fetch_total}) [{percent:.1f}%]",
                    )

            except httpx.HTTPStatusError as e_http:
                if e_http.response.status_code == 404 and page_num > 1:
                    logger.info(
                        f"Received 404 for WID list page {url}. Assuming end of workout list."
                    )
                    # Mark task as complete
                    progress_reporter.update(
                        current=pages_to_fetch_total,
                        description="[yellow]Reached end of pages (404).[/yellow]",
                    )
                    return
                logger.error(
                    f"HTTP error fetching WID list page {url}: {e_http}. Stopping WID discovery for this run."
                )
                progress_reporter.update(
                    description="[red]HTTP Error during discovery.[/red]"
                )
                return  # Stop further processing for this page type on HTTP error
            except Exception as e_gen:
                logger.error(
                    f"Unexpected error processing WID list page {url}: {e_gen}. Stopping WID discovery for this run.",
                    exc_info=True,
                )
                progress_reporter.update(
                    description="[red]Unexpected Error during discovery.[/red]"
                )
                return  # Stop further processing for this page type on general error

    if pages_to_fetch_total > 0:  # Only run tasks if there are pages to fetch
        tasks = [fetch_and_process_page(page_num) for page_num in pages_to_fetch]
        await asyncio.gather(*tasks)
    else:
        logger.info("No new pages to fetch for WID discovery.")

    if (
        pages_scraped_this_call >= MAX_PAGES_TO_SCRAPE_SESSION
        and pages_to_fetch_total > MAX_PAGES_TO_SCRAPE_SESSION
    ):
        msg = f"[yellow]WID discovery paused after {MAX_PAGES_TO_SCRAPE_SESSION} pages. Run script again to resume.[/yellow]"
        progress_reporter.log_warning(msg)
        logger.warning(
            f"WID discovery stopped this call after reaching MAX_PAGES_TO_SCRAPE_SESSION ({MAX_PAGES_TO_SCRAPE_SESSION}). Run again to continue."
        )

    # Update progress reporter with final status
    if pages_to_fetch_total > 0:
        # If all pages_to_fetch_total were processed or session limit not hit making it seem complete for this run
        if (
            pages_scraped_this_call == pages_to_fetch_total
            or pages_scraped_this_call < MAX_PAGES_TO_SCRAPE_SESSION
        ):
            final_desc = f"[green]WID Discovery: {len(_wids_found_this_session_for_progress)} new. Total: {len(state.discovered_wids)}. Pages: {len(state.processed_workout_list_pages)}/{max_page_num if max_page_num else '?'}"
            if (
                not _wids_found_this_session_for_progress
                and pages_scraped_this_call > 0
            ):
                final_desc = f"[green]WID Discovery: No new WIDs in {pages_scraped_this_call} page(s). Total: {len(state.discovered_wids)}. Pages: {len(state.processed_workout_list_pages)}/{max_page_num if max_page_num else '?'}"
            progress_reporter.complete(description=final_desc)

    logger.info(
        f"Finished WID discovery for this call. Total WIDs in state.discovered_wids: {len(state.discovered_wids)}. Total pages processed according to state: {len(state.processed_workout_list_pages)}."
    )
    return state.discovered_wids
