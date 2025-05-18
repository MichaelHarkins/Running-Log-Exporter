# Product Context

## Why This Project Exists

- To provide a robust, modern, and user-friendly CLI toolkit for exporting, processing, and synchronizing workout data from Running-Log.com, with seamless integration to Garmin Connect and other platforms.
- To enable athletes and coaches to migrate, back up, and analyze their workout data with minimal friction and maximum reliability.

## Problems Solved

- **Data Portability:** Users can export their complete workout history from Running-Log.com, overcoming platform lock-in.
- **CLI Usability:** A single, global runninglog command provides access to all features, with clear subcommands and help.
- **Resumable, Reliable Exports:** State management and idempotent operations ensure robust, resumable exports.
- **Data Quality:** All exported files are validated and compatible with Garmin and other fitness platforms.
- **Transparency:** Human-readable journals and audit tools provide clear insight into export status and data integrity.

## How It Should Work

- Users install the CLI with pip install -e . and run runninglog [subcommand] [args...].
- All configuration is via CLI arguments and environment variables (no code changes required).
- The CLI provides clear, actionable feedback and progress reporting.
- All core logic is importable for automation, scripting, or integration with other tools.

## User Experience Goals

- **Reliability:** Users can trust that their data will be exported and uploaded without loss or duplication, even if interrupted.
- **Clarity:** Output and logs are clear, actionable, and informative.
- **Simplicity:** The CLI is straightforward, with sensible defaults and helpful error messages.
- **Extensibility:** Advanced users can adapt or extend the toolkit for new platforms or workflows.

## New User Onboarding

- Install with pip install -e . from the project root.
- Run runninglog --help to see available commands.
- Use runninglog export, test-workout, audit, etc., as needed.
- All documentation and usage instructions are kept up to date in the Memory Bank and README.
