from datetime import datetime

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=7)


class GeneratedLetter(BaseModel):
    letter: str
    patch_id: str
    image_url: str
    score: float | None = None
    region: str | None = None
    source_type: str | None = None
    beauty_score: int | None = None
    readability_score: int | None = None


class GenerateResponse(BaseModel):
    word: str
    status: str
    letters: list[GeneratedLetter]
    missing_letters: list[str] = []


class PlaceCreate(BaseModel):
    name: str = Field(..., min_length=1)
    country: str = "Uzbekistan"
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    note: str | None = None


class PlaceResponse(BaseModel):
    id: str
    name: str
    country: str = "Uzbekistan"
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    note: str | None = None
    created_at: datetime


class LetterImageResponse(BaseModel):
    id: str
    letter: str
    original_filename: str | None = None
    storage_key: str
    image_path: str
    public_url: str
    source_type: str = "manual_satellite"
    place_id: str | None = None
    note: str | None = None
    location: str | None = None
    beauty_score: int | None = None
    readability_score: int | None = None
    created_at: datetime


class WordImageLetter(BaseModel):
    letter: str
    image_id: str
    public_url: str
    place_id: str | None = None
    location: str | None = None


class GenerateWordResponse(BaseModel):
    word: str
    status: str
    letters: list[WordImageLetter]
    missing_letters: list[str] = []
    message: str | None = None


class LetterPrediction(BaseModel):
    letter: str
    score: float


class ClassifyUploadResponse(BaseModel):
    id: str
    original_filename: str
    image_url: str
    processed_image_url: str
    predicted_letter: str | None
    top_predictions: list[LetterPrediction]
    top_score: float
    confidence_margin: float
    is_ambiguous: bool
    needs_review: bool
    message: str
    classification_status: str | None = None
    selected_crop_url: str | None = None


class ClassifyRoiRequest(BaseModel):
    image_id: str
    x: float
    y: float
    width: float
    height: float


class CandidateDecisionRequest(BaseModel):
    image_id: str
    action: str
    final_letter: str | None = None
    beauty_score: int | None = Field(default=None, ge=1, le=5)
    readability_score: int | None = Field(default=None, ge=1, le=5)
