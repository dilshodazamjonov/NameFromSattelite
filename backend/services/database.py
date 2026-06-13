from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "app.db"


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_images (
                id TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL,
                saved_filename TEXT NOT NULL,
                original_path TEXT NOT NULL,
                processed_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                predicted_letter TEXT,
                top_predictions_json TEXT NOT NULL,
                top_score REAL NOT NULL,
                confidence_margin REAL NOT NULL,
                is_ambiguous INTEGER NOT NULL,
                needs_review INTEGER NOT NULL,
                source_type TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS letter_images (
                id TEXT PRIMARY KEY,
                letter TEXT NOT NULL,
                original_filename TEXT,
                storage_key TEXT NOT NULL,
                image_path TEXT NOT NULL,
                public_url TEXT NOT NULL,
                note TEXT,
                location TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source_type TEXT DEFAULT 'manual_satellite',
                beauty_score INTEGER,
                readability_score INTEGER
            )
            """
        )
        ensure_columns(
            connection,
            "letter_images",
            {
                "location": "TEXT",
            },
        )
        ensure_columns(
            connection,
            "uploaded_images",
            {
                "crop_image_path": "TEXT",
                "processed_crop_path": "TEXT",
                "roi_x": "REAL",
                "roi_y": "REAL",
                "roi_width": "REAL",
                "roi_height": "REAL",
                "classification_status": "TEXT",
                "final_letter": "TEXT",
                "status": "TEXT NOT NULL DEFAULT 'uploaded'",
                "beauty_score": "INTEGER",
                "readability_score": "INTEGER",
                "decision_at": "TEXT",
            },
        )
        connection.commit()


def ensure_columns(connection: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    existing_columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
