from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from pathlib import Path
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import fitz
from docx import Document


SCHEMA_VERSION = "resume-v2"

# Keep these aliases conservative: a heading must match as a complete line.
SECTION_ALIASES = {
    "summary": ("summary", "professional summary", "profile", "professional profile", "career profile", "objective", "career objective", "about me"),
    "experience": ("experience", "work experience", "professional experience", "employment history", "employment", "internship"),
    "education": ("education", "academic background", "qualifications", "academic qualifications"),
    "skills": ("skills", "my skills", "technical skills", "key skills", "skill set", "technical highlights", "core competencies", "competencies", "areas of expertise"),
    "projects": ("projects", "personal projects", "academic projects", "selected projects"),
    "certifications": ("certifications", "certificates", "licenses", "licences"),
    "awards": ("awards", "honors", "honours", "achievements"),
    "leadership": ("positions of responsibility", "leadership", "leadership experience", "extracurricular activities", "student activities"),
    "languages": ("languages", "language proficiency"),
    "publications": ("publications", "research publications"),
    "volunteer": ("volunteer experience", "volunteering", "community involvement"),
    "coding_platforms": ("coding platforms", "competitive programming", "problem solving profiles"),
}

# Canonical skill names are emitted once; aliases never create duplicate skills.
SKILL_GROUPS = {
    "javascript": ("javascript", "js"),
    "typescript": ("typescript", "ts"),
    "node.js": ("node.js", "node js", "node"),
    "react": ("react", "react.js", "reactjs"),
    "express.js": ("express.js", "express js", "express"),
    "postgresql": ("postgresql", "postgres"),
    "mongodb": ("mongodb", "mongo db"),
    "aws": ("aws", "amazon web services"),
    "gcp": ("gcp", "google cloud platform"),
    "kubernetes": ("kubernetes", "k8s"),
    "machine learning": ("machine learning", "ml"),
    "deep learning": ("deep learning",),
    "rest api": ("rest api", "restful api", "rest apis"),
    "spring boot": ("spring boot",),
    "power bi": ("power bi",),
    "tensorflow": ("tensorflow",),
    "pytorch": ("pytorch",),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "c++": ("c++",),
    "c#": ("c#",),
    "html": ("html",),
    "css": ("css",),
    "python": ("python",),
    "java": ("java",),
    "sql": ("sql",),
    "mysql": ("mysql",),
    "react native": ("react native",),
    "docker": ("docker",),
    "azure": ("azure",),
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "git": ("git",),
    "linux": ("linux",),
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "terraform": ("terraform",),
    "redis": ("redis",),
    "kafka": ("kafka",),
    "excel": ("excel",),
    "tableau": ("tableau",),
    "kotlin": ("kotlin",),
    "go": ("golang",),
    "rust": ("rust",),
    "ruby": ("ruby",),
    "php": ("php",),
    "swift": ("swift",),
    "selenium": ("selenium",),
    "playwright": ("playwright",),
    "cypress": ("cypress",),
    "pytest": ("pytest",),
    "junit": ("junit",),
    "jest": ("jest",),
    "jenkins": ("jenkins",),
    "github actions": ("github actions",),
    "prometheus": ("prometheus",),
    "grafana": ("grafana",),
    "datadog": ("datadog",),
    "websockets": ("websocket", "websockets"),
    "webrtc": ("webrtc",),
    "socket.io": ("socket.io", "socket io"),
    "jwt": ("jwt", "json web token"),
    "oauth": ("oauth", "oauth 2.0"),
    "bash": ("bash",),
    "statistics": ("statistics",),
    "ci/cd": ("ci/cd", "continuous integration", "continuous delivery", "continuous deployment"),
    "athena": ("athena",),
    "iam": ("iam",),
    "s3": ("s3",),
    "yolo": ("yolo",),
    "wandb": ("wandb", "weights & biases", "weights and biases"),
    "quill": ("quill",),
    "razorpay": ("razorpay",),
    "leaflet.js": ("leaflet.js", "leaflet js"),
    "rasa": ("rasa",),
    "framer motion": ("framer motion", "framer-motion"),
    "calendarjs": ("calendarjs",),
    "data structures and algorithms": ("data structures and algorithms", "data structures & algorithms", "dsa"),
    "object-oriented programming": ("object-oriented programming", "object oriented programming", "object-oriented design", "object oriented design", "oop", "ood"),
    "distributed systems": ("distributed systems", "distributed system"),
    "api development": ("api development", "api design", "api implementation"),
    "gradle": ("gradle",),
    "maven": ("maven",),
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
URL_RE = re.compile(
    r"(?:(?:https?://|www\.)[^\s|<>]+|(?:github\.com|linkedin\.com|gitlab\.com|leetcode\.com)/[^\s|<>]+)",
    re.I,
)
PHONE_RE = re.compile(r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}(?!\w)")
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣∙·*-]|\d+[.)])\s+")
DATE_LINE_RE = re.compile(
    r"^\s*(?:(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
    r"sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)[a-z]*\.?\s+\d{4}|"
    r"\d{1,2}[/-]\d{4}|\d{4})\s*(?:-|–|—|to)\s*(?:present|current|\d{4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})\s*$",
    re.I,
)


def _clean_line(value: str) -> str:
    value = value.replace("\x00", " ").replace("\u00a0", " ")
    # PDF icon fonts sometimes map decorative icons to control/private-use chars.
    value = "".join(
        " " if unicodedata.category(char) in ("Cc", "Cf", "Co") else char
        for char in value
    )
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s*\|\s*", " | ", value)
    return value.strip(" \t|")


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
                for block in page.get_text("blocks"):
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
        table_index = 0
        # Preserve document order for paragraphs and tables instead of appending
        # every table after all paragraphs.
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        for child in doc.element.body.iterchildren():
            if child.tag.endswith("}p"):
                paragraph = Paragraph(child, doc)
                for raw_line in paragraph.text.splitlines():
                    line = _clean_line(raw_line)
                    if line:
                        records.append({"text": line, "page": None, "source": "docx_paragraph"})
            elif child.tag.endswith("}tbl"):
                table = Table(child, doc)
                for row_index, row in enumerate(table.rows):
                    cells = [_clean_line(cell.text) for cell in row.cells]
                    line = " | ".join(cell for cell in cells if cell)
                    if line:
                        records.append({
                            "text": line, "page": None, "source": "docx_table",
                            "table_index": table_index, "row_index": row_index,
                        })
                table_index += 1
    except Exception as exc:
        raise ValueError("We couldn't read this DOCX. Try opening and re-saving it in Word.") from exc
    return records


def _alias_pattern(alias: str) -> re.Pattern:
    escaped = re.escape(alias).replace(r"\ ", r"\s+")
    return re.compile(r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])", re.I)


def _detect_skills(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # A canonical skill is emitted once with all evidence lines that contain one
    # of its explicit aliases. Related concepts are not treated as synonyms.
    results = []
    for canonical, aliases in SKILL_GROUPS.items():
        matching_ids = []
        for record in records:
            text = record["text"]
            if any(_alias_pattern(alias).search(text) for alias in aliases):
                matching_ids.append(record["evidence_id"])
        if matching_ids:
            results.append({
                "canonical_name": canonical,
                "evidence_ids": matching_ids,
                "confidence": 1.0,
            })
    return sorted(results, key=lambda item: item["canonical_name"])


def _should_join(previous: Dict[str, Any], current_text: str) -> bool:
    if previous["kind"] != "bullet":
        return False
    if BULLET_RE.match(current_text) or _heading_type(current_text):
        return False
    if DATE_LINE_RE.match(current_text):
        return False
    previous_text = previous["text"]
    # A line-ending hyphen is a strong PDF wrap signal (e.g. Mon- / goDB).
    if previous_text.endswith("-"):
        return True
    # Lowercase continuation lines commonly result from PDF line wrapping.
    if current_text[:1].islower():
        return True
    # If the preceding line has no sentence-ending punctuation, it may continue.
    return not re.search(r"[.!?;:]$", previous_text)


def _append_item(section: Dict[str, Any], record: Dict[str, Any]) -> None:
    raw_text = record["text"]
    is_bullet = bool(BULLET_RE.match(raw_text))
    text = BULLET_RE.sub("", raw_text).strip()
    item = {
        "kind": "bullet" if is_bullet else "text",
        "text": text,
        "evidence_id": record["evidence_id"],
        "evidence_ids": [record["evidence_id"]],
        "page": record.get("page"),
    }
    if section["items"] and _should_join(section["items"][-1], text):
        previous = section["items"][-1]
        if previous["text"].endswith("-"):
            previous["text"] = previous["text"][:-1] + text
        else:
            previous["text"] = previous["text"].rstrip() + " " + text
        previous["evidence_ids"].append(record["evidence_id"])
        return
    section["items"].append(item)
    section["evidence_ids"].append(record["evidence_id"])


def _extract_profile_urls(text: str) -> List[str]:
    urls = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:)")
        if url.lower().startswith("www."):
            url = "https://" + url
        elif not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        if url not in urls:
            urls.append(url)
    return urls


def _candidate_name(records: List[Dict[str, Any]]) -> Optional[str]:
    # Candidate name is usually one of the first few header lines. Avoid treating
    # contact details, URLs, headings, or a role title as a person's name.
    for record in records[:6]:
        line = record["text"].strip()
        if (
            len(line) < 3 or len(line) > 70 or EMAIL_RE.search(line)
            or URL_RE.search(line) or PHONE_RE.search(line)
            or _heading_type(line) or " | " in line
            or re.search(r"\d", line)
        ):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.match(r"^[A-Z][A-Za-z'’-]+$", word) for word in words):
            return line
    return None


def parse_resume_v2(filename: str, content: bytes) -> Dict[str, Any]:
    """Parse PDF/DOCX into a normalized, evidence-linked resume representation.

    Extraction is heuristic. It does not score resumes, infer qualifications,
    perform OCR, or call an LLM.
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
    current_type, current_heading = "other", "Uncategorized"
    sections[(current_type, current_heading)] = {
        "type": current_type, "heading": current_heading, "items": [], "evidence_ids": []
    }

    for index, record in enumerate(records, start=1):
        record["evidence_id"] = "ev-{0:04d}".format(index)
        evidence_item = {
            "id": record["evidence_id"],
            "text": record["text"],
            "page": record.get("page"),
            "source": record.get("source"),
        }
        for optional_key in ("table_index", "row_index"):
            if optional_key in record:
                evidence_item[optional_key] = record[optional_key]
        evidence.append(evidence_item)

        detected_type = _heading_type(record["text"])
        if detected_type:
            current_type = detected_type
            current_heading = record["text"].rstrip(":").strip()
            key = (current_type, current_heading)
            if key not in sections:
                sections[key] = {
                    "type": current_type, "heading": current_heading,
                    "items": [], "evidence_ids": [],
                }
            continue

        key = (current_type, current_heading)
        _append_item(sections[key], record)

    normalized_sections = [
        section for section in sections.values()
        if section["items"] or section["type"] != "other"
    ]

    email_match = EMAIL_RE.search(full_text)
    phone_match = PHONE_RE.search(full_text)
    candidate = {
        "name": _candidate_name(records),
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
        "profile_urls": _extract_profile_urls(full_text),
    }

    skills = _detect_skills(records)
    # Preserve provenance: a skill in the skills section is listed, while a
    # skill in an experience/project bullet is demonstrated by resume evidence.
    section_by_evidence = {}
    achievement_evidence = set()
    for section in normalized_sections:
        for item in section.get("items", []):
            for evidence_id in item.get("evidence_ids", []):
                section_by_evidence[evidence_id] = section.get("type")
                if section.get("type") in ("experience", "projects") and item.get("kind") == "bullet":
                    achievement_evidence.add(evidence_id)
    for skill in skills:
        ids = list(dict.fromkeys(skill.get("evidence_ids", [])))
        skill["evidence_ids"] = ids
        skill["listed_evidence_ids"] = [
            evidence_id for evidence_id in ids
            if section_by_evidence.get(evidence_id) == "skills"
        ]
        skill["demonstrated_evidence_ids"] = [
            evidence_id for evidence_id in ids if evidence_id in achievement_evidence
        ]
        # No inference is made from related concepts or adjacent technologies.
        skill["inferred_evidence_ids"] = []
        skill["provenance"] = (
            "demonstrated" if skill["demonstrated_evidence_ids"] else
            "listed" if skill["listed_evidence_ids"] else "mentioned"
        )
    warnings = []
    if extension == ".pdf" and not records:
        warnings.append("No selectable text was extracted; this may be a scanned document.")
    if len(records) < 5:
        warnings.append("Only a small number of text lines were extracted; review the parsed content.")
    if any(re.search(r"\b(?:present|current)\b", record["text"], re.I) for record in records):
        warnings.append("One or more dates use 'Present' or 'Current'; verify that they reflect the candidate's current status.")
    if not candidate["name"]:
        warnings.append("Candidate name could not be identified confidently.")
    if not candidate["profile_urls"]:
        warnings.append("No profile URLs were detected.")
    # Flag suspiciously unfinished numeric claims; do not treat them as complete outcomes.
    incomplete_claims = [
        record for record in records
        if BULLET_RE.match(record["text"])
        and re.search(r"\bby\s+\d+(?:\.\d+)?\s*$", record["text"], re.I)
    ]
    if incomplete_claims:
        warnings.append(
            "One or more achievement bullets may contain truncated numeric outcomes; review the extracted text."
        )

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
