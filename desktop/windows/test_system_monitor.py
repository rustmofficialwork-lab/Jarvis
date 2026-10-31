"""Tests for local PC status reporting."""
import unittest
from datetime import datetime
from types import SimpleNamespace

from system_monitor import get_system_status, _format_uptime


class FakePsutil:
    def cpu_percent(self, interval=None):
        return 23.4

    def virtual_memory(self):
        return SimpleNamespace(percent=61.2)

    def disk_usage(self, path):
        return SimpleNamespace(percent=72.8)

    def sensors_battery(self):
        return SimpleNamespace(percent=88, power_plugged=True)

    def net_if_stats(self):
        return {"Ethernet": SimpleNamespace(isup=True), "Loopback": SimpleNamespace(isup=True)}

    def boot_time(self):
        return 1000


class SystemMonitorTests(unittest.TestCase):
    def test_status_contains_live_metrics(self):
        result = get_system_status(FakePsutil(), now=lambda: datetime.fromtimestamp(1000 + 90061))
        self.assertIn("CPU usage: 23%", result)
        self.assertIn("Memory usage: 61%", result)
        self.assertIn("System drive usage: 73%", result)
        self.assertIn("Battery: 88% (charging)", result)
        self.assertIn("Network: Online", result)
        self.assertIn("Uptime: 1d 1h 1m", result)

    def test_unsupported_sensor_does_not_hide_other_metrics(self):
        class Partial(FakePsutil):
            def sensors_battery(self):
                raise OSError("not supported")

        result = get_system_status(Partial())
        self.assertIn("Battery: Unavailable", result)
        self.assertIn("CPU usage: 23%", result)

    def test_uptime_format(self):
        self.assertEqual(_format_uptime(0), "0m")
        self.assertEqual(_format_uptime(3661), "1h 1m")
        self.assertEqual(_format_uptime(90061), "1d 1h 1m")


if __name__ == "__main__":
    unittest.main()
