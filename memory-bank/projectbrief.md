# Project Brief

## Project Name
RunningLog CLI Toolkit

## Purpose
To provide a modern, modular, and user-friendly command-line toolkit for exporting, processing, and synchronizing workout data from Running-Log.com, with seamless integration to Garmin Connect and other fitness platforms.

## Core Requirements and Goals

- **Export Workouts:** Batch export all workout data (segments, comments, metadata) for a specified athlete.
- **TCX Generation:** Generate Garmin-compatible TCX files for each workout segment, ensuring correct formatting and metadata.
- **Journal Creation:** Produce human-readable workout journals in Markdown format from exported data or TCX files.
- **Garmin Integration:** Upload, list, and delete activities on Garmin Connect, with support for duplicate detection and state tracking.
- **State Management:** Maintain resumable, idempotent export and upload operations using persistent state files.
- **Data Sanitization:** Provide tools to sanitize and validate TCX files for maximum compatibility.
- **CLI Usability:** Offer a global runninglog command with clear subcommands and help.
- **Extensibility:** Modular codebase designed for future enhancements and integrations.

## Out of Scope
- Real-time workout tracking or live device synchronization.
- Web-based user interface (CLI only).
- Direct editing of workout data on Running-Log.com (read/export only).

## Success Criteria
- All workouts for a given athlete can be exported, converted to valid TCX, and uploaded to Garmin Connect with accurate metadata.
- Operations are robust to interruptions and can be resumed without data loss or duplication.
- The toolkit is easy to install, use, and extend, with clear documentation and a global CLI entry point.
