# JARVIS Backend (initial foundation)

This service adds a private OpenRouter gateway and a small SQLite-backed memory API. It is an optional backend foundation; the Android app is not automatically connected to it yet.

## Features

- Fixed upstream destination (OpenRouter) to avoid arbitrary-URL proxying.
- Server-side provider key; the OpenRouter key never belongs in Android source code.
- Bearer-token authentication for chat and memory endpoints.
- Request size/message-count limits, bounded upstream timeout, generic error responses, and no response caching.
- Persistent SQLite memory records with create/list/delete endpoints.
- Docker image and Render blueprint.

## Run locally

Python 3.11+ recommended:

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set environment variables from `.env.example` in your shell or deployment dashboard (the app intentionally does not auto-load `.env`). Use a randomly generated `JARVIS_CLIENT_TOKEN` of at least 32 characters and your own `OPENROUTER_API_KEY`. Do not commit real credentials.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check `GET /health`. Protected routes require `Authorization: Bearer <JARVIS_CLIENT_TOKEN>`.

### Chat

Send an OpenAI-compatible JSON body to `POST /v1/chat/completions`, including `model` and `messages`. Requests are forwarded to OpenRouter using the server-side key. The provider's free-model router may choose models with different capabilities; vision requests can fail if the selected model does not accept image inputs.

### Memory API

- `GET /v1/memory` — list up to 200 saved notes.
- `POST /v1/memory` with `{"content":"..." }` — save a note (maximum 4,000 characters).
- `DELETE /v1/memory/{id}` — delete a note.

This initial version uses one private memory collection per backend deployment, not separate user accounts. Keep the client token private and do not expose this instance to untrusted users. A shared client token inside a mobile app can be extracted by a determined attacker; before public release, add per-user authentication and quotas or place the API behind an identity provider.

## Deploy with Render

1. Create a new Blueprint from this repository and select `backend/render.yaml`, or create a Docker web service with `backend` as the root directory.
2. Set `OPENROUTER_API_KEY` in the host's secret environment settings.
3. Copy the generated `JARVIS_CLIENT_TOKEN` from the private dashboard and keep it secret.
4. Attach a persistent disk mounted at `/data` if the host/plan supports it. Without a persistent disk, SQLite data can be lost on redeploy/restart. Check current hosting-plan limits before relying on free hosting.
5. Test `GET /health`, then verify an authenticated chat request and memory create/list/delete before connecting Android.

## Tests

```bash
cd backend
pip install -r requirements.txt
pip install httpx pytest
python -m unittest discover -s tests -v
```

The Android app still uses its existing direct-provider configuration until a separate integration change is made and tested. This avoids breaking current app behavior before the service is actually deployed.
