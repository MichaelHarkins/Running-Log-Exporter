"""Functions for exporting workout data to JSON and generating Markdown journals."""

from pathlib import Path
from typing import List

from .types import WorkoutSegment

def write_json_workout(
    workout, out_path: Path
) -> None:
    """
    Write a Workout object to a JSON file.

    Args:
        workout: The Workout object to write.
        out_path: The Path object for the output JSON file.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(workout.model_dump_json(indent=2))


def format_duration(seconds: int) -> str:
    """Formats seconds into HH:MM:SS string."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "00:00:00"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


async def write_journal_file(
    all_workouts: List, out_path: Path
) -> None:
    """Writes all workouts to a Markdown formatted journal file."""
    if not all_workouts:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "# Running Log Journal\n\nNo workouts processed or found to journal.\n"
        )
        return
    # Sort workouts by date
    sorted_workouts = sorted(all_workouts, key=lambda w: w.date)
    content = ["# Running Log Journal\n"]

    last_date = None
    for workout in sorted_workouts:
        seg_date_display = workout.date.strftime("%Y-%m-%d (%A)") if hasattr(workout, "date") else "Unknown Date"
        title = workout.title or "Untitled"
        weather = getattr(workout, "weather", None)
        comments = getattr(workout, "comments", None) or ""
        # Output date header only once per date
        if seg_date_display != last_date:
            content.append(f"\n## {seg_date_display}\n")
            last_date = seg_date_display

        # Output title as subheading (or "Untitled" if no title)
        content.append(f"### {title}\n")

        # Output hoisted fields as plain text
        if weather:
            content.append(f"**Weather:** {weather}  ")
        if comments:
            content.append(f"**Comments:** {comments}  ")

        # Only output the table if not all segments are zeroed-out
        if hasattr(workout, "segments") and workout.segments and not all(
            (getattr(seg, "distance_miles", 0) == 0 and (getattr(seg, "duration_seconds", 0) or 0) == 0)
            for seg in workout.segments
        ):
            content.append("")
            # Determine if any segment has shoes or interval type
            any_shoes = any(
                getattr(seg, "shoes", None) and str(getattr(seg, "shoes", "")).strip()
                for seg in workout.segments
            )
            any_interval_type = any(
                getattr(seg, "interval_type", None) and str(getattr(seg, "interval_type", "")).strip()
                for seg in workout.segments
            )
            # Build table header and separator dynamically
            table_header = "| Distance (mi) | Duration | Pace |"
            table_sep = "|---|---|---|"
            if any_interval_type:
                table_header += " Interval Type |"
                table_sep += "---|"
            if any_shoes:
                table_header += " Shoes |"
                table_sep += "---|"
            content.append(table_header)
            content.append(table_sep)
            for seg in workout.segments:
                # Calculate pace (MM:SS/mi) if possible
                miles = getattr(seg, "distance_miles", 0)
                seconds = getattr(seg, "duration_seconds", 0) or 0
                if miles > 0 and seconds > 0:
                    pace_sec = int(round(seconds / miles))
                    pace_min = pace_sec // 60
                    pace_rem = pace_sec % 60
                    pace_str = f"{pace_min}:{pace_rem:02d}/mi"
                else:
                    pace_str = ""
                row = f"| {miles:.2f} | {format_duration(seconds)} | {pace_str} |"
                if any_interval_type:
                    interval_type = getattr(seg, "interval_type", "") or ""
                    row += f" {interval_type} |"
                if any_shoes:
                    shoes = getattr(seg, "shoes", "") or ""
                    row += f" {shoes} |"
                content.append(row)
            content.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(content))
