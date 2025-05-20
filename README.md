## Garmin Uploader Environment Variables

Before using the Garmin uploader CLI, you must set the following environment variables in your shell:

```sh
export GARMIN_EMAIL="your-email@example.com"
export GARMIN_PASSWORD="your-garmin-password"
export GARMINTOKENS=/Users/youruser/.garminconnect
```

Replace the values with your actual Garmin Connect credentials and token directory. These variables are required for authentication and token management.

The RunningLog Exporter CLI is a robust, Typer-based command-line toolkit for exporting, organizing, and journaling workout data from running-log.com. It is designed for flexibility, clean organization, and reliable downstream processing.

## Features

- **Athlete-centric organization:** All state, debug, and journal files are stored under a subdirectory named after the athlete.
- **Custom output directory:** The `--output-dir` option is required and specifies where all athlete-specific data (output, debug, state, journal) will be created.
- **Granular refresh logic:** Use `--refresh-all` to reset all processed WIDs, or `--refresh-wids` with a comma-separated list to reset only specific WIDs.
- **JSON export:** All exported workouts are saved as a single JSON file per workout, containing all segments and metadata as explicit fields.
- **Markdown journal generation:** The `create_journal` command generates a clean Markdown journal from JSON files, using all structured fields and handling multi-segment workouts.

## Installation

### Option 1: Using pip (from source)

```bash
# Clone the repository
git clone https://github.com/MichaelHarkins/Running-Log-Exporter.git
cd Running-Log-Exporter

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Option 2: Pre-built Binary

Download the pre-built binary from the [Releases](https://github.com/MichaelHarkins/Running-Log-Exporter/releases) page. The binary is self-contained and does not require a Python installation.

#### Using the pre-built binary:

1. Download the appropriate zip file for your operating system:
   - `runninglog-linux.zip` for Linux
   - `runninglog-macos.zip` for macOS
   - `runninglog-windows.zip` for Windows

2. Extract the zip file:
   ```bash
   unzip runninglog-*.zip
   ```

3. Make the binary executable (Linux/macOS):
   ```bash
   chmod +x runninglog
   ```

4. Move to a directory in your PATH (optional, Linux/macOS):
   ```bash
   sudo mv runninglog /usr/local/bin/
   ```

## Directory Structure

When you run the exporter, it organizes files as follows:

```
<output-dir>/
  <athlete_name>/
    output/         # JSON files for this athlete (one per workout)
    debug/          # Debug files
    state/          # State files (e.g., runninglog_state.json)
    journal/        # Markdown journals
```

## Running the Scripts

### Basic Usage

If you installed via pip or are in the development environment:

```bash
# Show help
runninglog --help

# Show help for a specific command
runninglog export --help
runninglog create-journal --help
```

If you're using the standalone binary:

```bash
# Linux/macOS
./runninglog --help

# Windows
runninglog.exe --help
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
- `--debug`: Enable debug logging.

**Behavior:**
- All athlete-specific data (output, debug, state, journal) is created under `<output-dir>/<athlete_name>/`.
- Each workout is exported as a single JSON file containing all segments and metadata.
- `--refresh-all` clears all processed WIDs; `--refresh-wids` removes only the specified WIDs from state and deletes their JSON files.

### Create Journal

Generate a Markdown journal from JSON files.

**Options:**
- `--athlete-id` (required): Athlete ID to create journal for.
- `--output-dir` (required): Directory to read JSON files from (athlete-specific output/).
- `--out-file`: Output Markdown file (default: `<athlete_name>/journal/journal.md`).
- `--timezone`: Timezone for parsing (not used for JSON, but kept for compatibility).
- `--debug`: Enable debug logging.

**Behavior:**
- Reads JSON files from `<output-dir>/<athlete_name>/output/`.
- Aggregates all segments per workout and renders them in Markdown.
- Handles multi-line comments and notes, rendering them as multiple lines in Markdown.

## Example Usage

### Export Command Examples

```bash
# Export all workouts for an athlete, using a custom output directory
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports

# Enable debug logging
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports --debug

# Force reprocessing of all workouts
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports --force

# Refresh all processed WIDs before export
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports --refresh-all

# Refresh only specific WIDs
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports --refresh-wids 12345,67890

# Adjust concurrency for faster export (use with caution)
runninglog export --athlete-id 44524 --output-dir /tmp/my_exports --concurrency 10
```

### Create Journal Examples

```bash
# Create a journal with default settings
runninglog create-journal --athlete-id 44524 --output-dir /tmp/my_exports

# Create a journal with a custom output file
runninglog create-journal --athlete-id 44524 --output-dir /tmp/my_exports --out-file my_journal.md

# Specify timezone (maintained for compatibility)
runninglog create-journal --athlete-id 44524 --output-dir /tmp/my_exports --timezone "America/New_York"
```

### Full Workflow Example

This example shows a complete workflow from export to journal creation:

```bash
# Step 1: Export all workouts
runninglog export --athlete-id 44524 --output-dir ~/running_data

# Step 2: Create a journal from the exported data
runninglog create-journal --athlete-id 44524 --output-dir ~/running_data

# Step 3: View the generated journal
open ~/running_data/athlete44524/journal/journal.md  # macOS
xdg-open ~/running_data/athlete44524/journal/journal.md  # Linux
```

## System Architecture and Implementation Details

This section provides detailed information for developers about how the system works internally.

### Overall Architecture

The RunningLog Exporter follows a modular design with these key components:

1. **CLI Layer** (`runninglog/cli/`): Handles command-line arguments and user interaction
2. **Core Layer** (`runninglog/core/`): Contains the business logic for exporting and processing workouts
3. **Utils Layer** (`runninglog/utils/`): Provides utility functions for HTTP, logging, error handling, etc.

The data flow during export:
1. CLI parses arguments and initializes the export
2. `scrape_all_wids_from_workout_list_pages` discovers all workout IDs
3. `run_full_export` orchestrates the export of each workout
4. `run_one_wid` processes individual workouts
5. `scrape_workout` extracts data from the website
6. `write_json_workout` saves the workout data as JSON

### Data Model

Workouts are represented using Pydantic models defined in `core/types.py`:

```python
class WorkoutSegment(BaseModel):
    distance_miles: float
    duration_seconds: Optional[int]
    interval_type: Optional[str]
    shoes: Optional[str]
    pace: Optional[str]

class Workout(BaseModel):
    title: Optional[str]
    date: dt.datetime
    exercise_type: str
    weather: Optional[str]
    comments: Optional[str]
    total_distance_miles: float
    total_duration_seconds: Optional[int]
    segments: List[WorkoutSegment]
    exported_from: Optional[str] = "running-log"
```

These models provide validation, serialization, and data integrity.

### Duplication Prevention Logic

The exporter uses a state management system to prevent re-exporting workouts that have already been processed. The key components are:

1. **State Storage** (`core/state.py`):
   - Each athlete has a state file (default: `runninglog_state.json`)
   - The state file contains a list of processed workout IDs (`done_wids`)
   - State is persisted to disk after each workout is processed

2. **Workout Tracking**:
   - Before exporting, the system queries `running-log.com` for all workout IDs
   - The system compares these IDs against the `done_wids` in the state file
   - Only unprocessed workouts are exported

3. **Refresh Options**:
   - `--refresh-all`: Clears all `done_wids`, forcing re-export of all workouts
   - `--refresh-wids`: Clears specific workout IDs, targeted re-export
   - `--force`: Deletes the state file and all JSON files, starting from scratch

4. **Implementation** (in `orchestrator.py`):
   ```python
   # Discover WIDs
   discovered = await scrape_all_wids_from_workout_list_pages(...)
   
   # Determine new WIDs to process (no duplicates)
   pending = sorted(set(discovered) - state.done_wids, reverse=True)
   
   # After successful export of a workout
   await state.mark_done(wid)  # Add to done_wids
   await state.save()  # Persist to disk
   ```

### Journal Creation Process

The journal creator transforms JSON workout files into a markdown document. The process works as follows:

1. **File Discovery**:
   - Looks for all JSON files in the athlete's output directory
   - Parses each file into a `Workout` object

2. **Organization**:
   - Sorts workouts by date
   - Groups workouts by date for the markdown structure

3. **Markdown Generation** (in `export.py`):
   - Creates a header for each date with formatted date string
   - For each workout:
     - Creates a subheading with the workout title
     - Includes weather and comments as plain text
     - Generates a table with workout segments
     - Calculates and displays pace for each segment
     - Conditionally shows shoes and interval type if present

4. **Multi-segment Handling**:
   - Detects which columns (shoes, interval type) are used across all segments
   - Dynamically builds table structure based on available data
   - Aggregates all segments under a single workout heading
   - Each segment appears as a row in the workout's table

5. **Format Example**:
   ```markdown
   # Running Log Journal
   
   ## 2023-01-15 (Sunday)
   
   ### Easy Run
   **Weather:** Sunny, 65°F  
   **Comments:** Felt good today  
   
   | Distance (mi) | Duration | Pace | Interval Type | Shoes |
   |---|---|---|---|---|
   | 1.50 | 00:15:00 | 10:00/mi | Warmup | Adidas |
   | 3.00 | 00:28:30 | 9:30/mi | Steady | Adidas |
   | 0.50 | 00:05:00 | 10:00/mi | Cooldown | Adidas |
   ```

### Concurrency and Rate Limiting

The exporter uses asyncio for concurrency with controlled rate limiting:

1. **Rate Limiter** (`utils/http_client.py`):
   - Implements a token bucket algorithm
   - Default: 3 requests per second
   - Custom wait logic with exponential backoff for failures

2. **Concurrency Control**:
   - The `--concurrency` option limits parallel requests
   - Default: 5 concurrent requests
   - Implemented using asyncio semaphores:
   ```python
   sem = asyncio.Semaphore(concurrency)
   async def worker(wid):
       async with sem:  # Only N concurrent tasks
           result = await run_one_wid(...)
   ```

3. **Error Handling**: When hitting rate limits, the system:
   - Detects HTTP 429 errors
   - Implements exponential backoff
   - Retries with increasing delays
   - Logs detailed information about rate limit hits

### Error Handling and Resilience

The exporter implements robust error handling for network and parsing issues:

1. **Decorator-based Error Handling** (`utils/error_handler.py`):
   - The `@with_async_error_handling` decorator wraps key functions
   - Provides consistent error logging and context
   - Implements retries for transient errors

2. **HTTP Resilience**:
   - Connection pooling and keepalive to reduce overhead
   - Automatic retries for failed requests
   - Timeouts to prevent hanging operations

3. **HTML Parsing**:
   - Robust extraction of data with fallbacks
   - Clear error messages for parsing failures
   - Defensive coding to handle missing or malformed data

## Development

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/MichaelHarkins/Running-Log-Exporter.git
   cd Running-Log-Exporter
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Run tests:
   ```bash
   pytest
   ```

5. Run linting and formatting:
   ```bash
   make all
   ```

### Code Formatting and Style

This project uses:
- `black` for code formatting
- `flake8` for linting
- `isort` for import sorting
- `autoflake` for removing unused imports

Run all checks with:
```bash
make all
```

## Building Binary Executables

### Local Building

The project uses PyInstaller to create standalone executables:

```bash
# Install PyInstaller if not installed
pip install pyinstaller

# Build the binary using the spec file
pyinstaller runninglog.spec

# The executable will be created in the dist/ directory
```

### Using Make

```bash
# Install dev dependencies (includes PyInstaller)
make install-dev

# Build for all platforms
make build

# Build and package for macOS
make build-mac

# Build and package for Windows
make build-win

# Clean build artifacts
make clean
```

### Automated Builds via GitHub Actions

This project uses GitHub Actions to automatically build binaries for Linux, macOS, and Windows. These binaries are attached to GitHub Releases.

To trigger a build:
1. Push to the `main` branch (builds but doesn't publish)
2. Create a new Release in GitHub (builds and attaches binaries to the release)
3. Manually trigger the workflow from the Actions tab

## Metadata and Journal Handling

- All metadata fields (title, comments, weather, interval_type, shoes, etc.) are stored as explicit fields in the JSON file.
- The `exported_from` field is included for provenance.
- When generating the journal, all fields are used directly from the JSON structure for clean and robust Markdown output.

## Troubleshooting

### Common Issues

1. **Permission denied when running the binary**
   - On Linux/macOS, make sure the binary is executable: `chmod +x runninglog`

2. **Missing dependencies in custom-built binary**
   - Use the provided spec file with PyInstaller: `pyinstaller runninglog.spec`
   - Use the binaries from GitHub Releases which include all dependencies

3. **Error finding athlete data**
   - Ensure the athlete ID is correct
   - Check that the output directory exists and is writable

4. **Rate limiting issues**
   - The default rate limiter restricts to 3 requests per second
   - Reduce concurrency with `--concurrency 3` for very strict rate limits

### Logging

Enable debug logging for more detailed information:

```bash
runninglog export --athlete-id 44524 --output-dir ~/running_data --debug
```

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
