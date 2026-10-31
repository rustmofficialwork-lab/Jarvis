"""Local, read-only Windows system status for JARVIS commands."""
from __future__ import annotations

import os
from datetime import datetime


def get_system_status(psutil_module=None, now=None) -> str:
    """Return a compact snapshot; each sensor is isolated from unsupported hardware."""
    if psutil_module is None:
        import psutil as psutil_module
    now = now or datetime.now

    def read(callback, fallback="Unavailable"):
        try:
            value = callback()
            return value if value is not None else fallback
        except Exception:
            return fallback

    cpu = read(lambda: f"{psutil_module.cpu_percent(interval=None):.0f}%")
    memory = read(lambda: f"{psutil_module.virtual_memory().percent:.0f}%")
    drive = os.environ.get("SystemDrive", "C:") + chr(92)
    disk = read(lambda: f"{psutil_module.disk_usage(drive).percent:.0f}%")
    battery = read(
        lambda: (
            f"{psutil_module.sensors_battery().percent:.0f}%"
            + (" (charging)" if psutil_module.sensors_battery().power_plugged else "")
        ) if psutil_module.sensors_battery() is not None else "No battery detected"
    )
    network = read(
        lambda: "Online" if any(
            item.isup for name, item in psutil_module.net_if_stats().items()
            if name.casefold() not in {"lo", "loopback"}
        ) else "Offline"
    )
    uptime = read(
        lambda: _format_uptime(now().timestamp() - psutil_module.boot_time())
    )
    return (
        "PC status (live snapshot)\n"
        f"CPU usage: {cpu}\n"
        f"Memory usage: {memory}\n"
        f"System drive usage: {disk}\n"
        f"Battery: {battery}\n"
        f"Network: {network}\n"
        f"Uptime: {uptime}"
    )


def _format_uptime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)
