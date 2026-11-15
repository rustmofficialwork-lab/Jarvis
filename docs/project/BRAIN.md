# JARVIS smart brain (free)

JARVIS does not contain its own AI model. The "mind" is a free model (cloud free tier or local
Ollama `llama3.2:3b`). `smart_brain.py` is the layer that makes those free models behave better.
It is plain Python (no extra packages), runs on the PC, and sits *under* the safety policy in
`brain_core.py` - it can never run a tool the policy would not already allow.

## What it does today (offline / local model path)

| Part | What it fixes |
|------|---------------|
| `classify_query` | Understands the request: chat, factual, math, code, planning, reasoning, creative; difficulty; Hinglish vs English. No model call. |
| `generation_options` | Per-request settings: low temperature for math/code, higher for stories, larger (bounded) context and reply length for code/reasoning. Default chat is unchanged (2048 / 384 / 0.7). |
| `rank_memories` | BM25 + recency retrieval over saved memories. Only memories that actually match are sent, and only when "share memory with AI" is on. |
| `compact_history` | Old behaviour could send ~36k characters of history to a 2048-token window. History is now budgeted to the window, always keeping the newest turns plus a short summary of older ones. |
| `gather_grounding` | For maths, "what time is it", and CPU/RAM/battery questions, JARVIS first runs the existing read-only tools and gives the *verified result* to the model, so the offline model states real values instead of guessing. |
| `deliberate` | For hard questions, or when you say "step by step", "soch ke", "carefully", "in detail": draft -> self-critique -> revise (max 2 extra calls, 90 s budget, falls back to the draft). Opt-in by wording because it is slower. |

## Brain check

Type `brain check` (or `brain status karo`, `ollama check`) in JARVIS. `brain_health.py` asks the
loopback Ollama service whether it is running and whether `llama3.2:3b` is installed, reads free RAM,
and prints one concrete next step (for example the exact `ollama pull` command). It is read-only: it
never starts, installs, or changes anything. On an 8 GB laptop it warns when free RAM is low and tells
you to skip deep think.

## Review fixes (latest)

- Memory search now matches word forms (`file`/`files`, `use`/`used`, `run`/`running`).
- A person named "Ram" no longer triggers a PC-status lookup; RAM questions need context ("meri ram", "ram usage").
- More ways to ask the time/date are verified by the clock tool ("what is the time", "time batao", "aaj ki tarikh").
- "20% of 500" is computed by the calculator tool; ranges like "9-5 job" and dates are not treated as arithmetic.
- "class 10 ..." is no longer classified as code; `c++` is detected; "ok what is ...?" is a question, not small talk.
- Hindi in Devanagari (मेरा प्रोजेक्ट...) is tokenized correctly, so such memories are retrieved and the query is treated as Hinglish.
- Deep think: verbose approvals ("OK, the answer is correct") skip the revise call, and "Here is the corrected answer:" prefixes are removed.

## Multi-step commands and daily briefing

- **Chains** (`command_chain.py`): "notepad kholo aur phir calculator kholo", "open notepad, open youtube then pc status".
  Up to 4 steps joined by `aur`, `phir`, `uske baad`, `and`, `then` or commas. A chain runs only if *every* step is already an
  approved local action; all steps are checked with a dry run first, so nothing half-runs. Anything else goes to the AI as before.
- **Briefing** (`briefing.py`): say or type `briefing`, `aaj ka briefing` or `good morning jarvis`. It reads your saved reminders
  for the next 24 hours and the live PC snapshot, and warns about low battery, full RAM, busy CPU or a nearly full drive.
  It is read-only and works fully offline.

## Honest limits

- A 3B model is still a 3B model. This layer reduces slips; it does not turn it into a frontier model.
- Deep-think triples local latency on a CPU-only laptop. Simple chat always uses exactly one call.
- The cloud path is unchanged apart from better memory selection; cloud models already use tools.
- Nothing here trains or fine-tunes a model, and nothing is uploaded anywhere.

## Making the free brain stronger

- Cloud: the backend accepts up to 5 OpenAI-compatible providers in `JARVIS_AI_PROVIDERS`
  and falls back between them (see `backend/README.md`). Adding more free-tier providers
  increases uptime.
- Local: a larger Ollama model gives better answers but needs more RAM; the app currently
  supports only `llama3.2:3b`.

Tests: `python -m unittest test_smart_brain test_smart_brain_integration` (run in `desktop/windows`).
