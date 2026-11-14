"""Responsibility matching service using normalized engineering concepts."""
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "our", "that", "the", "their",
    "this", "to", "with", "will", "you", "your", "we", "using", "use",
    "experience", "ability", "work", "working", "responsible", "reliable",
    "reliability", "scalable", "scale", "clean", "efficient", "maintainable",
    "software", "strong", "good", "knowledge", "understanding", "including",
}
SYNONYMS = {
    "built": "build", "building": "build", "developed": "build", "develop": "build",
    "implemented": "build", "created": "build", "designed": "design",
    "maintained": "maintain", "maintaining": "maintain",
    "api": "endpoint", "apis": "endpoint", "restful": "rest",
    "service": "service_component", "services": "service_component",
    "module": "service_component", "modules": "service_component",
    "component": "service_component", "components": "service_component",
    "application": "service_component", "applications": "service_component",
    "query": "database_query", "queries": "database_query", "sql": "database_query",
    "optimize": "optimization", "optimized": "optimization",
    "automated": "automation", "automation": "automation",
    "integrated": "integration", "integrating": "integration",
    "authentication": "auth", "authorization": "auth",
}
CONCEPT_GROUPS = (
    {"rest", "endpoint", "http", "api"},
    {"database_query", "database", "postgresql", "mysql", "mongodb", "schema"},
    {"automation", "integration", "testing", "test"},
    {"auth", "jwt", "oauth", "security"},
    {"build", "design", "maintain", "optimization"},
)


def tokens(value: str) -> Set[str]:
    raw = re.findall(r"[a-z][a-z0-9+#.]{1,}", str(value or "").lower())
    result = {SYNONYMS.get(token.rstrip(".,;:!?"), token.rstrip(".,;:!?"))
              for token in raw if token not in STOP and len(token) > 2}
    for group in CONCEPT_GROUPS:
        if result & group:
            result.add("concept:" + str(sorted(group)[0]))
    return result


def similarity(left: str, right: str) -> float:
    a, b = tokens(left), tokens(right)
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    if overlap < 2:
        return 0.0
    return (2.0 * overlap) / float(len(a) + len(b))


def match_responsibilities(job_lines: Iterable[str], resume_bullets: Iterable[Dict[str, Any]],
                           threshold: float = 0.14) -> Tuple[List[Dict[str, Any]], int]:
    bullets = list(resume_bullets)
    lines = list(dict.fromkeys(line for line in job_lines if len(tokens(line)) >= 4))
    matches = []
    for line in lines:
        ranked = sorted(((similarity(line, bullet["text"]), bullet) for bullet in bullets),
                        key=lambda pair: pair[0], reverse=True)
        relevant = [(score, bullet) for score, bullet in ranked if score >= threshold][:2]
        if not relevant:
            continue
        best_score, best_bullet = relevant[0]
        matches.append({
            "job_responsibility": line,
            "resume_excerpt": best_bullet["text"],
            "similarity": round(best_score, 3),
            "evidence_ids": list(dict.fromkeys(
                eid for _, bullet in relevant for eid in bullet["evidence_ids"]
            )),
            "evidence_type": "direct" if best_score >= 0.30 else "supporting",
            "supporting_excerpts": [bullet["text"] for _, bullet in relevant[1:]],
        })
    score = int(round(25 * sum(
        min(1.0, {item["job_responsibility"]: item["similarity"] for item in matches}.get(line, 0.0) / 0.45)
        for line in lines
    ) / len(lines))) if lines else None
    return matches, score
