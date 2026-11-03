"""Storage provider interface.

Business code depends on this protocol, never on a filesystem or vendor SDK.
Keys are opaque, forward-slash-separated paths chosen by the caller.
"""

from __future__ import annotations

from typing import Protocol


class StorageError(Exception):
    """A stored object could not be written or read."""


class Storage(Protocol):
    """Minimal object store used by the import pipeline."""

    def save(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``, replacing an existing object."""
        ...

    def read(self, key: str) -> bytes:
        """Return the bytes stored under ``key``."""
        ...

    def delete(self, key: str) -> None:
        """Delete ``key`` if it exists."""
        ...
