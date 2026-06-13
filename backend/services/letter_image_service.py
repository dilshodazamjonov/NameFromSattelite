from __future__ import annotations

import json
import os
import re
import string
import urllib.parse
import urllib.request
import uuid
from io import BytesIO
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.db_models import LetterImage, Place
from backend.services.word_service import normalize_word, split_letters
from backend.storage import get_storage


DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES)))
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
REVERSE_GEOCODER_ENABLED = os.getenv("REVERSE_GEOCODER_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
REVERSE_GEOCODER_URL = os.getenv(
    "REVERSE_GEOCODER_URL",
    "https://nominatim.openstreetmap.org/reverse",
)
REVERSE_GEOCODER_USER_AGENT = os.getenv(
    "REVERSE_GEOCODER_USER_AGENT",
    "NameFromSatellite/0.1 local-development",
)
REVERSE_GEOCODER_TIMEOUT = float(os.getenv("REVERSE_GEOCODER_TIMEOUT", "4"))

COORDINATE_PATTERN = re.compile(
    r"""
    (?P<degrees>\d+(?:\.\d+)?)\s*(?:°|º|\?|deg|d)?\s*
    (?P<minutes>\d+(?:\.\d+)?)?\s*(?:'|’|min|m)?\s*
    (?P<seconds>\d+(?:\.\d+)?)?\s*(?:"|”|sec|s)?\s*
    (?P<hemisphere>[NSEW])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def validate_letter(value: str) -> str:
    letter = value.strip().upper()
    if len(letter) != 1 or letter not in string.ascii_uppercase:
        raise ValueError("letter must be one A-Z character")
    return letter


def save_letter_image(
    db: Session,
    filename: str | None,
    content: bytes,
    letter: str,
    place_id: str | None,
    note: str | None,
    beauty_score: int | None,
    readability_score: int | None,
    content_type: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    if not content:
        raise ValueError("uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        max_mb = MAX_UPLOAD_BYTES / (1024 * 1024)
        raise ValueError(f"uploaded file is too large; max size is {max_mb:g} MB")

    validate_upload_metadata(filename, content_type)
    final_letter = validate_letter(letter)
    final_place = resolve_place(db, place_id, location)
    final_beauty_score = validate_optional_score(beauty_score, "beauty_score")
    final_readability_score = validate_optional_score(readability_score, "readability_score")
    image = read_image(content)

    image_id = f"upload_{uuid.uuid4().hex}"
    storage_key = f"letters/{final_letter}/{image_id}.png"
    image_bytes = image_to_png_bytes(image)
    stored_file = get_storage().save_file(
        file_bytes=image_bytes,
        storage_key=storage_key,
        content_type="image/png",
    )

    record = LetterImage(
        id=image_id,
        letter=final_letter,
        original_filename=sanitize_original_filename(filename),
        storage_key=stored_file.storage_key,
        image_path=stored_file.storage_key,
        public_url=stored_file.public_url,
        source_type="manual_satellite",
        place_id=final_place.id if final_place else None,
        note=clean_optional_text(note),
        beauty_score=final_beauty_score,
        readability_score=final_readability_score,
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        get_storage().delete_file(stored_file.storage_key)
        raise
    db.refresh(record)
    if final_place is not None:
        record.place = final_place
    return letter_image_to_dict(record)


def validate_upload_metadata(filename: str | None, content_type: str | None) -> None:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise ValueError(f"unsupported image extension; use one of: {allowed}")

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError("unsupported image type; use JPG, PNG, or WEBP")


def read_image(content: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(content))
        image.verify()
        image = Image.open(BytesIO(content))
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except UnidentifiedImageError as error:
        raise ValueError("uploaded file is not a readable image") from error
    except OSError as error:
        raise ValueError("uploaded file is not a readable image") from error


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def sanitize_original_filename(filename: str | None) -> str:
    value = (filename or "upload.png").replace("\\", "/").split("/")[-1].strip()
    if not value:
        return "upload.png"
    sanitized = re.sub(r"[^A-Za-z0-9._ -]+", "_", value)
    sanitized = sanitized.strip(" .")
    return sanitized or "upload.png"


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def validate_optional_score(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if value < 1 or value > 5:
        raise ValueError(f"{field_name} must be between 1 and 5")
    return value


def resolve_place(db: Session, place_id: str | None, location: str | None) -> Place | None:
    clean_place_id = clean_optional_text(place_id)
    if clean_place_id:
        place = db.get(Place, clean_place_id)
        if place is None:
            raise ValueError(f"place not found: {clean_place_id}")
        return place

    clean_location = clean_optional_text(location)
    if not clean_location:
        return None

    coordinates = parse_coordinate_text(clean_location)
    latitude = coordinates[0] if coordinates else None
    longitude = coordinates[1] if coordinates else None
    reverse = reverse_geocode(latitude, longitude) if coordinates else {}
    place = Place(
        id=f"place_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
        name=clean_location,
        country=reverse.get("country") or "Uzbekistan",
        region=reverse.get("region"),
        city=reverse.get("city"),
        latitude=latitude,
        longitude=longitude,
        note="manual location text from upload form",
    )
    db.add(place)
    db.flush()
    return place


def parse_coordinate_text(value: str) -> tuple[float, float] | None:
    latitude: float | None = None
    longitude: float | None = None

    for match in COORDINATE_PATTERN.finditer(value):
        decimal = dms_match_to_decimal(match)
        hemisphere = match.group("hemisphere").upper()
        if hemisphere in {"N", "S"}:
            latitude = decimal
        elif hemisphere in {"E", "W"}:
            longitude = decimal

    if latitude is None or longitude is None:
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def dms_match_to_decimal(match: re.Match[str]) -> float:
    degrees = float(match.group("degrees"))
    minutes = float(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)
    decimal = degrees + minutes / 60 + seconds / 3600
    if match.group("hemisphere").upper() in {"S", "W"}:
        decimal *= -1
    return round(decimal, 7)


def reverse_geocode(latitude: float | None, longitude: float | None) -> dict[str, str | None]:
    if not REVERSE_GEOCODER_ENABLED or latitude is None or longitude is None:
        return {}

    query = urllib.parse.urlencode(
        {
            "format": "jsonv2",
            "lat": latitude,
            "lon": longitude,
            "addressdetails": 1,
            "zoom": 10,
            "accept-language": "en",
        }
    )
    request = urllib.request.Request(
        f"{REVERSE_GEOCODER_URL}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": REVERSE_GEOCODER_USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=REVERSE_GEOCODER_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}

    address = payload.get("address") if isinstance(payload, dict) else {}
    if not isinstance(address, dict):
        return {}

    region = first_present(
        address,
        "state",
        "region",
        "state_district",
        "county",
    )
    city = first_present(
        address,
        "city",
        "town",
        "municipality",
        "village",
        "city_district",
    )

    return {
        "country": address.get("country"),
        "region": region or city,
        "city": city,
    }


def first_present(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def list_letter_images(
    db: Session,
    letter: str | None = None,
    place_id: str | None = None,
) -> list[dict[str, Any]]:
    statement = select(LetterImage).options(joinedload(LetterImage.place)).order_by(
        LetterImage.created_at.desc()
    )
    if letter:
        statement = statement.where(LetterImage.letter == validate_letter(letter))
    if place_id:
        statement = statement.where(LetterImage.place_id == place_id)
    records = db.execute(statement).scalars().all()
    return [letter_image_to_dict(record) for record in records]


def generate_word_from_letter_images(db: Session, word: str) -> dict[str, Any]:
    normalized = normalize_word(word)
    selected_letters: list[dict[str, str | None]] = []
    missing_letters: list[str] = []

    for letter in split_letters(normalized):
        image = random_letter_image(db, letter)
        if image is None:
            if letter not in missing_letters:
                missing_letters.append(letter)
            continue
        selected_letters.append(
            {
                "letter": letter,
                "image_id": image.id,
                "public_url": image.public_url,
                "place_id": image.place_id,
                "location": place_location(image.place),
            }
        )

    if missing_letters:
        message = f"Missing images for: {', '.join(missing_letters)}"
    else:
        message = "Generated word from saved letter images."

    return {
        "word": normalized,
        "status": "complete" if not missing_letters else "incomplete",
        "letters": selected_letters,
        "missing_letters": missing_letters,
        "message": message,
    }


def random_letter_image(db: Session, letter: str) -> LetterImage | None:
    rows = (
        db.execute(
            select(LetterImage)
            .options(joinedload(LetterImage.place))
            .where(LetterImage.letter == letter)
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    import random

    return random.choice(rows)


def create_place(db: Session, payload: Any) -> dict[str, Any]:
    place = Place(
        id=f"place_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
        name=payload.name.strip(),
        country=(payload.country or "Uzbekistan").strip() or "Uzbekistan",
        region=clean_optional_text(payload.region),
        city=clean_optional_text(payload.city),
        latitude=payload.latitude,
        longitude=payload.longitude,
        note=clean_optional_text(payload.note),
    )
    db.add(place)
    db.commit()
    db.refresh(place)
    return place_to_dict(place)


def list_places(db: Session) -> list[dict[str, Any]]:
    places = db.execute(select(Place).order_by(Place.created_at.desc())).scalars().all()
    return [place_to_dict(place) for place in places]


def letter_image_to_dict(record: LetterImage) -> dict[str, Any]:
    return {
        "id": record.id,
        "letter": record.letter,
        "original_filename": record.original_filename,
        "storage_key": record.storage_key,
        "image_path": record.image_path,
        "public_url": record.public_url,
        "source_type": record.source_type,
        "place_id": record.place_id,
        "note": record.note,
        "location": place_location(record.place),
        "beauty_score": record.beauty_score,
        "readability_score": record.readability_score,
        "created_at": record.created_at,
    }


def place_to_dict(place: Place) -> dict[str, Any]:
    return {
        "id": place.id,
        "name": place.name,
        "country": place.country,
        "region": place.region,
        "city": place.city,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "note": place.note,
        "created_at": place.created_at,
    }


def place_location(place: Place | None) -> str | None:
    if place is None:
        return None
    if place.latitude is not None and place.longitude is not None:
        return f"{place.latitude}, {place.longitude}"
    return place.name
