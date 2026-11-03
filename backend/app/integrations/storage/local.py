"""Local-filesystem storage adapter for development and single-host deployments."""

from __future__ import annotations

import os
from pathlib import Path

from app.integrations.storage.base import StorageError


class LocalStorage:
    """Store objects beneath a configured root directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if not key or key.startswith("/") or "\\" in key:
            raise StorageError("Invalid storage key")

        parts = key.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise StorageError("Invalid storage key")

        return self.root.joinpath(*parts)

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(f"{path.suffix}.tmp")
            temporary.write_bytes(data)
            os.replace(temporary, path)
        except OSError as exc:
            raise StorageError("Could not write object") from exc

    def read(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError("Could not read object") from exc

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Could not delete object") from exc
