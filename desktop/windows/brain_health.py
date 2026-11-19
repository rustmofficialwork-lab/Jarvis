"""Read-only health check for JARVIS's free offline brain (Ollama + RAM).

Nothing here starts, stops, installs, or changes anything: it only asks the loopback
Ollama service which models are installed and reads RAM figures, then explains in
plain Hinglish what to do next. Typing "brain check" in JARVIS runs it.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
DEFAULT_MODEL = "qwen3.5:4b"
MAX_RESPONSE_BYTES = 1_000_000
LOW_RAM_FREE_GB = 3.5      # Qwen3.5 4B needs several GB beyond Windows and other apps
DEEP_THINK_FREE_GB = 5.0   # deep think makes multiple local model calls

_COMMAND = re.compile(
    r"^(?:(?:please|hey jarvis|jarvis|zara|ek baar)\s+)*"
    r"(?:"
    r"(?:brain|ai|ollama|offline ai|offline brain)\s+(?:status|check|health|test)(?:\s+(?:karo|kro|batao|dikhao|do))?"
    r"|(?:check|test)\s+(?:my\s+|mera\s+)?(?:brain|ai|ollama|offline ai|offline brain)"
    r"|(?:brain|ai|ollama)\s+ka\s+(?:status|health)(?:\s+(?:batao|dikhao|check karo))?"
    r"|(?:brain|ai)\s+(?:kaisa|kaise)\s+(?:hai|chal raha hai)"
    r")[\s?.!]*$"
)


def is_brain_check_command(prompt: str) -> bool:
    """True only for an explicit brain/AI status request, never for ordinary chat."""
    return bool(_COMMAND.match(" ".join(str(prompt or "").casefold().split())))


@dataclass(frozen=True)
class BrainHealth:
    ollama_running: bool
    model: str
    model_installed: bool
    installed_models: tuple[str, ...] = field(default_factory=tuple)
    ram_total_gb: float | None = None
    ram_free_gb: float | None = None
    error: str | None = None

    @property
    def ready(self) -> bool:
        return self.ollama_running and self.model_installed

    @property
    def low_ram(self) -> bool:
        return self.ram_free_gb is not None and self.ram_free_gb < LOW_RAM_FREE_GB

    @property
    def deep_think_ok(self) -> bool:
        return self.ready and (self.ram_free_gb is None or self.ram_free_gb >= DEEP_THINK_FREE_GB)


def _read_ram(psutil_module=None) -> tuple[float | None, float | None]:
    try:
        if psutil_module is None:
            import psutil as psutil_module
        memory = psutil_module.virtual_memory()
        total, available = float(memory.total), float(memory.available)
        if total <= 0 or available < 0:
            return None, None
        gib = 1024 ** 3
        return round(total / gib, 1), round(min(available, total) / gib, 1)
    except Exception:
        return None, None


def check_local_brain(*, model: str = DEFAULT_MODEL, opener=None, psutil_module=None,
                      timeout: float = 2.0) -> BrainHealth:
    """Ask the loopback Ollama service what is installed and read RAM. Never raises."""
    total, free = _read_ram(psutil_module)
    if opener is None:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        # Local traffic must never go through a configured HTTP proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(OLLAMA_TAGS_URL, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("response too large")
        body = json.loads(raw.decode("utf-8"))
        models = body.get("models") if isinstance(body, dict) else None
        if not isinstance(models, list):
            raise ValueError("unexpected response")
    except urllib.error.HTTPError as exc:
        return BrainHealth(True, model, False, (), total, free, f"Ollama HTTP {exc.code}")
    except (urllib.error.URLError, OSError, TimeoutError):
        return BrainHealth(False, model, False, (), total, free, None)
    except (ValueError, UnicodeDecodeError) as exc:
        return BrainHealth(True, model, False, (), total, free, f"Ollama response problem: {exc}")
    names = tuple(sorted({str(m.get("name", "")) for m in models if isinstance(m, dict) and m.get("name")}))
    return BrainHealth(True, model, model in names, names, total, free, None)


def format_brain_report(health: BrainHealth) -> str:
    """Plain Hinglish report with exactly one concrete next step."""
    lines = ["Brain health check (sirf padhta hai, kuch badalta nahi):"]
    if health.ollama_running:
        lines.append("• Offline AI engine (Ollama): chal raha hai ✔")
    else:
        lines.append("• Offline AI engine (Ollama): band hai ✘")
    if health.ollama_running:
        if health.model_installed:
            lines.append(f"• Model {health.model}: installed ✔")
        else:
            lines.append(f"• Model {health.model}: installed nahi hai ✘")
    if health.ram_total_gb is not None and health.ram_free_gb is not None:
        lines.append(f"• RAM: {health.ram_free_gb} GB free / {health.ram_total_gb} GB total")
    lines.append("• Online AI: har sawal par pehle try hota hai; fail hone par offline brain use hota hai.")

    if health.error:
        lines.append(f"Dikkat: {health.error}. Ollama ko restart karke dobara check karo.")
    elif not health.ollama_running:
        lines.append(
            "Agla kadam: Ollama Start menu se kholo. Offline sawal puchne par Jarvis use khud bhi start "
            "kar leta hai, par pehli baar 10-20 second lag sakte hain."
        )
    elif not health.model_installed:
        lines.append(f"Agla kadam: PowerShell me ye chalao: ollama pull {health.model}")
    elif health.low_ram:
        lines.append(
            "RAM kam bachi hai. Browser tabs aur baaki apps band karo, warna offline jawab bahut dheere aayenge. "
            "Abhi 'step by step' wali deep think mat use karo."
        )
    elif health.deep_think_ok:
        lines.append("Sab theek hai. Offline brain taiyar hai, aur 'step by step' bol kar deep think bhi chalega.")
    else:
        lines.append(
            "Offline brain taiyar hai. RAM thodi kam hai, isliye normal sawal poochho; "
            "deep think dheema ho sakta hai."
        )
    return "\n".join(lines)
