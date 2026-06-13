from __future__ import annotations

import json
import string
from pathlib import Path

from PIL import Image, ImageFilter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "templates"
APPROVED_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "approved"
CANDIDATES_PATH = PROJECT_ROOT / "backend" / "data" / "candidates.json"


def create_demo_patch(template_path: Path) -> Image.Image:
    image = Image.open(template_path).convert("L")
    image = image.rotate(0.8, resample=Image.Resampling.BICUBIC, fillcolor="white")
    image = image.filter(ImageFilter.GaussianBlur(radius=0.25))
    return image


def main() -> None:
    APPROVED_PATCH_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)

    candidates = []
    for letter in string.ascii_uppercase:
        template_path = TEMPLATE_DIR / f"{letter}.png"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Missing template {template_path}. Run scripts/01_generate_letter_templates.py first."
            )

        candidate_id = f"demo_{letter}_001"
        patch_filename = f"{candidate_id}.png"
        patch_path = APPROVED_PATCH_DIR / patch_filename
        create_demo_patch(template_path).save(patch_path)

        candidates.append(
            {
                "id": candidate_id,
                "letter": letter,
                "status": "approved",
                "score": 0.95,
                "image_path": f"data/patches/approved/{patch_filename}",
                "region": "Demo",
                "source_type": "template-demo",
            }
        )

    with CANDIDATES_PATH.open("w", encoding="utf-8") as file:
        json.dump(candidates, file, indent=2)
        file.write("\n")

    print(f"Generated {len(candidates)} demo candidates in {CANDIDATES_PATH}")


if __name__ == "__main__":
    main()
