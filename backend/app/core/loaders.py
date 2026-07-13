import csv
import hashlib
import io
import json

from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from pypdf import PdfReader


class LoadedDocument:
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata


def checksum(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_pdf(raw: bytes, filename: str) -> LoadedDocument:
    reader = PdfReader(io.BytesIO(raw))
    pages = []
    for i, page in enumerate(reader.pages):
        content = page.extract_text() or ""
        pages.append(f"\n\n[page {i + 1}]\n{content}")
    text = "".join(pages)
    return LoadedDocument(text=text, metadata={"filename": filename, "num_pages": len(reader.pages)})


def load_docx(raw: bytes, filename: str) -> LoadedDocument:
    doc = DocxDocument(io.BytesIO(raw))
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            style = para.style.name if para.style else "Normal"
            prefix = "# " if style.startswith("Heading 1") else "## " if style.startswith("Heading") else ""
            parts.append(f"{prefix}{para.text}")
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return LoadedDocument(text="\n".join(parts), metadata={"filename": filename})


def load_markdown(raw: bytes, filename: str) -> LoadedDocument:
    text = raw.decode("utf-8", errors="ignore")
    return LoadedDocument(text=text, metadata={"filename": filename})


def load_txt(raw: bytes, filename: str) -> LoadedDocument:
    text = raw.decode("utf-8", errors="ignore")
    return LoadedDocument(text=text, metadata={"filename": filename})


def load_html(raw: bytes, filename: str, source_url: str = "") -> LoadedDocument:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    title = soup.title.string if soup.title else filename
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return LoadedDocument(text="\n".join(lines), metadata={"filename": filename, "title": title, "url": source_url})


def load_csv(raw: bytes, filename: str) -> LoadedDocument:
    text_io = io.StringIO(raw.decode("utf-8", errors="ignore"))
    reader = csv.DictReader(text_io)
    rows = []
    for row in reader:
        rows.append(", ".join(f"{k}: {v}" for k, v in row.items()))
    return LoadedDocument(text="\n".join(rows), metadata={"filename": filename, "num_rows": len(rows)})


def load_json(raw: bytes, filename: str) -> LoadedDocument:
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    text = json.dumps(data, indent=2, ensure_ascii=False)
    return LoadedDocument(text=text, metadata={"filename": filename})


LOADERS = {
    "pdf": load_pdf,
    "docx": load_docx,
    "md": load_markdown,
    "markdown": load_markdown,
    "txt": load_txt,
    "html": load_html,
    "csv": load_csv,
    "json": load_json,
}


def load_document(raw: bytes, filename: str, source_type: str, source_url: str = "") -> LoadedDocument:
    loader = LOADERS.get(source_type)
    if not loader:
        raise ValueError(f"Unsupported source type: {source_type}")
    if source_type == "html":
        return loader(raw, filename, source_url)
    return loader(raw, filename)


def infer_source_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    if ext not in LOADERS:
        raise ValueError(f"Unsupported file extension: .{ext}")
    return ext
