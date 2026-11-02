# JARVIS live desktop dashboard

The native Windows dashboard preserves the original navy/cyan JARVIS interface and displays local telemetry without browser estimates.

- Local clock and date: refreshed every second.
- CPU, RAM, system-drive use, battery, CPU temperature, uptime and network link: refreshed about every 2.5 seconds.
- Network upload/download throughput: calculated from Windows network-interface byte counters between samples.
- NVIDIA GPU load, VRAM and temperature: read from the installed nvidia-smi utility; other GPU vendors or unsupported drivers show N/A.
- Top three memory-using processes: read-only process names and usage, refreshed about every five seconds.

Unsupported readings remain N/A; no hardware values are fabricated. Weather is not shown in the desktop HUD because a location has not been configured. Weather lookup remains available through the assistant's online command path.
