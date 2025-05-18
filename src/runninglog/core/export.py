"""Functions for exporting workout data to TCX and journal formats, and TCX validation."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import List, Optional

import pytz
from lxml import etree as ET
from pytz import timezone as pytz_timezone

from .constants import TCX_NAMESPACE_URI, TCX_SCHEMA_LOCATION, XSI_NAMESPACE_URI
from .types import WorkoutSegment

logger = logging.getLogger(__name__)


def tcx_el(name):
    return f"{{{TCX_NAMESPACE_URI}}}{name}"


def write_tcx(
    seg: WorkoutSegment,
    out_path: Path,
    source_timezone_str: str,
    description: Optional[str] = None,
) -> None:
    """Write a workout segment to a TCX file for Garmin compatibility.

    Args:
        seg: The WorkoutSegment object to write.
        out_path: The Path object for the output TCX file.
        source_timezone_str: The timezone string (e.g., 'America/New_York')
                             in which seg.date is to be interpreted (if naive).
        description: Optional description to include in the TCX file.
    """
    try:
        source_tz = pytz_timezone(source_timezone_str)
        localized_dt = source_tz.localize(seg.date)
        utc_dt = localized_dt.astimezone(pytz.utc)
    except pytz.exceptions.UnknownTimeZoneError:
        utc_dt = seg.date.replace(tzinfo=pytz.utc)
    except Exception:
        utc_dt = seg.date.replace(tzinfo=pytz.utc)

    root_nsmap = {None: TCX_NAMESPACE_URI, "xsi": XSI_NAMESPACE_URI}
    root = ET.Element(
        tcx_el("TrainingCenterDatabase"),
        attrib={
            f"{{{XSI_NAMESPACE_URI}}}schemaLocation": f"{TCX_NAMESPACE_URI} {TCX_SCHEMA_LOCATION}"
        },
        nsmap=root_nsmap,
    )
    activities_el = ET.SubElement(root, tcx_el("Activities"))
    sport_type = (
        seg.exercise if seg.exercise in ["Running", "Biking", "Other"] else "Other"
    )
    activity_el = ET.SubElement(activities_el, tcx_el("Activity"), Sport=sport_type)
    timestamp_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    ET.SubElement(activity_el, tcx_el("Id")).text = timestamp_str
    lap_el = ET.SubElement(activity_el, tcx_el("Lap"), StartTime=timestamp_str)
    ET.SubElement(lap_el, tcx_el("TotalTimeSeconds")).text = str(float(seg.secs))
    ET.SubElement(lap_el, tcx_el("DistanceMeters")).text = str(
        round(seg.miles * 1609.34, 2)
    )
    ET.SubElement(lap_el, tcx_el("Intensity")).text = "Active"
    ET.SubElement(lap_el, tcx_el("TriggerMethod")).text = "Manual"
    ET.SubElement(lap_el, tcx_el("MaximumSpeed")).text = "0.0"
    track_el = ET.SubElement(lap_el, tcx_el("Track"))
    trackpoint_el = ET.SubElement(track_el, tcx_el("Trackpoint"))
    ET.SubElement(trackpoint_el, tcx_el("Time")).text = timestamp_str
    ET.SubElement(trackpoint_el, tcx_el("AltitudeMeters")).text = "0.0"
    ET.SubElement(trackpoint_el, tcx_el("DistanceMeters")).text = "0.0"
    # Always write the full comment (including META) to <Notes>
    notes_to_write = seg.comment.strip() if seg.comment else ""
    # Add exported_from=running-log to META if not present
    if (
        notes_to_write.startswith("META:")
        and "exported_from=running-log" not in notes_to_write
    ):
        if notes_to_write.endswith(";") or notes_to_write == "META:":
            notes_to_write += "exported_from=running-log"
        else:
            notes_to_write += ";exported_from=running-log"
    if notes_to_write:
        ET.SubElement(activity_el, tcx_el("Notes")).text = notes_to_write
    # Do not write a <Description> tag; only <Notes> is used for metadata and user comments
    ET.ElementTree(root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    xml_bytes = ET.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
    with open(out_path, "wb") as fh:
        fh.write(xml_bytes)


def validate_tcx(tcx_path: Path) -> bool:
    """Basic validation of a TCX file to ensure it meets Garmin requirements."""
    try:
        tree = ET.parse(str(tcx_path))
        root = tree.getroot()
        xpath_ns = {"d": TCX_NAMESPACE_URI}
        required_elements_xpath = [
            "//d:Activities",
            "//d:Activity",
            "//d:Lap",
            "//d:Track",
            "//d:Trackpoint",
        ]
        for xpath_query in required_elements_xpath:
            if not root.xpath(xpath_query, namespaces=xpath_ns):
                return False
        return True
    except Exception:
        return False


def format_duration(seconds: int) -> str:
    """Formats seconds into HH:MM:SS string."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "00:00:00"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def sanitize_tcx_dir(directory_path: str) -> dict:
    """Sanitizes all TCX files in the given directory. Returns a summary dict."""
    dir_path = Path(directory_path).expanduser()
    if not dir_path.is_dir():
        return {"status": "error", "error": f"Not a directory: {dir_path}"}
    tcx_files = list(dir_path.glob("*.tcx"))
    if not tcx_files:
        return {"status": "empty", "files": []}
    success_count = 0
    fail_count = 0
    failed_files = []
    for tcx_file in tcx_files:
        try:
            # For now, just validate; could add in-place rewrite logic if needed
            if validate_tcx(tcx_file):
                success_count += 1
            else:
                fail_count += 1
                failed_files.append(str(tcx_file))
        except Exception:
            fail_count += 1
            failed_files.append(str(tcx_file))
    return {
        "status": "ok",
        "total": len(tcx_files),
        "success": success_count,
        "fail": fail_count,
        "failed_files": failed_files,
    }


async def write_journal_file(
    all_segments: List[WorkoutSegment], out_path: Path
) -> None:
    """Writes all workout segments to a Markdown formatted journal file."""
    if not all_segments:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "# Running Log Journal\n\nNo workouts processed or found to journal.\n"
        )
        return
    sorted_segments = sorted(all_segments, key=lambda s: (s.date, s.index))
    content = ["# Running Log Journal\n"]
    from collections import defaultdict

    # Group segments by (date, title)
    segments_by_workout = defaultdict(list)
    for seg in sorted_segments:
        try:
            seg_date_display = seg.date.strftime("%Y-%m-%d (%A)")
        except AttributeError:
            seg_date_display = "Unknown Date"
        # Parse title from META if present
        title = None
        user_comment = ""
        if seg.comment and seg.comment.startswith("META:"):
            try:
                meta_part = seg.comment[5:]
                meta_items = dict(
                    item.split("=", 1) for item in meta_part.split(";") if "=" in item
                )
                user_comment = meta_items.get("comments", "")
                title = meta_items.get("title")
            except Exception:
                user_comment = ""
        else:
            user_comment = seg.comment or ""
        title_out = None
        if title:
            stripped_title = title.strip()
            if stripped_title and "untitled" not in stripped_title.lower():
                title_out = stripped_title
        # Use (date, title) as the key
        segments_by_workout[(seg_date_display, title_out)].append((seg, user_comment))

    last_date = None
    for (seg_date_display, title), segs_with_comments in segments_by_workout.items():
        # Output date header only once per date
        if seg_date_display != last_date:
            if last_date is not None:
                content.append("\n---\n")
            content.append(f"\n## {seg_date_display}\n")
            last_date = seg_date_display

        # Output title as subheading (or "Untitled" if no title)
        if title:
            content.append(f"### {title}\n")
        else:
            content.append("### Untitled\n")

        # Gather weather and notes from the first segment in the group
        segs = [x[0] for x in segs_with_comments]
        notes = segs_with_comments[0][1].strip() if segs_with_comments else ""
        # Replace literal "\n" with actual newlines
        notes = notes.replace("\\n", "\n")
        if "META:" in notes:
            notes = notes.split("META:")[0].strip()
        weather = getattr(segs[0], "weather", None)

        # Output hoisted fields as plain text
        if weather:
            content.append(f"**Weather:** {weather}")
        if notes:
            if not (notes.startswith("META:")):
                for i, line in enumerate(notes.split("\n")):
                    if i == 0:
                        content.append(f"**Notes:** {line.strip()}")
                    else:
                        content.append(f"{line.strip()}")
        # Only output the table if not all segments are zeroed-out (any exercise type)
        if not all(seg.miles == 0 and seg.secs == 0 for seg in segs):
            content.append("")
            table_header = "| Exercise | Distance (mi) | Duration | Interval Type |"
            table_sep = "|---|---|---|---|"
            content.append(table_header)
            content.append(table_sep)
            # Output each segment as a table row
            for seg in segs:
                interval_type = getattr(seg, "interval_type", "") or ""
                row = f"| {seg.exercise} | {seg.miles:.2f} | {format_duration(seg.secs)} | {interval_type} |"
                content.append(row)
            content.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(content))


def parse_tcx_to_workout_segment(
    tcx_file_path: Path, target_timezone_str: str
) -> Optional[WorkoutSegment]:
    """Parses a TCX file and returns a WorkoutSegment object or None if parsing fails.

    The function expects the TCX to represent a single activity or takes the first one.
    It extracts overall/first lap data for distance, time, and start time.
    The start time is converted to the target_timezone_str and set to noon (naive).

    Args:
        tcx_file_path: Path to the TCX file.
        target_timezone_str: Timezone to convert the workout date to.

    Returns:
        A WorkoutSegment object if parsing is successful, otherwise None.
    """
    try:
        parser = ET.XMLParser(remove_blank_text=True)
        tree = ET.parse(str(tcx_file_path), parser)
        root = tree.getroot()

        activity_el = root.find(".//" + tcx_el("Activity"))
        if activity_el is None:
            logger.warning(f"No Activity element found in {tcx_file_path}. Skipping.")
            return None

        lap_el = activity_el.find(tcx_el("Lap"))
        if lap_el is None:
            logger.warning(
                f"No Lap element found in Activity in {tcx_file_path}. Skipping."
            )
            return None

        date_str = None
        activity_id_el = activity_el.find(tcx_el("Id"))
        if activity_id_el is not None and activity_id_el.text:
            date_str = activity_id_el.text
        elif lap_el.get("StartTime"):
            date_str = lap_el.get("StartTime")

        if not date_str:
            logger.warning(f"Could not find date/ID in {tcx_file_path}. Skipping.")
            return None

        try:
            utc_dt = dt.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            target_tz = pytz_timezone(target_timezone_str)
            localized_dt = utc_dt.astimezone(target_tz)
            workout_date = localized_dt.replace(
                hour=12, minute=0, second=0, microsecond=0, tzinfo=None
            )
        except (ValueError, pytz.exceptions.UnknownTimeZoneError) as e:
            logger.warning(
                f"Could not parse or convert date '{date_str}' from {tcx_file_path}: {e}. Skipping."
            )
            return None

        exercise = activity_el.get("Sport", "Other")
        if exercise.lower() not in ["running", "biking", "other"]:
            if "run" in exercise.lower():
                exercise = "Running"
            elif "bik" in exercise.lower():
                exercise = "Biking"
            else:
                exercise = "Other"

        notes_el = activity_el.find(tcx_el("Notes"))
        comment = (
            notes_el.text.strip() if notes_el is not None and notes_el.text else ""
        )

        # Parse weather and interval_type from META block in comment, if present
        weather = None
        interval_type = None
        if comment.startswith("META:"):
            try:
                meta_part = comment[5:]
                meta_items = dict(
                    item.split("=", 1) for item in meta_part.split(";") if "=" in item
                )
                weather = meta_items.get("weather")
                interval_type = meta_items.get("interval_type")
            except Exception as e:
                logger.warning(f"Failed to parse META block in comment: {e}")

        secs = 0
        total_time_el = lap_el.find(tcx_el("TotalTimeSeconds"))
        if total_time_el is not None and total_time_el.text:
            try:
                secs = int(float(total_time_el.text))
            except ValueError:
                logger.warning(
                    f"Could not parse TotalTimeSeconds '{total_time_el.text}' in {tcx_file_path}. Assuming 0."
                )
        else:
            logger.warning(
                f"TotalTimeSeconds not found in {tcx_file_path}. Assuming 0."
            )

        miles = 0.0
        distance_meters_el = lap_el.find(tcx_el("DistanceMeters"))
        if distance_meters_el is not None and distance_meters_el.text:
            try:
                distance_meters = float(distance_meters_el.text)
                miles = round(distance_meters / 1609.34, 2)
            except ValueError:
                logger.warning(
                    f"Could not parse DistanceMeters '{distance_meters_el.text}' in {tcx_file_path}. Assuming 0.0."
                )
        else:
            logger.warning(
                f"DistanceMeters not found in {tcx_file_path}. Assuming 0.0."
            )

        workout_index = 1

        return WorkoutSegment(
            date=workout_date,
            exercise=exercise,
            comment=comment,
            miles=miles,
            secs=secs,
            index=workout_index,
            weather=weather,
            interval_type=interval_type,
        )

    except ET.ParseError as e:
        logger.error(f"Error parsing TCX file {tcx_file_path}: {e}. Skipping.")
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error processing TCX file {tcx_file_path}: {e}. Skipping.",
            exc_info=True,
        )
        return None
