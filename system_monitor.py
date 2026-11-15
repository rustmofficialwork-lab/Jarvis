"""Shared local system-metric collection and PC status formatting for JARVIS."""
from __future__ import annotations

import math
import os
from datetime import datetime


def _safe_read(callback, fallback=None):
    try:
        return callback()
    except Exception:
        return fallback


def _finite_percent(value):
    """Return a real OS percentage, rejecting invalid or out-of-range readings."""
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value) or not 0 <= value <= 100:
        return None
    return value


def read_cpu_temperature(psutil_module):
    """Return a finite CPU/core/package reading; ignore GPU/board sensors and unsupported APIs."""
    sensors = _safe_read(
        lambda: psutil_module.sensors_temperatures(fahrenheit=False), {}
    )
    if not isinstance(sensors, dict):
        return None
    for name, entries in sensors.items():
        sensor_name = str(name).casefold()
        if not any(token in sensor_name for token in ("cpu", "core", "package", "k10temp", "coretemp")):
            continue
        for entry in entries or ():
            current = _safe_read(lambda: float(getattr(entry, "current", None)))
            if current is not None and current >= 0 and current < float("inf"):
                return current
    return None


def read_windows_power_status():
    """Read Windows' native power state; return None when the API is unavailable."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None
        if status.BatteryFlag == 128:
            return {"battery_present": False, "percent": None, "charging": None}
        percent = status.BatteryLifePercent
        return {
            "battery_present": status.BatteryFlag != 128,
            "percent": percent if percent <= 100 else None,
            "charging": bool(status.BatteryFlag & 8) if status.BatteryFlag != 255 else None,
        }
    except Exception:
        return None


def collect_system_metrics(psutil_module=None) -> dict:
    """Read each hardware metric once; shared by the HUD and spoken PC-status command."""
    if psutil_module is None:
        import psutil as psutil_module

    drive = os.environ.get("SystemDrive", "C:") + chr(92)
    battery = _safe_read(psutil_module.sensors_battery, "N/A")
    windows_power = read_windows_power_status()
    if windows_power is not None:
        if not windows_power["battery_present"]:
            battery = None
        elif windows_power["percent"] is not None:
            # Prefer Windows' native percentage when available; it avoids stale or
            # misreported psutil readings on some Windows power-management drivers.
            from types import SimpleNamespace
            original_seconds = _safe_read(lambda: battery.secsleft) if battery not in (None, "N/A") else None
            battery = SimpleNamespace(
                percent=windows_power["percent"],
                power_plugged=windows_power["charging"],
                secsleft=original_seconds,
            )
    memory = _safe_read(psutil_module.virtual_memory)
    disk = _safe_read(lambda: psutil_module.disk_usage(drive))
    battery_seconds = _safe_read(lambda: battery.secsleft) if battery not in (None, "N/A") else None
    temperature = _safe_read(lambda: read_cpu_temperature(psutil_module))
    network_online = _safe_read(
        lambda: any(
            item.isup for name, item in psutil_module.net_if_stats().items()
            if name.casefold() not in {"lo", "loopback"}
        )
    )
    return {
        "cpu_percent": _finite_percent(_safe_read(lambda: psutil_module.cpu_percent(interval=None))),
        "memory_percent": _finite_percent(_safe_read(lambda: memory.percent)) if memory is not None else None,
        "memory_total": _safe_read(lambda: memory.total) if memory is not None else None,
        "memory_used": _safe_read(lambda: memory.used) if memory is not None else None,
        "disk_percent": _finite_percent(_safe_read(lambda: disk.percent)) if disk is not None else None,
        "disk_total": _safe_read(lambda: disk.total) if disk is not None else None,
        "disk_used": _safe_read(lambda: disk.used) if disk is not None else None,
        "disk_free": _safe_read(lambda: disk.free) if disk is not None else None,
        "battery": battery,
        "battery_seconds": battery_seconds,
        "windows_power": windows_power,
        "uptime_seconds": _safe_read(lambda: __import__("time").time() - psutil_module.boot_time()),
        "cpu_temperature": temperature,
        "network_online": network_online,
    }


def format_battery_status(battery) -> str:
    """Format battery state for the dashboard without assuming a laptop battery."""
    if battery is None:
        return "AC POWER"
    percent = _finite_percent(getattr(battery, "percent", None))
    if percent is None:
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
        value = _finite_percent(value)
        return f"{value:.0f}%" if value is not None else "Unavailable"

    battery = metrics["battery"]
    if battery == "N/A":
        battery_text = "Unavailable"
    elif battery is None:
        battery_text = "No battery detected"
    else:
        battery_percent = _finite_percent(_safe_read(lambda: battery.percent))
        if battery_percent is None:
            battery_text = "Unavailable"
        else:
            battery_text = f"{battery_percent:.0f}%" + (
                " (charging)" if getattr(battery, "power_plugged", False) else ""
            )

    network = metrics["network_online"]
    network_text = "Online" if network is True else "Offline" if network is False else "Unavailable"
    uptime = _safe_read(
        lambda: _format_uptime(now().timestamp() - psutil_module.boot_time()),
        "Unavailable",
    )
    drive_usage = percent(metrics["disk_percent"])
    return (
        "PC status (live snapshot)\n"
        f"CPU usage: {percent(metrics['cpu_percent'])}\n"
        f"Memory usage: {percent(metrics['memory_percent'])}\n"
        f"System drive usage: {drive_usage}\n"
        f"Storage total/used/free: {_format_bytes(metrics.get('disk_total'))} / {_format_bytes(metrics.get('disk_used'))} / {_format_bytes(metrics.get('disk_free'))}\n"
        f"RAM total/used: {_format_bytes(metrics.get('memory_total'))} / {_format_bytes(metrics.get('memory_used'))}\n"
        f"Battery: {battery_text}\n"
        f"Battery time remaining: {_format_battery_time(metrics.get('battery_seconds'))}\n"
        f"Network adapter link: {network_text}\n"
        f"Uptime: {uptime}"
    )


def _format_bytes(value) -> str:
    """Format a byte count; unavailable readings stay explicit."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not math.isfinite(amount) or amount < 0:
        return "N/A"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return "N/A"


def _format_battery_time(seconds) -> str:
    """Return remaining time only when the OS supplies a finite estimate."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError, OverflowError):
        return "N/A"
    if seconds < 0 or seconds >= 0xFFFFFFFF:
        return "N/A"
    hours, remainder = divmod(seconds, 3600)
    return f"{hours}h {remainder // 60}m"


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
