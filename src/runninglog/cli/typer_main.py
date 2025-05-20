"""Typer-based CLI for the runninglog exporter application."""

import asyncio
import json
import re
import time
from pathlib import Path

import httpx
import typer
from rich.progress import Progress

from runninglog.core.export import write_journal_file
from runninglog.core.types import Workout
from runninglog.core.orchestrator import run_full_export
from runninglog.core.state import ExportState
from runninglog.utils.config import get_config
from runninglog.utils.console import get_console
from runninglog.utils.http_client import HttpClientFactory, get_with_rate_limit
from runninglog.utils.logging import configure_logging, get_logger

app = typer.Typer(help="RunningLog CLI Toolkit (Typer version)")
console = get_console()
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def main_setup(
    ctx: typer.Context,
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging (sets log level to DEBUG). Overrides --log-level.",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
        case_sensitive=False,
    ),
):
    """Global setup: configures logging for all commands."""
    if ctx.invoked_subcommand is None:
        pass

    configure_logging(
        level=log_level,
        debug=debug,
        console=console,
        show_path=False,
        rich_tracebacks=True,
        silence_libs=True,
    )


@app.command()
def export(
    athlete_id: str = typer.Option(..., help="Athlete ID to export"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force: clear athlete-specific export directory and effectively reset their state.",
    ),
    concurrency: int = typer.Option(
        5, "--concurrency", help="Number of concurrent workout exports (default: 5)"
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Custom output directory for TCX files (required)",
    ),
    refresh_all: bool = typer.Option(
        False, "--refresh-all", help="Reset all processed WIDs before export."
    ),
    refresh_wids: str = typer.Option(
        "",
        "--refresh-wids",
        help="Reset only the specified WIDs (comma-separated, e.g. --refresh-wids 12345,67890).",
    ),
):
    """
    Export all workouts for an athlete.
    Output and state are stored in a subdirectory named after the athlete, under the workspace root.
    If --force is used, the athlete's specific directory and its state are cleared before export.
    """
    if refresh_wids.strip() == "":
        refresh_wids_list = []
    else:
        refresh_wids_list = [
            int(w.strip()) for w in refresh_wids.split(",") if w.strip().isdigit()
        ]

    athlete_name = f"athlete{athlete_id}"
    db_path = Path("athlete_id_name_db.json")
    athlete_id_name_db = {}
    if db_path.exists():
        try:
            with open(db_path, "r") as f:
                athlete_id_name_db = json.load(f)
            if str(athlete_id) in athlete_id_name_db:
                athlete_name = athlete_id_name_db[str(athlete_id)]
        except Exception as e:
            logger.warning(f"Could not load athlete_id_name_db.json: {e}")

    if athlete_name == f"athlete{athlete_id}":
        url = f"http://running-log.com/workouts?athleteid={athlete_id}&page=1"
        for attempt in range(10):
            try:
                client = HttpClientFactory.create_client(timeout=10)

                async def fetch_athlete_name():
                    resp = await get_with_rate_limit(client, url)
                    match = re.search(r"Workouts \((.*?)\)", resp)
                    if match:
                        return match.group(1).strip().replace(" ", "_")
                    return None

                athlete_name_result = asyncio.run(fetch_athlete_name())
                if athlete_name_result:
                    athlete_name = athlete_name_result
                    athlete_id_name_db[str(athlete_id)] = athlete_name
                    try:
                        with open(db_path, "w") as f:
                            json.dump(athlete_id_name_db, f)
                    except Exception as e:
                        logger.warning(
                            f"Could not write to athlete_id_name_db.json: {e}"
                        )
                    break
            except httpx.RequestError as e:
                wait_time = min(10 * (attempt + 1), 60)
                logger.warning(
                    f"Attempt {attempt+1}/10: Could not parse athlete name (request error: {e}), retrying in {wait_time}s..."
                )
                if attempt < 9:
                    time.sleep(wait_time)
            except Exception as e:
                wait_time = min(10 * (attempt + 1), 60)
                logger.warning(
                    f"Attempt {attempt+1}/10: Could not parse athlete name (error: {e}), retrying in {wait_time}s..."
                )
                if attempt < 9:
                    time.sleep(wait_time)
            if athlete_name != f"athlete{athlete_id}":
                break
        else:
            logger.warning(
                f"Could not parse athlete name from page after retries, using default '{athlete_name}'."
            )

    output_dir = output_dir.expanduser()
    athlete_specific_dir = output_dir / athlete_name
    output_subdir = athlete_specific_dir / "output"
    debug_subdir = athlete_specific_dir / "debug"
    state_subdir = athlete_specific_dir / "state"
    output_subdir.mkdir(parents=True, exist_ok=True)
    debug_subdir.mkdir(parents=True, exist_ok=True)
    state_subdir.mkdir(parents=True, exist_ok=True)

    state_file = Path(get_config("default_state_file", "runninglog_state.json"))
    timezone = get_config("default_timezone", "UTC")

    if force:
        state_path = state_subdir / state_file
        logger.info(
            "[yellow]--force specified: Deleting state file '%s' and all TCX files in %s before export.[/yellow]",
            state_path,
            output_subdir,
        )
        json_files = list(output_subdir.glob("*.json"))
        for f in json_files:
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Could not delete JSON file {f}: {e}")
        if state_path.exists():
            state_path.unlink()
        else:
            logger.info(
                "[yellow]State file '%s' not found; nothing to delete.[/yellow]",
                state_path,
            )

    if refresh_all or refresh_wids_list:
        state_path = state_subdir / state_file
        if state_path.exists():
            state_to_update = ExportState.load(state_path)
            if len(refresh_wids_list) > 0:
                for wid in refresh_wids_list:
                    if (
                        hasattr(state_to_update, "done_wids")
                        and wid in state_to_update.done_wids
                    ):
                        state_to_update.done_wids.remove(wid)
                        logger.info(f"Removed WID {wid} from state file.")
                    json_files = list(output_subdir.glob(f"*wid{wid}.json"))
                    for f in json_files:
                        try:
                            f.unlink()
                            logger.info(f"Deleted JSON file for WID {wid}: {f}")
                        except Exception as e:
                            logger.warning(f"Could not delete JSON file {f}: {e}")
                logger.info(
                    "[cyan]--refresh-wids specified: Reset WIDs %s in %s and deleted their TCX files in %s before export.[/cyan]",
                    refresh_wids_list,
                    state_path,
                    output_subdir,
                )
            else:
                state_to_update.done_wids.clear()
                json_files = list(output_subdir.glob("*.json"))
                for f in json_files:
                    try:
                        f.unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete JSON file {f}: {e}")
                logger.info(
                    "[cyan]--refresh-all specified: Reset all processed WIDs in %s and deleted all TCX files in %s before export.[/cyan]",
                    state_path,
                    output_subdir,
                )
            asyncio.run(state_to_update.save())
        else:
            logger.info(
                "[cyan]--refresh specified, but state file %s does not exist yet (will be created during export).[/cyan]",
                state_path,
            )

    async def _run():
        console.print(
            "[bold cyan]═════════════════════════════════════════[/bold cyan]"
        )
        console.print("[bold cyan]     STARTING RUNNING LOG EXPORT[/bold cyan]")
        console.print(
            "[bold cyan]═════════════════════════════════════════[/bold cyan]"
        )
        console.file.flush()
        with Progress(
            console=console,
            expand=True,
            refresh_per_second=2,
            speed_estimate_period=30.0,
            disable=False,
        ) as progress:
            console.print(
                f"[yellow]Will export data for athlete ID: {athlete_id}[/yellow]"
            )
            console.print("[yellow]Starting export process now...[/yellow]")
            console.file.flush()
            print("")
            console.file.flush()
            result = await run_full_export(
                athlete_id=athlete_id,
                athlete_root_dir=athlete_specific_dir,
                output_dir=output_subdir,
                debug_dir=debug_subdir,
                state_dir=state_subdir,
                state_file=state_file,
                timezone=timezone,
                progress_bar=progress,
                console_for_messages=console,
                concurrency=concurrency,
            )
        console.print(
            "[bold green]════════════════════════════════════════[/bold green]"
        )
        console.print("[bold green]✓ Export process complete![/bold green]")
        console.print(
            "[bold green]════════════════════════════════════════[/bold green]"
        )
        console.file.flush()
        if result["status"] == "ok":
            console.print(
                f"[bold green]Successfully exported {len(result['exported'])} workouts.[/bold green]"
            )
            if result["failed"]:
                console.print(
                    f"[bold red]Failed to export {len(result['failed'])} workouts:[/bold red]"
                )
                for fail in result["failed"]:
                    console.print(
                        f"[red]  WID {fail['wid']}: {fail.get('error')}[/red]"
                    )
        elif result["status"] == "empty":
            console.print(
                f"[bold yellow]{result.get('message', 'No new workouts to export.')}[/bold yellow]"
            )
        else:
            console.print(f"[bold red]Export failed: {result}[/bold red]")

    asyncio.run(_run())


@app.command()
def create_journal(
    athlete_id: str = typer.Option(
        ..., "--athlete-id", help="Athlete ID to create journal for (required)"
    ),
    out_file: Path = typer.Option(
        None,
        "--out-file",
        help="Output Markdown journal file (defaults to journal/journal.md)",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Custom output directory for TCX files (required)",
    ),
    timezone: str = typer.Option("UTC", help="Timezone for parsing TCX files"),
):
    """
    Create a Markdown workout journal from TCX files in the athlete's output directory.
    """
    Path(__file__).resolve().parent.parent.parent.parent
    db_path = Path("athlete_id_name_db.json")
    athlete_id_name_db = {}
    athlete_name = None
    if db_path.exists():
        try:
            with open(db_path, "r") as f:
                athlete_id_name_db = json.load(f)
            if str(athlete_id) in athlete_id_name_db:
                athlete_name = athlete_id_name_db[str(athlete_id)]
        except Exception as e:
            logger.warning(f"Could not load athlete_id_name_db.json: {e}")
    if not athlete_name:
        athlete_name = f"athlete{athlete_id}"
    output_dir = output_dir.expanduser()
    athlete_specific_dir = output_dir / athlete_name
    output_subdir = athlete_specific_dir / "output"
    journal_dir = athlete_specific_dir / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)

    tcx_dir = output_subdir

    if out_file is not None:
        out_file = Path(out_file).expanduser()
        if not out_file.is_absolute():
            out_file = journal_dir / out_file
    else:
        out_file = journal_dir / "journal.md"

    json_files = sorted(tcx_dir.glob("*.json"))
    if not json_files:
        logger.info(
            f"[yellow]No JSON files found in the directory {tcx_dir} for journal creation.[/yellow]"
        )
        return
    workouts = []
    for json_file in json_files:
        try:
            workout = Workout.parse_file(json_file)
            workouts.append(workout)
        except Exception as e:
            logger.warning(f"Could not parse JSON workout file {json_file}: {e}")
    if not workouts:
        logger.info(
            f"[yellow]No valid workouts found in {tcx_dir} to create journal.[/yellow]"
        )
        return

    async def _run():
        await write_journal_file(workouts, out_file)
        logger.info(
            f"[green]Journal written to {out_file} ({len(workouts)} workouts).[/green]"
        )

    asyncio.run(_run())


if __name__ == "__main__":
    app()
