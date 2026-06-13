from __future__ import annotations

import argparse
import json
import os
import shutil
import string
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = PROJECT_ROOT / "backend" / "data" / "candidates.json"
APPROVED_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "approved"
REJECTED_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "rejected"


def load_candidates() -> list[dict[str, Any]]:
    if not CANDIDATES_PATH.exists():
        return []
    with CANDIDATES_PATH.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{CANDIDATES_PATH} must contain a JSON list")
    return data


def save_candidates(records: list[dict[str, Any]]) -> None:
    with CANDIDATES_PATH.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)
        file.write("\n")


def open_image(path: Path) -> None:
    if not path.exists():
        print(f"Image missing: {path}")
        return

    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as error:
        print(f"Could not open image automatically: {error}")
        print(f"Open manually: {path}")


def prompt_action() -> str:
    while True:
        action = input("Action [a=approve, r=reject, s=skip, c=change final letter]: ").strip().lower()
        if action in {"a", "approve", "r", "reject", "s", "skip", "c", "change"}:
            return action[0]
        print("Please enter a, r, s, or c.")


def prompt_letter(default: str | None) -> str:
    prompt = f"Final letter [{default}]: " if default else "Final letter A-Z: "
    while True:
        value = input(prompt).strip().upper()
        if not value and default:
            return default
        if len(value) == 1 and value in string.ascii_uppercase:
            return value
        print("Please enter one A-Z letter.")


def prompt_score(label: str, default: int | None = None) -> int | None:
    prompt = f"{label} 1-5 [{default or 'blank'}]: "
    while True:
        value = input(prompt).strip()
        if not value:
            return default
        if value.isdigit() and 1 <= int(value) <= 5:
            return int(value)
        print("Please enter 1, 2, 3, 4, 5, or blank.")


def copy_to_status_dir(record: dict[str, Any], target_dir: Path) -> str:
    source_path = PROJECT_ROOT / record["image_path"]
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    if source_path.resolve() != target_path.resolve():
        shutil.copy2(source_path, target_path)
    return f"data/patches/{target_dir.name}/{target_path.name}"


def review_candidates(open_images: bool) -> None:
    records = load_candidates()
    pending = [record for record in records if record.get("status") == "pending"]
    if not pending:
        print("No pending candidates to review.")
        return

    for record in pending:
        image_path = PROJECT_ROOT / record["image_path"]
        print("\n---")
        print(f"id: {record.get('id')}")
        print(f"candidate_letter: {record.get('candidate_letter')}")
        print(f"image_path: {record.get('image_path')}")
        print(f"source_type: {record.get('source_type')}")

        if open_images:
            open_image(image_path)

        action = prompt_action()
        if action == "s":
            continue

        default_letter = (record.get("final_letter") or record.get("candidate_letter") or "").upper()
        if action == "c":
            final_letter = prompt_letter(default_letter if default_letter in string.ascii_uppercase else None)
            action = prompt_action()
            if action == "s":
                record["final_letter"] = final_letter
                continue
        else:
            final_letter = prompt_letter(default_letter if default_letter in string.ascii_uppercase else None)

        if action == "a":
            record["status"] = "approved"
            record["final_letter"] = final_letter
            record["beauty_score"] = prompt_score("beauty_score", record.get("beauty_score"))
            record["readability_score"] = prompt_score("readability_score", record.get("readability_score"))
            record["image_path"] = copy_to_status_dir(record, APPROVED_PATCH_DIR)
        elif action == "r":
            record["status"] = "rejected"
            record["final_letter"] = final_letter
            record["beauty_score"] = prompt_score("beauty_score", record.get("beauty_score"))
            record["readability_score"] = prompt_score("readability_score", record.get("readability_score"))
            record["image_path"] = copy_to_status_dir(record, REJECTED_PATCH_DIR)

        save_candidates(records)
        print(f"Saved {record.get('id')} as {record.get('status')}")

    save_candidates(records)
    print(f"\nReview complete. Updated {CANDIDATES_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review pending patch candidates from candidates.json.")
    parser.add_argument("--no-open", action="store_true", help="Do not try to open each image automatically.")
    args = parser.parse_args()
    review_candidates(open_images=not args.no_open)


if __name__ == "__main__":
    main()
