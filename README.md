---
title: NameFromSatellite
emoji: 🛰️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# NameFromSatellite

Manual satellite-letter image collection and word generation.

NameFromSatellite is a small FastAPI pet project. A user manually uploads a clean satellite/aerial crop, labels it with one letter, and later the app generates short words by randomly selecting saved images for each requested character.

The manual label is the source of truth. The current MVP does not try to classify letters automatically.

## MVP Scope

- manual upload, drop, or paste of a clean satellite/aerial crop
- manual one-letter label from `A-Z`
- optional place, coordinate, and note metadata
- local image storage for development or Supabase Storage for free cloud deployment
- Postgres metadata storage
- word generation up to 7 letters
- clickable Google Maps links for generated images that have saved coordinates
- accepted upload formats: `jpg`, `jpeg`, `png`, `webp`
- default max upload size: 5 MB

## Out Of Scope

- automatic classification
- ML model training
- imagery scraping or downloading
- approve/reject workflows
- S3, MinIO, or object storage beyond the Supabase Storage backend
- user accounts, admin auth, roles, or permissions
- Kubernetes, nginx, CI/CD, Celery, Redis, or advanced infrastructure

Legacy classifier and candidate scripts are still present as experiments, but they are not the main product flow.

## Upload Rules

Only upload images that you have the right to use.

Uploaded images should be clean satellite/aerial crops and must not include:

- place labels or road labels
- pins or markers
- map icons
- UI controls
- watermarks
- browser chrome
- commercial map tile overlays

Do not scrape or download imagery from Google Maps, Google Earth, Yandex, Bing, or commercial map/satellite tile services.

See [docs/data_policy.md](docs/data_policy.md).

## Docker Compose Deployment

Start Docker Desktop first.

Build and start the backend plus Postgres:

```powershell
docker compose up --build
```

By default, Compose exposes the app at `127.0.0.1:18010` to avoid Windows machines where common ports such as `8000` or `8010` are reserved or blocked. To use another host port, set `HOST_PORT` before starting Compose.

In another terminal, confirm the backend can connect to Postgres:

```powershell
docker compose exec backend python scripts/check_db.py
```

Create or update database tables:

```powershell
docker compose exec backend python scripts/init_db.py
```

Open the app:

```text
http://localhost:18010/
```

Health check:

```text
http://localhost:18010/health
```

Stop containers without deleting data:

```powershell
docker compose down
```

Restart later:

```powershell
docker compose up
```

Reset all Docker data, including Postgres rows and uploaded images:

```powershell
docker compose down -v
```

The Compose stack uses named volumes:

```text
postgres_data -> Postgres database files
uploads_data  -> /app/data/uploads inside the backend container
```

Uploaded images survive container restarts because `uploads_data` is mounted at `STORAGE_ROOT=/app/data/uploads`.

## Docker Environment

`docker-compose.yml` sets:

```text
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/name_from_satellite
HOST_PORT=18010
STORAGE_BACKEND=local
STORAGE_ROOT=/app/data/uploads
STATIC_URL_PREFIX=/static
PUBLIC_BASE_URL=
MAX_UPLOAD_BYTES=5242880
REVERSE_GEOCODER_ENABLED=false
```

The Postgres password in `docker-compose.yml` is for local Docker deployment only. Change it before exposing the database outside your machine.

## Free Cloud Deployment: Hugging Face Spaces + Supabase

Free deployment architecture:

```text
Hugging Face Spaces -> Dockerized FastAPI backend
Supabase Free       -> Postgres metadata database
Supabase Storage    -> uploaded satellite-letter images
```

For cloud deployment, use `STORAGE_BACKEND=supabase`. Do not store uploads only inside the Hugging Face container filesystem; Space containers can restart/rebuild, so user uploads must live in Supabase Storage.

Setup:

1. Create a Supabase project.
2. Create a Supabase Storage bucket named `letter-images`.
3. Make the bucket public for the current implementation, because the app stores public image URLs for the frontend.
4. Copy the Supabase Postgres connection string into `DATABASE_URL`.
5. Copy `SUPABASE_URL`.
6. Copy `SUPABASE_SERVICE_ROLE_KEY`.
7. Push the repo to the Hugging Face Space repository.
8. Keep this README front matter set to `sdk: docker` and `app_port: 7860`.
9. Set the Hugging Face Space secrets/environment variables listed below.
10. Run `python scripts/check_db.py` in the Space terminal or Docker shell.
11. Run `python scripts/init_db.py` in the Space terminal or Docker shell.
12. Open deployed `/health`.
13. Upload an image.
14. Generate a word.
15. Click `Open map` on a generated tile that has coordinates.
16. Rebuild/restart the Space and confirm the uploaded image still loads.

Hugging Face Space environment variables/secrets:

```text
DATABASE_URL=
STORAGE_BACKEND=supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_BUCKET=letter-images
PUBLIC_BASE_URL=
MAX_UPLOAD_BYTES=5242880
REVERSE_GEOCODER_ENABLED=false
```

The Dockerfile defaults to Hugging Face's configured app port:

```text
python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers
```

Push an update to an existing Hugging Face Space repo:

```powershell
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
git push hf main
```

If the `hf` remote already exists:

```powershell
git push hf main
```

After the Space rebuilds, open:

```text
https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
```

Then check:

```text
/health
/letters
/upload
```

## Local Development Without Docker

Create the database in your local Postgres:

```powershell
createdb -U postgres name_from_satellite
```

Create a local `.env` file:

```text
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/name_from_satellite
STORAGE_BACKEND=local
STORAGE_ROOT=data/uploads
STATIC_URL_PREFIX=/static
PUBLIC_BASE_URL=
MAX_UPLOAD_BYTES=5242880
REVERSE_GEOCODER_ENABLED=true
REVERSE_GEOCODER_URL=https://nominatim.openstreetmap.org/reverse
REVERSE_GEOCODER_USER_AGENT="NameFromSatellite/0.1 local-development"
REVERSE_GEOCODER_TIMEOUT=4
```

`.env` is ignored by git. `.env.example` is committed as a template.

Install dependencies:

```powershell
pip install -r requirements.txt
```

Check the database connection and create tables:

```powershell
python scripts/check_db.py
python scripts/init_db.py
```

Start the app:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://localhost:8000/
```

Do not use `--reload` for the current upload workflow. The app writes uploads inside the project folder, and the reload watcher can restart or fail while files are being written.

## Current API

Main endpoints:

```text
GET  /health
POST /api/places
GET  /api/places
POST /api/letters/images
GET  /api/letters/images
POST /api/words/generate
```

Frontend routes:

```text
/letters
/upload
```

Root `/` redirects to `/letters`.

Compatibility aliases kept for old callers:

```text
POST /api/letter-images
GET  /api/letter-images
POST /api/generate-word
POST /generate
```

See [docs/api_plan.md](docs/api_plan.md).

`POST /api/words/generate` returns optional `latitude` and `longitude` for generated images that have linked place coordinates. The frontend makes those generated images clickable and also shows an `Open map` link:

```text
https://www.google.com/maps?q={latitude},{longitude}
```

## Storage

Saved image example:

```text
storage_key = letters/O/upload_abc123.png
image_path = letters/O/upload_abc123.png
public_url = /static/letters/O/upload_abc123.png
```

Local file:

```text
data/uploads/letters/O/upload_abc123.png
```

Supabase storage example:

```text
storage_key = letters/O/upload_abc123.png
public_url = https://your-project.supabase.co/storage/v1/object/public/letter-images/letters/O/upload_abc123.png
```

The database stores deployable relative storage keys and public URLs, not absolute local filesystem paths. In local Docker, `/app/data/uploads` is backed by the `uploads_data` volume. In Hugging Face/Supabase mode, uploaded bytes go to Supabase Storage.

See [docs/storage.md](docs/storage.md).

## Main Data Model

Postgres tables:

```text
places
letter_images
```

Main concepts:

- `place`: optional reusable location metadata
- `letter_image`: one uploaded image manually labeled as one letter
- `generated_word`: generated dynamically from saved letter images and not stored yet

If the upload form receives coordinate text like `41 deg 18'59.32"N 69 deg 17'56.05"E`, the backend parses it into decimal `latitude` and `longitude` on the `places` row. When reverse geocoding is enabled, it also tries to fill `country`, `region`, and `city`.

## Manual QA Checklist

- Start the app with Docker Compose.
- Open `/health` and confirm `status = ok`.
- Run `docker compose exec backend python scripts/check_db.py`.
- Run `docker compose exec backend python scripts/init_db.py`.
- Upload a valid `jpg`, `jpeg`, `png`, or `webp` image.
- Try uploading a non-image file and confirm it is rejected.
- Try an invalid letter and confirm it is rejected.
- Generate a short word such as `AZ`.
- Generate a 7-letter word.
- Generate a word containing a letter with no saved images and confirm the missing-letter response is clear.
- Generate a word using an image with coordinates and confirm `Open map` opens Google Maps.
- Restart containers with `docker compose restart`.
- Confirm the previously uploaded image still loads from `/static/...`.

## Supabase QA Checklist

- Set `STORAGE_BACKEND=supabase`.
- Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_BUCKET`.
- Run `python scripts/check_db.py`.
- Run `python scripts/init_db.py`.
- Upload a valid image.
- Confirm the file appears in the Supabase Storage bucket.
- Confirm the database row stores a relative `storage_key` and usable `public_url`.
- Generate a word and confirm image URLs load.
- Click `Open map` on a generated image with coordinates and confirm Google Maps opens.
- Restart or redeploy the backend and confirm images still work.

## Legacy Code

The repo still contains older classifier/candidate experiments:

- `backend/services/classification_service.py`
- `backend/services/patch_service.py`
- `/api/classify-upload`, `/api/classify-roi`, `/api/candidate-decision`
- `scripts/01_*` through `scripts/07_*`
- `backend/data/candidates.json`
- `backend/data/pending_patches.json`
- `data/patches/`, `data/templates/`, `data/processed/`

These are not the main project flow now. They are kept as optional experiments/reference code until they can be safely moved to `scripts/legacy/` or removed in a dedicated cleanup pass.
