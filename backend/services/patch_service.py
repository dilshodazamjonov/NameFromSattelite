from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANDIDATES_PATH = PROJECT_ROOT / "backend" / "data" / "candidates.json"
PATCHES_DIR = PROJECT_ROOT / "data" / "patches"
APPROVED_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "approved"


def load_candidates(path: Path = CANDIDATES_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        raise ValueError("candidates.json must contain a list of candidate records")
    return data


def approved_candidates_for_letter(letter: str) -> list[dict[str, Any]]:
    candidates = load_candidates()
    filtered = []
    for candidate in candidates:
        if candidate.get("status") == "approved" and candidate.get("final_letter") == letter:
            filtered.append(candidate)

    return sorted(filtered, key=candidate_rank, reverse=True)


def select_candidate_for_letter(letter: str) -> dict[str, Any] | None:
    candidates = approved_candidates_for_letter(letter)
    return candidates[0] if candidates else None


def image_url_for_candidate(candidate: dict[str, Any]) -> str:
    image_path = Path(candidate["image_path"])
    try:
        relative_path = image_path.relative_to("data/patches")
        return f"/patches/{relative_path.as_posix()}"
    except ValueError:
        return f"/patches/approved/{image_path.name}"


def candidate_score(candidate: dict[str, Any]) -> float:
    score = candidate.get("score")
    if score is None:
        score = candidate.get("template_score")
    if score is None:
        score = candidate.get("auto_score")
    return float(score or 0)


def candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, float]:
    beauty = int(candidate.get("beauty_score") or 0)
    readability = int(candidate.get("readability_score") or 0)
    return beauty, readability, candidate_score(candidate)
