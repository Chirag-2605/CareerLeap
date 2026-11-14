"""Experience depth evaluator based on evidence quality, not bullet count alone."""
from typing import Any, Dict, List


def evaluate_experience_depth(experience: List[Dict[str, Any]], role_context_items: List[Dict[str, Any]],
                              project_bullets: List[Dict[str, Any]], quality_scores: List[int]) -> Dict[str, Any]:
    if not experience:
        return {"score": 0, "average_quality": 0.0, "assessed_bullets": 0}
    average_quality = sum(quality_scores) / float(max(1, len(quality_scores)))
    substance = round(12 * average_quality / 7.0)
    context = 4 if role_context_items else 0
    breadth = min(2, max(0, len(experience) - 1))
    project_support = min(2, sum(1 for item in project_bullets if len(item["text"].split()) >= 8))
    return {
        "score": min(20, substance + context + breadth + project_support),
        "average_quality": round(average_quality, 2),
        "assessed_bullets": len(experience),
    }
