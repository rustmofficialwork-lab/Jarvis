import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from recoverable_file_actions import move_files_to_trash, validate_selected_files


class RecoverableFileActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.root = self.home / "Documents"
        self.root.mkdir()
        self.file = self.root / "notes.txt"
        self.file.write_text("test", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_validates_only_exact_regular_files_in_allowed_roots(self):
        self.assertEqual(validate_selected_files([str(self.file)], home=self.home), (self.file,))
        with self.assertRaises(ValueError):
            validate_selected_files([str(self.root)], home=self.home)
        outside = self.home / "outside.txt"
        outside.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_selected_files([str(outside)], home=self.home)

    def test_rejects_missing_duplicate_and_too_many_paths(self):
        with self.assertRaises(ValueError):
            validate_selected_files([str(self.file), str(self.file)], home=self.home)
        with self.assertRaises(ValueError):
            validate_selected_files([str(self.root / "missing.txt")], home=self.home)
        with self.assertRaises(ValueError):
            validate_selected_files([str(self.file)] * 21, home=self.home)

    def test_requires_exact_approval_before_trash_operation(self):
        trashed = []
        with self.assertRaises(PermissionError):
            move_files_to_trash(
                [str(self.file)], home=self.home,
                consume_approval=lambda details: SimpleNamespace(approved=False),
                trash=trashed.append,
            )
        self.assertEqual(trashed, [])
        self.assertTrue(self.file.exists())

    def test_moves_only_after_matching_approval_and_never_unlinks(self):
        trashed = []
        seen = {}
        def consume(details):
            seen.update(details)
            return SimpleNamespace(approved=True)
        moved = move_files_to_trash(
            [str(self.file)], home=self.home, consume_approval=consume, trash=trashed.append,
        )
        self.assertEqual(moved, (str(self.file.resolve()),))
        self.assertEqual(trashed, [str(self.file.resolve())])
        self.assertEqual(seen, {"paths": [str(self.file.resolve())], "recovery": True})
        # The injected trash adapter owns the move; this function never unlinks.
        self.assertTrue(self.file.exists())


if __name__ == "__main__":
    unittest.main()
