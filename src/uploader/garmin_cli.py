import os
import typer
import logging
from pathlib import Path
import asyncio
from .garmin_uploader import (
    create_manual_activity_from_json,
    initialize_garmin_client,
)
from .garmin_payload import workout_to_garmin_payloads

app = typer.Typer(help="Garmin Uploader CLI (Typer version)")

# Set up clean logging: default INFO, DEBUG only if --debug is set
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="[%X]"
)
logger = logging.getLogger("garmin_uploader")
# Suppress debug output from noisy libraries unless --debug is set
for noisy_logger in [
    "garminconnect", "urllib3", "requests", "garth", "requests_oauthlib", "oauthlib"
]:
    logging.getLogger(noisy_logger).setLevel(logging.INFO)
# Set garmin_uploader logger to WARNING unless --debug is set
logging.getLogger("garmin_uploader").setLevel(logging.WARNING)

def ensure_garth_token(token_dir="~/.garminconnect"):
    import garth
    from getpass import getpass
    token_dir = os.path.expanduser(token_dir)
    oauth1 = os.path.join(token_dir, "oauth1_token.json")
    oauth2 = os.path.join(token_dir, "oauth2_token.json")
    if not (os.path.exists(oauth1) and os.path.exists(oauth2)):
        print("No valid Garmin token found. Starting garth login...")
        email = input("Enter your Garmin Connect email: ")
        password = getpass("Enter your Garmin Connect password: ")
        garth.login(email, password)  # Will prompt for MFA if needed
        garth.save(token_dir)
        print("Garth session saved.")
    else:
        print("Found existing Garmin token, proceeding.")

@app.command()
def upload_json(
    input_path: str = typer.Argument(
        ...,
        help="Path to a JSON workout file, a comma-separated list of JSON files, or a directory containing JSON files."
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """
    Uploads workouts to Garmin Connect. Accepts:
    - A single JSON file (workout with segments)
    - A comma-separated list of JSON files
    - A directory (uploads all top-level .json files, skips subdirectories and non-json files)
    Each JSON file should be a workout (not a list); each segment is uploaded as a separate activity.
    """
    import json

    if debug or os.getenv("DEBUG", "").lower() in ["true", "1"]:
        logging.getLogger("garmin_uploader").setLevel(logging.DEBUG)
    else:
        logging.getLogger("garmin_uploader").setLevel(logging.INFO)

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        typer.echo("GARMIN_EMAIL and GARMIN_PASSWORD environment variables must be set.", err=True)
        raise typer.Exit(1)

    # Normalize all input types to a list of .json files (list logic)
    files_to_process = []
    # If input_path contains commas, treat as comma-separated list
    if "," in input_path:
        files_to_process = [Path(f.strip()) for f in input_path.split(",") if f.strip()]
    else:
        input_path_obj = Path(input_path)
        if input_path_obj.exists():
            if input_path_obj.is_dir():
                # Directory: all top-level .json files
                files_to_process = [
                    f for f in input_path_obj.iterdir()
                    if f.is_file() and f.suffix.lower() == ".json"
                ]
            elif input_path_obj.is_file() and input_path_obj.suffix.lower() == ".json":
                files_to_process = [input_path_obj]
            else:
                typer.echo(f"Input path is not a .json file or directory: {input_path}", err=True)
                raise typer.Exit(1)
        else:
            typer.echo(f"Input path does not exist: {input_path}", err=True)
            raise typer.Exit(1)
    # Validate all files
    files_to_process = [f for f in files_to_process if f.exists() and f.is_file() and f.suffix.lower() == ".json"]
    if not files_to_process:
        typer.echo("No valid JSON files to process.", err=True)
        raise typer.Exit(1)

    async def upload_all():
        login_successful = await initialize_garmin_client(email, password)
        if not login_successful:
            typer.echo("Exiting due to Garmin Connect login failure.", err=True)
            raise typer.Exit(1)

        # Gather all dates for deduplication range
        import re
        import datetime
        date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")
        all_dates = []
        for f in files_to_process:
            try:
                with f.open("r", encoding="utf-8") as wf:
                    workout = json.load(wf)
                # Try to extract date from workout
                date_str = ""
                if "date" in workout:
                    if isinstance(workout["date"], str):
                        date_str = workout["date"][:10]
                    elif isinstance(workout["date"], (datetime.date, datetime.datetime)):
                        date_str = str(workout["date"])[:10]
                if date_str:
                    all_dates.append(date_str)
            except Exception:
                continue
        if all_dates:
            start_date = min(all_dates)
            end_date = max(all_dates)
        else:
            start_date = "2000-01-01"
            end_date = datetime.date.today().isoformat()

        from garminconnect import Garmin
        def mfa_prompt():
            return input("Enter Garmin Connect MFA code: ")
        client = Garmin(email, password, prompt_mfa=mfa_prompt)
        client.login()
        existing_activities = client.get_activities_by_date(
            startdate=start_date,
            enddate=end_date
        )
        def activity_exists(date_str, name):
            # Normalize for comparison
            name_norm = (name or "").strip().lower()
            for act in existing_activities:
                act_date = (act.get("startTimeLocal", "") or "")[:10]
                act_name = (act.get("activityName", "") or "").strip().lower()
                if act_date == date_str and name_norm == act_name:
                    return True
            return False

        if debug:
            typer.echo(f"Deduplication: {len(existing_activities)} activities fetched for date range {start_date} to {end_date}")
            for act in existing_activities:
                act_date = (act.get("startTimeLocal", "") or "")[:10]
                act_name = (act.get("activityName", "") or "")
                typer.echo(f"  Existing: {act_date} - {act_name}")

        # Collect all payloads to upload (with deduplication)
        upload_tasks = []
        payload_to_file = []
        for f in files_to_process:
            try:
                with f.open("r", encoding="utf-8") as wf:
                    workout = json.load(wf)
            except Exception as e:
                typer.echo(f"Error loading JSON file {f}: {e}", err=True)
                continue

            payloads = workout_to_garmin_payloads(workout)
            if not payloads:
                typer.echo(f"No valid segments found in {f}, skipping.", err=True)
                continue

            for payload in payloads:
                date_str = payload["summaryDTO"]["startTimeLocal"][:10]
                name = payload["activityName"]
                if activity_exists(date_str, name):
                    typer.echo(f"Skipping duplicate activity for {date_str} with name '{name}' from file {f.name}")
                    continue
                upload_tasks.append(payload)
                payload_to_file.append((payload, f))

        # Parallelize uploads with a concurrency limit
        import asyncio
        concurrency = 5
        semaphore = asyncio.Semaphore(concurrency)

        async def upload_payload(payload, f):
            async with semaphore:
                activity_id = await create_manual_activity_from_json(payload)
                if activity_id:
                    date_str = payload["summaryDTO"]["startTimeLocal"][:10]
                    title = payload["activityName"]
                    typer.echo(f"Uploaded activity: {date_str} - {title} (ID: {activity_id})")
                else:
                    typer.echo(f"Failed to upload segment from {f.name}", err=True)

        await asyncio.gather(*(upload_payload(payload, f) for payload, f in payload_to_file))

    asyncio.run(upload_all())

import datetime
import json

@app.command()
def list_activities(
    start_date: str = typer.Option(None, help="Start date (YYYY-MM-DD). If not set, fetches from earliest."),
    end_date: str = typer.Option(None, help="End date (YYYY-MM-DD). If not set, fetches up to today."),
    output_json: Path = typer.Option(None, help="Optional: Path to save the listed activities as a JSON file."),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """
    List Garmin Connect activities within a date range, flagging those created by the exporter.
    """
    import asyncio

    if debug or os.getenv("DEBUG", "").lower() in ["true", "1"]:
        logging.getLogger("garmin_uploader").setLevel(logging.DEBUG)
    else:
        logging.getLogger("garmin_uploader").setLevel(logging.INFO)

    try:
        from garminconnect import Garmin
    except ImportError:
        typer.echo("garminconnect library not installed.", err=True)
        raise typer.Exit(1)

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        typer.echo("GARMIN_EMAIL and GARMIN_PASSWORD environment variables must be set.", err=True)
        raise typer.Exit(1)

    import re
    if not start_date or not end_date:
        # Infer date range from JSON files in the current directory
        date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")
        all_dates = []
        for f in Path(".").glob("*.json"):
            m = date_pattern.search(f.name)
            if m:
                all_dates.append(m.group(1))
        if all_dates:
            start_date = min(all_dates)
            end_date = max(all_dates)
        else:
            if not start_date:
                start_date = "2000-01-01"
            if not end_date:
                end_date = datetime.date.today().isoformat()

    def should_include_activity(a):
        name = str(a.get("activityName") or "")
        # Include any activity created by the exporter (name contains "Running-Log", case-sensitive)
        return "Running-Log" in name

    async def do_list():
        client = Garmin(email, password)
        await asyncio.to_thread(client.login)
        activities = await asyncio.to_thread(
            client.get_activities_by_date,
            startdate=start_date,
            enddate=end_date
        )
        filtered = [a for a in activities if should_include_activity(a)]
        # Sort by date (startTimeLocal)
        filtered = sorted(filtered, key=lambda a: a.get("startTimeLocal", ""))
        if output_json:
            with output_json.open("w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2, default=str)
            typer.echo(f"Wrote {len(filtered)} activities to {output_json}")
        else:
            typer.echo(f"Total activities found: {len(filtered)}")

    asyncio.run(do_list())

@app.command()
def delete_activities(
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate deletions and output a JSON file of what would have been deleted"),
    dry_run_output: Path = typer.Option(None, help="If set, output a JSON file of activities that would be deleted"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """
    Delete Garmin Connect activities created by the exporter (name starts with 'Running Log'), from 2007 to today.
    If --dry-run is set, outputs a JSON file of what would have been deleted.
    """
    import asyncio

    if debug or os.getenv("DEBUG", "").lower() in ["true", "1"]:
        logging.getLogger("garmin_uploader").setLevel(logging.DEBUG)
    else:
        logging.getLogger("garmin_uploader").setLevel(logging.INFO)

    try:
        from garminconnect import Garmin
    except ImportError:
        typer.echo("garminconnect library not installed.", err=True)
        raise typer.Exit(1)

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        typer.echo("GARMIN_EMAIL and GARMIN_PASSWORD environment variables must be set.", err=True)
        raise typer.Exit(1)

    start_date = "2007-01-01"
    end_date = datetime.date.today().isoformat()

    def should_include_activity(a):
        name = str(a.get("activityName") or "")
        # Delete any activity created by the exporter (name contains "Running-Log", case-sensitive)
        return "Running-Log" in name

    async def do_delete():
        def mfa_prompt():
            return input("Enter Garmin Connect MFA code: ")
        client = Garmin(email, password, prompt_mfa=mfa_prompt)
        client.login()
        activities = client.get_activities_by_date(
            startdate=start_date,
            enddate=end_date
        )
        # Use the same logic as the lister: include any activity with no GPS/device data, or if name starts with Running Log, and exclude cycling
        to_delete = [a for a in activities if should_include_activity(a)]
        # Sort by date (startTimeLocal)
        to_delete = sorted(to_delete, key=lambda a: a.get("startTimeLocal", ""))
        if dry_run:
            if not dry_run_output:
                typer.echo("You must specify --dry-run-output to save the list of activities to be deleted.", err=True)
                return
            with dry_run_output.open("w", encoding="utf-8") as f:
                json.dump(to_delete, f, indent=2, default=str)
            typer.echo(f"[DRY RUN] Would delete {len(to_delete)} activities. Wrote list to {dry_run_output}")
            return
        deleted_count = 0
        for activity in to_delete:
            activity_id = activity.get("activityId")
            if not activity_id:
                continue
            try:
                # The delete_activity method is synchronous, so run in a thread
                success = await asyncio.to_thread(client.delete_activity, activity_id)
                if success:
                    deleted_count += 1
                    typer.echo(f"Deleted activity {activity_id}")
                else:
                    typer.echo(f"Failed to delete activity {activity_id}", err=True)
            except Exception as e:
                typer.echo(f"Error deleting activity {activity_id}: {e}", err=True)
        typer.echo(f"Deleted {deleted_count} activities.")

    asyncio.run(do_delete())

if __name__ == "__main__":
    app()
