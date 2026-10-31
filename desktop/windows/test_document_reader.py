import tempfile
import unittest
import zipfile
from pathlib import Path

from document_reader import MAX_FILE_BYTES, read_document


class DocumentReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_reads_utf8_text_and_reports_metadata(self):
        path = self.root / "notes.txt"
        path.write_text("Namaste JARVIS\nSecond line", encoding="utf-8")
        result = read_document(path)
        self.assertEqual(result["name"], "notes.txt")
        self.assertIn("Namaste JARVIS", result["text"])
        self.assertIsNone(result["pages"])

    def test_reads_markdown_and_json_as_text(self):
        path = self.root / "notes.md"
        path.write_text("# Heading\nUseful notes", encoding="utf-8")
        self.assertIn("Useful notes", read_document(path)["text"])

    def test_reads_docx_paragraphs(self):
        path = self.root / "sample.docx"
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>Hello Word</w:t></w:r></w:p>
          <w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:body>
        </w:document>"""
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", xml)
        result = read_document(path)
        self.assertIn("Hello Word", result["text"])
        self.assertIn("Second paragraph", result["text"])

    def test_rejects_unsupported_extension(self):
        path = self.root / "secret.exe"
        path.write_bytes(b"not a document")
        with self.assertRaisesRegex(ValueError, "Supported files"):
            read_document(path)

    def test_rejects_oversized_file(self):
        path = self.root / "large.txt"
        with path.open("wb") as handle:
            handle.truncate(MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "15 MB"):
            read_document(path)

    def test_rejects_empty_file(self):
        path = self.root / "empty.txt"
        path.write_text("")
        with self.assertRaisesRegex(ValueError, "empty"):
            read_document(path)

    def test_rejects_invalid_docx(self):
        path = self.root / "broken.docx"
        path.write_text("not a zip")
        with self.assertRaisesRegex(ValueError, "damaged"):
            read_document(path)

    def test_rejects_invalid_pdf(self):
        path = self.root / "broken.pdf"
        path.write_bytes(b"%PDF this is not a valid PDF")
        with self.assertRaisesRegex(ValueError, "damaged"):
            read_document(path)


if __name__ == "__main__":
    unittest.main()
