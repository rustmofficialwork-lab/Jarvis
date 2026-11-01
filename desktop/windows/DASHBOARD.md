# JARVIS live desktop dashboard

The Windows desktop window includes a native live telemetry strip sourced from local `psutil` readings. It refreshes approximately every 2.5 seconds and displays CPU load, RAM usage, system-drive usage, battery state, CPU temperature (only when Windows exposes a CPU sensor), network-adapter link state, and storage capacity.

The dashboard does not report fabricated GPU load, GPU temperature, or unsupported sensor values. Unsupported readings remain `N/A`. Browser-only estimates are not presented as hardware telemetry. The telemetry refresh runs on Tk's event loop and uses the existing one-second metric cache to avoid unnecessary repeated sensor calls.

Use **system status** in chat for a detailed text snapshot and **top processes** for a read-only process usage list. Temperature support varies by PC vendor, driver, and sensor interface.
