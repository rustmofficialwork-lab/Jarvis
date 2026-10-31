"""Tests for local PC status reporting."""
import unittest
from datetime import datetime
from types import SimpleNamespace

from system_monitor import collect_system_metrics, get_system_status, get_top_processes, _format_uptime


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

    def test_shared_collector_reads_metrics_once_for_both_surfaces(self):
        calls = {"cpu": 0, "memory": 0, "disk": 0, "battery": 0, "network": 0}

        class CountingPsutil(FakePsutil):
            def cpu_percent(self, interval=None):
                calls["cpu"] += 1
                return super().cpu_percent(interval)

            def virtual_memory(self):
                calls["memory"] += 1
                return super().virtual_memory()

            def disk_usage(self, path):
                calls["disk"] += 1
                return super().disk_usage(path)

            def sensors_battery(self):
                calls["battery"] += 1
                return super().sensors_battery()

            def net_if_stats(self):
                calls["network"] += 1
                return super().net_if_stats()

            def sensors_temperatures(self, **kwargs):
                raise NotImplementedError

        metrics = collect_system_metrics(CountingPsutil())
        self.assertEqual(metrics["cpu_percent"], 23.4)
        self.assertEqual(metrics["memory_percent"], 61.2)
        self.assertEqual(metrics["disk_percent"], 72.8)
        self.assertEqual(metrics["network_online"], True)
        self.assertIsNone(metrics["cpu_temperature"])
        self.assertEqual(calls, {
            "cpu": 1, "memory": 1, "disk": 1, "battery": 1, "network": 1,
        })
    def test_uptime_format(self):
        self.assertEqual(_format_uptime(0), "0m")
        self.assertEqual(_format_uptime(3661), "1h 1m")
        self.assertEqual(_format_uptime(90061), "1d 1h 1m")


if __name__ == "__main__":
    unittest.main()


class TopProcessTests(unittest.TestCase):
    def test_processes_are_sorted_by_memory_and_bounded(self):
        class Process:
            def __init__(self, info):
                self.info = info
        class FakePsutil:
            def process_iter(self, attrs):
                self.attrs = attrs
                return [
                    Process({"pid": 10, "name": "Browser", "cpu_percent": 4, "memory_percent": 25}),
                    Process({"pid": 11, "name": "Editor", "cpu_percent": 8, "memory_percent": 5}),
                    Process({"pid": 12, "name": "Game", "cpu_percent": 20, "memory_percent": 40}),
                ]
        result = get_top_processes(2, FakePsutil())
        self.assertIn("Top 2 processes", result)
        self.assertLess(result.index("Game (PID 12)"), result.index("Browser (PID 10)"))
        self.assertNotIn("Editor (PID 11)", result)

    def test_unreadable_process_is_skipped(self):
        class Process:
            def __init__(self, info=None, fail=False):
                self.info, self.fail = info, fail
            @property
            def info(self):
                if self.fail:
                    raise PermissionError("access denied")
                return self._info
            @info.setter
            def info(self, value):
                self._info = value
        class FakePsutil:
            def process_iter(self, attrs):
                return [Process(fail=True), Process({"pid": 2, "name": "Safe", "cpu_percent": 1, "memory_percent": 3})]
        result = get_top_processes(psutil_module=FakePsutil())
        self.assertIn("Safe (PID 2)", result)
        self.assertNotIn("access denied", result)

    def test_invalid_limits_are_rejected(self):
        for limit in (0, 21, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                get_top_processes(limit, object())
