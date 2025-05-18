# System Patterns

## System Architecture

- **src Layout:** All code is under src/runninglog/, following modern Python packaging best practices.
- **Modular Core/CLI Split:** Pure, importable logic is in core/; all user interaction is in cli/.
- **Explicit Package Discovery:** pyproject.toml uses [tool.setuptools.packages.find] to include only runninglog* packages.
- **Global CLI Entry Point:** [project.scripts] in pyproject.toml provides a runninglog command.

## Key Technical Decisions

- **Separation of Concerns:** All business logic is in core/; CLI handles only user interaction and output.
- **Relative Imports:** All intra-package imports use relative paths for clarity and maintainability.
- **Editable Install:** pip install -e . enables development and CLI access without PYTHONPATH hacks.
- **No Legacy Code:** All dependencies on RunningLogExport/ have been removed.

## Design Patterns

- **Orchestrator Pattern:** core/orchestrator.py coordinates full exports and audits.
- **State Management:** core/state.py encapsulates ExportState with async locking and migration.
- **Pure Functions:** All core logic is side-effect-free except for file I/O and logging.
- **CLI Command Pattern:** Each CLI command is a small module with register/handle, mapped to core logic.

## Component Relationships

- **cli/main.py** dispatches to subcommands in cli/commands/.
- **cli/commands/** modules call core/orchestrator, core/export, etc.
- **core/** modules are import-only, with no user interaction.

## Critical Implementation Paths

- **Export Workflow:** CLI → core/orchestrator.run_full_export → core/scrape, core/export, core/state.
- **Audit Workflow:** CLI → core/orchestrator.audit_exports → core/state, core/export.

## Error Handling

- **Logging in Core:** All errors and warnings are logged in core; CLI displays user-friendly messages.
- **No sys.exit in Core:** Only CLI layer may exit or print.

## Extensibility

- New features can be added to core/ and exposed via new CLI commands.
- The project is ready for unit testing, CI, and packaging for PyPI.
