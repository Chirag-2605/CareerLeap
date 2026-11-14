"""Normalize parser output into a shared, source-linked evidence contract."""
from typing import Any, Dict, List


def collect_evidence(resume: Dict[str, Any], sections=None) -> List[Dict[str, Any]]:
    allowed = set(sections or ())
    output = []
    for section in resume.get("sections", []):
        section_type = section.get("type", "other")
        if allowed and section_type not in allowed:
            continue
        for item in section.get("items", []):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            ids = item.get("evidence_ids") or ([item.get("evidence_id")] if item.get("evidence_id") else [])
            output.append({
                "section": section_type,
                "kind": item.get("kind", "text"),
                "text": text,
                "evidence_ids": list(dict.fromkeys(value for value in ids if value)),
            })
    return output
