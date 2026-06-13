from __future__ import annotations

import argparse
import json
from pathlib import Path

from scoring_utils import score_patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "templates"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score one patch image against A-Z templates.")
    parser.add_argument("patch", type=Path, help="Path to a patch image.")
    parser.add_argument("--method", choices=["mse", "edge"], default="mse", help="Similarity method to use.")
    args = parser.parse_args()

    scores = score_patch(args.patch, TEMPLATE_DIR, method=args.method)
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
