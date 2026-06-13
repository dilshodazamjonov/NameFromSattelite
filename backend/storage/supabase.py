from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from backend.storage.base import StoredFile
from backend.storage.local import normalize_storage_key


class SupabaseStorage:
    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        bucket: str,
        public_base_url: str | None = None,
    ) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key.strip()
        self.bucket = bucket.strip().strip("/")
        self.public_base_url = (public_base_url or "").rstrip("/")

        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is required when STORAGE_BACKEND=supabase")
        if not self.service_role_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required when STORAGE_BACKEND=supabase")
        if not self.bucket:
            raise ValueError("SUPABASE_BUCKET is required when STORAGE_BACKEND=supabase")

    def save_file(
        self,
        file_bytes: bytes,
        storage_key: str,
        content_type: str | None = None,
    ) -> StoredFile:
        safe_key = normalize_storage_key(storage_key)
        url = self.object_url(safe_key)
        request = urllib.request.Request(
            url,
            data=file_bytes,
            method="POST",
            headers={
                **self.auth_headers(),
                "Content-Type": content_type or "application/octet-stream",
                "Cache-Control": "3600",
                "x-upsert": "true",
            },
        )
        self.open_request(request)
        return StoredFile(
            storage_key=safe_key,
            public_url=self.get_public_url(safe_key),
            size_bytes=len(file_bytes),
            content_type=content_type,
        )

    def delete_file(self, storage_key: str) -> bool:
        safe_key = normalize_storage_key(storage_key)
        payload = json.dumps({"prefixes": [safe_key]}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.supabase_url}/storage/v1/object/{urllib.parse.quote(self.bucket, safe='')}",
            data=payload,
            method="DELETE",
            headers={
                **self.auth_headers(),
                "Content-Type": "application/json",
            },
        )
        try:
            self.open_request(request)
        except ValueError as error:
            if "404" in str(error):
                return False
            raise
        return True

    def get_public_url(self, storage_key: str) -> str:
        safe_key = normalize_storage_key(storage_key)
        if self.public_base_url:
            return f"{self.public_base_url}/{safe_key}"
        quoted_bucket = urllib.parse.quote(self.bucket, safe="")
        quoted_key = urllib.parse.quote(safe_key, safe="/")
        return f"{self.supabase_url}/storage/v1/object/public/{quoted_bucket}/{quoted_key}"

    def exists(self, storage_key: str) -> bool:
        safe_key = normalize_storage_key(storage_key)
        request = urllib.request.Request(
            self.object_url(safe_key),
            method="HEAD",
            headers=self.auth_headers(),
        )
        try:
            self.open_request(request)
        except ValueError as error:
            if "404" in str(error):
                return False
            raise
        return True

    def object_url(self, storage_key: str) -> str:
        quoted_bucket = urllib.parse.quote(self.bucket, safe="")
        quoted_key = urllib.parse.quote(storage_key, safe="/")
        return f"{self.supabase_url}/storage/v1/object/{quoted_bucket}/{quoted_key}"

    def auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
        }

    def open_request(self, request: urllib.request.Request) -> bytes:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise ValueError(f"Supabase Storage request failed with HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise ValueError(f"Supabase Storage request failed: {error.reason}") from error
