"""Storage providers: interface, local adapter, in-memory mock, and factory."""

from __future__ import annotations

from app.integrations.storage.base import Storage, StorageError
from app.integrations.storage.factory import StorageNotConfigured, build_storage
from app.integrations.storage.local import LocalStorage
from app.integrations.storage.memory import MemoryStorage

__all__ = [
    "LocalStorage",
    "MemoryStorage",
    "Storage",
    "StorageError",
    "StorageNotConfigured",
    "build_storage",
]
