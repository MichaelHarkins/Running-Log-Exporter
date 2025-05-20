"""Orchestrates the workout export process, including scraping, file writing, and state management."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from runninglog.utils.console import get_console
from runninglog.utils.error_handler import with_async_error_handling
from runninglog.utils.http_client import HttpClientFactory, RateLimiter

from .export import write_json_workout
from .scrape import scrape_all_wids_from_workout_list_pages, scrape_workout
from .state import ExportState
from .types import Workout, WorkoutSegment

logger = logging.getLogger(__name__)
console = get_console()  # Use singleton console


# (Removed audit_exports: TCX audit logic is obsolete in JSON-only workflow)


@with_async_error_handling(context="run_one_wid", show_traceback=True)
async def run_one_wid(
    wid: int, athlete_id: str, output_dir: Path, timezone: str = "UTC"
) -> Dict[str, Any]:
    """Scrape and export a single workout by WID as a JSON file."""
    client = HttpClientFactory.create_client(
        follow_redirects=True, timeout=60.0, max_keepalive=5, max_connections=10
    )
    try:
        workout = await scrape_workout(client, int(athlete_id), wid)
        if not workout or not workout.segments:
            return {"status": "empty", "wid": wid}
        output_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{workout.date.date().isoformat()}_wid{wid}.json"
        path = output_dir / fname
        write_json_workout(workout, path)
        return {"status": "ok", "wid": wid, "files": [str(path)]}
    except Exception as e:
        logger.error(f"Error processing WID {wid}: {e}", exc_info=True)
        return {"status": "error", "wid": wid, "error": str(e)}
    finally:
        await client.aclose()


@with_async_error_handling(context="run_full_export", show_traceback=True)
async def run_full_export(
    athlete_id: str,
    athlete_root_dir: Path,
    output_dir: Path,
    debug_dir: Path,
    state_dir: Path,
    state_file: Path,
    timezone: str = "UTC",
    progress_bar: Optional[Any] = None,
    console_for_messages: Optional[Any] = None,
    concurrency: int = 5,
) -> Dict[str, Any]:
    """
    Export all new workouts for an athlete.
    State file and output are managed in athlete-specific directories.
    """
    athlete_root_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / state_file

    # Load or initialize state
    state = ExportState.load(state_path)
    state.output_dir = str(output_dir)
    await state.save()

    # Discover WIDs
    limiter = RateLimiter(rate=3, per=1.0)
    client = HttpClientFactory.create_client(
        follow_redirects=True, timeout=60.0, max_keepalive=5, max_connections=10
    )
    try:
        discovered = await scrape_all_wids_from_workout_list_pages(
            client=client,
            athlete_id=athlete_id,
            rate_limiter=limiter,
            state=state,
            progress_bar=None,  # No progress bar
            console_for_messages=None,
            concurrency=concurrency,
        )
        await state.save()
    finally:
        await client.aclose()

    # Determine new WIDs
    pending = sorted(set(discovered) - state.done_wids, reverse=True)
    if not pending:
        return {"status": "empty", "message": "No new workouts to export."}

    # Export concurrently, print status every 10 exports
    sem = asyncio.Semaphore(concurrency)
    results = []

    async def worker(wid: int, idx: int):
        async with sem:
            result = await run_one_wid(wid, athlete_id, output_dir, timezone)
            if result.get("status") == "ok":
                await state.mark_done(wid)
            if idx % 10 == 0 or idx == len(pending):
                print(f"Exported {idx}/{len(pending)} workouts...")
            return result

    for idx, wid in enumerate(pending, 1):
        results.append(await worker(wid, idx))

    success = [r["wid"] for r in results if r.get("status") == "ok"]
    failed = [
        {"wid": r["wid"], "error": r.get("error")}
        for r in results
        if r.get("status") != "ok"
    ]
    await state.save()
    return {
        "status": "ok",
        "exported": success,
        "failed": failed,
        "total": len(pending),
    }
