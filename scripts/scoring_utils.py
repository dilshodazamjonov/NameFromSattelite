from __future__ import annotations

import string
from pathlib import Path

import cv2
import numpy as np


IMAGE_SIZE = 256


def load_grayscale(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return cv2.resize(image, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_AREA)


def normalized_mse_similarity(patch: np.ndarray, template: np.ndarray) -> float:
    patch_float = patch.astype(np.float32)
    template_float = template.astype(np.float32)
    mse = np.mean((patch_float - template_float) ** 2)
    similarity = 1.0 - (mse / (255.0**2))
    return float(max(0.0, min(1.0, similarity)))


def score_patch(patch_path: Path, template_dir: Path, method: str = "mse") -> dict[str, float]:
    patch = load_grayscale(patch_path)
    scores: dict[str, float] = {}

    for letter in string.ascii_uppercase:
        template_path = template_dir / f"{letter}.png"
        if not template_path.exists():
            continue
        template = load_grayscale(template_path)
        if method == "edge":
            scores[letter] = edge_similarity(patch, template)
        else:
            scores[letter] = normalized_mse_similarity(patch, template)

    return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))


def edge_similarity(patch: np.ndarray, template: np.ndarray) -> float:
    patch_edges = cv2.Canny(cv2.equalizeHist(patch), 70, 170)
    template_mask = cv2.threshold(template, 180, 255, cv2.THRESH_BINARY_INV)[1]
    template_edges = cv2.Canny(template_mask, 50, 150)

    kernel = np.ones((5, 5), np.uint8)
    patch_edges = cv2.dilate(patch_edges, kernel, iterations=1)
    template_edges = cv2.dilate(template_edges, kernel, iterations=1)

    patch_binary = patch_edges > 0
    template_binary = template_edges > 0
    intersection = np.logical_and(patch_binary, template_binary).sum()
    union = np.logical_or(patch_binary, template_binary).sum()
    if union == 0:
        return 0.0

    edge_density = patch_binary.mean()
    density_penalty = max(0.2, 1.0 - abs(edge_density - 0.30) / 0.50)
    return float((intersection / union) * density_penalty)
