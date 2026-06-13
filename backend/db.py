from __future__ import annotations

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/name_from_satellite",
)


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    with SessionLocal() as db:
        db.execute(text("select 1")).scalar()


def readable_database_error(error: BaseException) -> str:
    if isinstance(error, UnicodeDecodeError):
        decoded = decode_driver_error(error)
        if decoded:
            return f"database connection failed: {decoded}. Check DATABASE_URL in .env."
        return "database connection failed. Check DATABASE_URL in .env."
    return str(error)


def decode_driver_error(error: UnicodeDecodeError) -> str | None:
    raw = error.object
    if not isinstance(raw, bytes):
        return None
    for encoding in ("utf-8", "cp1251", "cp1252"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()
