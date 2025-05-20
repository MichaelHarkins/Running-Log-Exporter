#!/usr/bin/env python3
"""
garmin_uploader.py

Uploads activities to Garmin Connect using the manual activity JSON endpoint.
This script assumes you have already parsed your source data and can construct the required JSON payload for each activity.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
import logging
from typing import Optional, List, Dict

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.traceback import install as install_rich_traceback

# Setup rich traceback and logging
install_rich_traceback()
console = Console()
logging.basicConfig(
    level="DEBUG",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)]
)
logger = logging.getLogger("garmin_uploader")

# Attempt to import Garmin Connect library
try:
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
    from garth.exc import GarthHTTPError
    GARMIN_CONNECT_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: Caught ImportError during garminconnect/garth import: {e}", file=sys.stderr)
    GARMIN_CONNECT_AVAILABLE = False
    class GarminConnectAuthenticationError(Exception): pass
    class GarminConnectConnectionError(Exception): pass
    class GarminConnectTooManyRequestsError(Exception): pass
    class GarthHTTPError(Exception): pass

garmin_client: Optional[Garmin] = None

def _simple_mfa_prompt() -> str:
    return input("Enter Garmin Connect MFA code: ")

async def initialize_garmin_client(email: str, password: str) -> bool:
    global garmin_client
    if not GARMIN_CONNECT_AVAILABLE:
        logger.error("Garmin Connect library not installed. Cannot initialize client.")
        return False
    try:
        token_dir = os.path.expanduser("~/.garminconnect")
        os.makedirs(token_dir, exist_ok=True)
        logger.info(f"Attempting to log in to Garmin Connect. Will try to use cached tokens from: {token_dir}")
        client_instance = Garmin(email, password, prompt_mfa=_simple_mfa_prompt)
        await asyncio.to_thread(client_instance.login, tokenstore=token_dir)
        profile = await asyncio.to_thread(client_instance.get_full_name)
        if profile:
            logger.info(f"Successfully logged in to Garmin Connect as {profile}.")
            garmin_client = client_instance
            return True
        else:
            logger.error("Garmin Connect login failed (unable to retrieve profile).")
            return False
    except Exception as e:
        logger.error(f"An error occurred during Garmin Connect login: {type(e).__name__} - {e}")
        return False

async def create_manual_activity_from_json(payload: dict) -> Optional[int]:
    """
    Uploads a manual activity to Garmin Connect using the JSON endpoint.
    Returns the new activity ID if successful, or None on failure.
    """
    global garmin_client
    if not garmin_client:
        logger.error("Garmin client not initialized. Cannot upload activity.")
        return None
    try:
        logger.debug(f"Uploading manual activity: {json.dumps(payload, indent=2)}")
        result = await asyncio.to_thread(garmin_client.create_manual_activity_from_json, payload)
        logger.info(f"Garmin response: {result}")
        # Try to extract the activity ID from the response
        data = result
        # If result is a Response object, parse JSON
        if hasattr(result, "json"):
            try:
                data = result.json()
            except Exception:
                logger.error(f"Could not parse JSON from response: {result}")
                return None
        if isinstance(data, dict):
            activity_id = data.get("activityId") or data.get("activity_id")
            if activity_id:
                logger.info(f"Successfully created activity. Activity ID: {activity_id}")
                return int(activity_id)
            # Some responses may nest the ID
            if "activity" in data and isinstance(data["activity"], dict):
                activity_id = data["activity"].get("activityId") or data["activity"].get("activity_id")
                if activity_id:
                    logger.info(f"Successfully created activity. Activity ID: {activity_id}")
                    return int(activity_id)
        logger.error(f"Could not extract activity ID from response. Raw response: {result}")
        return None
    except Exception as e:
        logger.error(f"Error uploading manual activity: {type(e).__name__} - {e}")
        return None

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Upload activities to Garmin Connect using manual activity JSON endpoint.")
    p.add_argument("json_file", type=str, help="Path to a JSON file containing a list of activity payloads.")
    p.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return p.parse_args(argv)

async def main():
    args = parse_args()

    if args.debug or os.getenv("DEBUG", "").lower() in ["true", "1"]:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    if not GARMIN_CONNECT_AVAILABLE:
        logger.error("The 'garminconnect' (and 'garth') library is not installed or fully functional. Please install/check it.")
        sys.exit(1)

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        logger.error("GARMIN_EMAIL and GARMIN_PASSWORD environment variables must be set.")
        sys.exit(1)

    # Load activity payloads from JSON file
    json_path = Path(args.json_file).expanduser()
    if not json_path.is_file():
        logger.error(f"JSON file not found: {json_path}")
        sys.exit(1)
    try:
        with json_path.open("r", encoding="utf-8") as f:
            activities = json.load(f)
        if not isinstance(activities, list):
            logger.error("JSON file must contain a list of activity payloads.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading JSON file: {e}")
        sys.exit(1)

    # Initialize Garmin client
    login_successful = await initialize_garmin_client(email, password)
    if not login_successful:
        logger.error("Exiting due to Garmin Connect login failure.")
        sys.exit(1)

    # Upload each activity
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress_bar:
        upload_task = progress_bar.add_task("Uploading activities...", total=len(activities))
        for payload in activities:
            activity_id = await create_manual_activity_from_json(payload)
            if activity_id:
                logger.info(f"Uploaded activity with ID: {activity_id}")
            else:
                logger.error("Failed to upload activity.")
            progress_bar.update(upload_task, advance=1)

    logger.info("All uploads complete.")

if __name__ == "__main__":
    asyncio.run(main())
