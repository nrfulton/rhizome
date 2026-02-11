from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CompostEntry:
    key: str
    content: str
    author: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    supersedes: str | None = None
    _stale: bool = field(default=False, repr=False)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "content": self.content,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "supersedes": self.supersedes,
            "_stale": self._stale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CompostEntry:
        entry = cls(
            key=d["key"],
            content=d["content"],
            author=d["author"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            supersedes=d.get("supersedes"),
        )
        entry._stale = d.get("_stale", False)
        return entry


class CompostPile:
    def __init__(self) -> None:
        self._entries: dict[str, CompostEntry] = {}
        self._lock = asyncio.Lock()

    async def add(self, entry: CompostEntry) -> None:
        async with self._lock:
            if entry.supersedes and entry.supersedes in self._entries:
                self._entries[entry.supersedes]._stale = True
            self._entries[entry.key] = entry

    async def update(self, key: str, content: str) -> None:
        async with self._lock:
            if key not in self._entries:
                raise KeyError(f"No compost entry with key '{key}'")
            self._entries[key].content = content
            self._entries[key].timestamp = datetime.now(timezone.utc)

    async def remove(self, key: str) -> None:
        async with self._lock:
            if key in self._entries:
                self._entries[key]._stale = True

    def get(self, key: str) -> CompostEntry | None:
        entry = self._entries.get(key)
        if entry and not entry._stale:
            return entry
        return None

    def query(self, *, author: str | None = None, include_stale: bool = False) -> list[CompostEntry]:
        results = []
        for entry in self._entries.values():
            if not include_stale and entry._stale:
                continue
            if author and entry.author != author:
                continue
            results.append(entry)
        return sorted(results, key=lambda e: e.timestamp)

    def active_entries(self) -> list[CompostEntry]:
        return self.query(include_stale=False)

    def all_entries(self) -> list[CompostEntry]:
        return self.query(include_stale=True)

    def to_json(self) -> str:
        return json.dumps(
            [e.to_dict() for e in self._entries.values()],
            indent=2,
        )

    @classmethod
    def from_json(cls, data: str) -> CompostPile:
        pile = cls()
        for d in json.loads(data):
            entry = CompostEntry.from_dict(d)
            pile._entries[entry.key] = entry
        return pile

    async def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    async def load(cls, path: Path) -> CompostPile:
        if path.exists():
            return cls.from_json(path.read_text())
        return cls()
