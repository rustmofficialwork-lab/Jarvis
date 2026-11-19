"""Integration tests: smart brain wired into the desktop app's offline (Ollama) path."""
import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[2] / "desktop" / "windows" / "jarvis_desktop.py"
SPEC = importlib.util.spec_from_file_location("jarvis_desktop", MODULE_PATH)
jarvis_desktop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jarvis_desktop)


def fake_ollama(replies):
    """Patch the opener so each POST returns the next scripted reply; capture payloads."""
    captured = []

    class Response:
        def __init__(self, text):
            self.text = text
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size=-1):
            return json.dumps({"message": {"role": "assistant", "content": self.text}}).encode("utf-8")

    class Opener:
        def open(self, request, timeout):
            captured.append(json.loads(request.data.decode("utf-8")))
            return Response(replies[len(captured) - 1])

    return patch.object(jarvis_desktop.urllib.request, "build_opener", return_value=Opener()), captured


def plan_for(prompt, history=()):
    return jarvis_desktop.prepare_brain_plan(
        prompt, jarvis_desktop.filter_memory_history(list(history)), None, fixed_chars=2800
    )


class OfflineSmartBrainTests(unittest.TestCase):
    def test_math_is_grounded_and_uses_low_temperature(self):
        opener, captured = fake_ollama(["Jawab 10 hai."])
        prompt = "2 x 3 + 4 kitna hota hai"
        with opener:
            answer = jarvis_desktop.local_chat_completion(prompt, [], brain_plan=plan_for(prompt))
        self.assertEqual(answer, "Jawab 10 hai.")
        system_text = " ".join(m["content"] for m in captured[0]["messages"] if m["role"] == "system")
        self.assertIn("2 * 3 + 4 = 10", system_text)
        self.assertLess(captured[0]["options"]["temperature"], 0.3)
        self.assertEqual(captured[0]["messages"][-1]["content"], prompt)

    def test_code_requests_get_a_bigger_but_bounded_window(self):
        opener, captured = fake_ollama(["print('hi')"])
        prompt = "python me bubble sort ka code likho"
        with opener:
            jarvis_desktop.local_chat_completion(prompt, [], brain_plan=plan_for(prompt))
        options = captured[0]["options"]
        self.assertEqual((options["num_ctx"], options["num_predict"]), (4096, 768))
        self.assertTrue(captured[0]["stream"] is False)

    def test_long_history_is_budgeted_so_the_system_prompt_cannot_be_pushed_out(self):
        history = []
        for i in range(8):
            history.append({"role": "user", "content": f"sawal {i}. " + "a" * 1400})
            history.append({"role": "assistant", "content": f"jawab {i}. " + "b" * 1400})
        prompt = "ab batao kya hai"
        opener, captured = fake_ollama(["ok"])
        with opener:
            jarvis_desktop.local_chat_completion(prompt, history, brain_plan=plan_for(prompt, history))
        messages = captured[0]["messages"]
        options = captured[0]["options"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("J.A.R.V.I.S.", messages[0]["content"])
        total_chars = sum(len(m["content"]) for m in messages)
        self.assertLessEqual(total_chars, options["num_ctx"] * 3 + 600)
        self.assertTrue(any("Earlier in this conversation" in m["content"] for m in messages))

    def test_deep_think_runs_draft_critique_revise_and_returns_revision(self):
        prompt = "explain why the sky is blue step by step"
        opener, captured = fake_ollama(["draft answer", "step 2 is missing", "final improved answer"])
        with opener:
            answer = jarvis_desktop.local_chat_completion(prompt, [], brain_plan=plan_for(prompt))
        self.assertEqual(answer, "final improved answer")
        self.assertEqual(len(captured), 3)

    def test_deep_think_stops_early_when_the_critique_says_ok(self):
        prompt = "explain why the sky is blue step by step"
        opener, captured = fake_ollama(["good draft", "OK"])
        with opener:
            answer = jarvis_desktop.local_chat_completion(prompt, [], brain_plan=plan_for(prompt))
        self.assertEqual((answer, len(captured)), ("good draft", 2))

    def test_simple_chat_makes_exactly_one_model_call(self):
        opener, captured = fake_ollama(["Namaste!"])
        with opener:
            self.assertEqual(
                jarvis_desktop.local_chat_completion("hello", [], brain_plan=plan_for("hello")), "Namaste!"
            )
        self.assertEqual(len(captured), 1)


class AppWiringTests(unittest.TestCase):
    @staticmethod
    def app(settings, memory_store):
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.settings = settings
        app.memory_store = memory_store
        app.history = []
        return app

    def test_memories_are_ranked_only_when_sharing_is_enabled(self):
        store = SimpleNamespace(list=lambda: [
            {"content": "User studies C programming for the RGPV exam", "updated_at": "2026-11-01T00:00:00+00:00"},
            {"content": "User likes cricket", "updated_at": "2026-11-02T00:00:00+00:00"},
        ])
        on = self.app({"share_memory_with_ai": True}, store)
        off = self.app({"share_memory_with_ai": False}, store)
        self.assertEqual(on._smart_memories("C programming exam", []),
                         ["User studies C programming for the RGPV exam"])
        self.assertEqual(off._smart_memories("C programming exam", []), [])
        self.assertEqual(off._smart_memories("anything", ["kept"]), ["kept"])

    def test_memory_ranking_failure_or_missing_list_falls_back_to_base(self):
        broken = SimpleNamespace(list=lambda: (_ for _ in ()).throw(OSError("db locked")))
        self.assertEqual(self.app({"share_memory_with_ai": True}, broken)._smart_memories("x y", ["base"]), ["base"])
        legacy = SimpleNamespace(context=lambda query: [])
        self.assertEqual(self.app({"share_memory_with_ai": True}, legacy)._smart_memories("x y", ["base"]), ["base"])

    def test_memories_are_deduplicated_and_capped_at_five(self):
        items = [{"content": f"project alpha item {i}"} for i in range(9)]
        store = SimpleNamespace(list=lambda: items)
        result = self.app({"share_memory_with_ai": True}, store)._smart_memories(
            "alpha project", ["project alpha item 0", "legacy"]
        )
        self.assertLessEqual(len(result), 5)
        self.assertEqual(len(result), len(set(result)))

    def test_planning_failure_never_breaks_the_reply(self):
        app = self.app({}, None)
        with patch.object(jarvis_desktop, "prepare_brain_plan", side_effect=RuntimeError("boom")):
            self.assertIsNone(app._plan_local_brain("hello", []))

    def test_offline_fallback_passes_a_plan_to_the_local_model(self):
        import queue
        app = self.app({"endpoint": jarvis_desktop.DEFAULT_ENDPOINT, "model": jarvis_desktop.DEFAULT_MODEL},
                       SimpleNamespace(context=lambda query: []))
        app.ai_api_key = ""
        app.device_token = "t"
        app.events = queue.Queue()
        app._ensure_device_token = lambda force=False: "t"
        with (
            patch.object(jarvis_desktop, "handle_online_command", return_value=None),
            patch.object(jarvis_desktop, "chat_completion", side_effect=RuntimeError("offline")),
            patch.object(jarvis_desktop, "local_chat_completion", return_value="local") as local,
        ):
            self.assertEqual(app._get_online_reply("2 + 2 kitna hota hai"), "local")
        plan = local.call_args.kwargs["brain_plan"]
        self.assertEqual(plan.profile.kind, "math")
        self.assertTrue(any("= 4" in note for note in plan.grounding))


class BrainCheckCommandTests(unittest.TestCase):
    @staticmethod
    def app():
        app = jarvis_desktop.JarvisDesktop.__new__(jarvis_desktop.JarvisDesktop)
        app.history = []
        app.shown = []
        app._append = lambda who, text, *rest: app.shown.append((who, text))
        app._set_status = lambda text: app.shown.append(("STATUS", text))
        return app

    def test_brain_check_shows_report_and_is_wired_into_local_commands(self):
        app = self.app()
        health = jarvis_desktop.check_local_brain.__globals__["BrainHealth"](
            True, "qwen3.5:4b", False, (), 8.0, 3.0, None)
        with (
            patch.object(jarvis_desktop, "check_local_brain", return_value=health),
            patch.object(jarvis_desktop, "save_chat_history"),
            patch.object(jarvis_desktop, "parse_advanced_command", return_value=None),
            patch.object(jarvis_desktop.JarvisDesktop, "_try_delete_files_command", return_value=False),
        ):
            self.assertTrue(app._try_local_command("brain check karo"))
        self.assertEqual(app.shown[0], ("YOU", "brain check karo"))
        self.assertIn("ollama pull qwen3.5:4b", app.shown[1][1])
        self.assertEqual(app.history[-1]["role"], "assistant")

    def test_ordinary_prompts_are_not_intercepted(self):
        app = self.app()
        with patch.object(jarvis_desktop, "check_local_brain") as check:
            self.assertFalse(app._handle_brain_check_command("brain tumour kya hota hai"))
        check.assert_not_called()
        self.assertEqual(app.shown, [])


if __name__ == "__main__":
    unittest.main()
