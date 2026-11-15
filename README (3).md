# JARVIS Backend

The backend is an authenticated AI gateway for the Windows desktop client. It forwards chat-completions requests through an ordered chain of configured OpenAI-compatible providers, with the legacy OpenRouter setup retained as the default. It does **not** expose a shared memory API or store desktop memories.

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

The app does not automatically load `.env`; export the values in your shell or configure them in your deployment dashboard. Set a random `JARVIS_DEVICE_TOKEN_SECRET` of at least 32 characters, keep `JARVIS_CLIENT_TOKEN` for existing installations, and set server-side `OPENROUTER_API_KEY` and `GROQ_API_KEY` secrets. Never put server secrets in the desktop client or commit real credentials. Render Blueprint deployments generate the device-token signing secret automatically.

### OpenRouter primary with Groq automatic fallback

The Render Blueprint now declares both providers in order. Add the real `GROQ_API_KEY` as a secret in the Render service environment; do not paste it into source code or commit it. Keep `OPENROUTER_API_KEY` configured as well. If OpenRouter is rate-limited, rejects its credentials, times out, has a network/server error, or returns an unusable response, the gateway tries Groq next. If the Groq key is absent, that provider is skipped.

The configured Groq endpoint is `https://api.groq.com/openai/v1/chat/completions`, using model `openai/gpt-oss-120b`. Provider model IDs can change; check Groq's current model catalogue before changing the configured model.

For custom provider chains, set `JARVIS_AI_PROVIDERS` only in the backend hosting dashboard:

```bash
JARVIS_AI_PROVIDERS='[
  {"name":"openrouter","base_url":"https://openrouter.ai/api/v1/chat/completions","api_key_env":"OPENROUTER_API_KEY","model":"openrouter/free"},
  {"name":"groq","base_url":"https://api.groq.com/openai/v1/chat/completions","api_key_env":"GROQ_API_KEY","model":"openai/gpt-oss-120b"}
]'
```

The provider array is attempted in order (maximum five entries; provider names must be unique and API-key environment-variable names must be valid). A provider timeout, network failure, HTTP 408/425/429, authentication rejection, server-side error, or malformed success response causes the gateway to try the next configured provider. A malformed/unsupported request (other 4xx responses) is not retried. If `JARVIS_AI_PROVIDERS` is unset, the existing `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` configuration remains unchanged. Each provider must expose an OpenAI-compatible `/chat/completions` endpoint and use HTTPS. Provider names, endpoint URLs, model IDs, and key environment-variable names are configuration; actual API key values remain server-side secrets. This is sequential failover, not parallel load balancing, and billing/rate limits are determined by each upstream provider.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## API

- `GET /health` — public minimal health response.
- `POST /v1/devices/register` — accepts a random per-installation UUID and returns a signed, 30-day device credential. Registration is rate-limited by network address.
- `POST /v1/chat/completions` — requires a valid signed device credential or a legacy `JARVIS_CLIENT_TOKEN`; accepts an OpenAI-compatible JSON object with 1–60 messages and forwards it to the configured provider chain. Signed device credentials are limited to 8 requests/minute and 120 requests/day. Legacy shared-token clients remain supported and are throttled per direct peer IP at 30 requests/minute and 600 requests/day.
- Interactive API docs are disabled.

Requests are size-limited. Upstream calls have a bounded timeout and response-size cap. When `REDIS_URL` points to a Redis-compatible Redis/Valkey service, registration and chat limits are enforced atomically across backend workers/instances. If `REDIS_URL` is unset, the backend falls back to in-process counters for local single-process development; those counters reset on restart and are not shared. If Redis is configured but unreachable, rate-limited endpoints fail closed with HTTP 503 instead of silently bypassing the shared limits. Configure the same private Redis URL on every backend instance. Keep this URL private and do not commit it. Streaming is intentionally disabled; the desktop client consumes a complete JSON response. Provider errors are normalized so secrets and upstream internals are not relayed.

## Personal memory

Personal memories are stored locally by each Windows desktop installation in the user's Local AppData SQLite database. They are not uploaded to this backend. There is no backend `/v1/memory` endpoint and no shared per-deployment memory collection.

## Deployment

The Docker image starts Uvicorn on port 8000 and runs as an unprivileged `jarvis` user. Configure `OPENROUTER_API_KEY` and `GROQ_API_KEY` as secret environment variables in the hosting dashboard; the Render Blueprint generates the device signing secret. For multi-instance rate limiting, provision a Redis-compatible service in the same private network/region and set `REDIS_URL` on the backend service. Keep this URL private and do not commit it. `JARVIS_CLIENT_TOKEN` remains available for older desktop clients. No database volume is required for backend chat because the backend does not persist chat or memory data.

## Tests

```bash
cd backend
pip install -r requirements.txt
python -m pip install httpx
python -m unittest discover -s tests -v
```

Automated tests validate local code paths, not live provider credentials, external provider availability, or the deployed service. Verify `GET /health` and an authenticated chat request against the deployment before relying on live AI features.
