from datetime import datetime
from zoneinfo import ZoneInfo

def workout_to_garmin_payloads(workout):
    """
    Convert a workout JSON object to a list of Garmin manual activity creation payloads,
    one per segment (since Garmin does not support segments in a single manual activity).
    """
    payloads = []
    date = workout["date"]
    if isinstance(date, str):
        date = datetime.fromisoformat(date)
    tz = ZoneInfo("America/New_York")
    date = date.astimezone(tz)

    type_map = {
        "run": "running",
        "running": "running",
        "bike": "cycling",
        "cycling": "cycling",
        "walk": "walking",
        "walking": "walking",
        "hike": "hiking",
        "hiking": "hiking",
        "swim": "swimming",
        "swimming": "swimming",
        "treadmill": "treadmill_running",
        "elliptical": "elliptical",
        "resort_skiing": "resort_skiing",
        "resort_skiing_snowboarding": "resort_skiing_snowboarding",
        "trail_running": "trail_running",
        "track_running": "track_running",
        # Add more as needed, matching Garmin's typeKey values from activity_types.properties
    }
    raw_type = str(workout.get("exercise_type", "running")).strip().lower()
    type_key = type_map.get(raw_type, raw_type)
    desc = workout.get("comments", "")
    if desc is None:
        desc = ""
    if len(desc) > 2000:
        trunc_marker = " (truncated)"
        desc = desc[:2000 - len(trunc_marker)] + trunc_marker

    found_valid = False
    wid = workout.get("wid") or workout.get("workout_id") or workout.get("id")
    if not wid:
        # Try to extract from filename if available (for future extensibility)
        import os
        if "source_file" in workout:
            base = os.path.basename(workout["source_file"])
            if "wid" in base:
                try:
                    wid = base.split("wid")[1].split("_")[0]
                except Exception:
                    wid = None

    for idx, seg in enumerate(workout.get("segments", []), 1):
        miles = seg.get("distance_miles", 0)
        seconds = seg.get("duration_seconds", 0)
        if miles == 0 and seconds == 0:
            continue
        found_valid = True
        # Use the workout date for all segments (or offset if you want to simulate real timing)
        start_time_local = date.strftime("%Y-%m-%dT%H:%M:%S.00")
        interval_label = seg.get('interval_type')
        if wid:
            wid_str = f"wid{wid}"
        else:
            wid_str = None
        if interval_label:
            activity_name = f"Running-Log - {workout.get('title', 'Untitled')} - {interval_label} {idx}"
        else:
            activity_name = f"Running-Log - {workout.get('title', 'Untitled')} - Segment {idx}"
        if wid_str:
            activity_name = f"{activity_name} [{wid_str}]"

        payload = {
            "activityTypeDTO": { "typeKey": type_key },
            "accessControlRuleDTO": { "typeId": 1, "typeKey": "public" },
            "timeZoneUnitDTO": { "unitKey": "America/New_York" },
            "eventTypeDTO": { "typeKey": "uncategorized" },
            "activityName": activity_name,
            "description": desc,
            "metadataDTO": {
                "autoCalcCalories": True,
                "videoUrl": None,
                "associatedCourseId": None
            },
            "summaryDTO": {
                "elevationGain": None,
                "elevationLoss": None,
                "averageHR": None,
                "maxHR": None,
                "averageTemperature": None,
                "minTemperature": None,
                "maxTemperature": None,
                "averagePower": None,
                "maxPower": None,
                "maxPowerTwentyMinutes": None,
                "averageRunCadence": None,
                "maxRunCadence": None,
                "maxSpeed": None,
                "beginPackWeight": None,
                "startTimeLocal": start_time_local,
                "distance": float(miles) * 1609.34,
                "duration": seconds,
                "calories": 0,
                "bmrCalories": 0
            }
        }
        payloads.append(payload)

    if not found_valid:
        # Always log a 0-mileage activity if no valid segments
        start_time_local = date.strftime("%Y-%m-%dT%H:%M:%S.00")
        activity_name = f"Running-Log - {workout.get('title', 'Untitled')} - No Data"
        payload = {
            "activityTypeDTO": { "typeKey": type_key },
            "accessControlRuleDTO": { "typeId": 1, "typeKey": "public" },
            "timeZoneUnitDTO": { "unitKey": "America/New_York" },
            "eventTypeDTO": { "typeKey": "uncategorized" },
            "activityName": activity_name,
            "description": desc,
            "metadataDTO": {
                "autoCalcCalories": True,
                "videoUrl": None,
                "associatedCourseId": None
            },
            "summaryDTO": {
                "elevationGain": None,
                "elevationLoss": None,
                "averageHR": None,
                "maxHR": None,
                "averageTemperature": None,
                "minTemperature": None,
                "maxTemperature": None,
                "averagePower": None,
                "maxPower": None,
                "maxPowerTwentyMinutes": None,
                "averageRunCadence": None,
                "maxRunCadence": None,
                "maxSpeed": None,
                "beginPackWeight": None,
                "startTimeLocal": start_time_local,
                "distance": 0.0,
                "duration": 0,
                "calories": 0,
                "bmrCalories": 0
            }
        }
        payloads.append(payload)
    return payloads
