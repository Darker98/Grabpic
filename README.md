# Grabpic

A facial recognition-powered photo retrieval system for large-scale events. Instead of manual tagging, Grabpic automatically groups event photos by face and lets attendees retrieve every photo they appear in using a single selfie — no account, no login, no manual search.

---

## How it works

### Ingestion (admin side)

1. An admin uploads a batch of event photos via `POST /admin/upload`
2. Each image is stored in a Supabase storage bucket
3. A job is enqueued per image on a Redis Stream (`grabpic:ingest`)
4. A background worker consumes the queue, downloads each image, and runs face detection
5. For every face detected, a 512-dimensional embedding is generated and compared against existing embeddings in pgvector
6. If the cosine similarity exceeds the threshold (default 0.82), the face is assigned an existing `grab_id` — otherwise a new one is minted
7. The embedding and the image-to-face mapping are written to the database

### Retrieval (user side)

1. A user uploads a selfie via `POST /auth/selfie`
2. The server extracts the face embedding from the selfie in memory — the selfie is never stored
3. A cosine ANN search runs against pgvector to find the closest matching `grab_id`
4. On match, a short-lived auth token is issued and stored in Redis keyed to the `grab_id`
5. The user calls `GET /images` with the token
6. The server resolves the token to a `grab_id`, queries all images that contain that face, and returns presigned Supabase URLs
7. Image bytes never pass through the API server — clients fetch directly from Supabase's CDN

---

## Architecture

```
┌─────────────┐     multipart      ┌──────────────────┐
│   Frontend  │ ─────────────────► │   FastAPI (API)  │
│  index.html │ ◄──────────────── │      Railway      │
└─────────────┘   presigned URLs   └────────┬─────────┘
                                            │
                          ┌─────────────────┼──────────────────┐
                          │                 │                  │
                    ┌─────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
                    │  Supabase  │  │  Supabase DB │  │    Redis     │
                    │  Storage   │  │  (pgvector)  │  │   Streams    │
                    │   Bucket   │  │  PostgreSQL  │  │  + Token TTL │
                    └────────────┘  └──────────────┘  └───────┬──────┘
                                                              │
                                                    ┌─────────▼────────┐
                                                    │  Worker Process  │
                                                    │  InsightFace +   │
                                                    │  Face Embeddings │
                                                    └──────────────────┘
```

---

## Stack

| Layer | Technology | Purpose |
|---|---|---|
| API framework | FastAPI 0.111 | Async HTTP endpoints |
| Face recognition | InsightFace 0.7.3 + buffalo_sc | Face detection and 512-d embedding generation |
| Inference runtime | ONNX Runtime 1.17.3 (CPU) | Model execution |
| Vector search | pgvector 0.2.5 | Cosine ANN search for face matching |
| Database ORM | SQLAlchemy 2.0 + asyncpg | Async PostgreSQL access |
| Database host | Supabase (PostgreSQL) | Managed Postgres with pgvector extension |
| Object storage | Supabase Storage (S3-compatible) | Image storage and presigned URL generation |
| Storage client | boto3 1.34 | S3-compatible bucket access |
| Message queue | Redis Streams | Async image ingestion job queue |
| Auth cache | Redis (key-value) | Short-lived token → grab_id mapping |
| Rate limiting | slowapi 0.1.9 | Per-IP rate limiting on selfie endpoint |
| Validation | Pydantic v2 | Request/response schema validation |
| Image validation | Pillow 10.3 | JPEG/PNG format verification |
| Deployment | Railway | Cloud hosting via Docker |
| Frontend | Vanilla HTML/CSS/JS | Single-file UI, no build step |

---

## Endpoints

### `POST /admin/upload`
Upload event photos. Requires `X-Admin-Key` header.

- Validates each file (JPEG/PNG, max 20MB)
- Uploads to Supabase bucket
- Enqueues a face processing job per image on Redis Streams
- Returns 202 immediately — processing is asynchronous

### `POST /auth/selfie`
Authenticate with a selfie to receive an access token.

- Extracts face embedding from the uploaded selfie in memory
- Runs cosine ANN search against all indexed face embeddings
- Returns a `tok_` prefixed token on match (similarity ≥ 0.82)
- Selfie is never persisted to storage
- Rate limited: 10 requests per IP per 10 minutes

### `GET /images`
Fetch all photos containing the authenticated face.

- Validates Bearer token against Redis
- Resolves token to internal `grab_id`
- Returns paginated presigned Supabase URLs (default 20 per page)
- Supports `page` and `limit` query params

---

## Database schema

```sql
images
  id          UUID  PK
  bucket_key  VARCHAR     -- path in Supabase bucket
  ingested_at TIMESTAMPTZ
  taken_at    TIMESTAMPTZ

face_embeddings
  id            UUID  PK
  grab_id       VARCHAR   -- internal identity token per unique face
  embedding     vector(512)
  image_id      UUID  FK → images.id
  bbox          JSON      -- {x1, y1, x2, y2}
  quality_score FLOAT
  created_at    TIMESTAMPTZ

image_face_mappings
  id         UUID  PK
  image_id   UUID  FK → images.id
  grab_id    VARCHAR
  created_at TIMESTAMPTZ
```

---

## Running locally

### Prerequisites

- Python 3.11
- Docker Desktop (for Redis)
- A Supabase project with a storage bucket and pgvector enabled

### Setup

```bash
# Clone and create virtualenv
git clone https://github.com/your-username/grabpic.git
cd grabpic
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
```

Enable pgvector on Supabase (run once in the SQL editor):

```sql
create extension if not exists vector;
```

Start Redis locally:

```bash
docker run -d --name grabpic-redis -p 6379:6379 redis:7-alpine
```

### Start the API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Start the worker (separate terminal)

```bash
python -m app.worker
```

### Open the frontend

Open `frontend/index.html` directly in your browser.

---

## Environment variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `SUPABASE_BUCKET` | Storage bucket name |
| `SUPABASE_S3_ENDPOINT` | S3-compatible endpoint for boto3 |
| `SUPABASE_S3_ACCESS_KEY` | S3 access key (from Supabase Storage settings) |
| `SUPABASE_S3_SECRET_KEY` | S3 secret key |
| `SUPABASE_S3_REGION` | S3 region (e.g. `ap-southeast-1`) |
| `DATABASE_URL` | asyncpg DSN: `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection URL |
| `ADMIN_API_KEY` | Secret key for admin upload endpoint |
| `FACE_SIMILARITY_THRESHOLD` | Cosine similarity cutoff (default `0.82`) |
| `TOKEN_TTL_SECONDS` | Auth token lifetime in seconds (default `3600`) |
| `WORKER_NAME` | Consumer name for Redis Streams (default `worker-1`) |

---

## Deployment

The project deploys as two separate services from the same Docker image:

| Service | Start command |
|---|---|
| API | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Worker | `python -m app.worker` |

A `render.yaml` is included for one-click Railway deployment. For Redis in production, [Upstash](https://upstash.com) provides a free managed Redis instance.

The Dockerfile pre-downloads the InsightFace `buffalo_sc` model at build time so containers start instantly without fetching ~300MB at runtime.

---

## Key design decisions

**Selfies are never stored.** The uploaded image is decoded into an embedding in memory and immediately discarded. This avoids building a biometric database of users and simplifies privacy compliance.

**Tokens, not grab_ids, cross the wire.** Users never see their internal `grab_id`. Tokens are opaque strings stored in Redis with a TTL, meaning they can be expired server-side without affecting the identity record.

**Asynchronous ingestion.** The admin upload endpoint returns immediately after enqueuing jobs. Face processing happens in the background worker, which means uploads are fast regardless of batch size and the worker can scale horizontally by running multiple instances consuming the same Redis Stream consumer group.

**Presigned URLs, not proxied bytes.** The `/images` endpoint returns short-lived URLs pointing directly at Supabase's CDN. Image bytes never pass through the API server, keeping Railway/Render instances stateless and bandwidth costs low.
