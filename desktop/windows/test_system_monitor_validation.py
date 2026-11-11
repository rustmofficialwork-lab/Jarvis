"""Regression tests for invalid operating-system metric readings."""
import unittest
from types import SimpleNamespace

from system_monitor import collect_system_metrics, format_battery_status, get_system_status


class InvalidMetricTests(unittest.TestCase):
    def test_non_finite_and_out_of_range_percentages_are_unavailable(self):
        class Psutil:
            def cpu_percent(self, interval=None):
                return float("nan")

            def virtual_memory(self):
                return SimpleNamespace(percent=float("inf"), total=1024, used=512)

            def disk_usage(self, path):
                return SimpleNamespace(percent=101, total=2048, used=1024, free=1024)

            def sensors_battery(self):
                return SimpleNamespace(percent=-1, power_plugged=False, secsleft=60)

            def net_if_stats(self):
                return {"Ethernet": SimpleNamespace(isup=True)}

            def boot_time(self):
                return 0

        metrics = collect_system_metrics(Psutil())
        self.assertIsNone(metrics["cpu_percent"])
        self.assertIsNone(metrics["memory_percent"])
        self.assertIsNone(metrics["disk_percent"])
        self.assertIn("CPU usage: Unavailable", get_system_status(Psutil()))
        self.assertIn("Memory usage: Unavailable", get_system_status(Psutil()))
        self.assertIn("System drive usage: Unavailable", get_system_status(Psutil()))
        self.assertIn("Battery: N/A", get_system_status(Psutil()))

    def test_battery_formatter_rejects_non_finite_values(self):
        for value in (float("nan"), float("inf"), -1, 101, "invalid"):
            with self.subTest(value=value):
                self.assertEqual(
                    format_battery_status(SimpleNamespace(percent=value)), "N/A"
                )


if __name__ == "__main__":
    unittest.main()
