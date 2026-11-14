"""Responsibility matching with conservative, source-linked lexical evidence.

The matcher intentionally avoids synthetic concept expansion: broad labels such
as "software artifact" or "build concept" caused generic bullets to resemble
specific engineering responsibilities.
"""
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "our", "that", "the", "their",
    "this", "to", "with", "will", "you", "your", "we", "using", "use",
    "experience", "ability", "work", "working", "responsible", "reliable",
    "reliability", "scalable", "scale", "clean", "efficient", "maintainable",
    "software", "strong", "good", "knowledge", "understanding", "including",
    "build", "built", "building", "develop", "developed", "implement",
    "implemented", "create", "created", "design", "designed", "maintain",
    "maintained", "support", "supported", "handle", "handling",
}
SYNONYMS = {
    "interfaces": "interface", "components": "component",
    "endpoints": "endpoint", "apis": "api", "restful": "rest",
    "services": "software_artifact", "service": "software_artifact",
    "modules": "software_artifact", "module": "software_artifact",
    "components": "software_artifact", "component": "software_artifact",
    "applications": "software_artifact", "application": "software_artifact",
    "queries": "query", "databases": "database", "schemas": "schema",
    "integrated": "integration", "integrating": "integration",
    "automated": "automation", "automating": "automation",
    "debugged": "debug", "debugging": "debug",
    "tested": "test", "testing": "test",
    "optimized": "optimization", "optimizing": "optimization",
    "authenticated": "authentication", "authorization": "authentication",
    "websockets": "websocket",
}

def tokens(value: str) -> Set[str]:
    raw = re.findall(r"[a-z][a-z0-9+#.]{1,}", str(value or "").lower())
    return {
        SYNONYMS.get(token.rstrip(".,;:!?"), token.rstrip(".,;:!?"))
        for token in raw
        if token not in STOP and len(token.rstrip(".,;:!?")) > 2
    }

def similarity(left: str, right: str) -> float:
    a, b = tokens(left), tokens(right)
    if not a or not b:
        return 0.0
    overlap = a & b
    if len(overlap) < 2:
        return 0.0
    return (2.0 * len(overlap)) / float(len(a) + len(b))

def match_responsibilities(job_lines: Iterable[str], resume_bullets: Iterable[Dict[str, Any]],
                           threshold: float = 0.20) -> Tuple[List[Dict[str, Any]], int]:
    bullets = list(resume_bullets)
    lines = list(dict.fromkeys(line for line in job_lines if len(tokens(line)) >= 3))
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
    best_by_line = {item["job_responsibility"]: item["similarity"] for item in matches}
    score = int(round(25 * sum(
        min(1.0, best_by_line.get(line, 0.0) / 0.45) for line in lines
    ) / len(lines))) if lines else None
    return matches, score
