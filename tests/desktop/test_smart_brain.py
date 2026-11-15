"""Tests for the JARVIS smart brain orchestration layer (no network, no model)."""
import unittest
from datetime import datetime, timedelta, timezone

import smart_brain as sb


class QueryUnderstandingTests(unittest.TestCase):
    def test_kinds_and_language(self):
        cases = {
            "hello": ("chat", "english"),
            "2 + 2 kitna hota hai": ("math", "hinglish"),
            "python me bubble sort ka code likho": ("code", "hinglish"),
            "what is the capital of France?": ("factual", "english"),
            "kal ka plan banao": ("planning", "hinglish"),
            "explain why the sky is blue": ("reasoning", "english"),
            "ek chhoti si kahani likho": ("creative", "hinglish"),
        }
        for prompt, (kind, language) in cases.items():
            with self.subTest(prompt=prompt):
                profile = sb.classify_query(prompt)
                self.assertEqual((profile.kind, profile.language), (kind, language))

    def test_step_by_step_is_reasoning_not_planning_and_triggers_deep_think(self):
        profile = sb.classify_query("explain why the sky is blue step by step")
        self.assertEqual(profile.kind, "reasoning")
        self.assertTrue(profile.deliberate)

    def test_dates_are_not_treated_as_arithmetic(self):
        self.assertNotEqual(sb.classify_query("12-05-2026 kab hai").kind, "math")
        self.assertEqual(sb.gather_grounding("12-05-2026 ko kya tha"), [])

    def test_trivial_chat_never_deliberates_and_complexity_is_bounded(self):
        profile = sb.classify_query("hi")
        self.assertFalse(profile.deliberate)
        self.assertEqual(profile.complexity, 0)
        long_prompt = "explain how " + "the system works and " * 30
        self.assertLessEqual(sb.classify_query(long_prompt).complexity, 3)

    def test_live_data_flag(self):
        self.assertTrue(sb.classify_query("latest news about AI").wants_live_data)
        self.assertFalse(sb.classify_query("what is a pointer in C").wants_live_data)

    def test_generation_options_are_bounded_and_kind_specific(self):
        code = sb.generation_options(sb.classify_query("write python code for a stack"))
        chat = sb.generation_options(sb.classify_query("hello"))
        math = sb.generation_options(sb.classify_query("5 * 5"))
        self.assertGreater(code["num_ctx"], chat["num_ctx"])
        self.assertLess(math["temperature"], chat["temperature"])
        for options in (code, chat, math):
            self.assertLessEqual(options["num_ctx"], sb.MAX_NUM_CTX)
            self.assertLessEqual(options["num_predict"], sb.MAX_NUM_PREDICT)
            self.assertGreaterEqual(options["num_ctx"], 2048)


class MemoryRankingTests(unittest.TestCase):
    MEMORIES = [
        "User is studying RGPV diploma 3rd semester computer programming in C",
        "User likes cricket and watches IPL",
        "User wants to build an Android APK of the Jarvis app",
        "Favourite food is paneer butter masala",
    ]

    def test_ranks_relevant_memory_first(self):
        result = sb.rank_memories("mera C programming ka exam kab hai", self.MEMORIES, limit=2)
        self.assertTrue(result and "programming" in result[0])

    def test_unrelated_prompt_gets_no_memories(self):
        self.assertEqual(sb.rank_memories("what is the speed of light", self.MEMORIES), [])

    def test_accepts_dicts_and_prefers_recent_on_ties(self):
        now = datetime(2026, 11, 15, tzinfo=timezone.utc)
        items = [
            {"content": "likes tea in the morning", "updated_at": (now - timedelta(days=400)).isoformat()},
            {"content": "likes tea in the evening", "updated_at": (now - timedelta(days=1)).isoformat()},
        ]
        result = sb.rank_memories("tea", items, limit=2, now=now)
        self.assertEqual(result[0], "likes tea in the evening")

    def test_limits_and_garbage_input(self):
        many = [f"project alpha note {i}" for i in range(30)]
        self.assertLessEqual(len(sb.rank_memories("alpha project", many, limit=3)), 3)
        self.assertEqual(sb.rank_memories("alpha", [None, 5, "", {"content": 3}]), [])
        self.assertEqual(sb.rank_memories("", self.MEMORIES), [])

    def test_bm25_zero_when_no_overlap(self):
        self.assertEqual(sb.bm25_scores("zebra", ["apple banana"]), [0.0])


class HistoryCompactionTests(unittest.TestCase):
    @staticmethod
    def turns(count, size=400):
        out = []
        for i in range(count):
            out.append({"role": "user", "content": f"Question number {i}. " + "x" * size})
            out.append({"role": "assistant", "content": f"Answer number {i}. " + "y" * size})
        return out

    def test_short_history_is_untouched(self):
        history = self.turns(2, size=20)
        result = sb.compact_history(history, max_chars=5000)
        self.assertEqual(result.messages, history)
        self.assertIsNone(result.summary)
        self.assertEqual(result.dropped, 0)

    def test_long_history_fits_budget_and_keeps_latest_turns(self):
        history = self.turns(20)
        result = sb.compact_history(history, max_chars=3000)
        total = sum(len(m["content"]) for m in result.messages)
        self.assertLessEqual(total + len(result.summary or ""), 3000 + 100)
        self.assertEqual(result.messages[-1], history[-1])
        self.assertGreater(result.dropped, 0)
        self.assertIn("Earlier in this conversation", result.summary)
        self.assertIn("Question number", result.summary)

    def test_oversized_last_turns_are_capped_not_overflowing(self):
        history = [{"role": "user", "content": "a" * 1500}, {"role": "assistant", "content": "b" * 1500}]
        result = sb.compact_history(history, max_chars=600)
        self.assertLessEqual(sum(len(m["content"]) for m in result.messages), 600)
        self.assertEqual(len(result.messages), 2)

    def test_ignores_malformed_entries(self):
        history = [None, {"role": "system", "content": "x"}, {"role": "user"}, {"role": "user", "content": "ok"}]
        self.assertEqual(sb.compact_history(history, max_chars=1000).messages,
                         [{"role": "user", "content": "ok"}])


class GroundingTests(unittest.TestCase):
    def test_math_is_computed_by_the_real_calculator(self):
        notes = sb.gather_grounding("2 x 3 + 4 kitna hota hai")
        self.assertEqual(len(notes), 1)
        self.assertIn("2 * 3 + 4 = 10", notes[0])

    def test_time_and_system_use_authorized_read_only_tools(self):
        calls = []

        def execute(tool, arguments):
            calls.append(tool)
            return "FAKE " + tool

        notes = sb.gather_grounding("abhi kitne baje hain aur cpu usage kya hai", execute=execute)
        self.assertEqual(calls, ["get_local_time", "get_system_status"])
        self.assertEqual(len(notes), 2)

    def test_unauthorized_or_failing_tools_are_skipped_silently(self):
        deny = lambda name, args, prompt: type("D", (), {"allowed": False})()
        self.assertEqual(sb.gather_grounding("2 + 2", authorize=deny, execute=lambda *a: "4"), [])

        def boom(tool, arguments):
            raise ValueError("nope")
        self.assertEqual(sb.gather_grounding("9 / 0", execute=boom), [])

    def test_plain_chat_triggers_no_tools(self):
        def execute(tool, arguments):
            raise AssertionError("no tool should run")
        self.assertEqual(sb.gather_grounding("tell me a fun fact", execute=execute), [])

    def test_division_by_zero_does_not_break_the_reply(self):
        self.assertEqual(sb.gather_grounding("5 / 0 kya hota hai"), [])


class DeliberationTests(unittest.TestCase):
    @staticmethod
    def scripted(replies):
        calls = []

        def generate(messages, options):
            calls.append((list(messages), dict(options)))
            reply = replies[len(calls) - 1]
            if isinstance(reply, Exception):
                raise reply
            return reply
        return generate, calls

    def test_ok_critique_returns_draft_after_two_calls(self):
        generate, calls = self.scripted(["Good answer", "OK"])
        result = sb.deliberate(generate, [{"role": "user", "content": "q"}], {"num_predict": 500})
        self.assertEqual((result.text, result.improved, len(calls)), ("Good answer", False, 2))
        self.assertLessEqual(calls[1][1]["num_predict"], 256)

    def test_ok_prefix_with_real_issues_is_not_treated_as_ok(self):
        generate, calls = self.scripted(["Draft", "Okay, but step 3 is wrong", "Fixed answer"])
        result = sb.deliberate(generate, [{"role": "user", "content": "q"}], {})
        self.assertTrue(result.improved)
        self.assertEqual(result.text, "Fixed answer")
        self.assertEqual(result.steps, ("draft", "critique", "revise"))

    def test_failures_after_draft_keep_the_draft(self):
        generate, _ = self.scripted(["Draft", RuntimeError("down")])
        self.assertEqual(sb.deliberate(generate, [], {}).text, "Draft")
        generate, _ = self.scripted(["Draft", "problems", RuntimeError("down")])
        self.assertEqual(sb.deliberate(generate, [], {}).text, "Draft")

    def test_empty_or_truncated_revision_is_rejected(self):
        draft = "d" * 400
        generate, _ = self.scripted([draft, "bad", "tiny"])
        self.assertEqual(sb.deliberate(generate, [], {}).text, draft)

    def test_empty_draft_raises_so_caller_can_fall_back(self):
        generate, _ = self.scripted([""])
        with self.assertRaises(RuntimeError):
            sb.deliberate(generate, [], {})

    def test_deadline_stops_extra_calls(self):
        ticks = iter([0.0, 100.0, 200.0, 300.0])
        generate, calls = self.scripted(["Draft", "problems", "revised"])
        result = sb.deliberate(generate, [], {}, deadline_seconds=60, clock=lambda: next(ticks))
        self.assertEqual((result.text, len(calls)), ("Draft", 1))


class PrepareTests(unittest.TestCase):
    def test_prepare_bundles_everything_without_network(self):
        history = [{"role": "user", "content": "x" * 1400}, {"role": "assistant", "content": "y" * 1400}] * 10
        plan = sb.prepare("2 + 2 kitna hota hai", history, ["User studies C programming"])
        self.assertEqual(plan.profile.kind, "math")
        self.assertTrue(plan.grounding and "= 4" in plan.grounding[0])
        self.assertEqual(plan.memories, [])  # unrelated memory is not injected
        total = sum(len(m["content"]) for m in plan.history.messages)
        self.assertLess(total, plan.options["num_ctx"] * 3)

    def test_prepare_handles_missing_memories_and_history(self):
        plan = sb.prepare("hello", [], None)
        self.assertEqual((plan.memories, plan.grounding, plan.history.messages), ([], [], []))



class ImprovementRegressionTests(unittest.TestCase):
    """Bugs found in review: each of these used to misbehave."""

    def test_stemmer_matches_word_forms(self):
        for group in (("file", "files"), ("use", "used", "using", "uses"), ("make", "making"),
                      ("run", "running"), ("study", "studies")):
            with self.subTest(group=group):
                self.assertEqual(len({sb._stem(w) for w in group}), 1)
        self.assertEqual(sb._stem("2024"), "2024")

    def test_memory_ranking_finds_word_forms(self):
        found = sb.rank_memories("which files are saved", ["User saves the file on desktop", "User likes tea"])
        self.assertEqual(found, ["User saves the file on desktop"])

    def test_person_named_ram_does_not_trigger_pc_status(self):
        seen = []
        allow = lambda tool, args, prompt: type("D", (), {"allowed": True})()
        run = lambda tool, args: seen.append(tool) or "ok"
        sb.gather_grounding("Ram ka birthday kab hai", execute=run, authorize=allow)
        self.assertEqual(seen, [])
        sb.gather_grounding("meri ram kitni free hai", execute=run, authorize=allow)
        self.assertEqual(seen, ["get_system_status"])

    def test_more_ways_to_ask_the_time_are_grounded(self):
        allow = lambda tool, args, prompt: type("D", (), {"allowed": True})()
        for prompt in ("what is the time", "time batao", "aaj ki tarikh kya hai", "what is the date today"):
            with self.subTest(prompt=prompt):
                notes = sb.gather_grounding(prompt, execute=lambda t, a: "2026-11-15T10:00:00", authorize=allow)
                self.assertEqual(len(notes), 1)

    def test_percent_of_is_computed_by_the_calculator(self):
        calls = []
        allow = lambda tool, args, prompt: type("D", (), {"allowed": True})()

        def run(tool, args):
            calls.append((tool, args))
            return "100"
        notes = sb.gather_grounding("20% of 500 kitna hota hai", execute=run, authorize=allow)
        self.assertEqual(calls, [("calculator", {"expression": "(20 / 100) * 500"})])
        self.assertIn("20% of 500 = 100", notes[0])
        self.assertEqual(sb.classify_query("20% of 500 kitna hota hai").kind, "math")

    def test_ranges_and_dates_are_not_arithmetic(self):
        self.assertIsNone(sb._find_arithmetic("9-5 job hai"))
        self.assertIsNone(sb._find_arithmetic("pages 10-12 padho"))
        self.assertIsNone(sb._find_arithmetic("12-05-2026 ko kya tha"))
        self.assertEqual(sb._find_arithmetic("9-5 job hai aur 2+2 kitna hota hai").group(0), "2+2")

    def test_hindi_medium_class_is_not_code_but_cpp_is(self):
        self.assertNotEqual(sb.classify_query("class 10 ke maths ka syllabus batao please").kind, "code")
        self.assertEqual(sb.classify_query("write a c++ program").kind, "code")
        self.assertEqual(sb.classify_query("python class kaise banate hain").kind, "code")

    def test_greeting_prefix_does_not_hide_a_real_question(self):
        self.assertEqual(sb.classify_query("ok what is the capital of France?").kind, "factual")
        self.assertEqual(sb.classify_query("how are you?").kind, "chat")

    def test_critique_approval_variants(self):
        for text in ("OK", "OK. The answer is correct and complete.", "No mistakes found.", "sab theek hai"):
            self.assertTrue(sb._critique_approves(text), text)
        for text in ("Okay, but step 3 is wrong", "1. step 2 is missing\n2. unit is wrong"):
            self.assertFalse(sb._critique_approves(text), text)

    def test_verbose_approval_skips_the_revise_call(self):
        replies = ["Draft", "OK. The answer is correct and complete."]
        calls = []

        def generate(messages, options):
            calls.append(1)
            return replies[len(calls) - 1]
        result = sb.deliberate(generate, [{"role": "user", "content": "q"}], {})
        self.assertEqual((result.text, result.improved, len(calls)), ("Draft", False, 2))

    def test_revision_preamble_is_removed(self):
        replies = ["Draft", "- step 2 is wrong", "Here is the corrected final answer:\nFinal text"]
        calls = []

        def generate(messages, options):
            calls.append(1)
            return replies[len(calls) - 1]
        result = sb.deliberate(generate, [{"role": "user", "content": "q"}], {})
        self.assertEqual(result.text, "Final text")


class DevanagariTests(unittest.TestCase):
    def test_devanagari_words_stay_whole(self):
        self.assertEqual(sb.tokenize("मेरा प्रोजेक्ट विंडोज़ फ़ाइल"), ["प्रोजेक्ट", "विंडोज़", "फ़ाइल"])

    def test_hindi_memories_are_retrieved(self):
        memories = ["User ka प्रोजेक्ट Jarvis hai", "User likes tea"]
        self.assertEqual(sb.rank_memories("मेरा प्रोजेक्ट क्या है", memories), [memories[0]])

    def test_devanagari_query_is_hinglish(self):
        self.assertEqual(sb.classify_query("मौसम कैसा है").language, "hinglish")


if __name__ == "__main__":
    unittest.main()
