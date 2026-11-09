from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import fitz
from docx import Document


SCHEMA_VERSION = "resume-v2"

SECTION_ALIASES = {
    "summary": ("summary", "professional summary", "profile", "objective", "career objective", "about me"),
    "experience": ("experience", "work experience", "professional experience", "employment history", "employment", "internship"),
    "education": ("education", "academic background", "qualifications", "academic qualifications"),
    "skills": ("skills", "technical skills", "core competencies", "competencies", "areas of expertise"),
    "projects": ("projects", "personal projects", "academic projects", "selected projects"),
    "certifications": ("certifications", "certificates", "licenses", "licences"),
    "awards": ("awards", "honors", "honours", "achievements"),
    "languages": ("languages", "language proficiency"),
    "publications": ("publications", "research publications"),
    "volunteer": ("volunteer experience", "volunteering", "community involvement"),
}

SKILL_TERMS = (
    "python", "java", "javascript", "typescript", "c++", "c#", "react", "react native",
    "node.js", "node", "sql", "postgresql", "mysql", "mongodb", "aws", "azure", "gcp",
    "docker", "kubernetes", "spring boot", "fastapi", "django", "flask", "git", "linux",
    "html", "css", "machine learning", "deep learning", "data analysis", "pandas", "numpy",
    "tensorflow", "pytorch", "rest api", "microservices", "terraform", "redis", "kafka",
    "excel", "power bi", "tableau", " kotlin", "go", "rust", "ruby", "php", "swift",
)
SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "ml": "machine learning",
    "amazon web services": "aws",
    "restful api": "rest api",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}\b")
DATE_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|\d{1,2})[\s,./-]+(?:19|20)\d{2}\b|"
    r"\b(?:19|20)\d{2}\s*(?:-|–|to)\s*(?:(?:19|20)\d{2}|present|current)\b",
    re.I,
)
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣*-]|\d+[.)])\s+")


def _clean_line(value: str) -> str:
    value = value.replace("\x00", " ").replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", value).strip()


def _heading_type(line: str) -> Optional[str]:
    candidate = re.sub(r"[:\s]+$", "", line.lower().strip())
    candidate = re.sub(r"\s+", " ", candidate)
    for section_type, aliases in SECTION_ALIASES.items():
        if candidate in aliases:
            return section_type
    return None


def _extract_pdf(content: bytes) -> Tuple[List[Dict[str, Any]], int]:
    records = []
    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            page_count = len(pdf)
            for page_index, page in enumerate(pdf):
                # Blocks retain a useful page association and are more robust than
                # flattening the whole document into one string.
                blocks = page.get_text("blocks")
                for block in blocks:
                    if len(block) < 5 or not isinstance(block[4], str):
                        continue
                    for raw_line in block[4].splitlines():
                        line = _clean_line(raw_line)
                        if line:
                            records.append({"text": line, "page": page_index + 1, "source": "pdf"})
    except Exception as exc:
        raise ValueError("We couldn't read this PDF. Try exporting it again or upload a DOCX.") from exc
    return records, page_count


def _extract_docx(content: bytes) -> List[Dict[str, Any]]:
    records = []
    try:
        doc = Document(BytesIO(content))
        for paragraph in doc.paragraphs:
            for raw_line in paragraph.text.splitlines():
                line = _clean_line(raw_line)
                if line:
                    records.append({"text": line, "page": None, "source": "docx_paragraph"})
        for table_index, table in enumerate(doc.tables):
            for row_index, row in enumerate(table.rows):
                cells = [_clean_line(cell.text) for cell in row.cells]
                line = " | ".join(cell for cell in cells if cell)
                if line:
                    records.append({
                        "text": line,
                        "page": None,
                        "source": "docx_table",
                        "table_index": table_index,
                        "row_index": row_index,
                    })
    except Exception as exc:
        raise ValueError("We couldn't read this DOCX. Try opening and re-saving it in Word.") from exc
    return records


def _canonical_skill_matches(text: str) -> List[str]:
    normalized = text.lower()
    found = []
    for term in sorted(set(t.strip() for t in SKILL_TERMS), key=len, reverse=True):
        if not term:
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", normalized):
            found.append(term)
    for alias, canonical in SKILL_ALIASES.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", normalized):
            if canonical not in found:
                found.append(canonical)
    return sorted(set(found))


def parse_resume_v2(filename: str, content: bytes) -> Dict[str, Any]:
    """Parse PDF/DOCX into a normalized, evidence-linked resume representation.

    This stage extracts and organizes content only. It does not score resumes,
    infer qualifications, or call an LLM.
    """
    extension = Path(filename or "").suffix.lower()
    if extension not in (".pdf", ".docx"):
        raise ValueError("Unsupported file type. Please upload a PDF or DOCX resume.")

    if extension == ".pdf":
        records, page_count = _extract_pdf(content)
        file_type = "PDF"
    else:
        records = _extract_docx(content)
        page_count = None
        file_type = "DOCX"

    full_text = "\n".join(record["text"] for record in records)
    if len(full_text.strip()) < 80:
        raise ValueError(
            "Very little text was extracted. This may be a scanned/image-only PDF; "
            "upload a text-based PDF or DOCX."
        )

    evidence = []
    sections = OrderedDict()
    current_type = "other"
    current_heading = "Uncategorized"
    sections[(current_type, current_heading)] = {
        "type": current_type, "heading": current_heading, "items": [], "evidence_ids": []
    }

    for index, record in enumerate(records, start=1):
        text = record["text"]
        evidence_id = "ev-{0:04d}".format(index)
        evidence_item = {
            "id": evidence_id,
            "text": text,
            "page": record.get("page"),
            "source": record.get("source"),
        }
        for optional_key in ("table_index", "row_index"):
            if optional_key in record:
                evidence_item[optional_key] = record[optional_key]
        evidence.append(evidence_item)

        detected_type = _heading_type(text)
        if detected_type:
            current_type = detected_type
            current_heading = text.rstrip(":").strip()
            key = (current_type, current_heading)
            if key not in sections:
                sections[key] = {
                    "type": current_type, "heading": current_heading,
                    "items": [], "evidence_ids": []
                }
            continue

        key = (current_type, current_heading)
        item = {
            "kind": "bullet" if BULLET_RE.match(text) else "text",
            "text": BULLET_RE.sub("", text).strip(),
            "evidence_id": evidence_id,
            "page": record.get("page"),
        }
        sections[key]["items"].append(item)
        sections[key]["evidence_ids"].append(evidence_id)

    normalized_sections = [
        section for section in sections.values()
        if section["items"] or section["type"] != "other"
    ]

    skills = []
    for skill in _canonical_skill_matches(full_text):
        matching_evidence = []
        for item in evidence:
            if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", item["text"].lower()):
                matching_evidence.append(item["id"])
        skills.append({
            "canonical_name": skill,
            "evidence_ids": matching_evidence,
            "confidence": 1.0,
        })

    email_match = EMAIL_RE.search(full_text)
    url_match = URL_RE.search(full_text)
    phone_match = PHONE_RE.search(full_text)
    candidate = {
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
        "profile_urls": [url_match.group(0).rstrip(".,)") ] if url_match else [],
    }

    warnings = []
    if extension == ".pdf" and not full_text.strip():
        warnings.append("No selectable text was extracted; this may be a scanned document.")
    if len(records) < 5:
        warnings.append("Only a small number of text lines were extracted; review the parsed content.")

    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": candidate,
        "sections": normalized_sections,
        "skills": skills,
        "evidence": evidence,
        "document": {
            "file_type": file_type,
            "pages": page_count,
            "line_count": len(records),
            "word_count": len(full_text.split()),
        },
        "warnings": warnings,
    }
