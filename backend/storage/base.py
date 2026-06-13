from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    public_url: str
    size_bytes: int | None = None
    content_type: str | None = None


class StorageService(Protocol):
    def save_file(
        self,
        file_bytes: bytes,
        storage_key: str,
        content_type: str | None = None,
    ) -> StoredFile:
        pass

    def delete_file(self, storage_key: str) -> bool:
        pass

    def get_public_url(self, storage_key: str) -> str:
        pass

    def exists(self, storage_key: str) -> bool:
        pass
