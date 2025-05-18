# Technology Context

## Project Structure
- **src Layout:** All code is under src/runninglog/, following modern Python packaging best practices.
- **Modular Core/CLI:** core/ contains pure logic; cli/ contains all user interaction and command-line interface code.

## Packaging and Installation
- **pyproject.toml** at project root configures dependencies, package discovery, and CLI entry point.
- **Editable Install:** Use pip install -e . for development and CLI access.
- **Entry Point:** [project.scripts] provides a global runninglog command.

## Programming Language
- Python 3.8+ (tested on 3.13)
- Uses asyncio for concurrency.

## Core Libraries and Frameworks
- **httpx** (async HTTP client)
- **beautifulsoup4** (HTML parsing)
- **lxml** (XML/TCX processing)
- **tenacity** (retry logic)
- **rich** (logging, progress bars, CLI output)
- **pytz** (timezone conversion)

## Data Modeling
- **dataclasses** for core data structures (WorkoutSegment, ExportState).
- **asyncio.Lock** for state mutation safety.

## CLI and Configuration
- **argparse** for command-line parsing.
- **Rich** for colored output and progress bars.
- **Environment Variables:** RL_USERNAME, RL_PASSWORD, RL_ATHLETE_ID, etc.

## Tooling and Dependencies
- All dependencies listed in pyproject.toml.
- Project is ready for CI, unit testing, and PyPI packaging.

## Development Practices
- All core logic is importable and testable.
- CLI is the only layer with user interaction or output.
- Logging is used in core; Rich/print only in CLI.
- No sys.exit or print in core logic.
