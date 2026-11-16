"""Tests for multi-step commands ("notepad kholo aur phir calculator kholo")."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

import command_chain as cc

MODULE_PATH = Path(__file__).resolve().parents[2] / "desktop" / "windows" / "jarvis_desktop.py"
SPEC = importlib.util.spec_from_file_location("jarvis_desktop", MODULE_PATH)
jarvis_desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jarvis_desktop)


class SplitTests(unittest.TestCase):
    def test_connectors_in_english_and_hinglish(self):
        self.assertEqual(cc.split_chain("open notepad and then open calculator"), ["open notepad", "open calculator"])
        self.assertEqual(cc.split_chain("notepad kholo aur phir calculator kholo"), ["notepad kholo", "calculator kholo"])
        self.assertEqual(cc.split_chain("open notepad, open calculator then pc status"),
                         ["open notepad", "open calculator", "pc status"])

    def test_plain_command_is_one_clause(self):
        self.assertEqual(cc.split_chain("volume up"), ["volume up"])
        self.assertEqual(cc.split_chain(""), [])

    def test_words_that_merely_contain_a_connector_are_not_split(self):
        self.assertEqual(cc.split_chain("open android studio"), ["open android studio"])
        self.assertEqual(cc.split_chain("open browser"), ["open browser"])


class RunChainTests(unittest.TestCase):
    def runner(self, known, log):
        def single(clause, dry_run=False):
            if clause not in known:
                return None
            if not dry_run:
                log.append(clause)
            return known[clause]
        return single

    def test_runs_all_steps_in_order(self):
        log = []
        out = cc.run_chain("a then b", self.runner({"a": "A done.", "b": "B done."}, log))
        self.assertEqual(log, ["a", "b"])
        self.assertEqual(out, "Done - 2 steps. A done. B done.")

    def test_one_unknown_step_runs_nothing(self):
        log = []
        self.assertIsNone(cc.run_chain("a then nonsense", self.runner({"a": "A done."}, log)))
        self.assertEqual(log, [])

    def test_too_many_steps_is_not_a_chain(self):
        known = {c: "ok" for c in "abcde"}
        self.assertIsNone(cc.run_chain("a then b then c then d then e", self.runner(known, [])))

    def test_failure_reports_the_step(self):
        def single(clause, dry_run=False):
            if clause == "b" and not dry_run:
                raise OSError("boom")
            return "ok"
        with self.assertRaises(RuntimeError) as ctx:
            cc.run_chain("a then b", single)
        self.assertIn("Step 2", str(ctx.exception))
        self.assertIn("1 step(s) completed", str(ctx.exception))


class DesktopChainTests(unittest.TestCase):
    def test_two_apps_launch_in_order(self):
        launched = []
        popen = lambda target, shell=False: launched.append(target)
        out = jarvis_desktop.run_local_command(
            "jarvis notepad kholo aur phir calculator kholo", popen=popen, open_url=lambda url: True)
        self.assertEqual(launched, [["notepad.exe"], ["calc.exe"]])
        self.assertIn("Opening Notepad.", out)
        self.assertIn("Opening Calculator.", out)

    def test_app_then_website(self):
        launched, opened = [], []
        out = jarvis_desktop.run_local_command(
            "open notepad and then open youtube",
            popen=lambda target, shell=False: launched.append(target), open_url=lambda url: opened.append(url) or True)
        self.assertEqual((launched, opened), ([["notepad.exe"]], ["https://www.youtube.com"]))
        self.assertTrue(out.startswith("Done - 2 steps."))

    def test_unknown_step_launches_nothing(self):
        launched = []
        out = jarvis_desktop.run_local_command(
            "open notepad then format my disk", popen=lambda *a, **k: launched.append(a), open_url=lambda url: True)
        self.assertIsNone(out)
        self.assertEqual(launched, [])

    def test_dry_run_never_touches_hardware_keys(self):
        with patch.object(jarvis_desktop, "press_windows_media_key") as press, \
                patch.object(jarvis_desktop, "adjust_windows_brightness") as bright:
            out = jarvis_desktop.run_local_command("volume up then brightness down then do something weird")
        self.assertIsNone(out)
        press.assert_not_called()
        bright.assert_not_called()

    def test_volume_and_brightness_chain_executes_after_validation(self):
        with patch.object(jarvis_desktop, "press_windows_media_key", return_value=True) as press, \
                patch.object(jarvis_desktop, "adjust_windows_brightness", return_value=60) as bright:
            out = jarvis_desktop.run_local_command("volume up aur phir brightness down")
        press.assert_called_once_with("volume_up")
        bright.assert_called_once_with("down")
        self.assertIn("Volume increased.", out)
        self.assertIn("60%", out)

    def test_single_commands_behave_as_before(self):
        launched = []
        out = jarvis_desktop.run_local_command(
            "open notepad", popen=lambda target, shell=False: launched.append(target))
        self.assertEqual((out, launched), ("Opening Notepad.", [["notepad.exe"]]))
        self.assertIsNone(jarvis_desktop.run_local_command("what is the weather"))


if __name__ == "__main__":
    unittest.main()
