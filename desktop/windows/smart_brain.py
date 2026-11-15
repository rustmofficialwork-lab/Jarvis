"""JARVIS smart brain: makes free models (cloud free tiers + local Ollama) behave smarter.

This module does NOT train or contain a model. It is the orchestration layer around
whatever free model is available. It is pure standard library, deterministic where
possible, and never executes anything the safety policy in ``brain_core`` would not
already allow.

What it adds:
  * ``classify_query``       - understands the request (kind, difficulty, language).
  * ``generation_options``   - picks sampling/length/context settings per request kind.
  * ``rank_memories``        - BM25 + recency memory retrieval (better than keyword AND).
  * ``compact_history``      - fits chat history into a small context window without
                               silently losing the system prompt or the latest turns.
  * ``gather_grounding``     - runs *read-only, already-allowlisted* local tools (math,
                               clock, PC status) BEFORE the model answers, so even a small
                               offline model without tool-calling states real values.
  * ``deliberate``           - bounded draft -> critique -> revise loop for hard questions.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

# --------------------------------------------------------------------------- text utils

# \w alone breaks Devanagari words at every vowel sign, so the block is added explicitly.
_WORD = re.compile(r"[\w\u0900-\u097f]+", re.UNICODE)
_DEVANAGARI = re.compile(r"[\u0900-\u097f]")

_STOP_WORDS = frozenset(
    """
    a an the is are was were be been am of to in on at for and or but if so as by with from
    my me i you your it its this that these those please jarvis hey can could would should
    do does did have has had will shall not no yes
    ka ki ke ko se me mein par pe hai hain tha thi the hu hoon ho hum aap tum main mai mera meri
    mere tera teri tere apna apni apne yeh ye woh wo kya kaise kab kahan kyun kyu kaun aur ya
    to toh bhi hi na nahi nahin karo kar karna kro de do dena batao bata
    और का की के को से में पर है हैं था थी थे यह वह ये वे इस उस एक मेरा मेरी मेरे मुझे आप
    क्या कैसे कब कहाँ क्यों बताओ करो करना चाहिए लिए भी तो ही नहीं अब तक
    """.split()
)

_HINGLISH_MARKERS = frozenset(
    """
    kya hai hain kaise karo kar mujhe mera meri mere batao bata nahi nahin aap tum kyun kyu
    bhai yaar ko ka ki ke kaun kab kahan abhi chahiye samjhao samjha likho dikhao kholo chalao
    acha accha theek thik haan han toh bahut thoda zyada kitna kitne baje
    """.split()
)


def _stem(token: str) -> str:
    """Tiny English stemmer so file/files, use/used/using and run/running match in BM25.

    Only plain ASCII words are touched; numbers and Roman-Hindi tokens that do not end in an
    English suffix pass through unchanged. Query and memories are stemmed the same way, so a
    slightly "wrong" stem is harmless as long as it is consistent.
    """
    if len(token) <= 2 or not (token.isascii() and token.isalpha()):
        return token
    word = token
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith(("sses", "ches", "shes", "xes", "zes")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            word = word[: -len(suffix)]
            if len(word) > 2 and word[-1] == word[-2] and word[-1] not in "aeiouslz":
                word = word[:-1]  # running -> run
            break
    if word.endswith("e") and len(word) > 2:
        word = word[:-1]  # make/making, file/files, use/used
    return word


def tokenize(text: str, *, drop_stop_words: bool = True) -> list[str]:
    tokens = []
    for raw in _WORD.findall(str(text or "").casefold()):
        if len(raw) < 2 and not raw.isdigit():
            continue
        if drop_stop_words and raw in _STOP_WORDS:
            continue
        tokens.append(_stem(raw))
    return tokens


# --------------------------------------------------------------------------- query understanding

@dataclass(frozen=True)
class QueryProfile:
    kind: str            # chat | factual | math | code | planning | reasoning | creative
    complexity: int      # 0 (trivial) .. 3 (hard)
    language: str        # hinglish | english
    deliberate: bool     # worth spending extra model calls on a critique/revise pass
    wants_live_data: bool = False
    signals: tuple[str, ...] = field(default_factory=tuple)


_ARITHMETIC = re.compile(
    r"(?<![\w.])(?:\(?\s*\d+(?:\.\d+)?\s*\)?\s*(?:\*\*|[+\-*/%^x\u00d7])\s*)+\(?\s*\d+(?:\.\d+)?\s*\)?(?![\w.])"
)
_DATE_LIKE = re.compile(r"\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b")
# "9-5 job", "pages 10-12", "10-12 baje": a hyphen between small numbers is a range, not a subtraction.
_RANGE_LIKE = re.compile(
    r"(?<![\w.])\d{1,4}\s*-\s*\d{1,4}\s*(?:job|shift|duty|office|timing|hours?|hrs?|pages?|pg|am|pm|baje|"
    r"years?|saal|students?|marks|se|tak)\b"
    r"|\b(?:pages?|pg|chapters?|ch|q|age|from|between|class)\s*\d{1,4}\s*-\s*\d{1,4}(?![\w.])"
)
_PERCENT_OF = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:%|percent|pratishat)\s*(?:of|ka|ki|ke)\s*(\d+(?:\.\d+)?)(?![\w.%])"
)


def _find_arithmetic(text: str) -> "re.Match[str] | None":
    """First real arithmetic expression, skipping dates (12-05-2026) and ranges (9-5 job)."""
    skip = [m.span() for pattern in (_DATE_LIKE, _RANGE_LIKE) for m in pattern.finditer(text)]
    for match in _ARITHMETIC.finditer(text):
        a, b = match.span()
        if not any(a < y and x < b for x, y in skip):
            return match
    return None
_MATH_WORDS = re.compile(
    r"\b(calculate|calculator|compute|percent(?:age)?|square root|sqrt|kitna hota|kitne hote|"
    r"hisab|jod|ghata|guna|bhaag|total kitna|sum of|multiply|divide)\b"
)
_CODE_WORDS = re.compile(
    r"(?<!\w)(code|coding|python|java|javascript|c\+\+|cpp|c program|html|css|sql|function|script|program|"
    r"debug|compile|compiler|algorithm|syntax|array|loop|pointer|bug|error|exception|stack trace|"
    r"api|regex|(?:python|java|c\+\+|cpp|js) class|variable)(?!\w)"
)
_PLAN_WORDS = re.compile(
    r"\b(plan|schedule|roadmap|strategy|(?:next )?steps (?:to|for|of)|organi[sz]e|timetable|routine|checklist|"
    r"kaise banau|kaise karu|kaise karun|how to|how do i|process)\b"
)
_REASON_WORDS = re.compile(
    r"\b(why|kyun|kyu|explain|samjhao|compare|difference|vs|versus|better|analy[sz]e|"
    r"pros and cons|prove|solve|reason|because|kaise kaam|how does|how do|what if|agar)\b"
)
_CREATIVE_WORDS = re.compile(
    r"\b(story|poem|kavita|shayari|joke|likho|write|essay|email|letter|speech|caption|slogan)\b"
)
_WH_WORDS = re.compile(r"\b(what|who|when|where|which|kya|kaun|kab|kahan|kitna|kitne|kaunsa)\b")
_DELIBERATE_PHRASES = re.compile(
    r"(step by step|think carefully|think deeply|think hard|carefully|in detail|detailed|"
    r"soch ke|soch kar|dhyan se|gehrai se|detail me|detail mein|vistar se|double check)"
)
_GREETING = re.compile(
    r"^\s*(hi|hello|hey|namaste|namaskar|hola|good (morning|afternoon|evening|night)|"
    r"kya haal|kaise ho|how are you|thanks|thank you|shukriya|dhanyavaad|ok|okay|theek hai)\b"
)
_LIVE_WORDS = re.compile(
    r"\b(latest|today'?s|current|news|weather|mausam|score|price|rate|stock|live|abhi ka|aaj ka)\b"
)


def classify_query(prompt: str) -> QueryProfile:
    """Cheap, deterministic request understanding (no model call)."""
    text = " ".join(str(prompt or "").casefold().split())
    words = text.split()
    n = len(words)
    signals: list[str] = []

    has_math = _find_arithmetic(text) is not None or _PERCENT_OF.search(text) is not None
    if has_math or _MATH_WORDS.search(text):
        kind = "math"
    elif _CODE_WORDS.search(text):
        kind = "code"
    elif _PLAN_WORDS.search(text):
        kind = "planning"
    elif _REASON_WORDS.search(text):
        kind = "reasoning"
    elif _CREATIVE_WORDS.search(text):
        kind = "creative"
    elif (_GREETING.search(text) and n <= 6 and not _WH_WORDS.search(text)) or (
        n <= 5 and "?" not in text and not _WH_WORDS.search(text)
    ):
        kind = "chat"
    elif "?" in text or _WH_WORDS.search(text):
        kind = "factual"
    else:
        kind = "chat"
    signals.append(kind)

    if n < 8:
        complexity = 0
    elif n < 25:
        complexity = 1
    elif n < 60:
        complexity = 2
    else:
        complexity = 3
    if kind in {"reasoning", "code", "planning"}:
        complexity += 1
    if len(re.findall(r"[?.!]", text)) >= 3 or len(re.findall(r"\b(and|aur|also|phir|then)\b", text)) >= 2:
        complexity += 1
    complexity = max(0, min(3, complexity))
    if kind == "chat":
        complexity = min(complexity, 1)

    explicit_deep = bool(_DELIBERATE_PHRASES.search(text))
    if explicit_deep:
        signals.append("explicit-deep-think")
    deliberate = explicit_deep or (kind in {"reasoning", "code", "planning", "math"} and complexity >= 3)

    hinglish_hits = sum(1 for w in set(words) if w.strip("?,.!") in _HINGLISH_MARKERS)
    language = "hinglish" if hinglish_hits >= 1 or _DEVANAGARI.search(text) else "english"
    return QueryProfile(
        kind=kind,
        complexity=complexity,
        language=language,
        deliberate=deliberate,
        wants_live_data=bool(_LIVE_WORDS.search(text)),
        signals=tuple(signals),
    )


_BASE_OPTIONS = {"num_ctx": 2048, "num_predict": 384, "temperature": 0.7}

_KIND_OPTIONS: dict[str, dict[str, Any]] = {
    "chat": {"num_predict": 256, "temperature": 0.7},
    "factual": {"num_predict": 384, "temperature": 0.3},
    "math": {"num_predict": 384, "temperature": 0.1},
    "code": {"num_ctx": 4096, "num_predict": 768, "temperature": 0.2},
    "planning": {"num_ctx": 4096, "num_predict": 768, "temperature": 0.4},
    "reasoning": {"num_ctx": 4096, "num_predict": 768, "temperature": 0.4},
    "creative": {"num_ctx": 3072, "num_predict": 640, "temperature": 0.9},
}

MAX_NUM_CTX = 4096
MAX_NUM_PREDICT = 1024


def generation_options(profile: QueryProfile) -> dict[str, Any]:
    """Local-model options per request kind. Bounded so a small laptop is never overloaded."""
    options = dict(_BASE_OPTIONS)
    options.update(_KIND_OPTIONS.get(profile.kind, {}))
    if profile.complexity >= 3 and profile.kind != "chat":
        options["num_predict"] = min(MAX_NUM_PREDICT, int(options["num_predict"]) + 256)
    options["num_ctx"] = max(2048, min(MAX_NUM_CTX, int(options["num_ctx"])))
    options["num_predict"] = max(64, min(MAX_NUM_PREDICT, int(options["num_predict"])))
    options["temperature"] = max(0.0, min(1.0, float(options["temperature"])))
    return options


# --------------------------------------------------------------------------- memory retrieval

def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def bm25_scores(query: str, documents: Sequence[str], *, k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Okapi BM25 scores of ``query`` against each document (all zeros when nothing matches)."""
    q_terms = list(dict.fromkeys(tokenize(query)))
    docs = [tokenize(d) for d in documents]
    if not q_terms or not docs:
        return [0.0] * len(docs)
    n_docs = len(docs)
    avg_len = sum(len(d) for d in docs) / n_docs or 1.0
    doc_freq = {t: sum(1 for d in docs if t in d) for t in q_terms}
    scores = []
    for tokens in docs:
        if not tokens:
            scores.append(0.0)
            continue
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        score = 0.0
        for term in q_terms:
            tf = counts.get(term, 0)
            if not tf:
                continue
            idf = math.log(1.0 + (n_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * len(tokens) / avg_len))
        scores.append(score)
    return scores


def rank_memories(
    query: str,
    memories: Iterable[Any],
    *,
    limit: int = 5,
    max_chars: int = 1500,
    now: datetime | None = None,
) -> list[str]:
    """Return the most relevant memory strings for ``query``.

    ``memories`` may be strings or dicts with ``content`` and optional ``updated_at``.
    Only memories that actually match the query are returned (no random filler), so an
    unrelated prompt never receives personal context it does not need.
    """
    items: list[tuple[str, datetime | None]] = []
    for entry in memories:
        if isinstance(entry, dict):
            content = entry.get("content")
            stamp = _parse_time(entry.get("updated_at"))
        else:
            content, stamp = entry, None
        if isinstance(content, str) and content.strip():
            items.append((content.strip(), stamp))
    if not items:
        return []
    limit = max(1, min(int(limit), 10))
    clock = now or datetime.now(timezone.utc)
    base = bm25_scores(query, [c for c, _ in items])
    ranked = []
    for (content, stamp), score in zip(items, base):
        if score <= 0:
            continue
        if stamp is not None:
            age_days = max(0.0, (clock - stamp).total_seconds() / 86400.0)
            score *= 1.0 + 0.2 / (1.0 + age_days / 30.0)
        ranked.append((score, content))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    selected, used = [], 0
    for _, content in ranked:
        content = content[:500]
        if used + len(content) > max_chars:
            continue
        selected.append(content)
        used += len(content)
        if len(selected) >= limit:
            break
    return selected


# --------------------------------------------------------------------------- history budgeting

@dataclass(frozen=True)
class CompactedHistory:
    messages: list[dict]
    summary: str | None
    dropped: int


def _first_sentence(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    match = re.search(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    return sentence[:limit].rstrip()


def compact_history(history: Sequence[dict], *, max_chars: int, keep_recent: int = 8,
                    per_message_chars: int = 1500) -> CompactedHistory:
    """Fit chat history into ``max_chars`` while always keeping the newest turns.

    Older turns that do not fit are replaced by one short extractive summary so the
    model still knows what was discussed. Nothing is sent to a model to do this.
    """
    clean = [
        {"role": m["role"], "content": str(m["content"])[:per_message_chars]}
        for m in history
        if isinstance(m, dict) and m.get("role") in {"user", "assistant"}
        and isinstance(m.get("content"), str) and m["content"].strip()
    ]
    max_chars = max(200, int(max_chars))
    if sum(len(m["content"]) for m in clean) <= max_chars:
        return CompactedHistory(clean, None, 0)

    recent = clean[-max(2, keep_recent):]
    older = clean[:len(clean) - len(recent)]
    # Shrink the recent window (oldest first) until it fits, but never below the last 2 turns.
    reserve = min(900, max_chars // 3)
    while len(recent) > 2 and sum(len(m["content"]) for m in recent) > max_chars - reserve:
        older.append(recent.pop(0))
    # If even the last turns are too long, cap each one rather than overflow the window.
    if sum(len(m["content"]) for m in recent) > max_chars - 100:
        cap = max(100, (max_chars - 100) // len(recent))
        recent = [{**m, "content": m["content"][:cap]} for m in recent]

    lines = []
    for msg in older:
        label = "User asked" if msg["role"] == "user" else "JARVIS answered"
        lines.append(f"- {label}: {_first_sentence(msg['content'], 110)}")
    summary_budget = max(120, max_chars - sum(len(m["content"]) for m in recent))
    summary_lines, used = [], 0
    for line in reversed(lines):  # newest older turns are the most useful
        if used + len(line) + 1 > summary_budget:
            break
        summary_lines.append(line)
        used += len(line) + 1
    summary_lines.reverse()
    summary = None
    if summary_lines:
        summary = "Earlier in this conversation (condensed):\n" + "\n".join(summary_lines)
    return CompactedHistory(recent, summary, len(older))


# --------------------------------------------------------------------------- grounding

_TIME_QUESTION = re.compile(
    r"\b(what time|what'?s the time|what is the time|current time|time now|tell me the time|"
    r"time kya|time batao|time bata do|kitne baje|kitna baja|abhi kitne|"
    r"what'?s the date|what is the date|what date|today'?s date|date today|aaj ki date|aaj ki tarikh|"
    r"aaj ki tareekh|date kya|date batao|tarikh kya|tareekh kya|tarikh batao|"
    r"aaj kaun ?sa din|aaj kya din|what day is|which day is)\b"
)
# "ram" alone is also a very common name (Ram ka birthday...), so memory questions need context.
_SYSTEM_QUESTION = re.compile(
    r"\b(cpu|battery|system status|pc health|pc ki health|laptop ki health|disk space|storage left|"
    r"memory usage|ram usage|cpu usage|laptop slow|pc slow|uptime)\b"
    r"|\b(?:my|meri|mera|free|total|check|laptop ki|pc ki|system ki)\s+ram\b"
    r"|\bram\s+(?:usage|free|status|kitni|kitna|full|low|used|check)\b"
)


def _normalise_expression(raw: str) -> str:
    expr = raw.replace("\u00d7", "*").replace("^", "**")
    expr = re.sub(r"(?<=[\d)\s])x(?=[\d(\s])", "*", expr)
    return " ".join(expr.split())


def gather_grounding(
    prompt: str,
    *,
    execute: Callable[[str, dict], str] | None = None,
    authorize: Callable[[str, dict, str], Any] | None = None,
) -> list[str]:
    """Run read-only local tools for obvious factual needs and return notes for the model.

    Every call is authorized through ``brain_core.authorize_tool_call`` first. Failures are
    swallowed (the model simply answers without the note) - grounding must never break a reply.
    """
    if execute is None:
        from ai_tools import execute_tool as execute  # local import: keeps this module light
    if authorize is None:
        from brain_core import authorize_tool_call as authorize

    text = " ".join(str(prompt or "").casefold().split())
    notes: list[str] = []

    def run(tool: str, arguments: dict) -> str | None:
        try:
            decision = authorize(tool, arguments, prompt)
            if not getattr(decision, "allowed", False):
                return None
            return str(execute(tool, arguments)).strip()
        except (ValueError, TypeError, OSError, RuntimeError, RecursionError):
            return None

    percent = _PERCENT_OF.search(text)
    match = _find_arithmetic(text)
    if percent:
        rate, base = percent.group(1), percent.group(2)
        value = run("calculator", {"expression": f"({rate} / 100) * {base}"})
        if value is not None:
            notes.append(f"Calculator result (use it only if the user is asking for this): {rate}% of {base} = {value}")
    elif match:
        expression = _normalise_expression(match.group(0))
        value = run("calculator", {"expression": expression})
        if value is not None:
            notes.append(
                f"Calculator result for the arithmetic expression in the user's message "
                f"(use it only if the user is asking for this calculation): {expression} = {value}"
            )
    if _TIME_QUESTION.search(text):
        value = run("get_local_time", {})
        if value:
            notes.append(f"Verified local date/time on this PC (ISO 8601): {value}")
    if _SYSTEM_QUESTION.search(text):
        value = run("get_system_status", {})
        if value:
            notes.append(f"Verified live PC status snapshot:\n{value[:700]}")
    return notes


# --------------------------------------------------------------------------- deliberation

Generate = Callable[[list, dict], str]

# Small models rarely answer the bare word "OK"; they say "OK. The answer is correct." or
# "No mistakes found." Treat those as approval instead of paying for a pointless revise call,
# but never when the same sentence also raises a problem ("Okay, but step 3 is wrong").
_CRITIQUE_APPROVES = re.compile(
    r"^\W*(?:ok(?:ay)?|correct|all good|looks good|no (?:real )?(?:mistakes?|issues?|errors?|problems?)"
    r"(?: found)?|sab theek(?: hai)?|theek hai)\W*$",
    re.IGNORECASE,
)
_CRITIQUE_LEADS_OK = re.compile(r"^\W*(?:ok(?:ay)?|correct|all good|looks good)\b", re.IGNORECASE)
_CRITIQUE_PROBLEM = re.compile(
    r"\b(but|however|although|wrong|incorrect|errors?|mistakes?|missing|issues?|problems?|should|needs?|"
    r"not|nahi|nahin|galat)\b",
    re.IGNORECASE,
)
_CRITIQUE_PRAISE = re.compile(r"\b(correct|complete|good|fine|right|accurate)\b", re.IGNORECASE)
_REVISION_PREAMBLE = re.compile(
    r"^\s*(?:here(?:'s| is)\b[^\n:]{0,60}:|(?:corrected |revised |updated )?final answer\s*:)\s*",
    re.IGNORECASE,
)


def _critique_approves(critique: str) -> bool:
    text = critique.strip()
    if not text or _CRITIQUE_APPROVES.fullmatch(text):
        return True
    return bool(
        "\n" not in text and len(text) <= 100
        and _CRITIQUE_LEADS_OK.match(text)
        and _CRITIQUE_PRAISE.search(text)
        and not _CRITIQUE_PROBLEM.search(text)
    )


@dataclass(frozen=True)
class Deliberation:
    text: str
    steps: tuple[str, ...]
    improved: bool


def deliberate(
    generate: Generate,
    messages: list[dict],
    options: dict[str, Any],
    *,
    deadline_seconds: float = 90.0,
    clock: Callable[[], float] = time.monotonic,
) -> Deliberation:
    """Draft -> self-critique -> revise, with at most two extra model calls.

    The critique pass is allowed to say "OK"; then the draft is returned unchanged. If the
    time budget runs out, or a later step fails or returns something worse, the draft wins.
    A small model will not become a large one, but this catches many slips (missed steps,
    arithmetic, wrong language) at the cost of extra latency, so callers keep it opt-in.
    """
    started = clock()
    draft = str(generate(messages, options) or "").strip()
    if not draft:
        raise RuntimeError("The model returned an empty draft.")
    steps = ["draft"]
    if clock() - started > deadline_seconds * 0.5:
        return Deliberation(draft, tuple(steps), False)

    critique_messages = list(messages) + [
        {"role": "assistant", "content": draft},
        {"role": "user", "content": (
            "Review your answer above. List at most 5 short bullet points naming real mistakes, "
            "missing steps, or unclear parts. If the answer is already correct and complete, "
            "reply with exactly: OK"
        )},
    ]
    try:
        critique = str(generate(critique_messages, {**options, "temperature": 0.2,
                                                       "num_predict": min(256, int(options.get("num_predict", 256)))}) or "").strip()
    except Exception:
        return Deliberation(draft, tuple(steps), False)
    steps.append("critique")
    if _critique_approves(critique):
        return Deliberation(draft, tuple(steps), False)
    if clock() - started > deadline_seconds:
        return Deliberation(draft, tuple(steps), False)

    revise_messages = critique_messages + [
        {"role": "assistant", "content": critique},
        {"role": "user", "content": (
            "Now write the corrected final answer. Fix the issues listed, keep what was right, "
            "keep the same language as the user, and reply with only the final answer."
        )},
    ]
    try:
        revised = str(generate(revise_messages, options) or "").strip()
    except Exception:
        return Deliberation(draft, tuple(steps), False)
    steps.append("revise")
    revised = _REVISION_PREAMBLE.sub("", revised, count=1).strip()
    if not revised or (len(draft) > 200 and len(revised) < len(draft) * 0.3):
        return Deliberation(draft, tuple(steps), False)
    return Deliberation(revised, tuple(steps), True)


# --------------------------------------------------------------------------- one-call preparation

@dataclass(frozen=True)
class BrainPlan:
    profile: QueryProfile
    options: dict[str, Any]
    memories: list[str]
    grounding: list[str]
    history: CompactedHistory


def history_budget_chars(options: dict[str, Any], *, fixed_chars: int) -> int:
    """Characters of history that fit: ~3 chars/token, leaving room for the reply."""
    window = int(options["num_ctx"]) * 3
    reply = int(options["num_predict"]) * 3
    return max(300, window - reply - int(fixed_chars))


def prepare(
    prompt: str,
    history: Sequence[dict],
    memory_items: Iterable[Any] | None = None,
    *,
    fixed_chars: int = 2400,
    execute: Callable[[str, dict], str] | None = None,
    authorize: Callable[[str, dict, str], Any] | None = None,
) -> BrainPlan:
    """Understand the request and assemble everything a model call needs. No network."""
    profile = classify_query(prompt)
    options = generation_options(profile)
    memories = rank_memories(prompt, memory_items or [], limit=5) if memory_items else []
    grounding = gather_grounding(prompt, execute=execute, authorize=authorize)
    budget = history_budget_chars(options, fixed_chars=fixed_chars + len(prompt) + sum(map(len, memories + grounding)))
    return BrainPlan(profile, options, memories, grounding, compact_history(history, max_chars=budget))
