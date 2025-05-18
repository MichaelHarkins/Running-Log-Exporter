# RunningLog Exporter CLI

[![GitHub Repo](https://img.shields.io/badge/GitHub-MichaelHarkins%2FRunning--Log--Exporter-blue?logo=github)](https://github.com/MichaelHarkins/Running-Log-Exporter)
[![Issues](https://img.shields.io/github/issues/MichaelHarkins/Running-Log-Exporter)](https://github.com/MichaelHarkins/Running-Log-Exporter/issues)

**Project Links:**  
- [Homepage](https://github.com/MichaelHarkins/Running-Log-Exporter)
- [Documentation](https://github.com/MichaelHarkins/Running-Log-Exporter#readme)
- [Issues](https://github.com/MichaelHarkins/Running-Log-Exporter/issues)

## Overview

The RunningLog Exporter CLI is a robust, Typer-based command-line toolkit for exporting, organizing, and journaling workout data from running-log.com. It is designed for flexibility, clean organization, and reliable downstream processing.

## Features

- **Athlete-centric organization:** All state, debug, and journal files are stored under a subdirectory named after the athlete.
- **Custom output directory:** The `--output-dir` option is required and specifies where all athlete-specific data (output, debug, state, journal) will be created.
- **Granular refresh logic:** Use `--refresh-all` to reset all processed WIDs, or `--refresh-wids` with a comma-separated list to reset only specific WIDs.
- **Metadata tagging:** All exported TCX files include a `META:` block in the `<Notes>` field, with `exported_from=running-log` for downstream detection.
- **Markdown journal generation:** The `create_journal` command generates a clean Markdown journal from TCX files, ignoring technical meta tags and handling multi-line comments.
- **No test_workout command:** The CLI is streamlined for clarity and simplicity.

## Directory Structure

```
<output-dir>/
  <athlete_name>/
    output/         # TCX files for this athlete
    debug/          # Debug files
    state/          # State files (e.g., runninglog_state.json)
    journal/        # Markdown journals
```

## Commands

### Export

Export all workouts for an athlete.

**Options:**
- `--athlete-id` (required): Athlete ID to export.
- `--output-dir` (required): Custom output directory for all athlete-specific data.
- `--force`: Clear athlete-specific export directory and reset state before export.
- `--refresh-all`: Reset all processed WIDs before export.
- `--refresh-wids`: Reset only the specified WIDs (comma-separated, e.g. `--refresh-wids 12345,67890`).
- `--concurrency`: Number of concurrent workout exports (default: 5).

**Behavior:**
- All athlete-specific data (output, debug, state, journal) is created under `<output-dir>/<athlete_name>/`.
- `--refresh-all` clears all processed WIDs; `--refresh-wids` removes only the specified WIDs from state and deletes their TCX files.
- The `META:` block in each TCX `<Notes>` includes `exported_from=running-log`.

### Create Journal

Generate a Markdown journal from TCX files.

**Options:**
- `--athlete-id` (required): Athlete ID to create journal for.
- `--output-dir` (required): Directory to read TCX files from (athlete-specific output/).
- `--out-file`: Output Markdown file (default: `<athlete_name>/journal/journal.md`).
- `--timezone`: Timezone for parsing TCX files.

**Behavior:**
- Reads TCX files from `<output-dir>/<athlete_name>/output/`.
- Ignores technical meta tags (e.g., `exported_from=running-log`) when generating the journal.
- Handles multi-line comments and notes, rendering them as multiple lines in Markdown.

## Metadata and Journal Handling

- The `<Notes>` field in each TCX file contains a `META:` block with key-value pairs (e.g., `META:comments=...;title=...;exported_from=running-log`).
- The `exported_from=running-log` tag is always present for downstream detection.
- When generating the journal, the logic strips out technical meta tags and converts literal `\n` to real newlines for proper Markdown rendering.

## Example Usage

```sh
# Export all workouts for an athlete, using a custom output directory
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports

# Refresh all processed WIDs before export
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports --refresh-all

# Refresh only specific WIDs
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports --refresh-wids 12345,67890

# Create a journal from a custom output directory
runninglog create-journal --athlete-id 44524 --output-dir /tmp/my_exports --out-file my_journal.md
```

## Notes

- All state, debug, output, and journal files are always created under the specified --output-dir, organized by athlete.
- The CLI is robust to multi-line comments and technical meta tags, ensuring clean journal output and reliable downstream processing.
- The test_workout command has been removed for clarity.
