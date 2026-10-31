# JARVIS Backend

The backend is an authenticated AI gateway for the Windows desktop client. It forwards chat-completions requests to a fixed OpenRouter endpoint. It does **not** expose a shared memory API or store desktop memories.

## Run locally

Python 3.11+:

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The app does not automatically load `.env`; export the values in your shell or configure them in your deployment dashboard. Set a random `JARVIS_CLIENT_TOKEN` of at least 32 characters and a server-side `OPENROUTER_API_KEY`. Never put the OpenRouter key in the desktop client or commit real credentials.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## API

- `GET /health` — public minimal health response.
- `POST /v1/chat/completions` — requires `Authorization: Bearer <JARVIS_CLIENT_TOKEN>`; accepts an OpenAI-compatible JSON object with 1–60 messages and forwards it to OpenRouter.
- Interactive API docs are disabled.

Requests are size-limited. Upstream calls have a bounded timeout and response-size cap. Streaming is intentionally disabled; the desktop client consumes a complete JSON response. Provider errors are normalized so secrets and upstream internals are not relayed.

## Personal memory

Personal memories are stored locally by each Windows desktop installation in the user's Local AppData SQLite database. They are not uploaded to this backend. There is no backend `/v1/memory` endpoint and no shared per-deployment memory collection.

## Deployment

The Docker image starts Uvicorn on port 8000 and runs as an unprivileged `jarvis` user. Configure `JARVIS_CLIENT_TOKEN` and `OPENROUTER_API_KEY` as secret environment variables in the hosting dashboard. No database volume is required for backend chat because the backend does not persist chat or memory data.

## Tests

```bash
cd backend
pip install -r requirements.txt
python -m pip install httpx
python -m unittest discover -s tests -v
```

Automated tests validate local code paths, not live OpenRouter credentials, external provider availability, or the deployed service. Verify `GET /health` and an authenticated chat request against the deployment before relying on live AI features.
