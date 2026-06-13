from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        raise SystemExit(1)

    safe_url = make_url(database_url).render_as_string(hide_password=True)
    print(f"DATABASE_URL={safe_url}")

    from backend.db import check_database_connection, readable_database_error

    try:
        check_database_connection()
    except Exception as error:
        print(readable_database_error(error))
        raise SystemExit(1) from error
    print("Database connection OK.")

    check_storage_environment()


def check_storage_environment() -> None:
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    print(f"STORAGE_BACKEND={backend}")

    if backend == "local":
        storage_root = Path(os.getenv("STORAGE_ROOT", "data/uploads"))
        if not storage_root.is_absolute():
            storage_root = PROJECT_ROOT / storage_root
        storage_root.mkdir(parents=True, exist_ok=True)
        probe = storage_root / ".storage_check"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as error:
            print(f"Local storage is not writable: {storage_root}")
            raise SystemExit(1) from error
        print(f"Local storage root OK: {storage_root}")
        return

    if backend == "supabase":
        required = [
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_BUCKET",
        ]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            print(f"Missing Supabase env vars: {', '.join(missing)}")
            raise SystemExit(1)
        print("Supabase storage env OK.")
        print(f"SUPABASE_URL={mask_url(os.getenv('SUPABASE_URL', ''))}")
        print(f"SUPABASE_BUCKET={os.getenv('SUPABASE_BUCKET')}")
        print("SUPABASE_SERVICE_ROLE_KEY is set.")
        return

    print(f"Unsupported STORAGE_BACKEND: {backend}")
    raise SystemExit(1)


def mask_url(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = make_url(value)
    except Exception:
        return value.split("?")[0]
    return parsed.render_as_string(hide_password=True)


if __name__ == "__main__":
    main()
