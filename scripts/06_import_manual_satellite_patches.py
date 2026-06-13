from __future__ import annotations

import argparse
import json
import re
import string
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_MANUAL_DIR = PROJECT_ROOT / "data" / "raw" / "manual_satellite"
PENDING_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "pending"
CANDIDATES_PATH = PROJECT_ROOT / "backend" / "data" / "candidates.json"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
MIN_IMAGE_SIDE = 256
MAX_DISPLAY_SIDE = 1024


def load_candidates() -> list[dict[str, Any]]:
    if not CANDIDATES_PATH.exists():
        return []
    with CANDIDATES_PATH.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{CANDIDATES_PATH} must contain a JSON list")
    return data


def save_candidates(records: list[dict[str, Any]]) -> None:
    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATES_PATH.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)
        file.write("\n")


def candidate_id_for_source(path: Path) -> str:
    safe_stem = re.sub(r"[^A-Za-z0-9]+", "_", path.stem).strip("_")
    return f"manual_{safe_stem}"


def candidate_letter_from_filename(path: Path) -> str:
    if not path.stem:
        raise ValueError("filename is empty")
    letter = path.stem[0].upper()
    if letter not in string.ascii_uppercase:
        raise ValueError("filename must start with A-Z candidate letter")
    return letter


def validate_and_write_display_image(source_path: Path, output_path: Path) -> tuple[int, int]:
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        width, height = image.size
        if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
            raise ValueError(f"image is too small: {width}x{height}; minimum side is {MIN_IMAGE_SIDE}px")

        image = image.convert("RGB")
        image.thumbnail((MAX_DISPLAY_SIDE, MAX_DISPLAY_SIDE), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")
        return width, height


def import_manual_patches(clear_existing_manual: bool = False) -> list[dict[str, Any]]:
    RAW_MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_PATCH_DIR.mkdir(parents=True, exist_ok=True)

    if clear_existing_manual:
        for image_path in PENDING_PATCH_DIR.glob("manual_*.png"):
            image_path.unlink()

    records = load_candidates()
    by_id = {record.get("id"): record for record in records if record.get("id")}

    imported: list[dict[str, Any]] = []
    for source_path in sorted(RAW_MANUAL_DIR.iterdir()):
        if not source_path.is_file() or source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        candidate_id = candidate_id_for_source(source_path)
        candidate_letter = candidate_letter_from_filename(source_path)
        output_path = PENDING_PATCH_DIR / f"{candidate_id}.png"
        original_width, original_height = validate_and_write_display_image(source_path, output_path)

        record = {
            "id": candidate_id,
            "candidate_letter": candidate_letter,
            "final_letter": None,
            "status": "pending",
            "score": None,
            "image_path": f"data/patches/pending/{output_path.name}",
            "region": "Unknown",
            "source_type": "manual_satellite",
            "source_note": "manual high-res crop, not scraped",
            "latitude": None,
            "longitude": None,
            "beauty_score": None,
            "readability_score": None,
            "source_file": f"data/raw/manual_satellite/{source_path.name}",
            "original_width": original_width,
            "original_height": original_height,
        }
        by_id[candidate_id] = record
        imported.append(record)

    save_candidates(list(by_id.values()))
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Import manually provided high-res satellite/aerial crops.")
    parser.add_argument(
        "--clear-existing-manual",
        action="store_true",
        help="Delete old manual pending PNGs before importing.",
    )
    args = parser.parse_args()

    imported = import_manual_patches(clear_existing_manual=args.clear_existing_manual)
    print(f"Imported {len(imported)} manual satellite candidates from {RAW_MANUAL_DIR}")
    print(f"Updated {CANDIDATES_PATH}")


if __name__ == "__main__":
    main()
