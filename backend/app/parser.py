from __future__ import annotations
from pathlib import Path
from io import BytesIO
import re
import fitz
from docx import Document

SUPPORTED = {".pdf", ".docx"}

def clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()

def parse_resume(filename: str, content: bytes) -> tuple[str, dict]:
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError("Unsupported file type. Please upload a PDF or DOCX resume.")
    if ext == ".pdf":
        try:
            with fitz.open(stream=content, filetype="pdf") as doc:
                text = "\n".join(page.get_text("text") for page in doc)
                pages = len(doc)
        except Exception as exc:
            raise ValueError("We couldn't read this PDF. Try exporting it again or upload a DOCX.") from exc
        meta = {"pages": pages, "file_type": "PDF"}
    else:
        try:
            doc = Document(BytesIO(content))
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(parts)
            meta = {"pages": None, "file_type": "DOCX"}
        except Exception as exc:
            raise ValueError("We couldn't read this DOCX. Try opening and re-saving it in Word.") from exc
    text = clean_text(text)
    if len(text) < 80:
        raise ValueError("Very little text was extracted. This may be a scanned/image-only PDF; upload a text-based PDF or DOCX.")
    return text, meta
