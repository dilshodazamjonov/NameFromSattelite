import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.db import check_database_connection, get_db, readable_database_error
from backend.models import (
    CandidateDecisionRequest,
    ClassifyRoiRequest,
    ClassifyUploadResponse,
    GenerateRequest,
    GenerateResponse,
    GenerateWordResponse,
    GeneratedLetter,
    LetterImageResponse,
    PlaceCreate,
    PlaceResponse,
)
from backend.services.classification_service import (
    apply_candidate_decision,
    classify_roi,
    classify_uploaded_image,
)
from backend.services.database import init_database
from backend.services.letter_image_service import (
    create_place,
    generate_word_from_letter_images,
    list_letter_images,
    list_places,
    save_letter_image,
)
from backend.services.patch_service import (
    PATCHES_DIR,
    PROJECT_ROOT,
)
from backend.storage import get_storage, static_url_prefix, storage_backend, storage_root_path


app = FastAPI(title="satellite-alphabet-uz")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STORAGE_DIR = storage_root_path()
STATIC_URL_PREFIX = static_url_prefix()

init_database()
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
PATCHES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/patches", StaticFiles(directory=PATCHES_DIR), name="patches")
if storage_backend() == "local":
    app.mount(STATIC_URL_PREFIX, StaticFiles(directory=STORAGE_DIR), name="static")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/health")
def health() -> JSONResponse:
    checks: dict[str, dict[str, str]] = {
        "app": {"status": "ok"},
        "database": {"status": "ok"},
        "storage": {"status": "ok"},
    }

    try:
        check_database_connection()
    except Exception as error:
        checks["database"] = {
            "status": "error",
            "detail": readable_database_error(error),
        }

    health_key = f"_health/{uuid.uuid4().hex}.txt"
    try:
        
        storage = get_storage()
        stored = storage.save_file(
            file_bytes=b"ok",
            storage_key=health_key,
            content_type="text/plain",
        )
        if not storage.exists(stored.storage_key):
            raise RuntimeError("health check file was not readable after write")
        storage.delete_file(stored.storage_key)
    except Exception as error:
        checks["storage"] = {
            "status": "error",
            "detail": str(error),
        }

    status = "ok" if all(check["status"] == "ok" for check in checks.values()) else "error"
    return JSONResponse(
        status_code=200 if status == "ok" else 503,
        content={"status": status, "checks": checks},
    )


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/letters", status_code=307)


@app.get("/letters")
def letters_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/upload")
def upload_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/places", response_model=PlaceResponse)
def create_place_endpoint(payload: PlaceCreate, db: Session = Depends(get_db)) -> PlaceResponse:
    try:
        result = create_place(db, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=readable_database_error(error)) from error
    return PlaceResponse(**result)


@app.get("/api/places", response_model=list[PlaceResponse])
def get_places(db: Session = Depends(get_db)) -> list[PlaceResponse]:
    try:
        return [PlaceResponse(**record) for record in list_places(db)]
    except Exception as error:
        raise HTTPException(status_code=500, detail=readable_database_error(error)) from error


@app.post("/api/letters/images", response_model=LetterImageResponse)
async def create_letter_image_target(
    image: UploadFile = File(...),
    letter: str = Form(...),
    place_id: str | None = Form(default=None),
    note: str | None = Form(default=None),
    beauty_score: int | None = Form(default=None),
    readability_score: int | None = Form(default=None),
    location: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> LetterImageResponse:
    return await create_letter_image_record(
        db=db,
        image=image,
        letter=letter,
        place_id=place_id,
        note=note,
        beauty_score=beauty_score,
        readability_score=readability_score,
        location=location,
    )


@app.post("/api/letter-images", response_model=LetterImageResponse)
async def create_letter_image_compat(
    image: UploadFile = File(...),
    letter: str = Form(...),
    place_id: str | None = Form(default=None),
    note: str | None = Form(default=None),
    beauty_score: int | None = Form(default=None),
    readability_score: int | None = Form(default=None),
    location: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> LetterImageResponse:
    return await create_letter_image_record(
        db=db,
        image=image,
        letter=letter,
        place_id=place_id,
        note=note,
        beauty_score=beauty_score,
        readability_score=readability_score,
        location=location,
    )


async def create_letter_image_record(
    db: Session,
    image: UploadFile,
    letter: str,
    place_id: str | None,
    note: str | None,
    beauty_score: int | None,
    readability_score: int | None,
    location: str | None,
) -> LetterImageResponse:
    try:
        content = await image.read()
        result = save_letter_image(
            db=db,
            filename=image.filename,
            content=content,
            letter=letter,
            place_id=place_id,
            note=note,
            beauty_score=beauty_score,
            readability_score=readability_score,
            content_type=image.content_type,
            location=location,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"image save failed: {readable_database_error(error)}") from error

    return LetterImageResponse(**result)


@app.get("/api/letters/images", response_model=list[LetterImageResponse])
def get_letter_images_target(
    letter: str | None = Query(default=None),
    place_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[LetterImageResponse]:
    try:
        records = list_letter_images(db, letter=letter, place_id=place_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=readable_database_error(error)) from error
    return [LetterImageResponse(**record) for record in records]


@app.get("/api/letter-images", response_model=list[LetterImageResponse])
def get_letter_images_compat(
    letter: str | None = Query(default=None),
    place_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[LetterImageResponse]:
    return get_letter_images_target(letter=letter, place_id=place_id, db=db)


@app.post("/api/words/generate", response_model=GenerateWordResponse)
def generate_word_target(request: GenerateRequest, db: Session = Depends(get_db)) -> GenerateWordResponse:
    try:
        result = generate_word_from_letter_images(db, request.word)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=readable_database_error(error)) from error
    return GenerateWordResponse(**result)


@app.post("/api/generate-word", response_model=GenerateWordResponse)
def generate_word_compat(request: GenerateRequest, db: Session = Depends(get_db)) -> GenerateWordResponse:
    return generate_word_target(request=request, db=db)


@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    try:
        result = generate_word_from_letter_images(db, request.word)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=readable_database_error(error)) from error

    selected_letters = [
        GeneratedLetter(
            letter=item["letter"],
            patch_id=item["image_id"],
            image_url=item["public_url"],
            source_type="manual_satellite",
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
        )
        for item in result["letters"]
    ]
    return GenerateResponse(
        word=result["word"],
        status=result["status"],
        letters=selected_letters,
        missing_letters=result["missing_letters"],
    )


@app.post("/api/classify-upload", response_model=ClassifyUploadResponse)
async def classify_upload(file: UploadFile = File(...)) -> ClassifyUploadResponse:
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="uploaded file must be an image")

    try:
        content = await file.read()
        result = classify_uploaded_image(file.filename or "upload.png", content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"classification failed: {error}") from error

    return ClassifyUploadResponse(**result)


@app.post("/api/classify-roi", response_model=ClassifyUploadResponse)
def classify_selected_region(request: ClassifyRoiRequest) -> ClassifyUploadResponse:
    try:
        result = classify_roi(
            image_id=request.image_id,
            x=request.x,
            y=request.y,
            width=request.width,
            height=request.height,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"ROI classification failed: {error}") from error

    return ClassifyUploadResponse(**result)


@app.post("/api/candidate-decision")
def candidate_decision(request: CandidateDecisionRequest) -> dict[str, object]:
    try:
        return apply_candidate_decision(
            image_id=request.image_id,
            action=request.action,
            final_letter=request.final_letter,
            beauty_score=request.beauty_score,
            readability_score=request.readability_score,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
