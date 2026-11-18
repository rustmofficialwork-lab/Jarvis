import json
import unittest
import urllib.error
from types import SimpleNamespace

import brain_health as bh

GIB = 1024 ** 3


def opener_returning(models=None, raw=None, exc=None):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, size=-1):
            return raw if raw is not None else json.dumps({"models": [{"name": n} for n in models or []]}).encode()

    class Opener:
        def __init__(self): self.urls = []
        def open(self, url, timeout):
            self.urls.append((url, timeout))
            if exc:
                raise exc
            return Response()
    return Opener()


def ram(total_gb, free_gb):
    return SimpleNamespace(virtual_memory=lambda: SimpleNamespace(total=total_gb * GIB, available=free_gb * GIB))


class CommandParsingTests(unittest.TestCase):
    def test_explicit_commands_match(self):
        for text in ("brain check", "Brain status karo", "jarvis ai health", "check my brain", "ollama check",
                     "brain ka status batao", "brain kaisa hai?", "please ai check karo"):
            with self.subTest(text=text):
                self.assertTrue(bh.is_brain_check_command(text))

    def test_normal_chat_is_never_hijacked(self):
        for text in ("what is a brain", "brain tumour kya hota hai", "check my email", "ai kya hai",
                     "explain brain status of a patient", "", None):
            with self.subTest(text=text):
                self.assertFalse(bh.is_brain_check_command(text))


class CheckTests(unittest.TestCase):
    def test_ready_when_model_installed(self):
        opener = opener_returning(["qwen3:4b", "other:1b"])
        health = bh.check_local_brain(opener=opener, psutil_module=ram(8, 3.2))
        self.assertTrue(health.ready and not health.deep_think_ok and health.low_ram)
        self.assertEqual((health.ram_total_gb, health.ram_free_gb), (8.0, 3.2))
        self.assertEqual(opener.urls[0][0], "http://127.0.0.1:11434/api/tags")
        self.assertIn("deep think", bh.format_brain_report(health))

    def test_ollama_down_gives_start_hint_without_raising(self):
        health = bh.check_local_brain(opener=opener_returning(exc=urllib.error.URLError("refused")),
                                      psutil_module=ram(8, 3))
        self.assertFalse(health.ollama_running)
        report = bh.format_brain_report(health)
        self.assertIn("band hai", report)
        self.assertIn("Start menu", report)

    def test_missing_model_gives_exact_pull_command(self):
        health = bh.check_local_brain(opener=opener_returning(["phi3:mini"]), psutil_module=ram(8, 3))
        self.assertTrue(health.ollama_running and not health.model_installed)
        self.assertIn("ollama pull qwen3:4b", bh.format_brain_report(health))

    def test_low_ram_warns_and_disables_deep_think(self):
        health = bh.check_local_brain(opener=opener_returning(["qwen3:4b"]), psutil_module=ram(8, 1.0))
        self.assertTrue(health.low_ram and not health.deep_think_ok)
        self.assertIn("RAM kam", bh.format_brain_report(health))

    def test_garbage_and_http_errors_are_reported_not_raised(self):
        bad = bh.check_local_brain(opener=opener_returning(raw=b"not json"), psutil_module=ram(8, 3))
        self.assertIsNotNone(bad.error)
        http = bh.check_local_brain(
            opener=opener_returning(exc=urllib.error.HTTPError("u", 500, "x", {}, None)), psutil_module=ram(8, 3))
        self.assertTrue(http.ollama_running and "500" in http.error)
        self.assertIn("Dikkat", bh.format_brain_report(http))

    def test_missing_psutil_still_reports(self):
        broken = SimpleNamespace(virtual_memory=lambda: (_ for _ in ()).throw(OSError("x")))
        health = bh.check_local_brain(opener=opener_returning(["qwen3:4b"]), psutil_module=broken)
        self.assertTrue(health.ready)
        self.assertIsNone(health.ram_free_gb)
        self.assertNotIn("RAM:", bh.format_brain_report(health))

    def test_oversized_response_is_rejected(self):
        health = bh.check_local_brain(opener=opener_returning(raw=b"x" * (bh.MAX_RESPONSE_BYTES + 5)),
                                      psutil_module=ram(8, 3))
        self.assertIsNotNone(health.error)


if __name__ == "__main__":
    unittest.main()
