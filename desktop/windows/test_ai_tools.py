"""Tests for JARVIS's bounded, read-only AI tools."""
import unittest

from ai_tools import calculate, execute_tool


class SafeToolTests(unittest.TestCase):
    def test_calculator_handles_basic_arithmetic(self):
        self.assertEqual(calculate("(12 + 8) * 3"), "60")
        self.assertEqual(calculate("7 / 2"), "3.5")
        self.assertEqual(calculate("2 ** 3"), "8")

    def test_calculator_rejects_code_and_names(self):
        for expression in ("__import__('os').system('whoami')", "open('x')", "x + 1"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    calculate(expression)

    def test_calculator_rejects_oversized_or_dangerous_math(self):
        for expression in ("9 ** 9", "1 / 0", "1e999 - 1e999", "9" * 121):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    calculate(expression)

    def test_tool_arguments_are_exact(self):
        self.assertEqual(execute_tool("calculator", {"expression": "6 * 7"}), "42")
        with self.assertRaises(ValueError):
            execute_tool("calculator", {"expression": "1+1", "extra": "ignored"})
        with self.assertRaises(ValueError):
            execute_tool("get_local_time", {"anything": True})

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            execute_tool("run_shell", {})

    def test_local_time_is_timezone_aware(self):
        value = execute_tool("get_local_time", {})
        self.assertRegex(value, r".+[+-]\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
