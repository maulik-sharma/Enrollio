"""Select the configured storage adapter."""

from __future__ import annotations

from app.core.config import Settings, StorageProvider
from app.integrations.storage.base import Storage
from app.integrations.storage.local import LocalStorage
from app.integrations.storage.memory import MemoryStorage


class StorageNotConfigured(RuntimeError):
    """The selected storage provider has no adapter yet."""


def build_storage(settings: Settings) -> Storage:
    """Return a storage adapter for ``settings``.

    Local storage is already credential-free, so it is used even when
    ``USE_MOCK_STORAGE`` is true. The mock flag only substitutes an in-memory
    store for a provider that would otherwise need external credentials.
    """
    if settings.STORAGE_PROVIDER is StorageProvider.local:
        return LocalStorage(settings.LOCAL_STORAGE_PATH)

    if settings.USE_MOCK_STORAGE:
        return MemoryStorage()

    raise StorageNotConfigured(
        f"No storage adapter is implemented for {settings.STORAGE_PROVIDER.value}"
    )
