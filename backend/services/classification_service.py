from __future__ import annotations

import json
import shutil
import string
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from backend.services.database import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_MANUAL_DIR = PROJECT_ROOT / "data" / "raw" / "manual_satellite"
PROCESSED_MANUAL_DIR = PROJECT_ROOT / "data" / "processed" / "manual_satellite"
PENDING_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "pending"
APPROVED_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "approved"
REJECTED_PATCH_DIR = PROJECT_ROOT / "data" / "patches" / "rejected"
CANDIDATES_PATH = PROJECT_ROOT / "backend" / "data" / "candidates.json"
TEMPLATE_DIR = PROJECT_ROOT / "data" / "templates"

IMAGE_SIZE = 256
MIN_IMAGE_SIDE = 96
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MIN_TOP_SCORE = 0.65
MIN_MARGIN = 0.10


@dataclass(frozen=True)
class TemplateVariant:
    letter: str
    mask: np.ndarray
    edges: np.ndarray
    contour: np.ndarray | None
    hog: np.ndarray
    density: float


def classify_uploaded_image(filename: str, content: bytes) -> dict[str, Any]:
    if not content:
        raise ValueError("uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("uploaded file is too large")

    upload_id = f"upload_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    saved_filename = f"{upload_id}.png"
    processed_filename = f"{upload_id}_edges.png"
    original_path = RAW_MANUAL_DIR / saved_filename
    processed_path = PROCESSED_MANUAL_DIR / processed_filename

    image = read_upload_image(content)
    original_width, original_height = image.size
    if original_width < MIN_IMAGE_SIDE or original_height < MIN_IMAGE_SIDE:
        raise ValueError(
            f"image is too small: {original_width}x{original_height}. "
            f"Upload a crop at least {MIN_IMAGE_SIDE}x{MIN_IMAGE_SIDE}px."
        )

    RAW_MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    image.save(original_path, format="PNG")

    normalized = normalize_image_for_classification(image)
    processed_edges = preprocess_edges(normalized)
    save_edge_preview(processed_edges, processed_path)

    top_predictions = classify_edges(processed_edges)
    top_score = top_predictions[0]["score"] if top_predictions else 0.0
    second_score = top_predictions[1]["score"] if len(top_predictions) > 1 else 0.0
    confidence_margin = max(0.0, top_score - second_score)
    status = classification_status(top_score, confidence_margin)
    is_ambiguous = status == "ambiguous"
    predicted_letter = top_predictions[0]["letter"] if status == "suggested" else None

    response = {
        "id": upload_id,
        "original_filename": filename,
        "image_url": f"/static/raw/manual_satellite/{saved_filename}",
        "processed_image_url": f"/static/processed/manual_satellite/{processed_filename}",
        "predicted_letter": predicted_letter,
        "top_predictions": top_predictions,
        "top_score": top_score,
        "confidence_margin": confidence_margin,
        "is_ambiguous": is_ambiguous,
        "needs_review": True,
        "message": "Classification completed.",
        "classification_status": status,
        "selected_crop_url": None,
    }

    store_upload_result(
        upload_id=upload_id,
        original_filename=filename,
        saved_filename=saved_filename,
        original_path=f"data/raw/manual_satellite/{saved_filename}",
        processed_path=f"data/processed/manual_satellite/{processed_filename}",
        predicted_letter=predicted_letter,
        top_predictions=top_predictions,
        top_score=top_score,
        confidence_margin=confidence_margin,
        is_ambiguous=is_ambiguous,
    )
    return response


def read_upload_image(content: bytes) -> Image.Image:
    try:
        from io import BytesIO

        image = Image.open(BytesIO(content))
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except UnidentifiedImageError as error:
        raise ValueError("uploaded file is not a readable image") from error


def normalize_image_for_classification(image: Image.Image) -> np.ndarray:
    image = ImageOps.fit(image, (IMAGE_SIZE, IMAGE_SIZE), method=Image.Resampling.LANCZOS)
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    normalized = clahe.apply(gray)
    return cv2.GaussianBlur(normalized, (3, 3), 0)


def preprocess_edges(gray: np.ndarray) -> np.ndarray:
    edges = cv2.Canny(gray, 60, 160)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
    return edges


def remove_tiny_components(edges: np.ndarray, min_area: int = 18) -> np.ndarray:
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(edges, connectivity=8)
    cleaned = np.zeros_like(edges)
    for label in range(1, component_count):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            cleaned[labels == label] = 255
    return cleaned


def save_edge_preview(edges: np.ndarray, output_path: Path) -> None:
    preview = 255 - edges
    Image.fromarray(preview).save(output_path, format="PNG")


def classify_edges(upload_edges: np.ndarray) -> list[dict[str, float | str]]:
    variants = load_template_variants()
    upload_binary = cv2.dilate(upload_edges, np.ones((5, 5), np.uint8), iterations=1) > 0
    upload_contour = largest_contour(upload_binary.astype(np.uint8) * 255)
    upload_density = float(upload_binary.mean())

    best_by_letter: dict[str, float] = {}
    for variant in variants:
        score = hybrid_similarity(upload_binary, upload_contour, upload_density, variant)
        best_by_letter[variant.letter] = max(score, best_by_letter.get(variant.letter, 0.0))

    ranked = sorted(best_by_letter.items(), key=lambda item: item[1], reverse=True)[:5]
    return [{"letter": letter, "score": round(float(score), 4)} for letter, score in ranked]


def hybrid_similarity(
    upload_binary: np.ndarray,
    upload_contour: np.ndarray | None,
    upload_density: float,
    variant: TemplateVariant,
) -> float:
    template_binary = cv2.dilate(variant.edges, np.ones((7, 7), np.uint8), iterations=1) > 0
    intersection = np.logical_and(upload_binary, template_binary).sum()
    union = np.logical_or(upload_binary, template_binary).sum()
    edge_overlap = 0.0 if union == 0 else intersection / union

    density_score = max(0.0, 1.0 - abs(upload_density - variant.density) / 0.35)
    contour_score = contour_similarity(upload_contour, variant.contour)
    hog_score = hog_similarity(upload_binary.astype(np.uint8) * 255, variant.hog)
    cleanliness_score = shape_cleanliness_score(upload_binary)
    raw_score = (
        0.42 * edge_overlap
        + 0.22 * hog_score
        + 0.20 * contour_score
        + 0.10 * density_score
        + 0.06 * cleanliness_score
    )

    # Classical scores on dense aerial imagery are conservative; calibrate to a 0-1 UI scale.
    return float(max(0.0, min(1.0, raw_score * 1.85)))


def hog_similarity(upload_edges: np.ndarray, template_hog: np.ndarray) -> float:
    upload_hog = compute_hog(upload_edges)
    denominator = np.linalg.norm(upload_hog) * np.linalg.norm(template_hog)
    if denominator == 0:
        return 0.0
    similarity = float(np.dot(upload_hog, template_hog) / denominator)
    return max(0.0, min(1.0, (similarity + 1.0) / 2.0))


def compute_hog(image: np.ndarray) -> np.ndarray:
    hog = cv2.HOGDescriptor(
        _winSize=(IMAGE_SIZE, IMAGE_SIZE),
        _blockSize=(32, 32),
        _blockStride=(16, 16),
        _cellSize=(16, 16),
        _nbins=9,
    )
    return hog.compute(cv2.resize(image, (IMAGE_SIZE, IMAGE_SIZE))).flatten()


def shape_cleanliness_score(binary: np.ndarray) -> float:
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (binary.astype(np.uint8) * 255), connectivity=8
    )
    if component_count <= 1:
        return 0.0
    areas = [stats[label, cv2.CC_STAT_AREA] for label in range(1, component_count)]
    total_area = sum(areas)
    if total_area == 0:
        return 0.0
    largest_ratio = max(areas) / total_area
    component_penalty = max(0.0, 1.0 - (len(areas) - 1) / 30.0)
    return float(0.65 * largest_ratio + 0.35 * component_penalty)


def contour_similarity(upload_contour: np.ndarray | None, template_contour: np.ndarray | None) -> float:
    if upload_contour is None or template_contour is None:
        return 0.0
    distance = cv2.matchShapes(upload_contour, template_contour, cv2.CONTOURS_MATCH_I1, 0.0)
    if not np.isfinite(distance):
        return 0.0
    return float(1.0 / (1.0 + min(distance, 10.0)))


def load_template_variants() -> list[TemplateVariant]:
    ensure_base_templates()
    variants: list[TemplateVariant] = []
    for letter in string.ascii_uppercase:
        template_path = TEMPLATE_DIR / f"{letter}.png"
        image = Image.open(template_path).convert("L")
        for angle in (-8, -4, 0, 4, 8):
            rotated = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=255)
            for scale in (0.88, 1.0, 1.12):
                variant_image = scale_template(rotated, scale)
                mask = np.asarray(variant_image)
                binary = cv2.threshold(mask, 180, 255, cv2.THRESH_BINARY_INV)[1]
                edges = cv2.Canny(binary, 50, 150)
                variants.append(
                    TemplateVariant(
                        letter=letter,
                        mask=binary,
                        edges=edges,
                        contour=largest_contour(binary),
                        hog=compute_hog(edges),
                        density=float((edges > 0).mean()),
                    )
                )
    return variants


def scale_template(image: Image.Image, scale: float) -> Image.Image:
    size = max(1, int(IMAGE_SIZE * scale))
    scaled = image.resize((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    x = (IMAGE_SIZE - size) // 2
    y = (IMAGE_SIZE - size) // 2
    canvas.paste(scaled, (x, y))
    return canvas


def largest_contour(binary: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def ensure_base_templates() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(TEMPLATE_DIR.glob("*.png"))
    if len(existing) >= 26:
        return
    for letter in string.ascii_uppercase:
        create_letter_template(letter).save(TEMPLATE_DIR / f"{letter}.png")


def create_letter_template(letter: str) -> Image.Image:
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    draw = ImageDraw.Draw(image)
    font = load_font(190)
    bbox = draw.textbbox((0, 0), letter, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = (IMAGE_SIZE - width) / 2 - bbox[0]
    y = (IMAGE_SIZE - height) / 2 - bbox[1]
    draw.text((x, y), letter, fill=0, font=font)
    return image


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for font_path in candidates:
        path = Path(font_path)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def store_upload_result(
    upload_id: str,
    original_filename: str,
    saved_filename: str,
    original_path: str,
    processed_path: str,
    predicted_letter: str | None,
    top_predictions: list[dict[str, Any]],
    top_score: float,
    confidence_margin: float,
    is_ambiguous: bool,
) -> None:
    uploaded_at = datetime.now(UTC).isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO uploaded_images (
                id,
                original_filename,
                saved_filename,
                original_path,
                processed_path,
                uploaded_at,
                predicted_letter,
                top_predictions_json,
                top_score,
                confidence_margin,
                is_ambiguous,
                needs_review,
                source_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                original_filename,
                saved_filename,
                original_path,
                processed_path,
                uploaded_at,
                predicted_letter,
                json.dumps(top_predictions),
                top_score,
                confidence_margin,
                int(is_ambiguous),
                1,
                "manual_upload",
            ),
        )
        connection.commit()


def classification_status(top_score: float, confidence_margin: float) -> str:
    if top_score < MIN_TOP_SCORE:
        return "weak_match"
    if confidence_margin < MIN_MARGIN:
        return "ambiguous"
    return "suggested"


def get_upload_record(image_id: str) -> Any | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM uploaded_images WHERE id = ?",
            (image_id,),
        ).fetchone()


def normalized_crop_box(
    image_size: tuple[int, int], x: float, y: float, width: float, height: float
) -> tuple[int, int, int, int]:
    image_width, image_height = image_size
    left = max(0, min(image_width - 1, int(round(x))))
    top = max(0, min(image_height - 1, int(round(y))))
    right = max(left + 1, min(image_width, int(round(x + width))))
    bottom = max(top + 1, min(image_height, int(round(y + height))))
    return left, top, right, bottom


def update_roi_result(
    image_id: str,
    crop_image_path: str,
    processed_crop_path: str,
    crop_box: tuple[int, int, int, int],
    predicted_letter: str | None,
    top_predictions: list[dict[str, Any]],
    top_score: float,
    confidence_margin: float,
    is_ambiguous: bool,
    classification_status_value: str,
) -> None:
    left, top, right, bottom = crop_box
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE uploaded_images
            SET crop_image_path = ?,
                processed_crop_path = ?,
                processed_path = ?,
                roi_x = ?,
                roi_y = ?,
                roi_width = ?,
                roi_height = ?,
                predicted_letter = ?,
                top_predictions_json = ?,
                top_score = ?,
                confidence_margin = ?,
                is_ambiguous = ?,
                needs_review = 1,
                classification_status = ?,
                status = 'pending'
            WHERE id = ?
            """,
            (
                crop_image_path,
                processed_crop_path,
                processed_crop_path,
                left,
                top,
                right - left,
                bottom - top,
                predicted_letter,
                json.dumps(top_predictions),
                top_score,
                confidence_margin,
                int(is_ambiguous),
                classification_status_value,
                image_id,
            ),
        )
        connection.commit()


def validate_final_letter(value: str | None) -> str:
    letter = validate_optional_letter(value)
    if letter is None:
        raise ValueError("final_letter is required when approving")
    return letter


def validate_optional_letter(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    letter = value.strip().upper()
    if len(letter) != 1 or letter not in string.ascii_uppercase:
        raise ValueError("final_letter must be one A-Z letter")
    return letter


def load_candidates_json() -> list[dict[str, Any]]:
    if not CANDIDATES_PATH.exists():
        return []
    content = CANDIDATES_PATH.read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return data


def save_candidates_json(records: list[dict[str, Any]]) -> None:
    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATES_PATH.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)
        file.write("\n")


def upsert_candidate_record(record: dict[str, Any]) -> None:
    records = load_candidates_json()
    by_id = {item.get("id"): item for item in records if item.get("id")}
    by_id[record["id"]] = record
    save_candidates_json(list(by_id.values()))


def classify_roi(image_id: str, x: float, y: float, width: float, height: float) -> dict[str, Any]:
    record = get_upload_record(image_id)
    if record is None:
        raise ValueError(f"uploaded image not found: {image_id}")

    original_path = PROJECT_ROOT / record["original_path"]
    if not original_path.exists():
        raise ValueError(f"original image is missing: {record['original_path']}")

    with Image.open(original_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        crop_box = normalized_crop_box(image.size, x, y, width, height)
        crop = image.crop(crop_box)

    crop_width, crop_height = crop.size
    if crop_width < MIN_IMAGE_SIDE or crop_height < MIN_IMAGE_SIDE:
        raise ValueError(
            f"selected region is too small: {crop_width}x{crop_height}. "
            f"Select at least {MIN_IMAGE_SIDE}x{MIN_IMAGE_SIDE}px."
        )

    PENDING_PATCH_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    crop_filename = f"{image_id}_roi.png"
    processed_filename = f"{image_id}_roi_edges.png"
    crop_path = PENDING_PATCH_DIR / crop_filename
    processed_path = PROCESSED_MANUAL_DIR / processed_filename
    crop.save(crop_path, format="PNG")

    normalized = normalize_image_for_classification(crop)
    processed_edges = preprocess_edges(normalized)
    processed_edges = remove_tiny_components(processed_edges)
    save_edge_preview(processed_edges, processed_path)

    top_predictions = classify_edges(processed_edges)
    top_score = top_predictions[0]["score"] if top_predictions else 0.0
    second_score = top_predictions[1]["score"] if len(top_predictions) > 1 else 0.0
    confidence_margin = max(0.0, top_score - second_score)
    status = classification_status(top_score, confidence_margin)
    predicted_letter = top_predictions[0]["letter"] if status == "suggested" else None

    update_roi_result(
        image_id=image_id,
        crop_image_path=f"data/patches/pending/{crop_filename}",
        processed_crop_path=f"data/processed/manual_satellite/{processed_filename}",
        crop_box=crop_box,
        predicted_letter=predicted_letter,
        top_predictions=top_predictions,
        top_score=top_score,
        confidence_margin=confidence_margin,
        is_ambiguous=status == "ambiguous",
        classification_status_value=status,
    )

    return {
        "id": image_id,
        "original_filename": record["original_filename"],
        "image_url": f"/static/{record['original_path'].removeprefix('data/')}",
        "selected_crop_url": f"/patches/pending/{crop_filename}",
        "processed_image_url": f"/static/processed/manual_satellite/{processed_filename}",
        "predicted_letter": predicted_letter,
        "top_predictions": top_predictions,
        "top_score": top_score,
        "confidence_margin": confidence_margin,
        "is_ambiguous": status == "ambiguous",
        "needs_review": True,
        "classification_status": status,
        "message": "Selected region classified.",
    }


def apply_candidate_decision(
    image_id: str,
    action: str,
    final_letter: str | None,
    beauty_score: int | None,
    readability_score: int | None,
) -> dict[str, Any]:
    action = action.lower().strip()
    if action not in {"approve", "reject"}:
        raise ValueError("action must be approve or reject")

    record = get_upload_record(image_id)
    if record is None:
        raise ValueError(f"uploaded image not found: {image_id}")
    if not record["crop_image_path"]:
        raise ValueError("classify a selected region before approving or rejecting")

    if action == "approve":
        final_letter = validate_final_letter(final_letter)
        target_dir = APPROVED_PATCH_DIR
        status = "approved"
    else:
        target_dir = REJECTED_PATCH_DIR
        status = "rejected"
        final_letter = validate_optional_letter(final_letter)

    target_dir.mkdir(parents=True, exist_ok=True)
    source_crop_path = PROJECT_ROOT / record["crop_image_path"]
    if not source_crop_path.exists():
        raise ValueError(f"selected crop image is missing: {record['crop_image_path']}")

    target_path = target_dir / source_crop_path.name
    if source_crop_path.resolve() != target_path.resolve():
        shutil.copy2(source_crop_path, target_path)

    crop_image_path = f"data/patches/{target_dir.name}/{target_path.name}"
    decision_at = datetime.now(UTC).isoformat(timespec="seconds")
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE uploaded_images
            SET status = ?,
                final_letter = ?,
                crop_image_path = ?,
                beauty_score = ?,
                readability_score = ?,
                decision_at = ?,
                needs_review = 0
            WHERE id = ?
            """,
            (
                status,
                final_letter,
                crop_image_path,
                beauty_score,
                readability_score,
                decision_at,
                image_id,
            ),
        )
        connection.commit()

    if status == "approved":
        upsert_candidate_record(
            {
                "id": image_id,
                "candidate_letter": record["predicted_letter"],
                "final_letter": final_letter,
                "status": "approved",
                "score": record["top_score"],
                "image_path": crop_image_path,
                "crop_image_path": crop_image_path,
                "original_image_path": record["original_path"],
                "processed_crop_path": record["processed_crop_path"],
                "top_predictions_json": record["top_predictions_json"],
                "region": "Unknown",
                "source_type": "manual_upload_roi",
                "source_note": "human-confirmed selected satellite/aerial crop",
                "latitude": None,
                "longitude": None,
                "beauty_score": beauty_score,
                "readability_score": readability_score,
            }
        )
    else:
        upsert_candidate_record(
            {
                "id": image_id,
                "candidate_letter": record["predicted_letter"],
                "final_letter": final_letter,
                "status": "rejected",
                "score": record["top_score"],
                "image_path": crop_image_path,
                "crop_image_path": crop_image_path,
                "original_image_path": record["original_path"],
                "processed_crop_path": record["processed_crop_path"],
                "top_predictions_json": record["top_predictions_json"],
                "region": "Unknown",
                "source_type": "manual_upload_roi",
                "source_note": "human-rejected selected satellite/aerial crop",
                "latitude": None,
                "longitude": None,
                "beauty_score": beauty_score,
                "readability_score": readability_score,
            }
        )

    return {
        "id": image_id,
        "status": status,
        "final_letter": final_letter,
        "crop_image_url": f"/patches/{target_dir.name}/{target_path.name}",
        "message": f"Candidate {status}.",
    }
