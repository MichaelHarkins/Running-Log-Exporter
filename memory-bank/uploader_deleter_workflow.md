# Garmin Uploader & Deleter Workflow (May 2025)

## Overview

This document summarizes the current architecture, logic, and best practices for the Garmin uploader and deleter CLI tools in the Exporter project.

---

## Uploader Workflow

- **No state file:**  
  The uploader no longer tracks upload state in a file. It always deduplicates by listing existing activities from Garmin Connect at the start of each run.

- **Date range inference:**  
  The uploader infers the date range to fetch from Garmin by scanning the JSON filenames to be uploaded and extracting the earliest and latest dates.

- **Deduplication:**  
  For each activity to upload, the uploader checks if an existing activity on the same date has a name that is a substring match (either way). If so, the upload is skipped.

- **Login and token management:**  
  The uploader uses the `garth` login logic to ensure a valid token is present, prompting for MFA if needed, and saves the session to `~/.garminconnect`.

- **Upload:**  
  Each segment is uploaded as a separate activity using the correct Garmin API payload structure, with all required fields and correct type keys.

---

## Deleter Workflow

- **No state file:**  
  The deleter does not track deletion state in a file. It always lists all activities from 2007 to today before deletion.

- **Advanced filtering:**  
  The deleter uses advanced filtering logic (ported from the old lister) to select activities for deletion:
    - Ignores activities with certain keywords (e.g., "bike", "swim", "walk", etc.).
    - Ignores activities with GPS/device data (max speed, HR, calories > 0).
    - Only deletes activities with "run" in the name and that pass the above filters.

- **Dry-run support:**  
  The deleter supports a `--dry-run` flag. When set, it requires `--dry-run-output` and writes the list of activities that would be deleted to the specified file, only printing the number of activities to be deleted.

- **Login and token management:**  
  Uses the same robust login/token logic as the uploader.

---

## Key Technical Concepts

- Typer-based CLI for all commands.
- Robust login and token management with `garth` and `garminconnect`.
- Deduplication and deletion always start by listing activities from Garmin.
- Advanced filtering logic for deletion, matching the old lister.
- No persistent state files for upload or deletion; everything is stateless and idempotent.
- Dry-run mode for safe deletion auditing.

---

## Pending Tasks / Next Steps

- [ ] Further customize filtering logic if needed.
- [ ] Add more logging or diagnostics if required.
- [ ] Continue to keep the memory bank updated as workflows evolve.
