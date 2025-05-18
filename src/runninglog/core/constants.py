"""Constants used throughout the runninglog exporter application."""

# Constants for Running-Log.com export script

BASE = "http://running-log.com"
# CAL_URL = BASE + "/calendar?athleteid={aid}&year={y}&month={m}" # Unused
WO_URL = BASE + "/workouts/{wid}?athleteid={aid}"

_HEADER = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# Namespace URIs for TCX
TCX_NAMESPACE_URI = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
XSI_NAMESPACE_URI = "http://www.w3.org/2001/XMLSchema-instance"
NS3_NAMESPACE_URI = (
    "http://www.garmin.com/xmlschemas/ActivityExtension/v2"  # For Activity Extensions
)
TCX_SCHEMA_LOCATION = "http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
