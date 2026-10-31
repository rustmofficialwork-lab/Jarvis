import tempfile
import unittest
from pathlib import Path

from memory_store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_add_list_search_update_delete(self):
        item = self.store.add("Prefers Hinglish replies", "preference")
        self.assertEqual(item["category"], "preference")
        self.assertEqual(self.store.search("hinglish")[0]["id"], item["id"])
        updated = self.store.update(item["id"], "Prefers concise Hinglish replies", "style")
        self.assertEqual(updated["category"], "style")
        self.assertTrue(self.store.delete(item["id"]))
        self.assertFalse(self.store.list())

    def test_duplicate_is_updated_not_duplicated(self):
        first = self.store.add("Likes dark theme")
        second = self.store.add("Likes dark theme", "preference")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list()), 1)
        self.assertEqual(self.store.list()[0]["category"], "preference")

    def test_sensitive_secrets_are_rejected(self):
        for value in ("my password is abc", "API key: xyz", "OTP 123456"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.store.add(value)

    def test_blank_and_oversized_memories_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add("   ")
        with self.assertRaises(ValueError):
            self.store.add("x" * 501)

    def test_context_is_bounded_and_persistent(self):
        self.store.add("User prefers Hindi")
        self.store.add("User works on Windows")
        self.assertEqual(len(self.store.context()), 2)
        reopened = MemoryStore(self.store.path)
        self.assertEqual(len(reopened.list()), 2)

    def test_clear_removes_all_memories(self):
        self.store.add("One")
        self.store.add("Two")
        self.assertEqual(self.store.clear(), 2)
        self.assertEqual(self.store.list(), [])

    def test_in_memory_database_is_shared_across_store_operations(self):
        store = MemoryStore(":memory:")
        item = store.add("Temporary memory")
        self.assertEqual(store.list()[0]["id"], item["id"])
        self.assertEqual(store.search("Temporary")[0]["content"], "Temporary memory")
        self.assertTrue(store.delete(item["id"]))
        self.assertEqual(store.list(), [])


if __name__ == "__main__":
    unittest.main()
