# JARVIS Backend

This service provides the shared OpenRouter gateway used by the Windows desktop client. Personal memories are stored locally by each desktop installation and are never read from this backend.

## Features

- Fixed OpenRouter upstream destination (not an arbitrary-URL proxy).
- Provider secret stays server-side; clients use a JARVIS client token.
- Bearer-token authentication for chat requests.
- Request size/message-count limits, bounded upstream timeout, generic error responses, and no response caching.
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

## Personal memory

The backend intentionally has no shared memory API. The Windows client stores memories in a local SQLite database under the current user's `%LOCALAPPDATA%\\JARVISDesktop` folder. This prevents memories from different desktop users being mixed together and keeps memory available offline.

## Render deployment and persistence

The current Render service is configured for this repository and uses the `backend` Docker context. Confirm deployment status in the Render dashboard. Set `OPENROUTER_API_KEY` and `JARVIS_CLIENT_TOKEN` as secret environment variables. Attach persistent storage mounted at `/data` if supported by the selected plan; backend chat does not store personal memories.

## Tests

```bash
cd backend
pip install -r requirements.txt
pip install httpx pytest
python -m unittest discover -s tests -v
```

CI checks and unit tests validate code paths, but they do not prove that live provider credentials, upstream availability, or physical-device audio work. Verify `GET /health`, authenticated chat against the deployed service before relying on those features.
