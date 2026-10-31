"""Safe, offline extraction of common local documents for the JARVIS desktop app."""
from __future__ import annotations

from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_TEXT_CHARS = 40_000
MAX_PDF_PAGES = 100
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".log", ".json", ".py", ".ini",
    ".yaml", ".yml", ".xml", ".html", ".htm", ".rst",
}


def _limit_text(text: str) -> str:
    cleaned = text.replace("\x00", "").strip()
    if len(cleaned) > MAX_TEXT_CHARS:
        return cleaned[:MAX_TEXT_CHARS].rstrip() + "\n\n[Document text truncated at 40,000 characters.]"
    return cleaned


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _read_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            total_uncompressed = sum(item.file_size for item in infos)
            if total_uncompressed > 30 * 1024 * 1024:
                raise ValueError("This Word document expands to an unsafe size.")
            try:
                xml = archive.read("word/document.xml")
            except KeyError as exc:
                raise ValueError("This DOCX file does not contain a readable document body.") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError("This Word document is damaged or is not a valid DOCX file.") from exc

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError("The Word document contains invalid XML.") from exc

    paragraphs = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        parts = [
            node.text or ""
            for node in paragraph.iter()
            if node.tag.endswith("}t")
        ]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _read_pdf(path: Path) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support is not installed. Update JARVIS or install pypdf.") from exc

    try:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception:
                unlocked = 0
            if not unlocked:
                raise ValueError("This PDF is password-protected and cannot be read.")
        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            raise ValueError(f"This PDF has {page_count} pages; the limit is {MAX_PDF_PAGES} pages per read.")
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                raise ValueError(f"Could not extract text from PDF page {number}.") from exc
            if page_text.strip():
                pages.append(f"[Page {number}]\n{page_text.strip()}")
        return "\n\n".join(pages), page_count
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("This PDF is damaged or could not be opened.") from exc


def read_document(file_path: str | Path) -> dict:
    """Extract text from a user-selected local document without uploading it."""
    path = Path(file_path).expanduser()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("The selected file could not be found.")
    suffix = path.suffix.casefold()
    if suffix not in TEXT_EXTENSIONS | {".pdf", ".docx"}:
        raise ValueError("Supported files: PDF, DOCX, TXT, MD, CSV, JSON, code and common text files.")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError("The selected file is larger than the 15 MB safety limit.")
    if size == 0:
        raise ValueError("The selected file is empty.")

    page_count = None
    if suffix == ".pdf":
        text, page_count = _read_pdf(path)
    elif suffix == ".docx":
        text = _read_docx(path)
    else:
        text = _read_text(path)

    text = _limit_text(text)
    if not text:
        if suffix == ".pdf":
            raise ValueError("No selectable text was found. This may be a scanned PDF; OCR is not available yet.")
        raise ValueError("No readable text was found in this file.")
    return {
        "name": path.name,
        "path": str(path),
        "text": text,
        "characters": len(text),
        "pages": page_count,
    }
