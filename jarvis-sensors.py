"""Read-only Windows 11 telemetry bridge. Requires Python 3; no pip packages."""
import argparse
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PORT = 8765
DEFAULT_ORIGINS = {
    "http://localhost:8080", "http://localhost:5173",
    "http://127.0.0.1:8080", "http://127.0.0.1:5173",
    "https://id-preview--0aada67e-2799-43f2-ae9b-1e882c4f5583.lovable.app",
}
ALLOWED_ORIGINS = set(DEFAULT_ORIGINS)
SNAPSHOT = None
LOCK = threading.Lock()
STOP = threading.Event()

POWERSHELL = r'''
$ErrorActionPreference = 'Stop'
function Read-Cim($class, $namespace = 'root/cimv2') {
  try { @(Get-CimInstance -ClassName $class -Namespace $namespace -OperationTimeoutSec 2 -ErrorAction Stop) } catch { @() }
}
$os = Read-Cim 'Win32_OperatingSystem' | Select-Object -First 1
$cpu = Read-Cim 'Win32_Processor' | Select-Object -First 1
$usage = Read-Cim 'Win32_PerfFormattedData_PerfOS_Processor' | Where-Object Name -eq '_Total' | Select-Object -First 1
$disk = Read-Cim 'Win32_LogicalDisk' | Where-Object DeviceID -eq 'C:' | Select-Object -First 1
$battery = Read-Cim 'Win32_Battery' | Select-Object -First 1
$gpu = Read-Cim 'Win32_VideoController' | Select-Object -First 1
$cpuTemp = $null; $gpuTemp = $null
foreach ($ns in @('root/LibreHardwareMonitor', 'root/OpenHardwareMonitor')) {
  $hardware = @(Read-Cim 'Hardware' $ns)
  $sensors = @(Read-Cim 'Sensor' $ns | Where-Object { $_.SensorType -eq 'Temperature' -and $null -ne $_.Value -and $_.Value -ge -50 -and $_.Value -le 150 })
  foreach ($sensor in $sensors) {
    $parent = $hardware | Where-Object Identifier -eq $sensor.Parent | Select-Object -First 1
    if ($parent.HardwareType -eq 'Cpu' -or $sensor.Identifier -match '/(intelcpu|amdcpu)/') {
      if ($null -eq $cpuTemp -or $sensor.Value -gt $cpuTemp) { $cpuTemp = [double]$sensor.Value }
    }
    if ($parent.HardwareType -match '^Gpu' -or $sensor.Identifier -match '/(nvidiagpu|atigpu|intelgpu)/') {
      if ($null -eq $gpuTemp -or $sensor.Value -gt $gpuTemp) { $gpuTemp = [double]$sensor.Value }
    }
  }
  if ($null -ne $cpuTemp -or $null -ne $gpuTemp) { break }
}
$charging = $null
if ($battery) {
  if ($battery.BatteryStatus -in @(2,3,6,7,8,9)) { $charging = $true }
  elseif ($battery.BatteryStatus -in @(1,4,5)) { $charging = $false }
}
$result = @{
  version = 1
  batteryPercent = $(if ($battery -and $null -ne $battery.EstimatedChargeRemaining) { [double]$battery.EstimatedChargeRemaining } else { $null })
  charging = $charging
  cpuPercent = $(if ($usage -and $null -ne $usage.PercentProcessorTime) { [double]$usage.PercentProcessorTime } else { $null })
  diskTotal = $(if ($disk) { [double]$disk.Size } else { $null })
  diskFree = $(if ($disk) { [double]$disk.FreeSpace } else { $null })
  ramTotal = $(if ($os) { [double]$os.TotalVisibleMemorySize * 1024 } else { $null })
  ramFree = $(if ($os) { [double]$os.FreePhysicalMemory * 1024 } else { $null })
  cpuTemperature = $cpuTemp; gpuTemperature = $gpuTemp
  cpuName = $(if ($cpu) { $cpu.Name.Trim() } else { $null })
  gpuName = $(if ($gpu) { $gpu.Name } else { $null })
  osName = $(if ($os) { $os.Caption } else { $null })
  architecture = $(if ($os) { $os.OSArchitecture } else { $null })
  uptimeSeconds = $(if ($os -and $os.LastBootUpTime) { [math]::Max(0, ((Get-Date) - $os.LastBootUpTime).TotalSeconds) } else { $null })
}
$result | ConvertTo-Json -Compress
'''

def valid_origin(origin):
    try:
        parsed = urlsplit(origin)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc) and not parsed.username and not parsed.password and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
    except ValueError:
        return False

def collect():
    global SNAPSHOT
    while not STOP.is_set():
        try:
            output = subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', POWERSHELL],
                capture_output=True, text=True, timeout=25, creationflags=0x08000000,
            )
            if output.returncode:
                raise RuntimeError('Windows sensor read failed')
            value = json.loads(output.stdout)
            with LOCK:
                SNAPSHOT = (time.monotonic(), value)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            with LOCK:
                SNAPSHOT = None
            print('Sensors unavailable; retrying. No previous readings will be served.', flush=True)
        STOP.wait(3)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, status, payload=None, origin=None):
        body = json.dumps(payload).encode('utf-8') if payload is not None else b''
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Vary', 'Origin')
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        if body:
            self.wfile.write(body)

    def authorized_origin(self):
        origin = self.headers.get('Origin')
        if self.headers.get('Host') not in (f'localhost:{PORT}', f'127.0.0.1:{PORT}'):
            return None
        return origin if origin in ALLOWED_ORIGINS else None

    def do_OPTIONS(self):
        origin = self.authorized_origin()
        if not origin or self.path != '/metrics' or self.headers.get('Access-Control-Request-Method') != 'GET':
            self.reply(403)
            return
        self.reply(204, origin=origin)

    def do_GET(self):
        origin = self.authorized_origin()
        if not origin:
            self.reply(403)
            return
        if self.path != '/metrics':
            self.reply(404, origin=origin)
            return
        with LOCK:
            snapshot = SNAPSHOT
        if snapshot is None or time.monotonic() - snapshot[0] > 10:
            self.reply(503, {'error': 'Sensors unavailable'}, origin)
        else:
            self.reply(200, snapshot[1], origin)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', action='append', default=[], help='Exact trusted dashboard origin (no path)')
    args = parser.parse_args()
    for origin in args.origin:
        if not valid_origin(origin):
            parser.error('Each origin must be an http(s) address without a path')
        ALLOWED_ORIGINS.add(origin.rstrip('/'))
    if sys.platform != 'win32':
        parser.error('This helper reads Windows sensors and must run on your Windows laptop')
    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError:
        parser.exit(1, 'Cannot start: port 8765 is already in use. Close the previous helper.\n')
    threading.Thread(target=collect, daemon=True).start()
    print('JARVIS sensors running on localhost:8765. Keep this window open; Ctrl+C stops it.')
    print('Temperature needs a compatible running LibreHardwareMonitor/Open Hardware Monitor WMI provider.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        STOP.set()
        server.server_close()

if __name__ == '__main__':
    main()