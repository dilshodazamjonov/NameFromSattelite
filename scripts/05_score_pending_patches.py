from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scoring_utils import score_patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "templates"
PENDING_METADATA_PATH = PROJECT_ROOT / "backend" / "data" / "pending_patches.json"
CANDIDATES_PATH = PROJECT_ROOT / "backend" / "data" / "candidates.json"


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    return data


def save_json_list(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)
        file.write("\n")


def score_pending_patches(top_n: int, method: str) -> list[dict[str, Any]]:
    pending_patches = load_json_list(PENDING_METADATA_PATH)
    if not pending_patches:
        raise RuntimeError(f"No pending patches found in {PENDING_METADATA_PATH}")

    candidate_records: list[dict[str, Any]] = []
    for patch in pending_patches:
        patch_path = PROJECT_ROOT / patch["image_path"]
        scores = score_patch(patch_path, TEMPLATE_DIR, method=method)
        if not scores:
            raise RuntimeError(f"No templates found in {TEMPLATE_DIR}")

        top_scores = dict(list(scores.items())[:top_n])
        candidate_letter, score = next(iter(top_scores.items()))

        candidate_records.append(
            {
                "id": patch["id"],
                "candidate_letter": candidate_letter,
                "status": "pending",
                "score": score,
                "template_score": score,
                "scoring_method": method,
                "top_scores": top_scores,
                "image_path": patch["image_path"],
                "latitude": patch.get("latitude"),
                "longitude": patch.get("longitude"),
                "source_type": patch.get("source_type", "osm-vector"),
            }
        )

    return candidate_records


def merge_candidates(new_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = load_json_list(CANDIDATES_PATH)
    by_id = {record.get("id"): record for record in existing if record.get("id")}
    for record in new_records:
        by_id[record["id"]] = record
    return list(by_id.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Score pending patch images against A-Z templates.")
    parser.add_argument("--top-n", type=int, default=3, help="Number of top letter scores to keep per patch.")
    parser.add_argument(
        "--method",
        choices=["mse", "edge"],
        default="edge",
        help="Use edge scoring by default for satellite imagery.",
    )
    args = parser.parse_args()

    if args.top_n < 1:
        raise ValueError("--top-n must be at least 1")

    new_records = score_pending_patches(args.top_n, args.method)
    merged_records = merge_candidates(new_records)
    save_json_list(CANDIDATES_PATH, merged_records)
    print(f"Scored {len(new_records)} pending patches")
    print(f"Updated {CANDIDATES_PATH} with {len(merged_records)} total candidates")


if __name__ == "__main__":
    main()
