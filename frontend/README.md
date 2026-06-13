# Frontend

The frontend is a simple static app served by FastAPI.

Routes:

- `/letters`: public word generation page
- `/upload`: manual letter-image upload page

Canonical APIs used by the frontend:

- `POST /api/words/generate`
- `POST /api/letters/images`
- `GET /api/letters/images`
- `GET /api/places`

The frontend does not call legacy classifier or compatibility endpoints.
