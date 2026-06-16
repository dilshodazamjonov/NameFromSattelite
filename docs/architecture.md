# Architecture

## Project Direction

NameFromSatellite is a manual satellite-letter collection and word-generation app.

The MVP flow is:

```text
manual image upload
-> manual A-Z letter label
-> local or Supabase storage for image files
-> Postgres metadata storage
-> random word generation from saved letter images
```

Automatic classification, approve/reject review, model training, and imagery scraping are not part of the main MVP flow.

## Main Entities

### place

Reusable optional location metadata describing where an uploaded satellite/aerial crop came from.

Postgres table:

```text
places
```

Fields:

```text
id
name
country
region
city
latitude
longitude
note
created_at
```

The frontend can submit a selected `place_id` or free-text location/coordinate input. For compatibility, the backend can turn location text into a simple `places` row and link the image through `place_id`.

Coordinate text such as `41 deg 18'59.32"N 69 deg 17'56.05"E` is parsed into decimal coordinates:

```text
latitude = 41.3164778
longitude = 69.2989028
```

When `REVERSE_GEOCODER_ENABLED=true`, the backend makes a best-effort reverse-geocode request to fill `country`, `region`, and `city`. If that request fails, image save still proceeds with the parsed coordinates.

### letter_image

An uploaded satellite/aerial crop manually labeled as one letter.

Postgres table:

```text
letter_images
```

Fields:

```text
id
letter
original_filename
storage_key
image_path
public_url
source_type
place_id
note
beauty_score
readability_score
created_at
```

Images are stored under:

```text
{STORAGE_ROOT}/letters/{LETTER}/{IMAGE_ID}.png
```

Public URLs are returned through:

```text
{STATIC_URL_PREFIX}/letters/{LETTER}/{IMAGE_ID}.png
```

The database stores `storage_key`, compatibility `image_path`, and `public_url`. It does not store image blobs or absolute local filesystem paths.

### generated_word

A generated word is dynamic and is not stored yet.

The backend receives a word, normalizes it to uppercase A-Z, and randomly selects one saved `letter_image` per character. If any character has no images, the response is incomplete and lists `missing_letters`.

When a selected image has linked place coordinates, the generated word response includes `latitude` and `longitude`. The frontend uses those numbers to show an `Open map` link to Google Maps.

## Backend Flows

### Add Letter Image

```text
frontend upload/drop/paste
-> user selects A-Z letter
-> user optionally selects place_id or enters location text/note
-> POST /api/letters/images
-> validate image format, image content, file size, and letter
-> normalize image to PNG
-> save through storage service
-> insert letter_images row in Postgres
-> return public_url and metadata
```

Compatibility alias:

```text
POST /api/letter-images
```

The user-entered letter is the source of truth.

### Add/List Places

```text
POST /api/places
-> validate place payload
-> insert places row in Postgres
-> return saved place

GET /api/places
-> list saved places
```

### Generate Word From Saved Letter Images

```text
POST /api/words/generate
-> normalize word
-> enforce A-Z and max length 7
-> split into letters
-> randomly select one Postgres letter_images row per letter
-> return public_url and optional coordinates for each selected image
```

Compatibility aliases:

```text
POST /api/generate-word
POST /generate
```

If a requested character is missing:

```text
status = incomplete
missing_letters = [...]
message = Missing images for: ...
```

If all characters are available:

```text
status = complete
```

## Deployment Shape

The local Docker deployment uses:

```text
backend service   -> FastAPI app on port 8000
postgres service  -> metadata database
postgres_data     -> persistent database volume
uploads_data      -> persistent upload volume mounted at /app/data/uploads
```

The free cloud deployment target uses:

```text
Hugging Face Spaces -> Dockerized FastAPI backend
Supabase Free       -> Postgres database
Supabase Storage    -> uploaded image files
```

In Supabase mode, the database still stores relative `storage_key` values and public URLs. Uploaded images are not stored only inside the Hugging Face container filesystem.

There is no nginx, Kubernetes, worker queue, ML service, or auth layer in this MVP.

## Legacy/Secondary Parts

The following remain in the repo but are not the primary architecture:

- classifier-first OpenCV logic in `backend/services/classification_service.py`
- legacy SQLite helper/table used by classifier endpoints
- old candidate JSON flow in `backend/data/candidates.json`
- old pending patch JSON flow in `backend/data/pending_patches.json`
- demo/template/candidate scripts in `scripts/`
- `data/templates/`, `data/patches/`, and `data/processed/`

Keep these as optional experiments until a dedicated cleanup can move them to `scripts/legacy/` or remove them safely.
