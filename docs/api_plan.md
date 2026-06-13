# API Plan

The main metadata source for the MVP is Postgres. Images are stored through the storage service, using local filesystem storage for development/Docker or Supabase Storage for cloud deployment.

## Health

### GET /health

Checks:

- app is alive
- database connection works
- configured storage can write, read, and delete a small health file

Example response:

```json
{
  "status": "ok",
  "checks": {
    "app": {"status": "ok"},
    "database": {"status": "ok"},
    "storage": {"status": "ok"}
  }
}
```

## Places

### POST /api/places

Create reusable place/location metadata.

Input:

```json
{
  "name": "Pakhtakor Central Stadium",
  "country": "Uzbekistan",
  "region": "Tashkent",
  "city": "Tashkent",
  "latitude": 41.0,
  "longitude": 69.0,
  "note": "optional"
}
```

### GET /api/places

List saved places.

## Letter Images

### POST /api/letters/images

Create one manually labeled letter image.

Input:

```text
multipart/form-data
image: jpg/jpeg/png/webp file
letter: A-Z
place_id: optional
note: optional text
beauty_score: optional integer 1-5
readability_score: optional integer 1-5
location: optional text
```

If `location` is supplied without `place_id`, the backend creates a simple `places` row and links it through `place_id`.

If `location` is coordinate text like `41 deg 18'59.32"N 69 deg 17'56.05"E`, the backend parses it into decimal `latitude` and `longitude` on the created `places` row. If reverse geocoding is enabled, it also tries to fill `country`, `region`, and `city`.

Behavior:

- allow only `jpg`, `jpeg`, `png`, or `webp`
- validate uploaded file is actually readable as an image
- enforce configured max upload size, default 5 MB
- validate `letter` is exactly one A-Z character
- normalize saved image to PNG
- save under `{STORAGE_ROOT}/letters/{LETTER}/{IMAGE_ID}.png`
- store relative `storage_key`, compatibility `image_path`, and `public_url`
- insert a Postgres `letter_images` row
- return the saved record

`public_url` is `/static/...` in local mode and a Supabase Storage public URL in Supabase mode.

Example response:

```json
{
  "id": "upload_abcd1234",
  "letter": "O",
  "original_filename": "stadium_o.png",
  "storage_key": "letters/O/upload_abcd1234.png",
  "image_path": "letters/O/upload_abcd1234.png",
  "public_url": "/static/letters/O/upload_abcd1234.png",
  "source_type": "manual_satellite",
  "place_id": "place_abcd",
  "note": "manual crop",
  "location": "Pakhtakor Central Stadium",
  "beauty_score": null,
  "readability_score": null,
  "created_at": "2026-06-12T12:00:00"
}
```

### GET /api/letters/images

List saved letter images.

Optional query params:

```text
letter=A
place_id=place_...
```

Behavior:

- return saved image metadata from Postgres
- include `public_url`
- never require absolute filesystem paths

## Words

### POST /api/words/generate

Generate a word from saved letter images.

Input:

```json
{
  "word": "AZIZ"
}
```

Behavior:

- uppercase and validate the word
- allow only A-Z
- max length 7
- split into characters
- randomly select one saved image for each letter
- allow repeated letters to select independently
- return `status = "complete"` if every letter has an image
- return `status = "incomplete"` and `missing_letters` if any requested letter is missing

Example complete response:

```json
{
  "word": "AZIZ",
  "status": "complete",
  "letters": [
    {
      "letter": "A",
      "image_id": "upload_a1",
      "public_url": "/static/letters/A/upload_a1.png",
      "place_id": "place_1",
      "location": "Pakhtakor Central Stadium"
    }
  ],
  "missing_letters": [],
  "message": "Generated word from saved letter images."
}
```

Example incomplete response:

```json
{
  "word": "AZIZ",
  "status": "incomplete",
  "letters": [
    {
      "letter": "A",
      "image_id": "upload_a1",
      "public_url": "/static/letters/A/upload_a1.png",
      "place_id": null,
      "location": null
    }
  ],
  "missing_letters": ["Z"],
  "message": "Missing images for: Z"
}
```

## Compatibility Endpoints

Kept for old callers:

```text
POST /api/letter-images  -> same as POST /api/letters/images
GET  /api/letter-images  -> same as GET /api/letters/images
POST /api/generate-word  -> same as POST /api/words/generate
POST /generate           -> Postgres-backed legacy response shape
```

Legacy classifier/candidate endpoints remain available but are not part of the target MVP API:

```text
POST /api/classify-upload
POST /api/classify-roi
POST /api/candidate-decision
```
