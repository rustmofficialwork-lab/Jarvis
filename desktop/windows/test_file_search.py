"""Unit tests for bounded filename-only search."""
import os
import tempfile
import unittest
from pathlib import Path

from file_search import (parse_file_search_query, parse_open_result_index, search_files,
                         validate_search_result_for_open)


class FileSearchTests(unittest.TestCase):
    def test_parse_supported_commands(self):
        self.assertEqual(parse_file_search_query("Find file budget.xlsx"), "budget.xlsx")
        self.assertEqual(parse_file_search_query("file dhundo notes"), "notes")
        self.assertEqual(parse_file_search_query("फाइल खोजो report"), "report")
        self.assertIsNone(parse_file_search_query("find file"))
        self.assertIsNone(parse_file_search_query("find file C:\\secret"))

    def test_parse_numbered_open_commands(self):
        self.assertEqual(parse_open_result_index("open file 2"), 2)
        self.assertEqual(parse_open_result_index("result kholo 10"), 10)
        self.assertEqual(parse_open_result_index("फाइल खोलो 3"), 3)
        self.assertIsNone(parse_open_result_index("open file 0"))
        self.assertIsNone(parse_open_result_index("open file 51"))
        self.assertIsNone(parse_open_result_index("open file C:\\\\secret"))

    def test_open_validation_allows_safe_files_and_rejects_executables(self):
        with tempfile.TemporaryDirectory() as temp:
            safe = Path(temp) / "notes.txt"
            safe.touch()
            self.assertEqual(validate_search_result_for_open(safe), safe.resolve())
            executable = Path(temp) / "run.exe"
            executable.touch()
            with self.assertRaises(ValueError):
                validate_search_result_for_open(executable)

    def test_searches_names_recursively_without_reading_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "nested").mkdir()
            (root / "budget.xlsx").write_text("not read", encoding="utf-8")
            (root / "nested" / "old-budget.csv").write_text("not read", encoding="utf-8")
            (root / "nested" / "other.txt").write_text("budget inside contents", encoding="utf-8")
            found = search_files(root, "budget")
            self.assertEqual({Path(item).name for item in found}, {"budget.xlsx", "old-budget.csv"})

    def test_skips_hidden_files_and_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            hidden = root / ".private"
            hidden.mkdir()
            (hidden / "report.txt").touch()
            (root / ".report.txt").touch()
            (root / "public-report.txt").touch()
            self.assertEqual([Path(p).name for p in search_files(root, "report")], ["public-report.txt"])

    def test_rejects_invalid_root_and_query(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                search_files(temp, "../secret")
            with self.assertRaises(NotADirectoryError):
                search_files(Path(temp) / "missing", "report")

    def test_result_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(5):
                (root / f"report-{index}.txt").touch()
            self.assertEqual(len(search_files(root, "report", max_results=2)), 2)

    def test_directory_limit_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "b" / "report.txt").touch()
            self.assertEqual(search_files(root, "report", max_directories=1), [])


if __name__ == "__main__":
    unittest.main()
