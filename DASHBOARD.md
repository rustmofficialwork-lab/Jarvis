# JARVIS live desktop dashboard

The Windows desktop window includes a native live telemetry strip sourced from local `psutil` readings. It refreshes approximately every 2.5 seconds and displays CPU load, RAM usage, system-drive usage, battery state, CPU temperature (only when Windows exposes a CPU sensor), network-adapter link state, and storage capacity.

Unsupported readings remain `N/A`. GPU load and GPU temperature are not fabricated. Temperature support varies by PC vendor, driver, and sensor interface.
