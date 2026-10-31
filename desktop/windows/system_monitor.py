"""Shared local system-metric collection and PC status formatting for JARVIS."""
from __future__ import annotations

import os
from datetime import datetime


def _safe_read(callback, fallback=None):
    try:
        return callback()
    except Exception:
        return fallback


def collect_system_metrics(psutil_module=None) -> dict:
    """Read each hardware metric once; shared by the HUD and spoken PC-status command."""
    if psutil_module is None:
        import psutil as psutil_module

    drive = os.environ.get("SystemDrive", "C:") + chr(92)
    battery = _safe_read(psutil_module.sensors_battery, "N/A")
    temperature = _safe_read(
        lambda: next(
            (entry.current for entries in psutil_module.sensors_temperatures(fahrenheit=False).values()
             for entry in entries if entry.current is not None),
            None,
        )
    )
    network_online = _safe_read(
        lambda: any(
            item.isup for name, item in psutil_module.net_if_stats().items()
            if name.casefold() not in {"lo", "loopback"}
        )
    )
    return {
        "cpu_percent": _safe_read(lambda: psutil_module.cpu_percent(interval=None)),
        "memory_percent": _safe_read(lambda: psutil_module.virtual_memory().percent),
        "disk_percent": _safe_read(lambda: psutil_module.disk_usage(drive).percent),
        "battery": battery,
        "cpu_temperature": temperature,
        "network_online": network_online,
    }


def format_battery_status(battery) -> str:
    """Format battery state for the dashboard without assuming a laptop battery."""
    if battery is None:
        return "AC POWER"
    try:
        percent = max(0, min(100, float(battery.percent)))
    except (AttributeError, TypeError, ValueError):
        return "N/A"
    charging = getattr(battery, "power_plugged", None)
    suffix = " • CHARGING" if charging is True and percent < 100 else (
        " • ON BATTERY" if charging is False else ""
    )
    return f"{percent:.0f}%{suffix}"


def get_system_status(psutil_module=None, now=None) -> str:
    """Return a compact PC snapshot using the same underlying metrics as the HUD."""
    if psutil_module is None:
        import psutil as psutil_module
    now = now or datetime.now
    metrics = collect_system_metrics(psutil_module)

    def percent(value):
        try:
            return f"{float(value):.0f}%"
        except (TypeError, ValueError):
            return "Unavailable"

    battery = metrics["battery"]
    if battery == "N/A":
        battery_text = "Unavailable"
    elif battery is None:
        battery_text = "No battery detected"
    else:
        try:
            battery_text = f"{float(battery.percent):.0f}%" + (
                " (charging)" if battery.power_plugged else ""
            )
        except (AttributeError, TypeError, ValueError):
            battery_text = "Unavailable"

    network = metrics["network_online"]
    network_text = "Online" if network is True else "Offline" if network is False else "Unavailable"
    uptime = _safe_read(
        lambda: _format_uptime(now().timestamp() - psutil_module.boot_time()),
        "Unavailable",
    )
    drive_usage = percent(metrics["disk_percent"])
    return (
        "PC status (live snapshot)\\n"
        f"CPU usage: {percent(metrics['cpu_percent'])}\\n"
        f"Memory usage: {percent(metrics['memory_percent'])}\\n"
        f"System drive usage: {drive_usage}\\n"
        f"Battery: {battery_text}\\n"
        f"Network: {network_text}\\n"
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


def get_top_processes(limit: int = 5, psutil_module=None) -> str:
    """Return a bounded, read-only snapshot of processes using the most memory."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("Process limit must be an integer from 1 to 20.")
    if psutil_module is None:
        import psutil as psutil_module

    rows = []
    try:
        processes = psutil_module.process_iter(
            attrs=["pid", "name", "cpu_percent", "memory_percent"]
        )
        for process in processes:
            try:
                info = process.info
                name = str(info.get("name") or "Unknown").strip() or "Unknown"
                pid = int(info.get("pid", 0))
                memory = float(info.get("memory_percent", 0.0) or 0.0)
                cpu = float(info.get("cpu_percent", 0.0) or 0.0)
                if not (0 <= memory <= 100 and 0 <= cpu <= 10000):
                    continue
                rows.append((memory, cpu, pid, name[:48]))
            except (AttributeError, KeyError, TypeError, ValueError, OSError):
                # Processes can exit or become inaccessible during enumeration.
                continue
    except Exception as exc:
        return f"Process information unavailable: {exc}"

    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not rows:
        return "No process information is currently available."
    lines = [f"Top {min(limit, len(rows))} processes by memory usage (read-only):"]
    for memory, cpu, pid, name in rows[:limit]:
        lines.append(f"{name} (PID {pid}) — RAM {memory:.1f}% | CPU {cpu:.1f}%")
    return "\n".join(lines)
