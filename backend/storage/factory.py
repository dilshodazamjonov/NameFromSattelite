from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from backend.services.patch_service import PROJECT_ROOT
from backend.storage.base import StorageService
from backend.storage.local import LocalStorage
from backend.storage.supabase import SupabaseStorage


load_dotenv()


def storage_root_path() -> Path:
    configured = Path(os.getenv("STORAGE_ROOT", "data/uploads"))
    if configured.is_absolute():
        return configured
    return PROJECT_ROOT / configured


def static_url_prefix() -> str:
    return os.getenv("STATIC_URL_PREFIX", "/static").rstrip("/") or "/static"


def storage_backend() -> str:
    return os.getenv("STORAGE_BACKEND", "local").strip().lower()


@lru_cache(maxsize=1)
def get_storage() -> StorageService:
    backend = storage_backend()
    if backend == "local":
        return LocalStorage(
            storage_root=storage_root_path(),
            static_url_prefix=static_url_prefix(),
            public_base_url=os.getenv("PUBLIC_BASE_URL"),
        )

    if backend == "supabase":
        return SupabaseStorage(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
            bucket=os.getenv("SUPABASE_BUCKET", ""),
            public_base_url=os.getenv("PUBLIC_BASE_URL"),
        )

    # Future backends can be wired here, for example S3 or Vercel Blob.
    raise ValueError(f"unsupported STORAGE_BACKEND: {backend}")
