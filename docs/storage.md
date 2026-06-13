# Storage

Image storage is accessed through a storage service, not direct filesystem writes from route code.

## Environment

```text
STORAGE_BACKEND=local
STORAGE_ROOT=data/uploads
STATIC_URL_PREFIX=/static
PUBLIC_BASE_URL=
MAX_UPLOAD_BYTES=5242880
```

Supabase mode:

```text
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_BUCKET=letter-images
PUBLIC_BASE_URL=
MAX_UPLOAD_BYTES=5242880
```

Docker Compose uses:

```text
STORAGE_ROOT=/app/data/uploads
```

and mounts the named Docker volume `uploads_data` at that path.

## Local Storage

For development and Docker, use:

```text
STORAGE_BACKEND=local
```

Example storage key:

```text
letters/A/upload_abc.png
```

Local development file:

```text
data/uploads/letters/A/upload_abc.png
```

Docker file inside the backend container:

```text
/app/data/uploads/letters/A/upload_abc.png
```

Public URL:

```text
/static/letters/A/upload_abc.png
```

FastAPI mounts `STORAGE_ROOT` at `STATIC_URL_PREFIX` when the local backend is active.

## Supabase Storage

For Koyeb or another container host, use:

```text
STORAGE_BACKEND=supabase
```

The storage backend uploads image bytes to:

```text
{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_key}
```

The app keeps the same relative key structure:

```text
letters/A/upload_abc.png
```

Default public URL:

```text
{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/letters/A/upload_abc.png
```

For the current MVP, make the Supabase bucket public so generated word images can load directly in the frontend. The service role key is used only by the backend for uploads/deletes and must be stored as a secret environment variable, not in git.

If `PUBLIC_BASE_URL` is set in Supabase mode, the app returns:

```text
{PUBLIC_BASE_URL}/{storage_key}
```

Use that only when a custom public CDN/base URL is configured for the bucket.

## Database References

The database stores:

```text
storage_key
public_url
image_path
```

`storage_key` and `public_url` are the deployment-safe references. `image_path` is currently kept for compatibility/debugging and should not be treated as the source of truth.

The app does not require absolute machine-specific filesystem paths in Postgres.

## Docker Persistence

`docker-compose.yml` mounts:

```text
uploads_data:/app/data/uploads
```

This means uploaded images survive:

- backend container restart
- `docker compose down`
- `docker compose up`

Uploaded images are deleted only when the named volume is removed, for example:

```powershell
docker compose down -v
```

## Future Object Storage

Object storage beyond Supabase Storage is out of scope for the current MVP. The storage factory can later add backends such as S3 or Vercel Blob while keeping the same interface:

```text
save_file(file_bytes, storage_key, content_type)
delete_file(storage_key)
get_public_url(storage_key)
exists(storage_key)
```

Do not store object-storage credentials in the database. Configure them through environment variables if that backend is implemented later.
