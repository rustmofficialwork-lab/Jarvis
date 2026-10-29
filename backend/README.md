# JARVIS Backend

This service provides the shared OpenRouter gateway and SQLite-backed memory API used by the Android and Windows clients when configured with the default endpoint.

## Features

- Fixed OpenRouter upstream destination (not an arbitrary-URL proxy).
- Provider secret stays server-side; clients use a JARVIS client token.
- Bearer-token authentication for chat and memory endpoints.
- Request size/message-count limits, bounded upstream timeout, generic error responses, and no response caching.
- Memory API: list, create, and delete notes.
- Docker image and Render deployment configuration.

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

Set environment variables from `.env.example` in your shell or deployment dashboard (the app intentionally does not auto-load `.env`). Use a randomly generated `JARVIS_CLIENT_TOKEN` of at least 32 characters and your own `OPENROUTER_API_KEY`. Never commit real credentials.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check `GET /health`. Protected routes require `Authorization: Bearer <JARVIS_CLIENT_TOKEN>`.

## Chat API

Send an OpenAI-compatible JSON body to `POST /v1/chat/completions`, including `model` and `messages`. Requests are forwarded to OpenRouter using the server-side key. The `openrouter/free` router may choose models with different capabilities; image/vision requests may fail if the selected model does not support image input.

## Memory API

- `GET /v1/memory` — list up to 200 saved notes.
- `POST /v1/memory` with `{"content":"..."}` — save a note (maximum 4,000 characters).
- `DELETE /v1/memory/{id}` — delete a note.

Saved notes are private to this single-token deployment, not separated by user accounts. A token embedded in a mobile/desktop client can be extracted by a determined attacker; do not expose this instance to untrusted users. Public release should add per-user authentication and quotas.

## Render deployment and persistence

The current Render service is configured for this repository and uses the `backend` Docker context. Confirm deployment status in the Render dashboard. Set `OPENROUTER_API_KEY` and `JARVIS_CLIENT_TOKEN` as secret environment variables. Attach persistent storage mounted at `/data` if supported by the selected plan; without it, SQLite memory may be lost after restarts/redeploys.

## Tests

```bash
cd backend
pip install -r requirements.txt
pip install httpx pytest
python -m unittest discover -s tests -v
```

CI checks and unit tests validate code paths, but they do not prove that live provider credentials, upstream availability, mobile permissions, or physical-device audio work. Verify `GET /health`, authenticated chat, and memory create/list/delete against the deployed service before relying on those features.
