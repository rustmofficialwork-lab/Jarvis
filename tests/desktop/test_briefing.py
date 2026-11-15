"""Tests for the read-only daily briefing."""
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import briefing as br

SPEC = importlib.util.spec_from_file_location("jarvis_desktop", Path(__file__).with_name("jarvis_desktop.py"))
jarvis_desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jarvis_desktop)

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 11, 16, 8, 30, tzinfo=IST)
SYSTEM = (
    "PC status (live snapshot)\nCPU usage: 12%\nMemory usage: 91%\nSystem drive usage: 55%\n"
    "Battery: 15%\nBattery time remaining: 40 min\nNetwork adapter link: Online\nUptime: 3h"
)


def reminder(message, when, notified=0):
    return {"message": message, "due_at": when.isoformat(timespec="seconds"), "notified": notified}


class CommandDetectionTests(unittest.TestCase):
    def test_accepts_briefing_requests(self):
        for text in ("briefing", "Jarvis, daily briefing", "good morning", "Good morning Jarvis!",
                     "aaj ka briefing do", "give me my briefing", "suprabhat"):
            with self.subTest(text=text):
                self.assertTrue(br.is_briefing_command(text))

    def test_ignores_ordinary_chat(self):
        for text in ("good morning everyone, explain pointers", "how is the weather", "brief me on python",
                     "what is a briefing note"):
            with self.subTest(text=text):
                self.assertFalse(br.is_briefing_command(text))


class BuildBriefingTests(unittest.TestCase):
    def test_greeting_and_date(self):
        text = br.build_briefing(NOW, [], None)
        self.assertTrue(text.startswith("Good morning!"))
        self.assertIn("Monday, 16 November 2026", text)
        self.assertIn("8:30 AM", text)
        self.assertIn("koi reminder nahi", text)

    def test_only_upcoming_unnotified_reminders_sorted(self):
        items = [
            reminder("late one", NOW + timedelta(hours=5)),
            reminder("soon one", NOW + timedelta(hours=1)),
            reminder("tomorrow far", NOW + timedelta(hours=40)),
            reminder("already shown", NOW + timedelta(hours=2), notified=1),
            reminder("past", NOW - timedelta(hours=1)),
            {"message": "broken", "due_at": "not-a-date"},
        ]
        lines = br.build_briefing(NOW, items, None).splitlines()
        reminder_lines = [line for line in lines if line.startswith("- ")]
        self.assertEqual(reminder_lines, ["- aaj 9:30 AM: soon one", "- aaj 1:30 PM: late one"])
        self.assertIn("(2)", lines[1])

    def test_tomorrow_label_and_item_cap(self):
        items = [reminder(f"r{i}", NOW + timedelta(minutes=10 * (i + 1))) for i in range(8)]
        text = br.build_briefing(NOW, items, None, max_items=3)
        self.assertEqual(sum(line.startswith("- ") for line in text.splitlines()), 3)
        self.assertIn("aur 5 aur", text)
        late_night = datetime(2026, 11, 16, 22, 0, tzinfo=IST)
        text = br.build_briefing(late_night, [reminder("gym", late_night + timedelta(hours=9))], None)
        self.assertIn("- kal 7:00 AM: gym", text)

    def test_pc_summary_and_warnings(self):
        text = br.build_briefing(NOW, [], SYSTEM)
        self.assertIn("PC: CPU 12%, RAM 91%, Drive 55%, Battery 15%.", text)
        self.assertIn("Battery kam hai", text)
        self.assertIn("RAM kaafi bhari", text)
        self.assertNotIn("CPU bahut busy", text)

    def test_charging_battery_has_no_warning(self):
        text = br.build_briefing(NOW, [], "Battery: 10% (charging)\nCPU usage: 5%")
        self.assertIn("Battery 10% (charging)", text)
        self.assertNotIn("Battery kam hai", text)

    def test_missing_or_garbled_system_text_is_skipped(self):
        self.assertNotIn("PC:", br.build_briefing(NOW, [], None))
        self.assertNotIn("PC:", br.build_briefing(NOW, [], "Unavailable"))

    def test_greeting_by_time_of_day(self):
        self.assertTrue(br.build_briefing(NOW.replace(hour=14), [], None).startswith("Good afternoon!"))
        self.assertTrue(br.build_briefing(NOW.replace(hour=19), [], None).startswith("Good evening!"))
        self.assertTrue(br.build_briefing(NOW.replace(hour=2), [], None).startswith("Hello!"))


class DesktopBriefingTests(unittest.TestCase):
    @staticmethod
    def app(reminders):
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.history, app.shown = [], []
        app.reminder_store = type("Store", (), {"list": lambda self, limit=100: reminders})()
        app._append = lambda who, text, *rest: app.shown.append((who, text))
        app._set_status = lambda text: app.shown.append(("STATUS", text))
        return app

    def test_briefing_is_wired_into_local_commands(self):
        soon = datetime.now().astimezone() + timedelta(minutes=30)
        app = self.app([reminder("pani peena", soon)])
        with (
            patch.object(jarvis_desktop, "save_chat_history"),
            patch.object(jarvis_desktop, "parse_advanced_command", return_value=None),
            patch.object(jarvis_desktop.JarvisDesktop, "_try_delete_files_command", return_value=False),
            patch("system_monitor.get_system_status", return_value="CPU usage: 10%\nBattery: 90%"),
        ):
            self.assertTrue(app._try_local_command("good morning jarvis"))
        self.assertEqual(app.shown[0], ("YOU", "good morning jarvis"))
        self.assertIn("pani peena", app.shown[1][1])
        self.assertIn("PC: CPU 10%, Battery 90%.", app.shown[1][1])

    def test_briefing_survives_broken_stores(self):
        app = self.app([])
        app.reminder_store = object()  # no .list at all
        with patch("system_monitor.get_system_status", side_effect=RuntimeError("no psutil")):
            text = app._compose_briefing()
        self.assertIn("koi reminder nahi", text)

    def test_ordinary_prompts_are_not_intercepted(self):
        app = self.app([])
        self.assertFalse(app._handle_briefing_command("good morning everyone, explain pointers"))
        self.assertEqual(app.shown, [])


if __name__ == "__main__":
    unittest.main()
