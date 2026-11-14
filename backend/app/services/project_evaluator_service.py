"""Project evidence evaluator; reports technical substance without inventing facts."""
import re
from typing import Any, Dict, List


TECHNICAL_SIGNAL = re.compile(
    r"\b(?:api|apis|react|node|express|spring|database|sql|mongodb|postgres|"
    r"websocket|webrtc|jwt|oauth|docker|aws|kubernetes|architecture|"
    r"authentication|deployment|pipeline|cache|endpoint|framework|model|workflow)\b", re.I
)


def evaluate_projects(project_bullets: List[Dict[str, Any]]) -> Dict[str, Any]:
    assessed = []
    for item in project_bullets:
        text = item["text"]
        words = len(re.findall(r"\b[\w+#.]+\b", text))
        technical = bool(TECHNICAL_SIGNAL.search(text))
        assessed.append({
            "text": text,
            "evidence_ids": list(item.get("evidence_ids", [])),
            "word_count": words,
            "technical_signal": technical,
            "substantive": words >= 8 and technical,
        })
    substantive = [item for item in assessed if item["substantive"]]
    return {
        "assessed_bullets": len(assessed),
        "substantive_bullets": len(substantive),
        "needs_detail": [item for item in assessed if not item["substantive"]],
        "evidence_ids": list(dict.fromkeys(
            eid for item in substantive for eid in item["evidence_ids"]
        )),
    }
