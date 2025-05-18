from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Set

import aiofiles

from runninglog.utils.console import get_console
from runninglog.utils.error_handler import with_async_error_handling

logger = logging.getLogger(__name__)
console = get_console()


@dataclass
class ExportState:
    done_wids: Set[int] = field(default_factory=set)
    processed_workout_list_pages: Set[int] = field(default_factory=set)
    discovered_wids: Set[int] = field(default_factory=set)
    path: Path = field(default=Path("runninglog_state.json"), repr=False, compare=False)
    version: int = 2
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "done_wids": sorted(list(self.done_wids)),
            "processed_workout_list_pages": sorted(
                list(self.processed_workout_list_pages)
            ),
            "discovered_wids": sorted(list(self.discovered_wids)),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], file_path: Path) -> "ExportState":
        return cls(
            done_wids=set(data.get("done_wids", [])),
            processed_workout_list_pages=set(
                data.get("processed_workout_list_pages", [])
            ),
            discovered_wids=set(data.get("discovered_wids", [])),
            path=file_path,
            version=data.get("version", 1),
        )

    @classmethod
    def load(cls, path: Path) -> "ExportState":
        if path.exists():
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    done_wids = set(data.get("done_wids", []))
                    processed_workout_list_pages = set(
                        data.get("processed_workout_list_pages", [])
                    )
                    discovered_wids = set(data.get("discovered_wids", []))
                    version = data.get("version", 1)
                    state = cls(
                        done_wids=done_wids,
                        processed_workout_list_pages=processed_workout_list_pages,
                        discovered_wids=discovered_wids,
                        path=path,
                        version=version,
                    )
                    # Handle migrations here if needed
                    return state
            except json.JSONDecodeError:
                logger.warning(
                    f"State file {path} is corrupted or not valid JSON. Starting with a new state."
                )
                return cls(path=path)
        return cls(path=path)

    @with_async_error_handling(context="ExportState._save_content")
    async def _save_content(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self.path, "w") as f:
            await f.write(json.dumps(self.to_dict(), indent=2))

    async def save(self):
        async with self._lock:
            await self._save_content()

    async def mark_done(self, wid: int):
        async with self._lock:
            self.done_wids.add(wid)
            await self._save_content()

    async def add_discovered(self, wids: Set[int]):
        async with self._lock:
            self.discovered_wids.update(wids)
            await self._save_content()
