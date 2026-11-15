JARVIS real readings - Windows 11

1. Install Python 3 from python.org (enable the Python launcher).
2. Download jarvis-sensors.py into Downloads.
3. Open Terminal in Downloads and run:
   py jarvis-sensors.py
4. Keep the terminal open. Open the dashboard in Chrome or Edge and click
   Connect laptop. Allow local network access if the browser asks.
5. Stop with Ctrl+C. No administrator rights or pip packages are needed.

The helper reads CPU use, battery, C: volume size/free space, RAM, hardware
names and uptime through Windows. It refreshes after each collection plus
3 seconds. Missing sensors stay Unavailable; numbers are never simulated.

CPU/GPU temperatures: run a compatible LibreHardwareMonitor or Open Hardware
Monitor version with its WMI provider enabled. Some versions/laptops do not
expose temperatures. The helper reports the highest available CPU/GPU sensor,
not room temperature. It never substitutes ACPI thermal-zone temperatures.
Obtain the monitor only from its official project. Its sensor driver may
require elevation; the JARVIS helper itself does not.

Allowed dashboard addresses: localhost ports 8080/5173 and this project's
Lovable preview. If running a different address, copy just its origin and run:
   py jarvis-sensors.py --origin https://your-real-dashboard-address
Only grant addresses you trust. No wildcard origins are accepted.

Troubleshooting: Leave this window running, use Chrome/Edge, allow local
network permission for the dashboard, and ensure the address is allowed.
Browser/Windows policies can block localhost access. No firewall opening
is required; the helper listens only on this laptop, not on the network.
Do not disable browser security. Browser battery readings can work without
the helper if Battery Status API is supported.

Readings remain on your laptop and are sent only to the allowed dashboard.
This helper cannot execute commands from web requests or change your system.