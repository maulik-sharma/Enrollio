"""In-memory storage adapter for unit tests and mock-only environments."""

from __future__ import annotations

from app.integrations.storage.base import StorageError


class MemoryStorage:
    """Keep uploaded objects in a process-local dictionary."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def save(self, key: str, data: bytes) -> None:
        if not key:
            raise StorageError("Invalid storage key")
        self._objects[key] = data

    def read(self, key: str) -> bytes:
        try:
            return self._objects[key]
        except KeyError as exc:
            raise StorageError("Object not found") from exc

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)
