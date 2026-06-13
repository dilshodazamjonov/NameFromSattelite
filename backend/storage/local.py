from __future__ import annotations

from pathlib import Path

from backend.storage.base import StoredFile


class LocalStorage:
    def __init__(
        self,
        storage_root: Path,
        static_url_prefix: str,
        public_base_url: str | None = None,
    ) -> None:
        self.storage_root = storage_root
        self.static_url_prefix = normalize_url_prefix(static_url_prefix)
        self.public_base_url = (public_base_url or "").rstrip("/")

    def save_file(
        self,
        file_bytes: bytes,
        storage_key: str,
        content_type: str | None = None,
    ) -> StoredFile:
        safe_key = normalize_storage_key(storage_key)
        target_path = self.resolve_path(safe_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(file_bytes)
        return StoredFile(
            storage_key=safe_key,
            public_url=self.get_public_url(safe_key),
            size_bytes=len(file_bytes),
            content_type=content_type,
        )

    def delete_file(self, storage_key: str) -> bool:
        path = self.resolve_path(normalize_storage_key(storage_key))
        if not path.exists():
            return False
        path.unlink()
        return True

    def get_public_url(self, storage_key: str) -> str:
        safe_key = normalize_storage_key(storage_key)
        path_url = f"{self.static_url_prefix}/{safe_key}"
        if self.public_base_url:
            return f"{self.public_base_url}{path_url}"
        return path_url

    def exists(self, storage_key: str) -> bool:
        return self.resolve_path(normalize_storage_key(storage_key)).exists()

    def resolve_path(self, storage_key: str) -> Path:
        root = self.storage_root.resolve()
        path = (root / storage_key).resolve()
        if root != path and root not in path.parents:
            raise ValueError("storage_key resolves outside STORAGE_ROOT")
        return path


def normalize_url_prefix(value: str) -> str:
    prefix = value.strip() or "/static"
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return prefix.rstrip("/") or "/static"


def normalize_storage_key(value: str) -> str:
    key = value.replace("\\", "/").strip().lstrip("/")
    parts = [part for part in key.split("/") if part and part not in {".", ".."}]
    if not parts:
        raise ValueError("storage_key must not be empty")
    return "/".join(parts)
